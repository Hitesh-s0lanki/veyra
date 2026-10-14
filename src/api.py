"""Authenticated video API that dispatches to deployed Modal model workers."""

import asyncio
import hashlib
import hmac
import json
import math
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import BotoCoreError, ClientError
import jwt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src import billing, cost, db, oauth, storage, creative_api, submissions, concepts
from src.config import DEFAULT_DURATION_SECONDS, DEFAULT_MODEL_ID, MAX_ACTIVE_JOBS, MODEL_PROFILES, VIDEO_URL_TTL_SECONDS

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class AssetRequest(BaseModel):
    content_type: str


class VideoKeyRequest(BaseModel):
    video_key: str = Field(min_length=1, max_length=300)


class VideoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = DEFAULT_MODEL_ID
    mode: str
    prompt: str = Field(min_length=1, max_length=2000)
    input_asset_id: str | None = None
    duration_seconds: int = DEFAULT_DURATION_SECONDS
    resolution: str | None = None
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def supported(self):
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("Prompt must not be blank")
        profile = MODEL_PROFILES.get(self.model_id)
        if profile is None:
            raise ValueError("Unsupported model_id")
        if self.resolution is None:
            self.resolution = profile["resolutions"][0]
        if self.mode not in profile["modes"]:
            raise ValueError("Unsupported mode for model")
        if self.duration_seconds not in profile["durations"] or self.resolution not in profile["resolutions"]:
            raise ValueError("Unsupported duration or resolution for model")
        if self.mode == "i2v" and self.resolution.endswith("-portrait"):
            raise ValueError("Image-to-video aspect ratio follows the source image")
        if set(self.parameters) - set(profile["defaults"]):
            raise ValueError("Unsupported parameter for model")
        self.parameters = {**profile["defaults"], **self.parameters}
        for name, value in self.parameters.items():
            if name == "inference_steps" and (type(value) is not int or not 1 <= value <= 100):
                raise ValueError("inference_steps must be an integer from 1 to 100")
            if name == "guidance_scale" and (
                type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 20
            ):
                raise ValueError("guidance_scale must be between 0 and 20")
        if "guidance_scale" in self.parameters:
            self.parameters["guidance_scale"] = float(self.parameters["guidance_scale"])
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
    creative_api.initialize()
    concepts.initialize()
    task = asyncio.create_task(_reconcile_loop())
    concept_task = asyncio.create_task(_concept_loop())
    try:
        yield
    finally:
        task.cancel()
        concept_task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await concept_task
        except asyncio.CancelledError:
            pass


async def _reconcile_loop():
    from src.reconcile import run_once

    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            # A temporary DB or Modal outage should not stop API serving.
            import logging
            logging.getLogger(__name__).exception("Video job reconciliation failed")
        await asyncio.sleep(300)


async def _concept_loop():
    while True:
        try:
            await asyncio.to_thread(concepts.tick)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Concept orchestration failed")
        await asyncio.sleep(5)


