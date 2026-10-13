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
PRESETS = {"512p": (768, 512)}
# LTX's temporal grid is 8n+1 frames. These render approximately 5, 10,
# and 20 seconds at 24 fps. The final encoded duration includes the last frame.
DEFAULT_DURATION_SECONDS = 5
DURATION_FRAMES = {5: 121, 10: 241, 20: 481}
GPU_TYPE = "H200"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_ACTIVE_JOBS = 2


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value
