"""Post-restart checks: models preset, wallet, billing tables, S3 artifact."""

import json
from pathlib import Path

import boto3
import psycopg
import urllib.request
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
cfg = dotenv_values(ROOT / ".env")
tokens = json.loads(cfg["API_TOKENS_JSON"])
token = next(t for t, user in tokens.items() if user == "marketing_agent")
job_id = "vid_00b292f4f0ac4201a45ecc92c3b269fe"


def get(path: str) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:8000" + path, headers={"Authorization": f"Bearer {token}"}
    )
    return json.load(urllib.request.urlopen(request, timeout=30))


models = get("/v1/models")["models"]
ltx = next(m for m in models if m["model_id"] == "ltx-2.3-distilled")
print("LTX resolutions:", ltx["resolutions"])
print("wallet:", json.dumps(get("/v1/wallet")))

conn = psycopg.connect(cfg["DATABASE_URL"].strip().strip('"'))
tables = [
    row[0] for row in conn.execute(
        "SELECT tablename FROM pg_tables WHERE tablename IN ('credit_wallets','credit_ledger')"
    ).fetchall()
]
print("billing tables present:", sorted(tables))

s3 = boto3.client(
    "s3", region_name=cfg["AWS_DEFAULT_REGION"],
    aws_access_key_id=cfg["AWS_ACCESS_KEY_ID"], aws_secret_access_key=cfg["AWS_SECRET_ACCESS_KEY"],
)
key = f"videos/user_123/{job_id}/output.mp4"
dest = ROOT / "outputs" / "ltx-landscape-test.mp4"
s3.download_file(cfg["S3_BUCKET"].strip('"'), key, str(dest))
print(f"verification artifact: {dest.stat().st_size:,} bytes")
