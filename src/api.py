"""Authenticated async video API. Served by the CPU Modal web function."""

import hashlib
import hmac
import json
import re
import secrets
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from src import db, storage
from src.config import DEFAULT_DURATION_SECONDS, DURATION_FRAMES, MAX_ACTIVE_JOBS, PRESETS, require_env

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class AssetRequest(BaseModel):
    content_type: str


class VideoRequest(BaseModel):
    mode: str
    prompt: str = Field(min_length=1, max_length=2000)
    input_asset_id: str | None = None
    duration_seconds: int = DEFAULT_DURATION_SECONDS
    resolution: str = "512p"
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def supported(self):
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("Prompt must not be blank")
        if self.mode not in ("t2v", "i2v"):
            raise ValueError("Mode must be t2v or i2v")
        if self.duration_seconds not in DURATION_FRAMES or self.resolution not in PRESETS:
            raise ValueError("Unsupported duration or resolution")
        if self.mode == "i2v" and not self.input_asset_id:
            raise ValueError("I2V requires input_asset_id")
        if self.mode == "t2v" and self.input_asset_id:
            raise ValueError("T2V cannot use input_asset_id")
        if self.input_asset_id and not IDENTIFIER.fullmatch(self.input_asset_id):
            raise ValueError("Invalid asset ID")
        return self


@asynccontextmanager
async def lifespan(_app):
    db.initialize()
    yield


api = FastAPI(title="LTX-2.3 Video API", version="1.0", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def current_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    candidate = authorization[7:]
    try:
        tokens = json.loads(require_env("API_TOKENS_JSON"))
    except (ValueError, RuntimeError) as exc:
        raise RuntimeError("Invalid API_TOKENS_JSON configuration") from exc
    for token, user_id in tokens.items():
        if hmac.compare_digest(candidate, token):
            if not isinstance(user_id, str) or not IDENTIFIER.fullmatch(user_id):
                raise RuntimeError("Invalid user ID in API_TOKENS_JSON")
            return user_id
    raise HTTPException(status_code=401, detail="Invalid token")


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/v1/assets", status_code=201)
def create_asset(body: AssetRequest, user_id: str = Depends(current_user)):
    if body.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=422, detail="Unsupported image type")
    asset_id = "asset_" + uuid4().hex
    key = storage.input_key(user_id, asset_id)
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO video_assets (id,user_id,object_key,content_type) VALUES (%s,%s,%s,%s)",
            (asset_id, user_id, key, body.content_type),
        )
    return {"asset_id": asset_id, "upload": storage.upload_form(key, body.content_type)}


def _public_job(job: dict) -> dict:
    result = {
        "job_id": job["id"], "status": job["status"],
        "status_url": f"/v1/videos/{job['id']}", "progress": None,
    }
    if job["status"] == "succeeded":
        result["download_url"] = f"/v1/videos/{job['id']}/download"
    if job["status"] == "failed":
        result["error_code"] = job["error_code"]
    return result


@api.post("/v1/videos", status_code=202)
def submit_video(
    body: VideoRequest,
    user_id: str = Depends(current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key is not None and not IDENTIFIER.fullmatch(idempotency_key):
        raise HTTPException(status_code=422, detail="Invalid Idempotency-Key")
    snapshot = body.model_dump()
    request_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    with db.connection() as conn:
        # Serialize submissions for this user so the quota and idempotency checks stay atomic.
        lock_key = int.from_bytes(hashlib.sha256(user_id.encode()).digest()[:8], "big", signed=True)
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
        if idempotency_key:
            existing = conn.execute(
                "SELECT * FROM video_jobs WHERE user_id=%s AND idempotency_key=%s",
                (user_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise HTTPException(status_code=409, detail="Idempotency key reused with different request")
                return _public_job(existing)
        if body.mode == "i2v":
            asset = conn.execute(
                "SELECT * FROM video_assets WHERE id=%s AND user_id=%s",
                (body.input_asset_id, user_id),
            ).fetchone()
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found")
            try:
                storage.validate_image(asset["object_key"])
            except Exception as exc:
                raise HTTPException(status_code=422, detail="Asset missing or invalid") from exc
        count = conn.execute(
            "SELECT count(*) AS n FROM video_jobs WHERE user_id=%s AND status IN ('queued','running')",
            (user_id,),
        ).fetchone()["n"]
        if count >= MAX_ACTIVE_JOBS:
            raise HTTPException(status_code=429, detail="Too many active jobs")
        job_id = "vid_" + uuid4().hex
        seed = body.seed if body.seed is not None else secrets.randbelow(2**32)
        conn.execute(
            """INSERT INTO video_jobs
            (id,user_id,idempotency_key,request_hash,mode,prompt,asset_id,duration_seconds,resolution,seed)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (job_id, user_id, idempotency_key, request_hash, body.mode, body.prompt,
             body.input_asset_id, body.duration_seconds, body.resolution, seed),
        )
    # The DB row is committed before spawning. Worker state changes are conditional.
    try:
        from modal_app import VideoWorker
        call = VideoWorker().generate.spawn(job_id)
        with db.connection() as conn:
            conn.execute("UPDATE video_jobs SET call_id=%s WHERE id=%s", (call.object_id, job_id))
    except Exception as exc:
        with db.connection() as conn:
            db.set_status(conn, job_id, ("queued",), "failed", error_code="dispatch_failed")
        raise HTTPException(status_code=503, detail="Unable to dispatch video job") from exc
    return {"job_id": job_id, "status": "queued", "status_url": f"/v1/videos/{job_id}"}


@api.get("/v1/videos/{job_id}")
def get_video(job_id: str, user_id: str = Depends(current_user)):
    with db.connection() as conn:
        job = db.owned_job(conn, job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video not found")
    return _public_job(job)


@api.get("/v1/videos/{job_id}/download")
def download_video(job_id: str, user_id: str = Depends(current_user)):
    with db.connection() as conn:
        job = db.owned_job(conn, job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video not found")
    if job["status"] != "succeeded" or not job["output_key"]:
        raise HTTPException(status_code=409, detail="Video not ready")
    return {"video_url": storage.download_url(job["output_key"]), "expires_in": 900}


@api.post("/v1/videos/{job_id}/cancel")
def cancel_video(job_id: str, user_id: str = Depends(current_user)):
    with db.connection() as conn:
        job = db.owned_job(conn, job_id, user_id)
        if not job:
            raise HTTPException(status_code=404, detail="Video not found")
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return _public_job(job)
        db.set_status(conn, job_id, ("queued", "running"), "cancelled")
    if job["call_id"]:
        try:
            import modal
            modal.FunctionCall.from_id(job["call_id"]).cancel()
        except Exception:
            pass  # Best effort; the worker checks DB status before publishing output.
    job["status"] = "cancelled"
    return _public_job(job)
