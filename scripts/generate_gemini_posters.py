"""Generate stylized marketing posters for the ten showcase clips with Gemini.

Two Gemini steps, as requested:

1. Idea: a Gemini text model turns each clip's video prompt into a poster
   composition brief (hero framing, palette, typography-free key art).
2. Image: a Gemini image model renders the poster as a 16:9 JPEG that matches
   the scene's art style, saved to ``frontend/public/videos/<slug>.jpg``.

Run from the repository root: ``.venv/Scripts/python scripts/generate_gemini_posters.py``.
Existing posters are replaced so all ten come from the same source.
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "marketing_videos.json"
DEST = ROOT / "frontend" / "public" / "videos"
API = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = "gemini-3.8-flash"
IMAGE_MODEL = "gemini-3.1-flash-image"


def api_key() -> str:
    key = dotenv_values(ROOT / ".env").get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")
    return key


def call(model: str, body: dict, key: str, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        f"{API}/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini {model} returned HTTP {exc.code}: {exc.read(300).decode(errors='replace')}") from exc


def poster_brief(clip: dict, key: str) -> str:
    """Step 1: Gemini designs the poster composition for one scene."""
    prompt = (
        "You are an art director for an animated-video studio landing page. "
        "Turn this video scene into a one-paragraph image-generation brief for a "
        "16:9 landscape key-art poster of the SAME scene, style, subject, and palette. "
        "Choose a striking hero composition (single clear focal subject, generous "
        "negative space, rich lighting) that reads well as a small thumbnail. "
        "No text, letters, logos, borders, or watermarks in the image. "
        f"Scene (from the video prompt): {clip['prompt']} "
        "Return only the brief text."
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    data = call(TEXT_MODEL, body, key)
    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini text model returned no brief")
    return text


def render_poster(brief: str, key: str) -> bytes:
    """Step 2: Gemini renders the poster image bytes."""
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
            data = call(IMAGE_MODEL, body, key)
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


def save_jpeg(raw: bytes, path: Path) -> int:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if image.width > 1280:
        image = image.resize((1280, round(image.height * 1280 / image.width)), Image.LANCZOS)
    image.save(path, "JPEG", quality=86, optimize=True)
    return path.stat().st_size


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    key = api_key()
    only = os.getenv("SLUG")
    for slug, clip in records.items():
        if only and slug != only:
            continue
        poster = DEST / f"{slug}.jpg"
        try:
            brief = poster_brief(clip, key)
            raw = render_poster(brief, key)
            size = save_jpeg(raw, poster)
            print(f"{slug}: poster {size:,} bytes :: {brief[:100]}...", flush=True)
        except Exception as exc:
            print(f"{slug}: ERROR {exc}", flush=True)
            continue
        time.sleep(1)


if __name__ == "__main__":
    main()
