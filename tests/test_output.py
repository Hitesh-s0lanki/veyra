from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src import api as api_module, cost, storage
from src.config import VIDEO_URL_TTL_SECONDS


def test_download_url_is_signed_for_one_hour(monkeypatch):
    calls = []

    class Client:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            calls.append((operation, Params, ExpiresIn))
            return "https://example.test/signed-video"

    monkeypatch.setattr(storage, "client", Client)
    monkeypatch.setattr(storage, "bucket", lambda: "private-bucket")
    url = storage.download_url("videos/alice/vid_123/output.mp4")
    assert url == "https://example.test/signed-video"
    assert calls == [(
        "get_object",
        {"Bucket": "private-bucket", "Key": "videos/alice/vid_123/output.mp4"},
        3600,
    )]


def test_completed_job_exposes_signed_output_and_estimated_cost(monkeypatch):
    monkeypatch.setattr(storage, "video_metadata", lambda _key: {"size_bytes": 1234, "content_type": "video/mp4"})
    monkeypatch.setattr(storage, "download_url", lambda _key: "https://example.test/signed-video")
    monkeypatch.setattr(cost, "estimate", lambda _job: "0.063210")
    job = {
        "id": "vid_123", "model_id": "wan-2.2", "status": "succeeded",
        "output_key": "videos/alice/vid_123/output.mp4",
    }
    before = datetime.now(timezone.utc)
    result = api_module._public_job(job)
    after = datetime.now(timezone.utc)
    output = result["output"]
    assert output["video_key"] == job["output_key"]
    assert output["video_url"] == "https://example.test/signed-video"
    assert output["expires_in"] == VIDEO_URL_TTL_SECONDS
    assert before.timestamp() + 3600 <= datetime.fromisoformat(output["expires_at"]).timestamp() <= after.timestamp() + 3600
    assert output["size_bytes"] == 1234
    assert result["cost"]["estimated_gpu_cost_usd"] == "0.063210"
    assert result["cost"]["is_exact_bill"] is False


def test_key_lookup_is_owner_scoped(monkeypatch):
    class Connection:
        def execute(self, sql, values):
            assert "output_key=%s AND user_id=%s" in sql
            assert values == ("videos/alice/vid_123/output.mp4", "bob")
            return self

        def fetchone(self):
            return None

    @contextmanager
    def fake_connection():
        yield Connection()

    monkeypatch.setattr(api_module.db, "connection", fake_connection)
    body = api_module.VideoKeyRequest(video_key="videos/alice/vid_123/output.mp4")
    with pytest.raises(api_module.HTTPException) as error:
        api_module.video_url_from_key(body, user_id="bob")
    assert error.value.status_code == 404


def test_cost_estimate_is_snapshotted_with_rate(monkeypatch):
    writes = []

    class Connection:
        def execute(self, sql, values):
            assert "UPDATE video_jobs SET gpu_cost_estimate_usd" in sql
            writes.append(values)
            return self

        def fetchone(self):
            return {"gpu_cost_estimate_usd": writes[-1][0]}

    @contextmanager
    def fake_connection():
        yield Connection()

    monkeypatch.setattr(cost.db, "connection", fake_connection)
    job = {"id": "vid_123", "status": "succeeded", "gpu_model": "NVIDIA H200", "inference_seconds": 1800}
    assert cost.estimate(job) == "2.270000"
    assert writes[0][1] == Decimal("4.54")
