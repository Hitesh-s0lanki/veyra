"""Deploy with: modal deploy modal_app.py"""

import os
import tempfile
import time
from pathlib import Path

import modal

from src.config import (
    CHECKPOINT, DURATION_FRAMES, FPS, GEMMA_REVISION, GEMMA_REPO, GEMMA_ROOT,
    GPU_TYPE, LTX_COMMIT, MODEL_REPO, MODEL_REVISION, MODEL_VERSION, PRESETS, UPSCALER,
)

app = modal.App("ltx-23-video")
secret = modal.Secret.from_name("video-pipeline")
models = modal.Volume.from_name("ltx-23-models", create_if_missing=True)

api_image = modal.Image.debian_slim(python_version="3.12").pip_install_from_requirements(
    "requirements.txt"
).add_local_python_source("src")

# Install the pinned official pipeline once in the image. The model weights live in a Volume.
gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg")
    .pip_install("uv==0.9.8")
    .run_commands(
        "git clone https://github.com/Lightricks/LTX-2.git /opt/LTX-2",
        f"cd /opt/LTX-2 && git checkout {LTX_COMMIT}",
    )
    .add_local_file("vendor/ltx-uv.lock", "/opt/LTX-2/uv.lock", copy=True)
    .run_commands("cd /opt/LTX-2 && uv sync --frozen --no-dev --package ltx-pipelines")
    .pip_install_from_requirements("requirements.txt")
    .env({
        "PYTHONPATH": "/opt/LTX-2/.venv/lib/python3.12/site-packages:/opt/LTX-2/packages/ltx-core/src:/opt/LTX-2/packages/ltx-pipelines/src",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    })
    .add_local_python_source("src")
)


@app.function(image=api_image, volumes={"/models": models}, secrets=[secret], timeout=3600)
def prepare_models():
    """Download pinned weights on CPU before deploying the GPU worker."""
    from huggingface_hub import hf_hub_download, snapshot_download

    # Fail before downloading the large LTX files if Gemma access is not granted.
    hf_hub_download(
        GEMMA_REPO, "config.json", revision=GEMMA_REVISION,
        local_dir=GEMMA_ROOT, token=os.getenv("HF_TOKEN") or None,
    )
    snapshot_download(
        MODEL_REPO, revision=MODEL_REVISION, local_dir="/models/ltx",
        allow_patterns=[Path(CHECKPOINT).name, Path(UPSCALER).name],
        token=os.getenv("HF_TOKEN") or None,
    )
    models.commit()
    snapshot_download(
        GEMMA_REPO, revision=GEMMA_REVISION, local_dir=GEMMA_ROOT,
        token=os.getenv("HF_TOKEN") or None,
    )
    models.commit()
    return {"checkpoint": Path(CHECKPOINT).exists(), "gemma": Path(GEMMA_ROOT).exists()}


