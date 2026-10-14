"""Snapshot a job's GPU-runtime estimate without claiming exact Modal billing."""

from decimal import Decimal, ROUND_HALF_UP

from src import db
from src.config import GPU_HOURLY_RATES_USD


def gpu_type(name: str | None) -> str | None:
    if not name:
        return None
    upper = name.upper()
    return next((gpu for gpu in GPU_HOURLY_RATES_USD if gpu in upper), None)


def estimate(job: dict) -> str | None:
    """Return a stable USD estimate, storing the rate used on first read."""
    if job.get("gpu_cost_estimate_usd") is not None:
        return f"{Decimal(str(job['gpu_cost_estimate_usd'])):.6f}"
    seconds = job.get("inference_seconds")
    kind = gpu_type(job.get("gpu_model"))
    if job.get("status") != "succeeded" or seconds is None or kind is None:
        return None
    rate = Decimal(GPU_HOURLY_RATES_USD[kind])
    amount = (Decimal(str(seconds)) * rate / Decimal(3600)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    with db.connection() as conn:
        row = conn.execute(
            """UPDATE video_jobs SET gpu_cost_estimate_usd=%s, gpu_rate_usd_per_hour=%s
            WHERE id=%s AND status='succeeded' AND gpu_cost_estimate_usd IS NULL
            RETURNING gpu_cost_estimate_usd""",
            (amount, rate, job["id"]),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT gpu_cost_estimate_usd FROM video_jobs WHERE id=%s", (job["id"],)
            ).fetchone()
    return f"{Decimal(str(row['gpu_cost_estimate_usd'])):.6f}" if row and row["gpu_cost_estimate_usd"] is not None else None
