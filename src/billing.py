"""Atomic promotional wallet for generation charges.

Clerk identifies users; this ledger is authoritative for GPU and Gemini work.
Clerk Billing account credits apply to Clerk-created charges, not these jobs.
"""

from decimal import Decimal

from fastapi import HTTPException

from src import clerk_credits
from src.config import (MODEL_PROFILES, VIDEO_BASE_PRICES_CENTS,
                        STARTER_CREDIT_CENTS, PRICING_VERSION, CREATIVE_PRICES_CENTS)


def usd(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def quote(model_id: str, mode: str, duration_seconds: int,
          resolution: str, parameters: dict) -> dict:
    profile = MODEL_PROFILES.get(model_id)
    if (profile is None or mode not in profile["modes"] or
            duration_seconds not in profile["durations"] or
            resolution not in profile["resolutions"]):
        raise ValueError("Unsupported video settings")
    base = VIDEO_BASE_PRICES_CENTS[model_id][duration_seconds]
    default_steps = profile["defaults"].get("inference_steps")
    steps = parameters.get("inference_steps", default_steps)
    # More diffusion steps increase worker runtime. Charge whole baseline
    # multiples; exact amount is locked in before the job is dispatched.
    amount = base * ((steps + default_steps - 1) // default_steps) if default_steps else base
    return {"currency": "USD", "amount_cents": amount, "amount_usd": usd(amount),
            "model_id": model_id, "mode": mode, "duration_seconds": duration_seconds,
            "resolution": resolution, "pricing_version": PRICING_VERSION}


def ensure_wallet(conn, user_id: str) -> None:
    # The grant is attached to the verified Clerk subject and guarded by the
    # wallet primary key, so repeated sessions/webhooks cannot grant twice.
    amount = STARTER_CREDIT_CENTS if user_id.startswith("user_") else 0
    row = conn.execute(
        """INSERT INTO credit_wallets (user_id,balance_cents)
        VALUES (%s,%s) ON CONFLICT (user_id) DO NOTHING RETURNING user_id""",
        (user_id, amount),
    ).fetchone()
    if row and amount:
        clerk_credits.adjust(user_id, amount, "increase", f"starter:{user_id}",
                             "Video app signup credit")
        conn.execute(
            """INSERT INTO credit_ledger
            (user_id,operation_id,kind,amount_cents,balance_after_cents)
            VALUES (%s,%s,'starter_grant',%s,%s)""",
            (user_id, f"starter:{user_id}", amount, amount),
        )


def balance(conn, user_id: str) -> dict:
    ensure_wallet(conn, user_id)
    row = conn.execute("SELECT balance_cents FROM credit_wallets WHERE user_id=%s", (user_id,)).fetchone()
    cents = row["balance_cents"]
    return {"currency": "USD", "balance_cents": cents, "balance_usd": usd(cents),
            "initial_credit_cents": STARTER_CREDIT_CENTS if user_id.startswith("user_") else 0}


def reserve(conn, user_id: str, operation_id: str, amount_cents: int, reason: str) -> int:
    if amount_cents <= 0:
        raise ValueError("A paid operation must have a positive price")
    ensure_wallet(conn, user_id)
    # Caller holds a per-user advisory transaction lock for video submissions.
    # This row lock also serializes creative operations and other API replicas.
    row = conn.execute(
        "SELECT balance_cents FROM credit_wallets WHERE user_id=%s FOR UPDATE", (user_id,)
    ).fetchone()
    existing = conn.execute(
        "SELECT amount_cents,kind FROM credit_ledger WHERE operation_id=%s AND kind='reserve'",
        (operation_id,),
    ).fetchone()
    if existing:
        if existing["amount_cents"] != -amount_cents:
            raise HTTPException(status_code=409, detail="Operation reused with different price")
        return row["balance_cents"]
    if row["balance_cents"] < amount_cents:
        raise HTTPException(status_code=402, detail="Insufficient credits")
    after = row["balance_cents"] - amount_cents
    clerk_credits.adjust(user_id, amount_cents, "decrease", f"reserve:{operation_id}",
                         f"Video app {reason}")
    conn.execute("UPDATE credit_wallets SET balance_cents=%s WHERE user_id=%s", (after, user_id))
    conn.execute(
        """INSERT INTO credit_ledger
        (user_id,operation_id,kind,amount_cents,balance_after_cents,reason)
        VALUES (%s,%s,'reserve',%s,%s,%s)""",
        (user_id, operation_id, -amount_cents, after, reason),
    )
    return after


def settle(conn, operation_id: str, success: bool = True) -> bool:
    reserve_row = conn.execute(
        """SELECT user_id,amount_cents FROM credit_ledger
        WHERE operation_id=%s AND kind='reserve'""", (operation_id,)
    ).fetchone()
    if not reserve_row:
        return False  # Legacy job with no user-facing charge.
    user_id = reserve_row["user_id"]
    row = conn.execute(
        "SELECT balance_cents FROM credit_wallets WHERE user_id=%s FOR UPDATE", (user_id,)
    ).fetchone()
    terminal = conn.execute(
        """SELECT kind FROM credit_ledger WHERE operation_id=%s
        AND kind IN ('capture','refund')""", (operation_id,)
    ).fetchone()
    if terminal:
        return False
    amount = 0 if success else -reserve_row["amount_cents"]
    after = row["balance_cents"] + amount
    if amount:
        clerk_credits.adjust(user_id, amount, "increase", f"refund:{operation_id}",
                             "Video app failed or cancelled operation refund")
        conn.execute("UPDATE credit_wallets SET balance_cents=%s WHERE user_id=%s", (after, user_id))
    conn.execute(
        """INSERT INTO credit_ledger
        (user_id,operation_id,kind,amount_cents,balance_after_cents)
        VALUES (%s,%s,%s,%s,%s)""",
        (user_id, operation_id, "capture" if success else "refund", amount, after),
    )
    return True
