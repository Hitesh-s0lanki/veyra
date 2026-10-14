import asyncio
import json
from contextlib import contextmanager
from io import BytesIO

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from src import api as api_module, storage
from src.config import DURATION_FRAMES, I2V_DIMS
from src.config import MODEL_PROFILES


def test_video_request_rejects_unsupported_settings_and_missing_image():
    with pytest.raises(ValidationError):
        api_module.VideoRequest(mode="i2v", prompt="A lake")
    with pytest.raises(ValidationError):
        api_module.VideoRequest(mode="t2v", prompt="A lake", resolution="1080p")
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


@pytest.mark.parametrize("model_id,resolution,scale", [
    ("wan-2.2", "720p", 5.0),
    ("hunyuanvideo-1.5", "480p", 6.0),
    ("cogvideox-1.5", "480p", 6.0),
])
def test_deployed_model_profiles_have_valid_defaults(model_id, resolution, scale):
    request = api_module.VideoRequest(model_id=model_id, mode="t2v", prompt="A lake")
    assert request.resolution == resolution
    assert request.parameters == {"inference_steps": 10, "guidance_scale": scale}
    assert MODEL_PROFILES[model_id]["app"].startswith("video-pipeline-")


@pytest.mark.parametrize("model_id,base_resolution", [
    ("ltx-2.3-distilled", "512p"),
    ("ltx-2.3-distilled", "720p"),
    ("wan-2.2", "720p"),
    ("hunyuanvideo-1.5", "480p"),
    ("cogvideox-1.5", "480p"),
])
def test_portrait_text_to_video_presets(model_id, base_resolution):
    portrait = f"{base_resolution}-portrait"
    request = api_module.VideoRequest(
        model_id=model_id, mode="t2v", prompt="A lake", resolution=portrait,
    )
    assert request.resolution == portrait
    assert portrait in MODEL_PROFILES[model_id]["resolutions"]
    assert api_module.billing.quote(
        model_id, "t2v", request.duration_seconds, portrait, request.parameters,
    )["resolution"] == portrait
    with pytest.raises(ValidationError):
        api_module.VideoRequest(
            model_id=model_id, mode="i2v", prompt="A lake",
            input_asset_id="asset_123", resolution=portrait,
        )


def test_ltx_image_to_video_dimensions_match_two_stage_grid():
    for orientations in I2V_DIMS.values():
        for width, height in orientations.values():
            assert width % 64 == 0
            assert height % 64 == 0


def test_model_specific_settings_are_validated():
    invalid = [
        {"model_id": "unknown"},
        {"model_id": "wan-2.2", "mode": "i2v", "input_asset_id": "asset_1"},
        {"model_id": "wan-2.2", "duration_seconds": 10},
        {"model_id": "wan-2.2", "resolution": "480p"},
        {"model_id": "ltx-2.3-distilled", "parameters": {"inference_steps": 10}},
        {"model_id": "wan-2.2", "parameters": {"inference_steps": 0}},
        {"model_id": "wan-2.2", "parameters": {"inference_steps": True}},
        {"model_id": "wan-2.2", "parameters": {"guidance_scale": 21}},
        {"model_id": "wan-2.2", "parameters": {"guidance_scale": float("nan")}},
        {"model_id": "wan-2.2", "guidance_scale": 5},
    ]
    for settings in invalid:
        with pytest.raises(ValidationError):
            api_module.VideoRequest(**{"mode": "t2v", "prompt": "A lake", **settings})


@pytest.mark.parametrize("model_id", list(MODEL_PROFILES))
def test_submit_dispatches_to_selected_deployed_worker(monkeypatch, model_id):
    import modal

    statements = []
    spawned = []

    class Connection:
        def execute(self, sql, values):
            statements.append((sql, values))
            self.sql = sql
            return self

        def fetchone(self):
            if "count(*)" in self.sql:
                return {"n": 0}
            return None

    @contextmanager
    def fake_connection():
        yield Connection()

    class Worker:
        def __init__(self):
            self.generate = self

        def spawn(self, job_id):
            spawned.append(job_id)
            return type("Call", (), {"object_id": "fc_test"})()

    class WorkerClass:
        def __call__(self):
            return Worker()

    def from_name(app_name, class_name):
        spawned.append((app_name, class_name))
        return WorkerClass()

    monkeypatch.setattr(api_module.db, "connection", fake_connection)
    monkeypatch.setattr(api_module.billing, "reserve", lambda *_args: 0)
    monkeypatch.setattr(modal.Cls, "from_name", from_name)
    request = api_module.VideoRequest(model_id=model_id, mode="t2v", prompt="A lake")
    result = api_module.submit_video(request, user_id="alice", idempotency_key=None)

    assert result["model_id"] == model_id
    assert spawned[0] == (MODEL_PROFILES[model_id]["app"], "VideoWorker")
    insert = next(values for sql, values in statements if "INSERT INTO video_jobs" in sql)
    assert insert[-4] == model_id
    assert json.loads(insert[-3]) == MODEL_PROFILES[model_id]["defaults"]
    assert any("UPDATE video_jobs SET call_id" in sql for sql, _ in statements)


def test_bearer_token_is_scoped_to_configured_user(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"token-one":"alice"}')
    assert api_module.current_user("Bearer token-one") == "alice"
    with pytest.raises(api_module.HTTPException) as exc:
        api_module.current_user("Bearer bad-token")
    assert exc.value.status_code == 401


def test_models_endpoint_lists_the_deployed_profiles(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"token-one":"alice"}')

    async def request():
        transport = httpx.ASGITransport(app=api_module.api)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            unauthorized = await client.get("/v1/models")
            authorized = await client.get("/v1/models", headers={"Authorization": "Bearer token-one"})
            return unauthorized, authorized

    unauthorized, authorized = asyncio.run(request())
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert {model["model_id"] for model in authorized.json()["models"]} == set(MODEL_PROFILES)


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
