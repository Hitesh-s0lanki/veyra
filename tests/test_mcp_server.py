"""FastMCP tools use the API contract without starting billable jobs."""

import asyncio
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from PIL import Image

from src import mcp_server


JOB_ID = "vid_" + "a" * 32


def test_mcp_tools_are_discoverable_and_submit_correct_payload(monkeypatch):
    calls = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/v1/models":
            return {"models": [{"model_id": "wan-2.2"}]}
        return {"job_id": JOB_ID, "status": "queued"}

    monkeypatch.setattr(mcp_server, "_request", fake_request)

    async def check():
        async with Client(mcp_server.mcp) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert names == {
                "list_video_models", "upload_video_image", "generate_video",
                "get_video_status", "get_video_url", "download_video", "cancel_video",
            }
            models = await client.call_tool("list_video_models", {})
            assert models.data["models"][0]["model_id"] == "wan-2.2"
            result = await client.call_tool("generate_video", {
                "prompt": "A slow pan over a lake", "model_id": "wan-2.2",
                "duration_seconds": 5, "resolution": "720p", "seed": 42,
                "inference_steps": 10, "guidance_scale": 5.0,
                "idempotency_key": "lake_001",
            })
            assert result.data["job_id"] == JOB_ID
            assert result.data["idempotency_key"] == "lake_001"

    asyncio.run(check())
    assert calls[1] == (
        "POST", "/v1/videos", {
            "json": {
                "model_id": "wan-2.2", "mode": "t2v", "prompt": "A slow pan over a lake",
                "duration_seconds": 5, "parameters": {
                    "inference_steps": 10, "guidance_scale": 5.0,
                }, "resolution": "720p", "seed": 42,
            },
            "headers": {"Idempotency-Key": "lake_001"},
        },
    )


def test_status_and_retry_omit_signed_url(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"job_id": JOB_ID, "status": "succeeded", "output": {
            "video_key": "videos/owned/output.mp4", "video_url": "private-signed-url",
        }}

    monkeypatch.setattr(mcp_server, "_request", fake_request)
    status = asyncio.run(mcp_server.get_video_status(JOB_ID))
    retry = asyncio.run(mcp_server.generate_video("A lake", idempotency_key="retry_001"))
    cancelled = asyncio.run(mcp_server.cancel_video(JOB_ID))
    for result in (status, retry, cancelled):
        assert result["output"] == {"video_key": "videos/owned/output.mp4"}


def test_url_by_owned_key_and_job_id(monkeypatch):
    calls = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"video_url": "private-signed-url", "expires_in": 3600}

    monkeypatch.setattr(mcp_server, "_request", fake_request)
    assert asyncio.run(mcp_server.get_video_url(job_id=JOB_ID))["expires_in"] == 3600
    assert asyncio.run(mcp_server.get_video_url(video_key="videos/owned/output.mp4"))["expires_in"] == 3600
    assert calls == [
        ("GET", f"/v1/videos/{JOB_ID}/download", {}),
        ("POST", "/v1/videos/url", {"json": {"video_key": "videos/owned/output.mp4"}}),
    ]
    with pytest.raises(ValueError):
        asyncio.run(mcp_server.get_video_url(job_id="../other"))


def test_image_upload_path_is_confined(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    image_path = allowed / "frame.png"
    Image.new("RGB", (256, 256), "blue").save(image_path)
    monkeypatch.setenv("VIDEO_MCP_IMAGE_ROOT", str(allowed))
    path, content_type, data = mcp_server._image_file(str(image_path))
    assert path == image_path and content_type == "image/png" and data.startswith(b"\x89PNG")
    outside = tmp_path / "outside.png"
    Image.new("RGB", (256, 256), "red").save(outside)
    with pytest.raises(ValueError, match="within VIDEO_MCP_IMAGE_ROOT"):
        mcp_server._image_file(str(outside))


def test_token_falls_back_only_for_single_local_user(monkeypatch, tmp_path):
    monkeypatch.delenv("VIDEO_API_TOKEN", raising=False)
    monkeypatch.setattr(mcp_server, "PROJECT_ROOT", Path(tmp_path))
    (tmp_path / ".env").write_text('API_TOKENS_JSON={"one-token":"user_1"}\n')
    assert mcp_server._api_token() == "one-token"
    (tmp_path / ".env").write_text('API_TOKENS_JSON={"a":"user_1","b":"user_2"}\n')
    with pytest.raises(RuntimeError, match="Configure VIDEO_API_TOKEN"):
        mcp_server._api_token()


def test_download_saves_mp4_and_rejects_overwrite(monkeypatch, tmp_path):
    payload = b"mock mp4 bytes"

    async def fake_url(**_kwargs):
        return {
            "video_url": "https://download.example/video.mp4",
            "video_key": "videos/owned/output.mp4",
            "size_bytes": len(payload),
            "cost": {"estimated_gpu_cost_usd": "0.012345"},
        }

    real_client = httpx.AsyncClient

    def mock_client(**kwargs):
        transport = httpx.MockTransport(lambda _request: httpx.Response(
            200, headers={"content-type": "video/mp4"}, content=payload,
        ))
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(mcp_server, "get_video_url", fake_url)
    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", mock_client)
    monkeypatch.setenv("VIDEO_MCP_OUTPUT_ROOT", str(tmp_path))
    result = asyncio.run(mcp_server.download_video(JOB_ID))
    assert Path(result["path"]).read_bytes() == payload
    assert result["cost"]["estimated_gpu_cost_usd"] == "0.012345"
    with pytest.raises(FileExistsError):
        asyncio.run(mcp_server.download_video(JOB_ID))
