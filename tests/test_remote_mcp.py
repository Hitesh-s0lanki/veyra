"""Hosted MCP exposes only remote-safe tools and requires OAuth."""

import asyncio

import httpx
from starlette.testclient import TestClient

from src import mcp_server, remote_mcp


def configure(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_ORIGIN", "http://localhost:8001")
    monkeypatch.setenv("MCP_FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("MCP_JWT_SIGNING_KEY", "abcdefghijklmnopqrstuvwxyz123456")
    monkeypatch.setenv("CLERK_OAUTH_ISSUER", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_OAUTH_CLIENT_ID", "mcp-client")
    monkeypatch.setenv("CLERK_OAUTH_CLIENT_SECRET", "private-secret")


def test_remote_endpoint_requires_oauth_and_has_no_filesystem_tools(monkeypatch):
    configure(monkeypatch)
    server = remote_mcp.create_remote_mcp()
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert names == {"list_video_models", "generate_video", "get_video_status", "get_video_url", "cancel_video"}

    with TestClient(server.http_app(path="/mcp")) as client:
        challenge = client.get("/mcp")
        assert challenge.status_code == 401
        assert "resource_metadata=" in challenge.headers["www-authenticate"]
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.json()["resource"] == "http://localhost:8001/mcp"
        auth_metadata = client.get("/.well-known/oauth-authorization-server").json()
        assert auth_metadata["authorization_endpoint"] == "http://localhost:8001/authorize"


def test_clerk_verifier_accepts_only_active_tokens_for_this_client(monkeypatch):
    configure(monkeypatch)
    real_client = httpx.AsyncClient

    def mock_client(**kwargs):
        def respond(request):
            assert request.url.path == "/oauth/token_info"
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={
                "active": request.content == b"token=valid-token",
                "client_id": "mcp-client", "scope": "profile offline_access", "sub": "user_123",
            })
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(remote_mcp.httpx, "AsyncClient", mock_client)
    verifier = remote_mcp.ClerkTokenVerifier()
    valid = asyncio.run(verifier.verify_token("valid-token"))
    assert valid is not None and valid.subject == "user_123" and valid.token == "valid-token"
    assert asyncio.run(verifier.verify_token("invalid-token")) is None


def test_hosted_request_uses_clerk_token_and_private_api_origin(monkeypatch):
    monkeypatch.setenv("MCP_API_INTERNAL_ORIGIN", "http://127.0.0.1:9000")
    monkeypatch.setenv("VIDEO_API_BASE_URL", "https://unrelated.example")
    monkeypatch.setattr(mcp_server, "get_access_token", lambda: remote_mcp.AccessToken(
        token="upstream-clerk-token", client_id="mcp-client", scopes=["profile"], subject="user_123",
    ))
    assert mcp_server._api_token() == "upstream-clerk-token"
    assert mcp_server._base_url() == "http://127.0.0.1:9000"
