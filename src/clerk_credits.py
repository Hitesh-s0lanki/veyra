"""Clerk Billing account credit adjustments with stable idempotency keys."""

import os

import httpx
from fastapi import HTTPException


def adjust(user_id: str, amount_cents: int, action: str, key: str, note: str) -> None:
    if not user_id.startswith("user_"):
        return  # Static integration tokens have no Clerk account.
    secret = os.getenv("CLERK_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="Clerk credit service not configured")
    try:
        response = httpx.post(
            f"https://api.clerk.com/v1/users/{user_id}/billing/credits",
            headers={"Authorization": f"Bearer {secret}"},
            json={"amount": amount_cents, "action": action,
                  "idempotency_key": key, "currency": "USD", "note": note},
            timeout=10,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Clerk credit service unavailable") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="Clerk credit adjustment failed")
