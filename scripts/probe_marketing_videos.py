"""Probe every showcase MP4 by fully decoding it with ffmpeg.

A clean decode pass (exit code 0, no decode errors) proves the MP4 is
complete and playable; duration, resolution, and frame count are parsed
from the ffmpeg banner.
"""

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

VIDEO_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "videos"


def main() -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for mp4 in sorted(VIDEO_DIR.glob("*.mp4")):
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-v", "info", "-i", str(mp4), "-f", "null", "-"],
            capture_output=True, text=True,
        )
        errors = [
            line for line in result.stderr.splitlines()
            if "error" in line.lower() or "invalid" in line.lower() or "moov atom not found" in line.lower()
        ]
        stderr = result.stderr
        duration_match = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", stderr)
        resolution_match = re.search(r"Video: .*?, (\d{3,4}x\d{3,4})", stderr)
        duration = duration_match.group(1) if duration_match else "?"
        resolution = resolution_match.group(1) if resolution_match else "?"
        status = "OK" if result.returncode == 0 and not errors else f"SUSPECT rc={result.returncode} {'; '.join(errors[:2])}"
        print(f"{mp4.name}: {status} {resolution} {duration} {mp4.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
