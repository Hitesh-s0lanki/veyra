"""Extract a still preview from each downloaded marketing video."""

from pathlib import Path
import subprocess

import imageio_ffmpeg


VIDEO_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "videos"


def main() -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for video in sorted(VIDEO_DIR.glob("*.mp4")):
        poster = video.with_suffix(".jpg")
        if poster.exists():
            continue
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "1",
                   "-i", str(video), "-frames:v", "1", "-q:v", "3", "-update", "1", str(poster)]
        subprocess.run(command, check=True)
        print(f"Created {poster.name}")


if __name__ == "__main__":
    main()
