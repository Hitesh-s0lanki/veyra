"""Verify Clerk OAuth access tokens for the video API."""

import os
import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException


USER_ID = re.compile(r"^user_[A-Za-z0-9_-]{1,75}$")


def verify_oauth_token(token: str) -> str:
    """Introspect every token so expiry and revocation take effect immediately."""
    issuer = os.getenv("CLERK_OAUTH_ISSUER", "").rstrip("/")
    client_id = os.getenv("CLERK_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("CLERK_OAUTH_CLIENT_SECRET", "")
    parsed = urlparse(issuer)
    if not (parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password
            and not parsed.path and client_id and client_secret):
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        response = httpx.post(
            f"{issuer}/oauth/token_info",
            auth=(client_id, client_secret),
            data={"token": token},
            timeout=5,
            follow_redirects=False,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc
    if response.status_code in (400, 401):
        raise HTTPException(status_code=401, detail="Invalid token")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    try:
        info = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc
    if (info.get("active") is not True or info.get("client_id") != client_id
            or not isinstance(info.get("sub"), str) or not USER_ID.fullmatch(info["sub"])
            or "profile" not in str(info.get("scope", "")).split()):
        raise HTTPException(status_code=401, detail="Invalid token")
    return info["sub"]
