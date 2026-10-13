"""Modal worker for creator video challenge verification."""

import tempfile
from pathlib import Path

import modal
from psycopg.types.json import Jsonb

from src import db, storage
from src.config import VERIFICATION_MODAL_APP_NAME
from src.verification import build_report, get_challenge

app = modal.App(VERIFICATION_MODAL_APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("ffmpeg")
    .pip_install_from_pyproject("pyproject.toml", optional_dependencies=["verification"])
    .add_local_python_source("src", copy=True)
    .add_local_dir("src/data", "/root/src/data", copy=True)
)


@app.function(image=image, secrets=[modal.Secret.from_name("video-pipeline")], timeout=3600)
def verify_submission(submission_id: str):
    with db.connection() as conn:
        submission = conn.execute(
            """UPDATE video_submissions SET status='running', updated_at=now()
            WHERE id=%s AND status='queued' RETURNING *""", (submission_id,)
        ).fetchone()
    if not submission:
        return {"status": "skipped"}
    try:
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / ("source" + Path(submission["object_key"]).suffix)
            storage.client().download_file(storage.bucket(), submission["object_key"], str(video_path))
            challenge = get_challenge(submission["challenge_id"])
            if challenge is None:
                raise ValueError("Unknown challenge")
            report = build_report(
                submission_id, challenge, submission["selected_product"], video_path,
            )
            report["source_video"] = f"/v1/submissions/{submission_id}/video"
        with db.connection() as conn:
            conn.execute(
                """UPDATE video_submissions SET status='complete', report=%s, updated_at=now()
                WHERE id=%s AND status='running'""", (Jsonb(report), submission_id),
            )
        return {"status": "complete"}
    except Exception:
        with db.connection() as conn:
            conn.execute(
                """UPDATE video_submissions SET status='failed', error_code='verification_failed',
                updated_at=now() WHERE id=%s AND status='running'""", (submission_id,),
            )
        raise
