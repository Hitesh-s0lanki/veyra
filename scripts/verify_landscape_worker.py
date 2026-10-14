"""One cheap LTX verification render to confirm the redeployed worker is landscape.

Submits a 5-second t2v job, polls it, downloads to outputs/, and probes the
dimensions. Not wired into the marketing page.
"""

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "outputs" / "ltx-landscape-test.mp4"
BODY = {
    "model_id": "ltx-2.3-distilled",
    "mode": "t2v",
    "prompt": "A red paper hot-air balloon drifts slowly over layered turquoise mountains at sunrise while clouds pass beneath. The camera pans gently to the right. Whimsical storybook animation.",
    "duration_seconds": 5,
    "resolution": "512p",
    "seed": 62040,
}


def bearer() -> str:
    return next(iter(json.loads(dotenv_values(ROOT / ".env")["API_TOKENS_JSON"])))


def main() -> None:
    headers = {"Authorization": f"Bearer {bearer()}", "Content-Type": "application/json",
               "Idempotency-Key": "verify-landscape-62040"}
    request = urllib.request.Request("http://127.0.0.1:8000/v1/videos",
                                     data=json.dumps(BODY).encode(), headers=headers, method="POST")
    response = json.load(urllib.request.urlopen(request, timeout=30))
    job_id = response["job_id"]
    print(f"submitted {job_id}")
    while True:
        status = json.load(urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:8000/v1/videos/{job_id}",
                                   headers={"Authorization": f"Bearer {bearer()}" }), timeout=30))
        if status["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(10)
    if status["status"] != "succeeded":
        raise SystemExit(f"job {status['status']} ({status.get('error_code')})")
    download = json.load(urllib.request.urlopen(
        urllib.request.Request(f"http://127.0.0.1:8000/v1/videos/{job_id}/download",
                               headers={"Authorization": f"Bearer {bearer()}"}), timeout=30))
    with urllib.request.urlopen(download["video_url"], timeout=300) as r, DEST.open("wb") as f:
        while chunk := r.read(1024 * 1024):
            f.write(chunk)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run([ffmpeg, "-hide_banner", "-v", "info", "-i", str(DEST), "-f", "null", "-"],
                            capture_output=True, text=True)
    resolution = re.search(r"Video: .*?, (\d{3,4}x\d{3,4})", result.stderr)
    duration = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", result.stderr)
    print(f"verification render: {resolution.group(1) if resolution else '?'} "
          f"{duration.group(1) if duration else '?'} {DEST.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