@app.cls(
    image=gpu_image, gpu=GPU_TYPE, volumes={"/models": models}, secrets=[secret],
    min_containers=0, max_containers=1, scaledown_window=120,
    startup_timeout=1800, timeout=3600, retries=0, memory=65536,
)
class VideoWorker:
    @modal.enter()
    def load(self):
        if not Path(CHECKPOINT).is_file() or not Path(UPSCALER).is_file():
            raise RuntimeError("Model files missing; run prepare_models first")
        if not (Path(GEMMA_ROOT) / "config.json").is_file():
            raise RuntimeError("Gemma encoder missing; run prepare_models first")
        from ltx_pipelines.distilled import DistilledPipeline
        from ltx_pipelines.utils.model_paths import ModelPaths
        from ltx_pipelines.utils.types import OffloadMode
        self.pipeline = DistilledPipeline(
            model_paths=ModelPaths.from_monolith(CHECKPOINT, GEMMA_ROOT),
            spatial_upsampler_path=UPSCALER,
            loras=[],
            offload_mode=OffloadMode.CPU,
        )

    @modal.method()
    def generate(self, job_id: str):
        import torch
        from ltx_core.model.video_vae import get_video_chunks_number
        from ltx_pipelines.utils.media_io import encode_video
        from ltx_pipelines.utils.args import ImageConditioningInput
        from src import db, storage

        with db.connection() as conn:
            job = conn.execute("SELECT * FROM video_jobs WHERE id=%s", (job_id,)).fetchone()
            if not job or not db.set_status(conn, job_id, ("queued",), "running"):
                return {"status": "skipped"}
        started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                images = []
                if job["mode"] == "i2v":
                    with db.connection() as conn:
                        asset = conn.execute(
                            "SELECT object_key, content_type FROM video_assets WHERE id=%s AND user_id=%s",
                            (job["asset_id"], job["user_id"]),
                        ).fetchone()
                    if not asset:
                        raise ValueError("Missing source asset")
                    storage.validate_image(asset["object_key"])
                    source = str(Path(tmp) / ("input_image" + {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[asset["content_type"]]))
                    storage.client().download_file(storage.bucket(), asset["object_key"], source)
                    images = [ImageConditioningInput(path=source, frame_idx=0, strength=1.0)]
                width, height = PRESETS[job["resolution"]]
                num_frames = DURATION_FRAMES[job["duration_seconds"]]
                output = str(Path(tmp) / "output.mp4")
                # The pinned official CLI runs construction and inference in inference mode.
                with torch.inference_mode():
                    video, audio, frames, tiling = self.pipeline(
                        prompt=job["prompt"], seed=job["seed"], height=height,
                        width=width, frame_rate=FPS, images=images, num_frames=num_frames,
                    )
                    encode_video(
                        video=video, fps=FPS, audio=audio, output_path=output,
                        video_chunks_number=get_video_chunks_number(frames, tiling),
                    )
                if not Path(output).is_file() or Path(output).stat().st_size == 0:
                    raise RuntimeError("Video encoding produced no output")
                with db.connection() as conn:
                    current = conn.execute("SELECT status FROM video_jobs WHERE id=%s", (job_id,)).fetchone()
                if current["status"] == "cancelled":
                    return {"status": "cancelled"}
                key = storage.output_key(job["user_id"], job_id)
                storage.client().upload_file(
                    output, storage.bucket(), key,
                    ExtraArgs={"ContentType": "video/mp4", "ServerSideEncryption": "AES256"},
                )
                head = storage.client().head_object(Bucket=storage.bucket(), Key=key)
                if head["ContentLength"] != Path(output).stat().st_size:
                    raise RuntimeError("Video upload verification failed")
                with db.connection() as conn:
                    changed = db.set_status(
                        conn, job_id, ("running",), "succeeded", output_key=key,
                        model_version=MODEL_VERSION, gpu_model=torch.cuda.get_device_name(),
                        inference_seconds=time.monotonic() - started,
                    )
                if not changed:
                    storage.client().delete_object(Bucket=storage.bucket(), Key=key)
                    return {"status": "cancelled"}
                return {"status": "succeeded", "output_key": key}
        except Exception as exc:
            code = "out_of_memory" if isinstance(exc, torch.cuda.OutOfMemoryError) else "generation_failed"
            with db.connection() as conn:
                db.set_status(conn, job_id, ("running",), "failed", error_code=code)
            print(f"Video job {job_id} failed: {type(exc).__name__}")
            raise


@app.function(image=api_image, secrets=[secret], min_containers=0)
@modal.asgi_app()
def web():
    from src.api import api
    return api


@app.function(image=api_image, secrets=[secret], schedule=modal.Period(minutes=5))
def reconcile_jobs():
    """Repair DB state after dispatch crashes, GPU timeouts, or container termination."""
    from src import db

    with db.connection() as conn:
        jobs = conn.execute(
            """SELECT id, status, call_id FROM video_jobs
            WHERE status IN ('queued','running') AND updated_at < now() - interval '10 minutes'
            ORDER BY updated_at LIMIT 100"""
        ).fetchall()
    repaired = 0
    for job in jobs:
        if not job["call_id"]:
            if job["status"] == "queued":
                with db.connection() as conn:
                    repaired += db.set_status(conn, job["id"], ("queued",), "failed", error_code="dispatch_lost")
            continue
        try:
            modal.FunctionCall.from_id(job["call_id"]).get(timeout=0)
        except TimeoutError:
            continue
        except Exception:
            # An execution exception or expired call result must not leave a job active.
            pass
        with db.connection() as conn:
            repaired += db.set_status(
                conn, job["id"], ("queued", "running"), "failed", error_code="worker_lost"
            )
    return {"checked": len(jobs), "repaired": repaired}
