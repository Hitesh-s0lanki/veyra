"""Fetch the knitted-whale MP4 from S3 and verify it decodes as a complete clip.

The stored object is 67,349 bytes, which the manifest flagged as small.
This script saves the full object regardless of size and runs the same
decode check as probe_marketing_videos.py; it reports the verdict so a
re-render can be scheduled only if the artifact is actually broken.
"""

import json
import re
import subprocess
import urllib.request
from pathlib import Path

import imageio_ffmpeg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "vid_4a206df7df69448687dacb4e7454c534"
DEST = ROOT / "frontend" / "public" / "videos" / "knitted-whale.mp4"


def bearer() -> str:
    return next(iter(json.loads(dotenv_values(ROOT / ".env")["API_TOKENS_JSON"])))


def main() -> None:
    headers = {"Authorization": f"Bearer {bearer()}"}
    request = urllib.request.Request(
        f"http://127.0.0.1:8000/v1/videos/{JOB_ID}/download", headers=headers
    )
    payload = json.load(urllib.request.urlopen(request, timeout=30))
    url = payload["video_url"]
    data = b""
    with urllib.request.urlopen(url, timeout=300) as response:
        while chunk := response.read(1024 * 1024):
            data += chunk
    print(f"downloaded {len(data):,} bytes (S3 reports {payload['size_bytes']:,})")
    DEST.write_bytes(data)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "info", "-i", str(DEST), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    stderr = result.stderr
    duration = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", stderr)
    resolution = re.search(r"Video: .*?, (\d{3,4}x\d{3,4})", stderr)
    errors = [line for line in stderr.splitlines() if "error" in line.lower()]
    verdict = "OK" if result.returncode == 0 and not errors else f"BROKEN rc={result.returncode} {'; '.join(errors[:2])}"
    print(f"knitted-whale.mp4: {verdict} {resolution.group(1) if resolution else '?'} "
          f"{duration.group(1) if duration else '?'} {DEST.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
