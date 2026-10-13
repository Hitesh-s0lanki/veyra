"""Add five landscape 720p showcase clips: Gemini idea + poster, LTX i2v render.

Pipeline per scene, matching the established showcase workflow:

1. Idea: ``gemini-3.8-flash`` turns the scene's motion prompt into a key-art
   poster brief (16:9, thumbnail-readable, no text).
2. Image: ``gemini-3.1-flash-image`` renders the poster to
   ``frontend/public/videos/<slug>.jpg``.
3. Video: the poster is uploaded through the asset flow and animated with an
   LTX-2.3 i2v job at ``resolution: "720p"`` (1280x704 landscape on the
   redeployed aspect-following worker). One action beat plus one camera move.

Resumable: scenes whose manifest entry already says ``status: downloaded`` are
skipped. Run from the repository root.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from dotenv import dotenv_values
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = "gemini-3.8-flash"
IMAGE_MODEL = "gemini-3.1-flash-image"
VIDEO_DIR = ROOT / "frontend" / "public" / "videos"
WORK_DIR = ROOT / "outputs" / "landscape-720p-renders"
MANIFEST = ROOT / "reports" / "marketing_videos.json"
LOCK = Lock()

SCENES = {
    "origami-dragon": {
        "title": "Origami Dragon",
        "style": "Folded paper",
        "seed": 62041,
        "prompt": "A creased origami dragon unfolds its wings from a folded mountain peak, then breathes a ribbon of glittering golden paper flames across the sky. The camera cranes slowly upward over the papercraft valley.",
    },
    "neon-jellyfish": {
        "title": "Neon Jellyfish",
        "style": "Bioluminescent 3D",
        "seed": 62042,
        "prompt": "A translucent neon jellyfish pulses gracefully upward through deep blue water, its trailing tentacles sparking soft pink and cyan light while tiny plankton drift around it. The camera rises with it through the glow.",
    },
    "chalk-village": {
        "title": "Chalk Village",
        "style": "Chalk pastel",
        "seed": 62043,
        "prompt": "In a chalk-drawn village square, bunting flutters and a chalk sun spins in the sky while tiny chalk figures dance around a maypole. The camera dollies sideways along the cobblestone street.",
    },
    "felt-campfire": {
        "title": "Felt Campfire",
        "style": "Needle-felt",
        "seed": 62044,
        "prompt": "A fuzzy felt fox and a hedgehog sit at a glowing campfire in a mossy forest clearing as warm embers float upward, and the fox lifts a toasted marshmallow stick. The camera pushes in gently through the trees.",
    },
    "toy-carousel": {
        "title": "Toy Carousel",
        "style": "Wooden toy",
        "seed": 62045,
        "prompt": "A hand-painted wooden carousel spins up to speed in a cozy toy shop window, its carved horses bobbing up and down as warm bulbs glow around the canopy. The camera orbits slowly around it.",
    },
}


def gemini_key() -> str:
    key = dotenv_values(ROOT / ".env").get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")
    return key


def gemini_call(model: str, body: dict, key: str) -> dict:
    request = urllib.request.Request(
        f"{GEMINI}/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini {model} returned HTTP {exc.code}: {exc.read(300).decode(errors='replace')}") from exc


def poster_brief(scene: dict, key: str) -> str:
    prompt = (
        "You are an art director for an animated-video studio landing page. "
        "Turn this video scene into a one-paragraph image-generation brief for a "
        "16:9 landscape key-art poster of the SAME scene, style, subject, and palette. "
        "Choose a striking hero composition (single clear focal subject, generous "
        "negative space, rich lighting) that reads well as a small thumbnail. "
        "No text, letters, logos, borders, or watermarks in the image. "
        f"Scene: {scene['prompt']} "
        "Return only the brief text."
    )
    data = gemini_call(TEXT_MODEL, {"contents": [{"parts": [{"text": prompt}]}]}, key)
    text = "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"]).strip()
    if not text:
        raise RuntimeError("Gemini text model returned no brief")
    return text


def render_poster(brief: str, key: str) -> bytes:
    prompt = (
        f"{brief} Style match is critical: this is key art for an animated short. "
        "Vibrant, high-quality illustration, clean edges, cinematic lighting, "
        "landscape 16:9 composition, absolutely no text or watermarks."
    )
    attempts = [
        {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": "16:9"}},
        {"responseModalities": ["TEXT", "IMAGE"]},
        {},
    ]
    last_error = ""
    for config in attempts:
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}
        try:
            data = gemini_call(IMAGE_MODEL, body, key)
        except RuntimeError as exc:
            last_error = str(exc)
            continue
        images = [
            part["inlineData"]["data"]
            for part in data["candidates"][0].get("content", {}).get("parts", [])
            if "inlineData" in part and part["inlineData"].get("data")
        ]
        if images:
            return base64.b64decode(max(images, key=len))
        last_error = "response contained no image part"
    raise RuntimeError(last_error)


def save_poster(raw: bytes, path: Path) -> None:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if image.width > 1280:
        image = image.resize((1280, round(image.height * 1280 / image.width)), Image.LANCZOS)
    image.save(path, "JPEG", quality=86, optimize=True)


def bearer() -> str:
    tokens = json.loads(dotenv_values(ROOT / ".env")["API_TOKENS_JSON"])
    token = next((t for t, user in tokens.items() if user == "marketing_agent"), None)
    if not token:
        raise RuntimeError("marketing_agent token missing from API_TOKENS_JSON")
    return token


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
    return asset["asset_id"]


def verify(path: Path) -> None:
    import re
    import subprocess

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "info", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or "error" in result.stderr.lower():
        raise RuntimeError("rendered clip failed the ffmpeg decode check")
    match = re.search(r"Video: .*?, (\d{3,4}x\d{3,4})", result.stderr)
    print(f"  decoded {match.group(1) if match else '?'}", flush=True)


def render(slug: str, scene: dict, records: dict, key: str) -> None:
    current = records.get(slug, {})
    if current.get("status") == "downloaded":
        print(f"{slug}: already done", flush=True)
        return
    brief = poster_brief(scene, key)
    raw = render_poster(brief, key)
    save_poster(raw, VIDEO_DIR / f"{slug}.jpg")
    print(f"{slug}: poster saved", flush=True)

    asset_id = upload_poster(slug)
    body = {
        "model_id": "ltx-2.3-distilled",
        "mode": "i2v",
        "prompt": scene["prompt"],
        "input_asset_id": asset_id,
        "duration_seconds": 5,
        "resolution": "720p",
        "seed": scene["seed"],
    }
    request_key = f"marketing-{slug}-i2v720-" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    response = api("/v1/videos", body, {"Idempotency-Key": request_key}, "POST")
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
        records[slug] = {
            "title": scene["title"],
            "model_id": "ltx-2.3-distilled",
            "mode": "i2v",
            "input_asset_id": asset_id,
            "prompt": scene["prompt"],
            "seed": scene["seed"],
            "resolution": "720p",
            "job_id": job_id,
            "status": "downloaded",
            "file": f"/videos/{slug}.mp4",
            "bytes": (VIDEO_DIR / f"{slug}.mp4").stat().st_size,
            "estimated_gpu_cost_usd": (output.get("cost") or {}).get("estimated_gpu_cost_usd"),
            "note": "Landscape 720p LTX-2.3 image-to-video clip animated from its Gemini poster.",
        }
        temp = MANIFEST.with_suffix(".tmp")
        temp.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        temp.replace(MANIFEST)
    print(f"{slug}: downloaded {(VIDEO_DIR / f'{slug}.mp4').stat().st_size:,} bytes", flush=True)


def main() -> None:
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    key = gemini_key()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(render, slug, scene, records, key): slug for slug, scene in SCENES.items()}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"{slug}: ERROR {exc}", flush=True)


if __name__ == "__main__":
    main()
