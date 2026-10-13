"""Repair stale jobs after a worker exits without updating the database."""

import modal

from src import db


def run_once() -> dict[str, int]:
    with db.connection() as conn:
        jobs = conn.execute(
            """SELECT id, status, call_id FROM video_jobs
            WHERE status IN ('queued','running') AND updated_at < now() - interval '10 minutes'
            ORDER BY updated_at LIMIT 100"""
        ).fetchall()
    repaired = 0
    for job in jobs:
        if not job["call_id"]:
            if job["status"] == "queued":
                with db.connection() as conn:
                    repaired += db.set_status(conn, job["id"], ("queued",), "failed", error_code="dispatch_lost")
            continue
        try:
            modal.FunctionCall.from_id(job["call_id"]).get(timeout=0)
        except TimeoutError:
            continue
        except Exception:
            pass  # A failed or expired Modal call still needs a terminal DB state.
        with db.connection() as conn:
            repaired += db.set_status(
                conn, job["id"], ("queued", "running"), "failed", error_code="worker_lost"
            )
    with db.connection() as conn:
        submissions = conn.execute(
            """SELECT id,status,call_id FROM video_submissions
            WHERE status IN ('queued','running') AND updated_at < now() - interval '10 minutes'
            ORDER BY updated_at LIMIT 100"""
        ).fetchall()
    for submission in submissions:
        if not submission["call_id"]:
            if submission["status"] != "queued":
                continue
            error_code = "dispatch_lost"
        else:
            try:
                modal.FunctionCall.from_id(submission["call_id"]).get(timeout=0)
            except TimeoutError:
                continue
            except Exception:
                pass
            error_code = "worker_lost"
        with db.connection() as conn:
            repaired += conn.execute(
                """UPDATE video_submissions SET status='failed', error_code=%s, updated_at=now()
                WHERE id=%s AND status IN ('queued','running') RETURNING id""",
                (error_code, submission["id"]),
            ).fetchone() is not None
    return {"checked": len(jobs) + len(submissions), "repaired": repaired}
