"""Local FastMCP tools for the authenticated video generation API."""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import dotenv_values
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from PIL import Image, UnidentifiedImageError

from src.config import DEFAULT_MODEL_ID, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = re.compile(r"^vid_[a-f0-9]{32}$")
OUTPUT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.mp4$")

mcp = FastMCP(
    "Video Generation",
    instructions=(
        "Video generation starts a billable GPU job. Call generate_video only when the user asks "
        "to generate a clip. Use list_video_models to choose supported settings, then poll "
        "get_video_status. A succeeded job has a stable video_key and an estimated GPU cost. "
        "Use get_video_url only when a shareable, one-hour signed link is needed; do not put "
        "the API bearer token or signed link in logs or unrelated messages."
    ),
)


def _base_url() -> str:
    setting = "MCP_API_INTERNAL_ORIGIN" if get_access_token() is not None else "VIDEO_API_BASE_URL"
    value = os.getenv(setting, "http://127.0.0.1:8000").rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError(f"{setting} is invalid")
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(f"Remote {setting} must use HTTPS")
    return value


def _api_token() -> str:
    # Hosted MCP requests carry a Clerk token after the browser OAuth flow.
    # The stdio client continues to use its private environment token.
    access = get_access_token()
    if access is not None:
        return access.token
    token = os.getenv("VIDEO_API_TOKEN")
    if token:
        return token
    raw = dotenv_values(PROJECT_ROOT / ".env").get("API_TOKENS_JSON")
    try:
        tokens = json.loads(raw or "{}")
    except ValueError as exc:
        raise RuntimeError("Configure VIDEO_API_TOKEN for the MCP server") from exc
    if isinstance(tokens, dict) and len(tokens) == 1:
        return next(iter(tokens))
    raise RuntimeError("Configure VIDEO_API_TOKEN for the MCP server")


def _api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_base_url(),
        headers={"Authorization": f"Bearer {_api_token()}"},
        timeout=30,
        follow_redirects=False,
    )


async def _request(method: str, path: str, **kwargs: Any) -> dict:
    try:
        async with _api_client() as client:
            response = await client.request(method, path, **kwargs)
    except httpx.RequestError as exc:
        raise RuntimeError("Video API is unavailable") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        message = detail if isinstance(detail, str) else "Request rejected"
        raise ValueError(f"Video API HTTP {response.status_code}: {message}")
    return response.json()


def _job_id(value: str) -> str:
    if not VIDEO_ID.fullmatch(value):
        raise ValueError("Invalid job_id")
    return value


def _without_signed_url(result: dict) -> dict:
    if isinstance(result.get("output"), dict):
        result["output"] = {key: value for key, value in result["output"].items() if key != "video_url"}
    return result


def _image_file(image_path: str) -> tuple[Path, str, bytes]:
    root = Path(os.getenv("VIDEO_MCP_IMAGE_ROOT", str(PROJECT_ROOT))).resolve()
    path = Path(image_path).expanduser().resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Image must be a file within VIDEO_MCP_IMAGE_ROOT")
    size = path.stat().st_size
    if not 1 <= size <= MAX_IMAGE_BYTES:
        raise ValueError("Image must be between 1 byte and 10 MB")
    try:
        with Image.open(path) as image:
            image_format = image.format
            width, height = image.size
            if image_format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Image must be JPEG, PNG, or WebP")
            if width < 256 or height < 256 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions are outside supported limits")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid image file") from exc
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format]
    return path, content_type, path.read_bytes()


@mcp.tool
async def list_video_models() -> dict:
    """List model IDs and accepted modes, durations, resolutions, and parameter defaults."""
    return await _request("GET", "/v1/models")


