"""Add a static integration token for the marketing batch and fund its wallet.

The restarted API rejects static tokens mapped to Clerk-style ``user_*`` IDs,
and a fresh wallet starts at zero, so this script:

1. Generates a random token mapped to ``marketing_agent`` in API_TOKENS_JSON
   (.env). The token value is never printed.
2. Tops the wallet up to 2000 cents with a clearly-labelled ledger entry.

Run once; safe to re-run (it keeps any existing marketing_agent token).
Restart the API afterwards so it reloads the environment.
"""

import json
import secrets
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
USER_ID = "marketing_agent"
TOPUP_CENTS = 2000
env_path = ROOT / ".env"


def main() -> None:
    lines = env_path.read_text(encoding="utf-8").splitlines()
    value = dotenv_values(env_path)
    tokens = json.loads(value["API_TOKENS_JSON"])
    existing = next((t for t, u in tokens.items() if u == USER_ID and t != USER_ID), None)
    if existing:
        print("marketing_agent token already present")
    else:
        token = "mk_" + secrets.token_urlsafe(32)
        # API_TOKENS_JSON maps token -> user_id.
        tokens = {t: u for t, u in tokens.items() if u != USER_ID and t != USER_ID}
        tokens[token] = USER_ID
        replaced = False
        for index, line in enumerate(lines):
            if line.startswith("API_TOKENS_JSON="):
                lines[index] = f"API_TOKENS_JSON={json.dumps(tokens)}"
                replaced = True
                break
        if not replaced:
            lines.append(f"API_TOKENS_JSON={json.dumps(tokens)}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("new marketing_agent token written to .env")

    conn = psycopg.connect(value["DATABASE_URL"].strip().strip('"'))
    with conn.transaction():
        row = conn.execute(
            "SELECT balance_cents FROM credit_wallets WHERE user_id=%s", (USER_ID,)
        ).fetchone()
        if row:
            print(f"wallet exists: {row[0]} cents")
        else:
            conn.execute(
                "INSERT INTO credit_wallets (user_id,balance_cents) VALUES (%s,%s)",
                (USER_ID, TOPUP_CENTS),
            )
            conn.execute(
                """INSERT INTO credit_ledger
                (user_id,operation_id,kind,amount_cents,balance_after_cents,reason)
                VALUES (%s,%s,'starter_grant',%s,%s,%s)""",
                (USER_ID, f"manual-topup:{USER_ID}", TOPUP_CENTS, TOPUP_CENTS,
                 "Manual local topup for the landscape marketing batch"),
            )
            print(f"wallet created with {TOPUP_CENTS} cents")
    conn.close()


if __name__ == "__main__":
    main()
