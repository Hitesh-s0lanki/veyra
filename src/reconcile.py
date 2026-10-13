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
    return {"checked": len(jobs), "repaired": repaired}