@mcp.tool
async def upload_video_image(image_path: str) -> dict:
    """Upload a local JPEG, PNG, or WebP for LTX image-to-video; return its asset_id."""
    path, content_type, data = _image_file(image_path)
    asset = await _request("POST", "/v1/assets", json={"content_type": content_type})
    upload = asset["upload"]
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            response = await client.post(
                upload["url"],
                data=upload["fields"],
                files={"file": (path.name, data, content_type)},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError("Image upload failed") from exc
    return {"asset_id": asset["asset_id"], "content_type": content_type, "size_bytes": len(data)}


@mcp.tool
async def generate_video(
    prompt: str,
    mode: Literal["t2v", "i2v"] = "t2v",
    model_id: str = DEFAULT_MODEL_ID,
    duration_seconds: int = 5,
    resolution: str | None = None,
    seed: int | None = None,
    input_asset_id: str | None = None,
    inference_steps: int | None = None,
    guidance_scale: float | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Start one billable video job and return its job_id; use an uploaded asset_id for i2v."""
    if mode == "i2v" and not input_asset_id:
        raise ValueError("i2v requires input_asset_id from upload_video_image")
    if mode == "t2v" and input_asset_id:
        raise ValueError("t2v cannot use input_asset_id")
    parameters = {}
    if inference_steps is not None:
        parameters["inference_steps"] = inference_steps
    if guidance_scale is not None:
        parameters["guidance_scale"] = guidance_scale
    body: dict[str, Any] = {
        "model_id": model_id, "mode": mode, "prompt": prompt,
        "duration_seconds": duration_seconds, "parameters": parameters,
    }
    if resolution is not None:
        body["resolution"] = resolution
    if seed is not None:
        body["seed"] = seed
    if input_asset_id:
        body["input_asset_id"] = input_asset_id
    key = idempotency_key or f"mcp_{uuid4().hex}"
    result = await _request("POST", "/v1/videos", json=body, headers={"Idempotency-Key": key})
    return {**_without_signed_url(result), "idempotency_key": key}


@mcp.tool
async def get_video_status(job_id: str) -> dict:
    """Check job status, output key, file metadata, and USD estimate without exposing the signed URL."""
    return _without_signed_url(await _request("GET", f"/v1/videos/{_job_id(job_id)}"))


@mcp.tool
async def get_video_url(job_id: str | None = None, video_key: str | None = None) -> dict:
    """Get a fresh one-hour signed MP4 URL for an owned completed video by job_id or video_key."""
    if (job_id is None) == (video_key is None):
        raise ValueError("Provide exactly one of job_id or video_key")
    if job_id is not None:
        return await _request("GET", f"/v1/videos/{_job_id(job_id)}/download")
    return await _request("POST", "/v1/videos/url", json={"video_key": video_key})


@mcp.tool
async def download_video(job_id: str, filename: str | None = None) -> dict:
    """Save a completed MP4 inside VIDEO_MCP_OUTPUT_ROOT and return its local path and cost."""
    _job_id(job_id)
    name = filename or f"{job_id}.mp4"
    if not OUTPUT_NAME.fullmatch(name):
        raise ValueError("filename must be a simple .mp4 name")
    output_root = Path(os.getenv("VIDEO_MCP_OUTPUT_ROOT", str(PROJECT_ROOT / "outputs"))).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    destination = (output_root / name).resolve()
    if not destination.is_relative_to(output_root):
        raise ValueError("Output path is outside VIDEO_MCP_OUTPUT_ROOT")
    if destination.exists():
        raise FileExistsError(f"Output file already exists: {destination}")
    video = await get_video_url(job_id=job_id)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="video-mcp-", suffix=".part", dir=output_root, delete=False) as stream:
            temporary = Path(stream.name)
        written = 0
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            async with client.stream("GET", video["video_url"]) as response:
                response.raise_for_status()
                if response.headers.get("content-type", "").split(";")[0] != "video/mp4":
                    raise ValueError("Download is not an MP4")
                with temporary.open("wb") as stream:
                    async for chunk in response.aiter_bytes():
                        stream.write(chunk)
                        written += len(chunk)
        if written < 1 or written != video["size_bytes"]:
            raise ValueError("Downloaded video size did not match")
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"job_id": job_id, "video_key": video["video_key"], "path": str(destination),
            "size_bytes": written, "cost": video["cost"]}


@mcp.tool
async def cancel_video(job_id: str) -> dict:
    """Request best-effort cancellation of an owned queued or running video job."""
    return _without_signed_url(await _request("POST", f"/v1/videos/{_job_id(job_id)}/cancel"))


if __name__ == "__main__":
    mcp.run(transport="stdio")
