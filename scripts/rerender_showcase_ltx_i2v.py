"""Re-render the nine remaining showcase clips as LTX-2.3 image-to-video.

Every clip starts from its own Gemini key-art poster
(``frontend/public/videos/<slug>.jpg``) uploaded through the asset flow, so
the rendered video replicates the generated image while the prompt adds one
motion beat plus one camera move scoped to five seconds, per the repository's
LTX-2.3 prompting reference.

Run from the repository root:
``.venv/Scripts/python scripts/rerender_showcase_ltx_i2v.py``

Resumable: clips whose manifest entry already says ``mode: i2v`` and
``status: downloaded`` are skipped. Failed jobs never overwrite the existing
MP4; the previous renders stay in ``outputs/pre-ltx-i2v-backups/``.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import imageio_ffmpeg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
VIDEO_DIR = ROOT / "frontend" / "public" / "videos"
WORK_DIR = ROOT / "outputs" / "ltx-i2v-renders"
MANIFEST = ROOT / "reports" / "marketing_videos.json"
LOCK = Lock()

# One action beat + one camera move each; the poster fixes the look.
CLIPS = {
    "paper-city": {
        "prompt": "The little paper tram glides steadily from left to right along its track while warm windows light up one by one across the square. The camera slowly pushes in toward the central fountain.",
        "seed": 62031,
    },
    "clay-astronaut": {
        "prompt": "The clay astronaut takes two slow buoyant steps forward, then raises one arm and waves cheerfully as its helmet glints. The camera dollies in gently, keeping the flag and ringed planet behind it.",
        "seed": 62032,
    },
    "watercolor-koi": {
        "prompt": "The two koi swim along their circular path, their tails stirring fresh pigment blooms that swirl outward across the paper while lily leaves drift at the edge. The camera glides slowly clockwise above the pond.",
        "seed": 62033,
    },
    "balloon-voyage": {
        "prompt": "The red paper hot-air balloon rises smoothly toward the golden sunrise while foreground clouds drift aside in soft parallax. The camera pans slowly sideways, holding the layered turquoise mountains behind it.",
        "seed": 62034,
    },
    "pixel-train": {
        "prompt": "The pixel train rolls steadily across the bridge from left to right, its glowing windows reflecting on the luminous river below as stars blink overhead. The camera tracks smoothly alongside the train.",
        "seed": 62035,
    },
    "ink-fox": {
        "prompt": "The ink fox bounds forward two strides through the brushstroke forest, then pauses and lifts its nose as the glowing firefly rises slowly past it. The camera tracks gently to follow the fox.",
        "seed": 62036,
    },
    "knitted-whale": {
        "prompt": "The knitted whale arcs upward through the yarn waves and releases a soft puff of cotton spray from its blowhole while the waves roll beneath it. The camera tracks slowly to follow the whale.",
        "seed": 62037,
    },
    "isometric-market": {
        "prompt": "The tiny delivery bicycle pedals down the center lane of the night market as shop lights turn on in sequence and the awnings sway gently. The camera cranes slowly upward over the miniature stalls.",
        "seed": 62038,
    },
    "glass-butterfly": {
        "prompt": "The stained-glass butterfly slowly opens its amber and turquoise wings, then lifts off and glides across the shaft of golden light. The camera tilts gently upward, following its flight.",
        "seed": 62039,
    },
}


def bearer() -> str:
    return next(iter(json.loads(dotenv_values(ROOT / ".env")["API_TOKENS_JSON"])))


def api(path: str, data: dict | bytes | None = None, headers: dict | None = None, method: str | None = None) -> dict:
    all_headers = {"Authorization": f"Bearer {bearer()}"}
    if isinstance(data, dict):
        all_headers["Content-Type"] = "application/json"
    if headers:
        all_headers.update(headers)
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    request = urllib.request.Request(BASE_URL + path, data=body, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API {path} returned HTTP {exc.code}: {exc.read(300).decode(errors='replace')}") from exc


def upload_poster(slug: str) -> str:
    poster = VIDEO_DIR / f"{slug}.jpg"
    asset = api("/v1/assets", {"content_type": "image/jpeg"})
    asset_id = asset["asset_id"]
    fields = asset["upload"]["fields"]
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts += [f"--{boundary}", f'Content-Disposition: form-data; name="{key}"', "", value]
    parts += [
        f"--{boundary}",
        'Content-Disposition: form-data; name="file"; filename="poster.jpg"',
        "Content-Type: image/jpeg",
        "",
    ]
    payload = ("\r\n".join(parts) + "\r\n").encode() + poster.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        asset["upload"]["url"], data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        response.read()
    return asset_id


def save_manifest(records: dict) -> None:
    temp = MANIFEST.with_suffix(".tmp")
    temp.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    temp.replace(MANIFEST)


def verify(path: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess_run([ffmpeg, "-hide_banner", "-v", "info", "-i", str(path), "-f", "null", "-"])
    if result.returncode != 0 or "error" in result.stderr.lower():
        raise RuntimeError("rendered clip failed the ffmpeg decode check")


def subprocess_run(command: list[str]):
    import subprocess
    return subprocess.run(command, capture_output=True, text=True)


def render(slug: str, clip: dict, records: dict) -> str:
    current = records.get(slug, {})
    if current.get("mode") == "i2v" and current.get("status") == "downloaded":
        return f"{slug}: already re-rendered"
    asset_id = upload_poster(slug)
    body = {
        "model_id": "ltx-2.3-distilled",
        "mode": "i2v",
        "prompt": clip["prompt"],
        "input_asset_id": asset_id,
        "duration_seconds": 5,
        "resolution": "512p",
        "seed": clip["seed"],
    }
    key = f"marketing-{slug}-i2v-" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    response = api("/v1/videos", body, {"Idempotency-Key": key}, "POST")
    job_id = response["job_id"]
    print(f"{slug}: submitted {job_id} (asset {asset_id})", flush=True)
    while True:
        status = api(f"/v1/videos/{job_id}")
        state = status["status"]
        if state in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(10)
    if state != "succeeded":
        raise RuntimeError(f"{state} ({status.get('error_code', 'unknown')})")
    output = api(f"/v1/videos/{job_id}/download")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    local = WORK_DIR / f"{slug}.mp4"
    with urllib.request.urlopen(output["video_url"], timeout=300) as response, local.open("wb") as file:
        while chunk := response.read(1024 * 1024):
            file.write(chunk)
    verify(local)
    (VIDEO_DIR / f"{slug}.mp4").write_bytes(local.read_bytes())
    with LOCK:
        records.setdefault(slug, {}).update({
            "model_id": "ltx-2.3-distilled",
            "mode": "i2v",
            "input_asset_id": asset_id,
            "prompt": clip["prompt"],
            "seed": clip["seed"],
            "job_id": job_id,
            "status": "downloaded",
            "file": f"/videos/{slug}.mp4",
            "bytes": (VIDEO_DIR / f"{slug}.mp4").stat().st_size,
            "estimated_gpu_cost_usd": (output.get("cost") or {}).get("estimated_gpu_cost_usd"),
            "note": "Re-rendered as LTX-2.3 image-to-video from the Gemini poster so the clip replicates the key art. Previous render in outputs/pre-ltx-i2v-backups/.",
        })
        save_manifest(records)
    return f"{slug}: downloaded {(VIDEO_DIR / f'{slug}.mp4').stat().st_size:,} bytes"


def main() -> None:
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(render, slug, clip, records): slug for slug, clip in CLIPS.items()}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                print(f"{futures[future]}: ERROR {exc}", flush=True)


if __name__ == "__main__":
    main()
