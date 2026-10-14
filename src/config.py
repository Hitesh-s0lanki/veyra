"""Shared generation settings for the API and Modal worker."""

import os

MODEL_REPO = "Lightricks/LTX-2.3"
MODEL_REVISION = "3c6a4e66e5d0a684231950b9c74dd4ded7b6fadc"
GEMMA_REPO = "google/gemma-3-12b-it-qat-q4_0-unquantized"
GEMMA_REVISION = "68f7ee4fbd59087436ada77ed2d62f373fdd4482"
LTX_COMMIT = "d151147788a9284cca791edc6ce898007e727fe6"  # v1.2.0
MODEL_VERSION = "ltx-2.3-22b-distilled-1.1/cpu-offload"
MODEL_ROOT = "/models"
CHECKPOINT = f"{MODEL_ROOT}/ltx/ltx-2.3-22b-distilled-1.1.safetensors"
UPSCALER = f"{MODEL_ROOT}/ltx/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"
GEMMA_ROOT = f"{MODEL_ROOT}/gemma"
FPS = 24
PRESETS = {
    "512p": (768, 512), "512p-portrait": (512, 768),
    "720p": (1280, 704), "720p-portrait": (704, 1280),
}
# Text-to-video uses the preset directly. Image-to-video follows the
# conditioning image's aspect at that preset's pixel class via I2V_DIMS
# (see modal_app.py), so inputs are never stretched.
I2V_DIMS = {
    "512p": {"landscape": (896, 512), "portrait": (512, 896), "square": (640, 640)},
    "720p": {"landscape": (1280, 704), "portrait": (704, 1280), "square": (896, 896)},
}
# LTX's temporal grid is 8n+1 frames. These render approximately 5, 10,
# and 20 seconds at 24 fps. The final encoded duration includes the last frame.
DEFAULT_DURATION_SECONDS = 5
DURATION_FRAMES = {5: 121, 10: 241, 20: 481}
GPU_TYPE = "H200"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_ACTIVE_JOBS = 2
VIDEO_URL_TTL_SECONDS = 3600
VERIFICATION_MODAL_APP_NAME = "video-pipeline-verification"

# Snapshot of this workspace's `modal billing rates --json` on 2026-10-13.
# These rates support a GPU-runtime estimate, not an exact per-job invoice.
GPU_HOURLY_RATES_USD = {"H100": "3.95", "H200": "4.54"}

# The API dispatches to independently deployed Modal model apps. Keep this
# registry aligned with the workers' deployment_identity functions and verified
# successful jobs before widening a model's accepted settings.
DEFAULT_MODEL_ID = "ltx-2.3-distilled"
MODEL_PROFILES = {
    "ltx-2.3-distilled": {
        "app": "video-pipeline-ltx-23",
        "modes": ("t2v", "i2v"),
        "durations": (5, 10, 20),
        "resolutions": ("512p", "512p-portrait", "720p", "720p-portrait"),
        "defaults": {},
    },
    "wan-2.2": {
        "app": "video-pipeline-wan-22",
        "modes": ("t2v",),
        "durations": (5,),
        "resolutions": ("720p", "720p-portrait"),
        "defaults": {"inference_steps": 10, "guidance_scale": 5.0},
    },
    "hunyuanvideo-1.5": {
        "app": "video-pipeline-hunyuanvideo-15",
        "modes": ("t2v",),
        "durations": (5,),
        "resolutions": ("480p", "480p-portrait"),
        "defaults": {"inference_steps": 10, "guidance_scale": 6.0},
    },
    "cogvideox-1.5": {
        "app": "video-pipeline-cogvideox-15",
        "modes": ("t2v",),
        "durations": (5,),
        "resolutions": ("480p", "480p-portrait"),
        "defaults": {"inference_steps": 10, "guidance_scale": 6.0},
    },
}

# Retail prices in USD cents. These are fixed user charges, distinct from the
# historical Modal GPU-runtime estimates returned on completed jobs.
VIDEO_BASE_PRICES_CENTS = {
    "ltx-2.3-distilled": {5: 45, 10: 60, 20: 90},
    "wan-2.2": {5: 65},
    "hunyuanvideo-1.5": {5: 55},
    "cogvideox-1.5": {5: 55},
}
CREATIVE_PRICES_CENTS = {"prompt": 2, "image": 20}
STARTER_CREDIT_CENTS = 500
PRICING_VERSION = "2026-10-13.1"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value
