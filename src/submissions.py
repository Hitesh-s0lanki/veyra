"""Owner-scoped creator video verification routes."""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src import db, storage
from src.config import VERIFICATION_MODAL_APP_NAME, VIDEO_URL_TTL_SECONDS
from src.verification import get_challenge, product_options

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


def _save_video(video: UploadFile, user_id: str, submission_id: str) -> str:
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=415, detail="Upload a video file")
    name = (video.filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(name).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported video extension")
    size = 0
    while chunk := video.file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Video exceeds the 200 MB upload limit")
    if size == 0:
        raise HTTPException(status_code=422, detail="Video is empty")
    video.file.seek(0)
    key = f"submissions/{user_id}/{submission_id}/source{extension}"
    storage.client().upload_fileobj(
        video.file, storage.bucket(), key,
        ExtraArgs={"ContentType": video.content_type, "ServerSideEncryption": "AES256"},
    )
    return key


def create_router(current_user):
    router = APIRouter(prefix="/v1")

    @router.get("/challenges")
    def list_challenges(_user_id: str = Depends(current_user)):
        from src.verification import CHALLENGES_PATH
        import json

        challenges = json.loads(CHALLENGES_PATH.read_text())["data"]
        return {"challenges": [
            {"challenge_id": item["id"], "title": item["title"], "description": item["description"],
             "rules": item["rules"], "product_options": product_options(item), "concept_test": True}
            for item in challenges
        ]}

    @router.post("/submissions", status_code=202)
    def create_submission(
        video: UploadFile = File(), challenge_id: str = Form(),
        selected_product: str | None = Form(default=None),
        user_id: str = Depends(current_user),
    ):
        challenge = get_challenge(challenge_id)
        if challenge is None:
            raise HTTPException(status_code=404, detail="Unknown challenge_id")
        options = product_options(challenge)
        if selected_product and selected_product not in options:
            raise HTTPException(status_code=422, detail="selected_product must match a listed product option")
        if challenge.get("product_required") and len(options) > 1 and not selected_product:
            raise HTTPException(status_code=422, detail="selected_product is required for this challenge")
        if not selected_product and len(options) == 1:
            selected_product = options[0]

        submission_id = uuid4().hex
        key = _save_video(video, user_id, submission_id)
        try:
            with db.connection() as conn:
                conn.execute(
                    """INSERT INTO video_submissions
                    (id,user_id,challenge_id,selected_product,object_key)
                    VALUES (%s,%s,%s,%s,%s)""",
                    (submission_id, user_id, challenge_id, selected_product, key),
                )
        except Exception:
            storage.client().delete_object(Bucket=storage.bucket(), Key=key)
            raise
        try:
            import modal
            call = modal.Function.from_name(VERIFICATION_MODAL_APP_NAME, "verify_submission").spawn(submission_id)
            with db.connection() as conn:
                conn.execute("UPDATE video_submissions SET call_id=%s WHERE id=%s", (call.object_id, submission_id))
        except Exception as exc:
            with db.connection() as conn:
                conn.execute(
                    """UPDATE video_submissions SET status='failed', error_code='dispatch_failed', updated_at=now()
                    WHERE id=%s AND status='queued'""", (submission_id,)
                )
            raise HTTPException(status_code=503, detail="Unable to dispatch verification") from exc
        return {"submission_id": submission_id, "processing_status": "queued",
                "report_url": f"/v1/submissions/{submission_id}"}

    @router.get("/submissions")
    def list_submissions(user_id: str = Depends(current_user)):
        with db.connection() as conn:
            rows = conn.execute(
                """SELECT id,challenge_id,selected_product,status,error_code,created_at
                FROM video_submissions WHERE user_id=%s ORDER BY created_at DESC LIMIT 100""", (user_id,)
            ).fetchall()
        return {"submissions": [
            {"submission_id": row["id"], "challenge_id": row["challenge_id"],
             "selected_product": row["selected_product"], "processing_status": row["status"],
             "error_code": row["error_code"], "created_at": row["created_at"]}
            for row in rows
        ]}

    @router.get("/submissions/{submission_id}")
    def get_submission(submission_id: UUID, user_id: str = Depends(current_user)):
        with db.connection() as conn:
            submission = db.owned_submission(conn, submission_id.hex, user_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        if submission["report"] is not None:
            return submission["report"]
        return {"submission_id": submission_id.hex, "challenge_id": submission["challenge_id"],
                "processing_status": submission["status"], "error_code": submission["error_code"]}

    @router.get("/submissions/{submission_id}/video")
    def download_submission_video(submission_id: UUID, user_id: str = Depends(current_user)):
        with db.connection() as conn:
            submission = db.owned_submission(conn, submission_id.hex, user_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        return {"video_url": storage.download_url(submission["object_key"]),
                "expires_in": VIDEO_URL_TTL_SECONDS}

    return router
