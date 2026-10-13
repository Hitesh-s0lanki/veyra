import asyncio
from contextlib import contextmanager
from io import BytesIO

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from src import api as api_module, storage
from src.config import DURATION_FRAMES


def test_video_request_rejects_unsupported_settings_and_missing_image():
    with pytest.raises(ValidationError):
        api_module.VideoRequest(mode="i2v", prompt="A lake")
    with pytest.raises(ValidationError):
        api_module.VideoRequest(mode="t2v", prompt="A lake", resolution="720p")
    with pytest.raises(ValidationError):
        api_module.VideoRequest(mode="t2v", prompt="   ")
    request = api_module.VideoRequest(mode="t2v", prompt=" A lake ")
    assert request.prompt == "A lake"


@pytest.mark.parametrize("duration", [5, 10, 20])
@pytest.mark.parametrize("mode,asset_id", [("t2v", None), ("i2v", "asset_123")])
def test_supported_video_durations_for_text_and_image(mode, asset_id, duration):
    request = api_module.VideoRequest(
        mode=mode, prompt="A lake with moving clouds",
        input_asset_id=asset_id, duration_seconds=duration,
    )
    assert request.duration_seconds == duration
    assert DURATION_FRAMES[duration] % 8 == 1


@pytest.mark.parametrize("duration", [0, 6, 15, 30, 60])
def test_unsupported_single_clip_durations_are_rejected(duration):
    with pytest.raises(ValidationError):
        api_module.VideoRequest(mode="t2v", prompt="A lake", duration_seconds=duration)


def test_bearer_token_is_scoped_to_configured_user(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"token-one":"alice"}')
    assert api_module.current_user("Bearer token-one") == "alice"
    with pytest.raises(api_module.HTTPException) as exc:
        api_module.current_user("Bearer bad-token")
    assert exc.value.status_code == 401


def test_private_job_cannot_be_read_by_another_user(monkeypatch):
    class Connection:
        def execute(self, _sql, values):
            assert values == ("vid_123", "bob")
            return self

        def fetchone(self):
            return None

    @contextmanager
    def fake_connection():
        yield Connection()

    monkeypatch.setattr(api_module.db, "connection", fake_connection)
    api_module.api.dependency_overrides[api_module.current_user] = lambda: "bob"

    async def request():
        transport = httpx.ASGITransport(app=api_module.api)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/v1/videos/vid_123")

    try:
        response = asyncio.run(request())
        assert response.status_code == 404
    finally:
        api_module.api.dependency_overrides.clear()


def test_image_validation_rejects_non_image_payload(monkeypatch):
    class Body:
        def read(self, _size):
            return b"not an image"

    class Client:
        def get_object(self, **_kwargs):
            return {"ContentLength": 12, "Body": Body()}

    monkeypatch.setattr(storage, "client", Client)
    monkeypatch.setattr(storage, "bucket", lambda: "bucket")
    with pytest.raises(ValueError, match="Invalid image"):
        storage.validate_image("uploads/alice/asset")


def test_image_validation_accepts_small_valid_png(monkeypatch):
    buffer = BytesIO()
    Image.new("RGB", (256, 256), "red").save(buffer, format="PNG")
    data = buffer.getvalue()

    class Body:
        def read(self, _size):
            return data

    class Client:
        def get_object(self, **_kwargs):
            return {"ContentLength": len(data), "Body": Body()}

    monkeypatch.setattr(storage, "client", Client)
    monkeypatch.setattr(storage, "bucket", lambda: "bucket")
    assert storage.validate_image("uploads/alice/asset")["width"] == 256
