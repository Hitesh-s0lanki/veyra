"""Re-render the robot-garden showcase clip with LTX-2.3.

The previous clip came from CogVideoX and drifted from the Gemini key-art
poster. This script submits one LTX text-to-video job whose prompt mirrors
the poster scene (mint-green robot, terracotta sunflower pot, rooftop deck
at sunrise), polls it, verifies the artifact with a full ffmpeg decode, and
swaps it into frontend/public/videos/robot-garden.mp4. The manifest and the
showcase model label are updated by the caller or manually afterwards.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
JOB_OUT = ROOT / "outputs" / "robot-garden-ltx.mp4"
DEST = ROOT / "frontend" / "public" / "videos" / "robot-garden.mp4"

PROMPT = (
    "A friendly rounded mint-green robot with a glossy shell stands on the right side "
    "of a wooden rooftop garden deck at sunrise, facing a terracotta pot holding one "
    "tall blooming sunflower. The robot tips a small copper watering can, sparkling "
    "droplets fall onto the soil, and the sunflower's petals brighten as it drinks. "
    "A gentle camera push-in moves toward the flower. Potted herbs line a wooden "
    "railing, hazy Parisian rooftops glow in the background, warm golden light with "
    "soft shadows, polished 3D animated film look."
)
BODY = {
    "model_id": "ltx-2.3-distilled",
    "mode": "t2v",
    "prompt": PROMPT,
    "duration_seconds": 5,
    "resolution": "512p",
    "seed": 62021,
}
IDEMPOTENCY_KEY = "marketing-robot-garden-ltx-62021"


def bearer() -> str:
    return next(iter(json.loads(dotenv_values(ROOT / ".env")["API_TOKENS_JSON"])))


def api(path: str, method: str = "GET", data: dict | None = None, headers: dict | None = None) -> dict:
    all_headers = {"Authorization": f"Bearer {bearer()}"}
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    if headers:
        all_headers.update(headers)
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=all_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API {path} returned HTTP {exc.code}: {exc.read(300).decode(errors='replace')}") from exc


def verify(path: Path) -> tuple[str, str]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "info", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    duration = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", result.stderr)
    resolution = re.search(r"Video: .*?, (\d{3,4}x\d{3,4})", result.stderr)
    errors = [line for line in result.stderr.splitlines() if "error" in line.lower()]
    if result.returncode != 0 or errors:
        raise RuntimeError(f"downloaded clip failed decode: {'; '.join(errors[:2])}")
    return resolution.group(1) if resolution else "?", duration.group(1) if duration else "?"


def main() -> None:
    response = api("/v1/videos", "POST", BODY, {"Idempotency-Key": IDEMPOTENCY_KEY})
    job_id = response["job_id"]
    print(f"submitted {job_id} ({response['status']})", flush=True)
    while True:
        status = api(f"/v1/videos/{job_id}")
        state = status["status"]
        if state in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(10)
    if state != "succeeded":
        raise RuntimeError(f"job {state} ({status.get('error_code', 'unknown')}) — not retrying automatically")
    output = api(f"/v1/videos/{job_id}/download")
    with urllib.request.urlopen(output["video_url"], timeout=300) as response, JOB_OUT.open("wb") as file:
        while chunk := response.read(1024 * 1024):
            file.write(chunk)
    resolution, duration = verify(JOB_OUT)
    DEST.write_bytes(JOB_OUT.read_bytes())
    cost = (output.get("cost") or {}).get("estimated_gpu_cost_usd")
    print(f"robot-garden.mp4 replaced: {resolution} {duration} {DEST.stat().st_size:,} bytes, gpu estimate ${cost}")


if __name__ == "__main__":
    main()
