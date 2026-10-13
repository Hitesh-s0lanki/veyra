"""Render the ten marketing clips through the local authenticated video API.

Run from the repository root. Safe to restart: every prompt has a stable
idempotency key and completed downloads are skipped.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "frontend" / "public" / "videos"
MANIFEST = ROOT / "reports" / "marketing_videos.json"
BASE_URL = os.getenv("VIDEO_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LOCK = Lock()

CLIPS = [
    {"slug": "paper-city", "title": "Paper City", "model_id": "ltx-2.3-distilled", "seed": 62011,
     "prompt": "A tiny handcrafted paper city sits on a cream tabletop, with layered coral and cobalt buildings around a central square. A little paper tram glides from left to right and warm windows light up one by one. The camera slowly pushes toward the square; crisp cut-paper edges, soft studio shadows, playful stop-motion animation."},
    {"slug": "clay-astronaut", "title": "Clay Astronaut", "model_id": "wan-2.2", "seed": 62012,
     "prompt": "A small clay astronaut in an orange suit stands on a pastel lavender moon beside a miniature flag. The astronaut takes two buoyant steps and waves at a passing ringed planet. Gentle camera dolly in, tactile fingerprints in the clay, bright softbox lighting, charming stop-motion animation."},
    {"slug": "watercolor-koi", "title": "Watercolor Koi", "model_id": "hunyuanvideo-1.5", "seed": 62013,
     "prompt": "Two vivid orange koi swim in a circular path through a pale blue watercolor pond. Pigment blooms and soft ink ripples follow their tails while lily leaves drift at the edge of frame. Overhead camera glides gently clockwise, textured paper, flowing hand-painted animation."},
    {"slug": "robot-garden", "title": "Robot Garden", "model_id": "cogvideox-1.5", "seed": 62014,
     "prompt": "A friendly rounded mint-green robot waters one sprout in a colorful miniature rooftop garden. The sprout unfurls into a bright sunflower and the robot tilts its head with delight. Slow camera push in, polished 3D animated film look, warm sunrise light and soft shadows."},
    {"slug": "balloon-voyage", "title": "Balloon Voyage", "model_id": "wan-2.2", "seed": 62015,
     "prompt": "A red paper hot-air balloon floats above layered turquoise mountains and fluffy cream clouds. Foreground clouds drift aside as the balloon rises smoothly toward a golden sunrise. Slow sideways camera pan, intricate cut-paper textures, gentle parallax, whimsical storybook animation."},
    {"slug": "pixel-train", "title": "Pixel Train", "model_id": "ltx-2.3-distilled", "seed": 62016,
     "prompt": "A tiny teal pixel-art train rolls across a bridge over a luminous purple river at twilight. Its windows glow as it travels left to right; stars blink above blocky pine trees. The camera tracks smoothly alongside the train, crisp pixel edges, layered parallax and colorful retro game animation."},
    {"slug": "ink-fox", "title": "Ink Fox", "model_id": "hunyuanvideo-1.5", "seed": 62017,
     "prompt": "A curious little fox painted in orange ink bounds through a quiet forest of indigo brushstrokes. It pauses beside a glowing firefly, then lifts its nose as the insect rises. Gentle tracking camera, visible rice-paper grain, expressive hand-drawn animation, moonlit blue and amber palette."},
    {"slug": "knitted-whale", "title": "Knitted Whale", "model_id": "cogvideox-1.5", "seed": 62018,
     "prompt": "A small blue knitted whale swims through a sea made of soft yarn waves beneath felt clouds. It arcs upward and releases a puff of cotton spray as the waves roll beneath it. Smooth side-on tracking camera, detailed stitches, cozy tactile stop-motion animation, cheerful pastel colors."},
    {"slug": "isometric-market", "title": "Isometric Market", "model_id": "wan-2.2", "seed": 62019,
     "prompt": "An isometric miniature night market glows with peach and cyan lanterns. A tiny delivery bicycle travels down the center lane while awnings sway softly and shop lights turn on in sequence. Camera cranes slowly upward, detailed stylized 3D animation, clean geometry, lively but readable motion."},
    {"slug": "glass-butterfly", "title": "Glass Butterfly", "model_id": "ltx-2.3-distilled", "seed": 62020,
     "prompt": "A translucent stained-glass butterfly rests on a dark blue flower in a dreamy illustrated garden. Its amber and turquoise wings open, then it lifts off and crosses a shaft of golden light. The camera follows with a gentle upward tilt; luminous glass facets, soft painterly background, elegant animated motion."},
]


def token() -> str:
    config = dotenv_values(ROOT / ".env")
    tokens = json.loads(config["API_TOKENS_JSON"] or "{}")
    if not tokens:
        raise RuntimeError("API_TOKENS_JSON has no configured token")
    return next(iter(tokens))


def api(path: str, bearer: str, data: dict | None = None, key: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {bearer}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API {path} returned HTTP {exc.code}: {exc.read(300).decode(errors='replace')}") from exc


def save_manifest(records: dict) -> None:
    temp = MANIFEST.with_suffix(".tmp")
    temp.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    temp.replace(MANIFEST)


def update(records: dict, slug: str, **fields: object) -> None:
    with LOCK:
        records.setdefault(slug, {}).update(fields)
        save_manifest(records)


def render(clip: dict, records: dict, bearer: str) -> str:
    slug = clip["slug"]
    destination = DEST / f"{slug}.mp4"
    if destination.exists() and destination.stat().st_size > 100_000:
        return f"{slug}: already downloaded"
    request_body = {
        "model_id": clip["model_id"], "mode": "t2v", "prompt": clip["prompt"],
        "duration_seconds": 5,
        "resolution": {"ltx-2.3-distilled": "512p", "wan-2.2": "720p",
                       "hunyuanvideo-1.5": "480p", "cogvideox-1.5": "480p"}[clip["model_id"]],
        "seed": clip["seed"],
    }
    digest = hashlib.sha256(json.dumps(request_body, sort_keys=True).encode()).hexdigest()[:24]
    current = records.get(slug, {})
    job_id = current.get("job_id")
    if not job_id:
        response = api("/v1/videos", bearer, request_body, f"marketing-{slug}-{digest}")
        job_id = response["job_id"]
        update(records, slug, title=clip["title"], model_id=clip["model_id"],
               prompt=clip["prompt"], seed=clip["seed"], job_id=job_id, status=response["status"])
        print(f"{slug}: submitted {job_id}", flush=True)
    while True:
        status = api(f"/v1/videos/{job_id}", bearer)
        state = status["status"]
        update(records, slug, status=state)
        if state in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(10)
    if state != "succeeded":
        update(records, slug, error_code=status.get("error_code"))
        return f"{slug}: {state} ({status.get('error_code', 'unknown')})"
    output = api(f"/v1/videos/{job_id}/download", bearer)
    signed_url = output["video_url"]
    temp = destination.with_suffix(".mp4.part")
    with urllib.request.urlopen(signed_url, timeout=180) as response, temp.open("wb") as file:
        while chunk := response.read(1024 * 1024):
            file.write(chunk)
    if temp.stat().st_size < 100_000:
        raise RuntimeError(f"{slug}: downloaded file is unexpectedly small")
    temp.replace(destination)
    update(records, slug, status="downloaded", file=f"/videos/{slug}.mp4",
           bytes=destination.stat().st_size,
           estimated_gpu_cost_usd=(output.get("cost") or {}).get("estimated_gpu_cost_usd"))
    return f"{slug}: downloaded {destination.stat().st_size:,} bytes"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    bearer = token()
    health = urllib.request.urlopen(BASE_URL + "/health", timeout=10)
    if health.status != 200:
        raise RuntimeError("API health check failed")
    models = api("/v1/models", bearer)["models"]
    if not {clip["model_id"] for clip in CLIPS} <= {model["model_id"] for model in models}:
        raise RuntimeError("The live API is missing a requested model")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(render, clip, records, bearer): clip["slug"] for clip in CLIPS}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                print(f"{futures[future]}: ERROR {exc}", flush=True)


if __name__ == "__main__":
    main()
