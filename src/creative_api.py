"""Authenticated, credit-gated creative tools; never dispatches video jobs."""

import hashlib
import io
import json
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from PIL import Image, UnidentifiedImageError

from src import creative, db, storage
from src.config import DEFAULT_MODEL_ID, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, MODEL_PROFILES

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS creative_operations (
    id text PRIMARY KEY, user_id text NOT NULL, idempotency_key text NOT NULL,
    request_hash text NOT NULL, kind text NOT NULL, status text NOT NULL,
    result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key)
);
"""


def initialize():
    with db.connection() as conn:
        conn.execute(SCHEMA)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = DEFAULT_MODEL_ID
    mode: str = "t2v"
    idea: str = Field(min_length=1, max_length=4000)
    duration_seconds: int | None = None
    input_asset_id: str | None = None

    @model_validator(mode="after")
    def check(self):
        self.idea = self.idea.strip()
        profile = MODEL_PROFILES.get(self.model_id)
        if not self.idea or not profile or self.mode not in profile["modes"]:
            raise ValueError("Unsupported creative draft")
        if self.duration_seconds is None:
            self.duration_seconds = 10 if self.model_id == DEFAULT_MODEL_ID else profile["durations"][0]
        if self.duration_seconds not in profile["durations"]:
            raise ValueError("Unsupported duration")
        if self.mode == "i2v" and not self.input_asset_id:
            raise ValueError("Image mode requires input_asset_id")
        if self.mode == "t2v" and self.input_asset_id:
            raise ValueError("Text mode cannot use an image")
        if self.input_asset_id and not IDENTIFIER.fullmatch(self.input_asset_id):
            raise ValueError("Invalid asset ID")
        return self


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=4000)
    source_asset_id: str | None = None

    @model_validator(mode="after")
    def check(self):
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("Prompt must not be blank")
        if self.source_asset_id and not IDENTIFIER.fullmatch(self.source_asset_id):
            raise ValueError("Invalid asset ID")
        return self


def _image_from_asset(user_id: str, asset_id: str) -> tuple[str, bytes]:
    with db.connection() as conn:
        asset = conn.execute(
            "SELECT object_key,content_type FROM video_assets WHERE id=%s AND user_id=%s",
            (asset_id, user_id),
        ).fetchone()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        storage.validate_image(asset["object_key"])
        obj = storage.client().get_object(Bucket=storage.bucket(), Key=asset["object_key"])
        data = obj["Body"].read(MAX_IMAGE_BYTES + 1)
        if not 1 <= len(data) <= MAX_IMAGE_BYTES:
            raise ValueError("Invalid image size")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Asset missing or invalid") from exc
    return asset["content_type"], data


def _save_image(user_id: str, mime: str, data: bytes) -> str:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Unsupported image")
            width, height = image.size
            if width < 256 or height < 256 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("Invalid image dimensions")
            image.verify()
    except (ValueError, UnidentifiedImageError, OSError) as exc:
        raise creative.GeminiError("Gemini returned an invalid image") from exc
    asset_id = "asset_" + uuid4().hex
    key = storage.input_key(user_id, asset_id)
    storage.client().put_object(Bucket=storage.bucket(), Key=key, Body=data, ContentType=mime)
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO video_assets (id,user_id,object_key,content_type) VALUES (%s,%s,%s,%s)",
            (asset_id, user_id, key, mime),
        )
    return asset_id


def _image_response(user_id: str, asset_id: str) -> dict:
    with db.connection() as conn:
        row = conn.execute(
            "SELECT object_key,content_type FROM video_assets WHERE id=%s AND user_id=%s",
            (asset_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"asset_id": asset_id, "image_url": storage.download_url(row["object_key"]),
            "content_type": row["content_type"], "expires_in": 3600}


def _start(user_id: str, key: str, kind: str, request: dict, amount_cents: int):
    from src import billing
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    failed_prior = False
    with db.connection() as conn:
        lock_key = int.from_bytes(hashlib.sha256(user_id.encode()).digest()[:8], "big", signed=True)
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
        row = conn.execute(
            "SELECT * FROM creative_operations WHERE user_id=%s AND idempotency_key=%s",
            (user_id, key),
        ).fetchone()
        if row:
            if row["request_hash"] != fingerprint or row["kind"] != kind:
                raise HTTPException(status_code=409, detail="Idempotency key reused with different request")
            if row["status"] == "succeeded":
                return row["id"], row["result"]
            if row["status"] in ("ready", "refund_pending"):
                billing.settle(conn, row["id"], success=row["status"] == "ready")
                final = "succeeded" if row["status"] == "ready" else "failed"
                conn.execute("UPDATE creative_operations SET status=%s WHERE id=%s", (final, row["id"]))
                if final == "succeeded":
                    return row["id"], row["result"]
                failed_prior = True
            if failed_prior:
                pass  # Let the transaction commit the refund before reporting failure.
            else:
                raise HTTPException(status_code=409, detail="Creative operation already in progress or failed")
        else:
            operation_id = "creative_" + hashlib.sha256(f"{user_id}\0{key}".encode()).hexdigest()[:32]
            conn.execute(
                "INSERT INTO creative_operations (id,user_id,idempotency_key,request_hash,kind,status) "
                "VALUES (%s,%s,%s,%s,%s,'pending')",
                (operation_id, user_id, key, fingerprint, kind),
            )
            billing.reserve(conn, user_id, operation_id, amount_cents, kind)
    if failed_prior:
        raise HTTPException(status_code=409, detail="Creative operation failed; use a new idempotency key")
    return operation_id, None


def _finish(operation_id: str, result: dict | None):
    from src import billing
    status = "ready" if result else "refund_pending"
    with db.connection() as conn:
        conn.execute(
            "UPDATE creative_operations SET status=%s,result=%s::jsonb WHERE id=%s",
            (status, json.dumps(result) if result else None, operation_id),
        )
    with db.connection() as conn:
        billing.settle(conn, operation_id, success=bool(result))
        conn.execute(
            "UPDATE creative_operations SET status=%s WHERE id=%s",
            ("succeeded" if result else "failed", operation_id),
        )


def create_router(current_user):
    router = APIRouter(prefix="/v1/creative", tags=["creative"])

    @router.get("/pricing")
    def pricing(_user_id: str = Depends(current_user)):
        from src import billing
        return {"currency": "USD", "prompt_cents": billing.CREATIVE_PRICES_CENTS["prompt"],
                "image_cents": billing.CREATIVE_PRICES_CENTS["image"]}

    @router.post("/prompt")
    def prompt(body: DraftRequest, user_id: str = Depends(current_user),
               idempotency_key: str = Header(alias="Idempotency-Key")):
        from src import billing
        if not IDENTIFIER.fullmatch(idempotency_key):
            raise HTTPException(status_code=422, detail="Invalid Idempotency-Key")
        source = _image_from_asset(user_id, body.input_asset_id) if body.input_asset_id else None
        operation_id, prior = _start(user_id, idempotency_key, "prompt", body.model_dump(),
                                     billing.CREATIVE_PRICES_CENTS["prompt"])
        if prior:
            return prior
        try:
            result = creative.optimize_prompt(model_id=body.model_id, mode=body.mode,
                                              idea=body.idea, duration_seconds=body.duration_seconds,
                                              source_image=source)
        except Exception as exc:
            _finish(operation_id, None)
            raise HTTPException(status_code=502, detail="Creative prompt generation failed") from exc
        _finish(operation_id, result)
        return result

    @router.post("/images")
    def images(body: ImageRequest, user_id: str = Depends(current_user),
               idempotency_key: str = Header(alias="Idempotency-Key")):
        from src import billing
        if not IDENTIFIER.fullmatch(idempotency_key):
            raise HTTPException(status_code=422, detail="Invalid Idempotency-Key")
        source = _image_from_asset(user_id, body.source_asset_id) if body.source_asset_id else None
        operation_id, prior = _start(user_id, idempotency_key, "image", body.model_dump(),
                                     billing.CREATIVE_PRICES_CENTS["image"])
        if prior:
            return _image_response(user_id, prior["asset_id"])
        try:
            mime, data = creative.create_image(prompt=body.prompt, source_image=source)
            asset_id = _save_image(user_id, mime, data)
        except Exception as exc:
            _finish(operation_id, None)
            raise HTTPException(status_code=502, detail="Image generation failed") from exc
        _finish(operation_id, {"asset_id": asset_id})
        return _image_response(user_id, asset_id)

    return router
