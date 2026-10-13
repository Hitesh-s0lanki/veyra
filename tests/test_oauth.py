"""OAuth introspection keeps API ownership tied to verified Clerk users."""

import httpx
import pytest
from fastapi import HTTPException

from src import oauth


@pytest.fixture(autouse=True)
def oauth_settings(monkeypatch):
    monkeypatch.setenv("CLERK_OAUTH_ISSUER", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_OAUTH_CLIENT_ID", "client_1")
    monkeypatch.setenv("CLERK_OAUTH_CLIENT_SECRET", "secret_1")


def test_verified_token_maps_to_clerk_user(monkeypatch):
    def fake_post(url, **kwargs):
        assert url == "https://example.clerk.accounts.dev/oauth/token_info"
        assert kwargs["auth"] == ("client_1", "secret_1")
        assert kwargs["data"] == {"token": "oauth-token"}
        return httpx.Response(200, json={
            "active": True, "client_id": "client_1", "sub": "user_abc123", "scope": "profile offline_access",
        })

    monkeypatch.setattr(oauth.httpx, "post", fake_post)
    assert oauth.verify_oauth_token("oauth-token") == "user_abc123"


@pytest.mark.parametrize("info", [
    {"active": False, "client_id": "client_1", "sub": "user_abc123", "scope": "profile"},
    {"active": True, "client_id": "another-client", "sub": "user_abc123", "scope": "profile"},
    {"active": True, "client_id": "client_1", "sub": "user_abc123", "scope": "email"},
    {"active": True, "client_id": "client_1", "sub": "other_account", "scope": "profile"},
])
def test_rejects_inactive_wrong_client_scope_or_subject(monkeypatch, info):
    monkeypatch.setattr(oauth.httpx, "post", lambda *_args, **_kwargs: httpx.Response(200, json=info))
    with pytest.raises(HTTPException) as error:
        oauth.verify_oauth_token("oauth-token")
    assert error.value.status_code == 401


def test_introspection_outage_is_unavailable_not_authenticated(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(oauth.httpx, "post", unavailable)
    with pytest.raises(HTTPException) as error:
        oauth.verify_oauth_token("oauth-token")
    assert error.value.status_code == 503
