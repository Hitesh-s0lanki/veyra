"""Verify Clerk OAuth access tokens for the video API."""

import os
import re
from functools import lru_cache
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import HTTPException


USER_ID = re.compile(r"^user_[A-Za-z0-9_-]{1,75}$")


@lru_cache(maxsize=4)
def _session_keys(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", lifespan=300)


def verify_session_token(token: str) -> str:
    """Verify a short-lived Clerk browser session token for the web dashboard."""
    issuer = os.getenv("CLERK_OAUTH_ISSUER", "").rstrip("/")
    origin = os.getenv("CLERK_WEB_ORIGIN", "").rstrip("/")
    parsed = urlparse(issuer)
    web = urlparse(origin)
    if not (parsed.scheme == "https" and parsed.netloc and not parsed.path
            and web.scheme in ("http", "https") and web.netloc and not web.path
            and (web.scheme == "https" or web.hostname in ("localhost", "127.0.0.1"))):
        raise HTTPException(status_code=503, detail="Session authentication is not configured")
    try:
        key = _session_keys(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], issuer=issuer,
            options={"require": ["iss", "sub", "sid", "azp", "exp", "nbf", "iat"], "verify_aud": False},
            leeway=5,
        )
    except (jwt.PyJWKClientConnectionError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user_id = claims.get("sub")
    if (claims.get("azp") != origin or not isinstance(claims.get("sid"), str)
            or not claims["sid"].startswith("sess_")
            or not isinstance(user_id, str) or not USER_ID.fullmatch(user_id)):
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


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
