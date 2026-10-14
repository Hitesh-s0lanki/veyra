"""Submission routes keep challenge validation and report access owner-scoped."""

from contextlib import contextmanager
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.api import api
from src.verification import SPEAKER_ID, TRIMMER_ID

AUTH = {"Authorization": "Bearer test-token"}


def test_verification_routes_require_authentication(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"test-token":"test_owner"}')
    client = TestClient(api)
    assert client.get("/v1/challenges").status_code == 401
    response = client.get("/v1/challenges", headers=AUTH)
    assert response.status_code == 200
    assert {item["challenge_id"] for item in response.json()["challenges"]} == {SPEAKER_ID, TRIMMER_ID}
    assert all(item["concept_test"] for item in response.json()["challenges"])


def test_submission_requires_listed_product_before_upload(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"test-token":"test_owner"}')
    client = TestClient(api)
    with patch("src.submissions._save_video") as save_video:
        response = client.post(
            "/v1/submissions", headers=AUTH,
            data={"challenge_id": TRIMMER_ID},
            files={"video": ("clip.mp4", b"video", "video/mp4")},
        )
    assert response.status_code == 422
    save_video.assert_not_called()


def test_submission_creates_owner_scoped_job(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"test-token":"test_owner"}')
    connection = Mock()

    @contextmanager
    def fake_connection():
        yield connection

    call = Mock(object_id="call-123")
    client = TestClient(api)
    with patch("src.submissions.db.connection", fake_connection), \
         patch("src.submissions._save_video", return_value="submissions/test_owner/source.mp4"), \
         patch("modal.Function.from_name", return_value=Mock(spawn=Mock(return_value=call))) as dispatch:
        response = client.post(
            "/v1/submissions", headers=AUTH,
            data={"challenge_id": SPEAKER_ID},
            files={"video": ("clip.mp4", b"video", "video/mp4")},
        )
    assert response.status_code == 202
    assert response.json()["processing_status"] == "queued"
    assert response.json()["report_url"].endswith(response.json()["submission_id"])
    dispatch.assert_called_once_with("video-pipeline-verification", "verify_submission")
    assert connection.execute.call_count == 2
    assert connection.execute.call_args_list[0].args[1][1] == "test_owner"


def test_another_users_submission_is_not_returned(monkeypatch):
    monkeypatch.setenv("API_TOKENS_JSON", '{"test-token":"test_owner"}')
    connection = Mock()

    @contextmanager
    def fake_connection():
        yield connection

    client = TestClient(api)
    with patch("src.submissions.db.connection", fake_connection), \
         patch("src.submissions.db.owned_submission", return_value=None) as owned:
        response = client.get("/v1/submissions/00000000-0000-0000-0000-000000000001", headers=AUTH)
    assert response.status_code == 404
    assert owned.call_args.args[2] == "test_owner"
