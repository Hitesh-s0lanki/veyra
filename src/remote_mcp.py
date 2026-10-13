"""Hosted, OAuth-protected MCP endpoint for the video API."""

import os
from urllib.parse import urlparse

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, OAuthProxy, TokenVerifier

from src.mcp_server import (
    cancel_video,
    generate_video,
    get_video_status,
    get_video_url,
    list_video_models,
)
from src.oauth import USER_ID


class ClerkTokenVerifier(TokenVerifier):
    """Check Clerk's opaque OAuth tokens before each MCP request."""

    async def verify_token(self, token: str) -> AccessToken | None:
        issuer = os.environ["CLERK_OAUTH_ISSUER"].rstrip("/")
        client_id = os.environ["CLERK_OAUTH_CLIENT_ID"]
        client_secret = os.environ["CLERK_OAUTH_CLIENT_SECRET"]
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                response = await client.post(
                    f"{issuer}/oauth/token_info",
                    auth=(client_id, client_secret),
                    data={"token": token},
                )
            if response.status_code != 200:
                return None
            info = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        scopes = str(info.get("scope", "")).split()
        subject = info.get("sub")
        if (info.get("active") is not True or info.get("client_id") != client_id
                or "profile" not in scopes or not isinstance(subject, str)
                or not USER_ID.fullmatch(subject)):
            return None
        return AccessToken(token=token, client_id=client_id, scopes=scopes, subject=subject)


def create_remote_mcp() -> FastMCP:
    origin = os.environ["MCP_PUBLIC_ORIGIN"].rstrip("/")
    parsed = urlparse(origin)
    if (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"))
            or not parsed.netloc or parsed.path or parsed.query or parsed.fragment):
        raise RuntimeError("MCP_PUBLIC_ORIGIN must be an HTTPS origin or localhost")
    issuer = os.environ["CLERK_OAUTH_ISSUER"].rstrip("/")
    frontend_origin = os.environ["MCP_FRONTEND_ORIGIN"].rstrip("/")
    frontend = urlparse(frontend_origin)
    if (frontend.scheme != "https" and not (frontend.scheme == "http" and frontend.hostname in ("localhost", "127.0.0.1"))
            or not frontend.netloc or frontend.path or frontend.query or frontend.fragment):
        raise RuntimeError("MCP_FRONTEND_ORIGIN must be an HTTPS origin or localhost")
    auth = OAuthProxy(
        upstream_authorization_endpoint=f"{frontend_origin}/api/mcp/authorize",
        upstream_token_endpoint=f"{issuer}/oauth/token",
        upstream_revocation_endpoint=f"{issuer}/oauth/token/revoke",
        upstream_client_id=os.environ["CLERK_OAUTH_CLIENT_ID"],
        upstream_client_secret=os.environ["CLERK_OAUTH_CLIENT_SECRET"],
        token_verifier=ClerkTokenVerifier(),
        base_url=origin,
        valid_scopes=["profile", "offline_access"],
        extra_authorize_params={"scope": "profile offline_access"},
        forward_resource=False,
        jwt_signing_key=os.environ["MCP_JWT_SIGNING_KEY"],
    )
    server = FastMCP("Video Generation", auth=auth)
    for tool in (list_video_models, generate_video, get_video_status, get_video_url, cancel_video):
        server.add_tool(tool)
    return server


if __name__ == "__main__":
    create_remote_mcp().run(
        transport="http", host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8001")), path="/mcp",
    )
