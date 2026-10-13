"""Job persistence; every state change is conditional and owner-scoped."""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from src.config import require_env

SCHEMA = """
CREATE TABLE IF NOT EXISTS video_assets (
    id text PRIMARY KEY, user_id text NOT NULL, object_key text NOT NULL UNIQUE,
    content_type text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS video_jobs (
    id text PRIMARY KEY, user_id text NOT NULL, idempotency_key text,
    request_hash text NOT NULL, mode text NOT NULL, prompt text NOT NULL,
    asset_id text REFERENCES video_assets(id), duration_seconds integer NOT NULL,
    resolution text NOT NULL, seed bigint NOT NULL, status text NOT NULL DEFAULT 'queued',
    call_id text, output_key text, error_code text, model_version text,
    gpu_model text, inference_seconds double precision, attempt integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT video_status_check CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    CONSTRAINT video_user_idempotency UNIQUE (user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS video_jobs_user_status ON video_jobs(user_id, status);
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS model_id text NOT NULL DEFAULT 'ltx-2.3-distilled';
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS parameters jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS gpu_cost_estimate_usd numeric(14,6);
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS gpu_rate_usd_per_hour numeric(10,4);
CREATE UNIQUE INDEX IF NOT EXISTS video_jobs_output_key_unique ON video_jobs(output_key) WHERE output_key IS NOT NULL;
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS price_cents integer;
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS pricing_version text;
CREATE TABLE IF NOT EXISTS credit_wallets (
    user_id text PRIMARY KEY, balance_cents integer NOT NULL DEFAULT 0,
    CONSTRAINT wallet_nonnegative CHECK (balance_cents >= 0)
);
CREATE TABLE IF NOT EXISTS credit_ledger (
    id bigserial PRIMARY KEY, user_id text NOT NULL REFERENCES credit_wallets(user_id),
    operation_id text NOT NULL, kind text NOT NULL, amount_cents integer NOT NULL,
    balance_after_cents integer NOT NULL, reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ledger_kind CHECK (kind IN ('starter_grant','reserve','capture','refund')),
    CONSTRAINT ledger_operation_kind UNIQUE (operation_id,kind)
);
CREATE INDEX IF NOT EXISTS credit_ledger_user_created ON credit_ledger(user_id,created_at DESC,id DESC);
"""


@contextmanager
def connection():
    with psycopg.connect(require_env("DATABASE_URL"), row_factory=dict_row) as conn:
        yield conn


def initialize():
    with connection() as conn:
        conn.execute(SCHEMA)


def owned_job(conn, job_id: str, user_id: str):
    return conn.execute(
        "SELECT * FROM video_jobs WHERE id=%s AND user_id=%s", (job_id, user_id)
    ).fetchone()


def set_status(conn, job_id: str, before: tuple[str, ...], after: str, **fields):
    allowed = {"call_id", "output_key", "error_code", "model_version", "gpu_model", "inference_seconds"}
    if set(fields) - allowed:
        raise ValueError("Unexpected job field")
    assignments = ["status=%s", "updated_at=now()"] + [f"{key}=%s" for key in fields]
    sql = f"UPDATE video_jobs SET {', '.join(assignments)} WHERE id=%s AND status=ANY(%s) RETURNING id"
    values = [after, *fields.values(), job_id, list(before)]
    changed = conn.execute(sql, values).fetchone() is not None
    if changed and after in ("succeeded", "failed", "cancelled"):
        from src import billing
        billing.settle(conn, job_id, success=after == "succeeded")
    return changed
