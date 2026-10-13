"""OAuth introspection keeps API ownership tied to verified Clerk users."""

import httpx
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric import rsa
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


def test_dashboard_session_signature_and_origin(monkeypatch):
    monkeypatch.setenv("CLERK_WEB_ORIGIN", "http://localhost:3000")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    class Keys:
        def get_signing_key_from_jwt(self, _token):
            return type("SigningKey", (), {"key": public_key})()
    monkeypatch.setattr(oauth, "_session_keys", lambda _issuer: Keys())
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://example.clerk.accounts.dev", "sub": "user_abc123",
        "sid": "sess_123", "azp": "http://localhost:3000",
        "iat": now, "nbf": now, "exp": now + timedelta(minutes=1),
    }
    valid = jwt.encode(claims, private_key, algorithm="RS256")
    assert oauth.verify_session_token(valid) == "user_abc123"

    wrong_origin = jwt.encode({**claims, "azp": "https://other.example"}, private_key, algorithm="RS256")
    forged = jwt.encode(claims, rsa.generate_private_key(public_exponent=65537, key_size=2048), algorithm="RS256")
    for token in (wrong_origin, forged):
        with pytest.raises(HTTPException) as error:
            oauth.verify_session_token(token)
        assert error.value.status_code == 401