api = FastAPI(title="Video Generation API", version="2.0", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


def current_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    candidate = authorization[7:]
    try:
        tokens = json.loads(os.getenv("API_TOKENS_JSON", "{}"))
    except ValueError as exc:
        raise RuntimeError("Invalid API_TOKENS_JSON configuration") from exc
    for token, user_id in tokens.items():
        if hmac.compare_digest(candidate, token):
            if not isinstance(user_id, str) or not IDENTIFIER.fullmatch(user_id):
                raise RuntimeError("Invalid user ID in API_TOKENS_JSON")
            if user_id.startswith("user_"):
                raise RuntimeError("Static tokens cannot impersonate Clerk users")
            return user_id
    if candidate.count(".") == 2:
        try:
            if jwt.decode(candidate, options={"verify_signature": False}).get("sid"):
                return oauth.verify_session_token(candidate)
        except jwt.PyJWTError:
            pass
    return oauth.verify_oauth_token(candidate)


api.include_router(creative_api.create_router(current_user))
api.include_router(concepts.create_router(current_user))
api.include_router(submissions.create_router(current_user))


@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/v1/models")
def list_models(_user_id: str = Depends(current_user)):
    return {"models": [
        {"model_id": model_id, "modes": profile["modes"],
         "duration_seconds": profile["durations"], "resolutions": profile["resolutions"],
         "parameter_defaults": profile["defaults"]}
        for model_id, profile in MODEL_PROFILES.items()
    ]}


@api.get("/v1/wallet")
def get_wallet(user_id: str = Depends(current_user)):
    with db.connection() as conn:
        return billing.balance(conn, user_id)


@api.get("/v1/wallet/transactions")
def wallet_transactions(user_id: str = Depends(current_user)):
    with db.connection() as conn:
        billing.ensure_wallet(conn, user_id)
        rows = conn.execute(
            """SELECT id,kind,amount_cents,balance_after_cents,operation_id,reason,created_at
            FROM credit_ledger WHERE user_id=%s ORDER BY id DESC LIMIT 100""", (user_id,)
        ).fetchall()
    return {"transactions": rows}


@api.post("/v1/videos/quote")
def quote_video(body: VideoRequest, _user_id: str = Depends(current_user)):
    return billing.quote(body.model_id, body.mode, body.duration_seconds,
                         body.resolution, body.parameters)


@api.get("/v1/assets")
def list_assets(user_id: str = Depends(current_user)):
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT id AS asset_id, content_type, created_at FROM video_assets
            WHERE user_id=%s ORDER BY created_at DESC LIMIT 100""", (user_id,)
        ).fetchall()
    return {"assets": rows}


@api.get("/v1/assets/{asset_id}/download")
def download_asset(asset_id: str, user_id: str = Depends(current_user)):
    with db.connection() as conn:
        asset = conn.execute(
            "SELECT object_key,content_type FROM video_assets WHERE id=%s AND user_id=%s",
            (asset_id, user_id),
        ).fetchone()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        url = storage.download_url(asset["object_key"])
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail="Asset temporarily unavailable") from exc
    return {"asset_id": asset_id, "url": url, "content_type": asset["content_type"],
            "expires_in": VIDEO_URL_TTL_SECONDS}


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
        "job_id": job["id"], "model_id": job.get("model_id") or DEFAULT_MODEL_ID,
        "status": job["status"], "mode": job.get("mode"),
        "prompt": job.get("prompt"), "duration_seconds": job.get("duration_seconds"),
        "resolution": job.get("resolution"), "price_cents": job.get("price_cents"),
        "created_at": job.get("created_at"),
        "status_url": f"/v1/videos/{job['id']}", "progress": None,
    }
    if job["status"] == "succeeded":
        result["download_url"] = f"/v1/videos/{job['id']}/download"
        result["output"] = _video_output(job)
        result["cost"] = _job_cost(job)
    if job["status"] == "failed":
        result["error_code"] = job["error_code"]
    return result


def _job_cost(job: dict) -> dict:
    return {
        "estimated_gpu_cost_usd": cost.estimate(job),
        "currency": "USD",
        "basis": "generation_worker_runtime",
        "is_exact_bill": False,
    }


def _video_output(job: dict) -> dict:
    key = job.get("output_key")
    if not key:
        raise HTTPException(status_code=503, detail="Video temporarily unavailable")
    try:
        metadata = storage.video_metadata(key)
        signed_at = datetime.now(timezone.utc)
        url = storage.download_url(key)
    except (BotoCoreError, ClientError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Video temporarily unavailable") from exc
    return {
        "video_key": key,
        "video_url": url,
        "expires_in": VIDEO_URL_TTL_SECONDS,
        "expires_at": (signed_at + timedelta(seconds=VIDEO_URL_TTL_SECONDS)).isoformat().replace("+00:00", "Z"),
        **metadata,
    }


@api.post("/v1/videos", status_code=202)
def submit_video(
    body: VideoRequest,
    user_id: str = Depends(current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key is not None and not IDENTIFIER.fullmatch(idempotency_key):
        raise HTTPException(status_code=422, detail="Invalid Idempotency-Key")
    if user_id.startswith("user_") and idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key required")
    price = billing.quote(body.model_id, body.mode, body.duration_seconds,
                          body.resolution, body.parameters)
    snapshot = body.model_dump()
    request_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    legacy_snapshot = {key: value for key, value in snapshot.items() if key not in ("model_id", "parameters")}
    legacy_hash = hashlib.sha256(json.dumps(legacy_snapshot, sort_keys=True).encode()).hexdigest()
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
                compatible_legacy = (
                    body.model_id == DEFAULT_MODEL_ID and not body.parameters
                    and existing["request_hash"] == legacy_hash
                )
                if existing["request_hash"] != request_hash and not compatible_legacy:
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
        job_id = ("vid_" + hashlib.sha256(f"{user_id}:{idempotency_key}".encode()).hexdigest()[:32]
                  if idempotency_key else "vid_" + uuid4().hex)
        seed = body.seed if body.seed is not None else secrets.randbelow(2**32)
        billing.reserve(conn, user_id, job_id, price["amount_cents"], "video")
        conn.execute(
            """INSERT INTO video_jobs
            (id,user_id,idempotency_key,request_hash,mode,prompt,asset_id,duration_seconds,resolution,seed,model_id,parameters,price_cents,pricing_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (job_id, user_id, idempotency_key, request_hash, body.mode, body.prompt,
             body.input_asset_id, body.duration_seconds, body.resolution, seed,
             body.model_id, json.dumps(body.parameters), price["amount_cents"],
             price["pricing_version"]),
        )
    # The DB row is committed before spawning. Worker state changes are conditional.
    try:
        import modal
        app_name = MODEL_PROFILES[body.model_id]["app"]
        call = modal.Cls.from_name(app_name, "VideoWorker")().generate.spawn(job_id)
        with db.connection() as conn:
            conn.execute("UPDATE video_jobs SET call_id=%s WHERE id=%s", (call.object_id, job_id))
    except Exception as exc:
        with db.connection() as conn:
            db.set_status(conn, job_id, ("queued",), "failed", error_code="dispatch_failed")
        raise HTTPException(status_code=503, detail="Unable to dispatch video job") from exc
    return {"job_id": job_id, "model_id": body.model_id,
            "status": "queued", "status_url": f"/v1/videos/{job_id}",
            "price_cents": price["amount_cents"]}


@api.get("/v1/videos")
def list_videos(user_id: str = Depends(current_user)):
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT * FROM video_jobs AS job WHERE user_id=%s
            AND NOT EXISTS (SELECT 1 FROM concept_scenes AS scene WHERE scene.job_id=job.id)
            ORDER BY created_at DESC LIMIT 100""", (user_id,),
        ).fetchall()
    return {"videos": [_public_job(row) for row in rows]}


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
    return {**_video_output(job), "cost": _job_cost(job)}


@api.post("/v1/videos/url")
def video_url_from_key(body: VideoKeyRequest, user_id: str = Depends(current_user)):
    """Renew a one-hour URL for a completed video owned by this API user."""
    with db.connection() as conn:
        job = conn.execute(
            """SELECT * FROM video_jobs
            WHERE output_key=%s AND user_id=%s AND status='succeeded'""",
            (body.video_key, user_id),
        ).fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Video not found")
    return {**_video_output(job), "cost": _job_cost(job)}


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
