"""Show the most recent video jobs from the local database."""

import sys

import psycopg
from dotenv import dotenv_values

url = dotenv_values(".env")["DATABASE_URL"].strip().strip('"')
conn = psycopg.connect(url)
rows = conn.execute(
    "SELECT id, model_id, mode, resolution, status, error_code, created_at "
    "FROM video_jobs ORDER BY created_at DESC LIMIT %s",
    (int(sys.argv[1]) if len(sys.argv) > 1 else 5,),
).fetchall()
for row in rows:
    print(row)
