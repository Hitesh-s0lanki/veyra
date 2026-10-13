# LTX-2.3 video API on Modal

This repository implements the [deployment design](docs/LTX-2.3_Modal_On_Demand_Deployment_Design.docx): a CPU FastAPI web endpoint, an on-demand H200 GPU worker, PostgreSQL job state, and private S3 input/output objects. It uses the official LTX-2.3 distilled checkpoint and pipeline with CPU weight offload. The selected pipeline requires dimensions divisible by 64, so a literal 1280×720 setting is not exposed.

The Modal app is `ltx-23-video`. The web endpoint exposes `POST /v1/assets`, `POST /v1/videos`, `GET /v1/videos/{job_id}`, `GET /v1/videos/{job_id}/download`, and `POST /v1/videos/{job_id}/cancel`. All `/v1` routes require `Authorization: Bearer <token>`. The API token maps to a stable user ID; object keys and jobs are scoped to that ID. The public web function allocates CPU only; the worker allocates an H200 when called.

## Generation settings

Both `t2v` (text prompt) and `i2v` (uploaded image plus text prompt) accept the following single-clip durations at `512p` (768×512), 24 fps:

| Requested duration | Frames | Encoded duration |
| --- | ---: | ---: |
| 5 seconds | 121 | About 5.04 seconds |
| 10 seconds | 241 | About 10.04 seconds |
| 20 seconds | 481 | About 20.04 seconds |

The exact frame counts are configured in `src/config.py`. A 30-second single generation is outside [LTX-2.3's published duration range](https://ltx.io/model/ltx-2-3) and is rejected by this API. Longer finished videos require generating and combining shorter clips. Longer runs use more GPU memory and time. The 5-second T2V, 10-second I2V, and 20-second T2V settings have been verified end to end; other mode/duration combinations are accepted by the API but have not each been rendered in a live test.

## Prerequisites

- Modal account and `modal setup` completed.
- PostgreSQL database reachable from Modal, with permission to create the two tables on first API startup.
- Private S3 bucket and an IAM credential able to read/write only this bucket. Configure lifecycle expiration for `uploads/` and `videos/` according to your retention policy.
- Hugging Face account granted access to [Gemma 3](https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-unquantized), with a read token in the Modal secret. Review the [LTX-2.3 model terms](https://huggingface.co/Lightricks/LTX-2.3) and Gemma terms before using them.
- Budget for downloading and caching large checkpoints and for H200 GPU inference. The longer duration settings have not been benchmarked by this repository.

Copy `.env.example` values into a private file and create a Modal Secret named `video-pipeline` with those environment variables. Keep your local `.env` out of git. The bucket must remain private. `API_TOKENS_JSON` maps each long, random bearer token to a user ID consisting of letters, digits, `_` or `-`.

```bash
uv sync --extra test
uvx --from modal==1.6.1 --with python-dotenv modal secret create video-pipeline --from-dotenv .env
modal run modal_app.py::prepare_models
modal deploy modal_app.py
```

If you change `.env` after creating the Secret, rerun that Secret command with `--force` before testing. Gemma access requires accepting the model terms using the account associated with `HF_TOKEN`; viewing its model page alone does not verify download permission.

`prepare_models` downloads the exact LTX-2.3 checkpoint, matching spatial upscaler, and Gemma 3 encoder into a persistent Modal Volume. It should return `checkpoint: true` and `gemma: true`. The pinned upstream source is commit `d151147788a9284cca791edc6ce898007e727fe6` (v1.2.0); its resolved package lock is `vendor/ltx-uv.lock`. Model repository revisions are pinned in `src/config.py`.

The `modal deploy` output contains the web URL. Replace `$BASE_URL` below with it:

```bash
curl -X POST "$BASE_URL/v1/videos" \
  -H "Authorization: Bearer $VIDEO_API_TOKEN" \
  -H "Idempotency-Key: my-first-video-1" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"t2v","prompt":"A slow dolly toward a mountain at sunrise","duration_seconds":5,"resolution":"512p","seed":42}'

curl "$BASE_URL/v1/videos/$JOB_ID" -H "Authorization: Bearer $VIDEO_API_TOKEN"
curl "$BASE_URL/v1/videos/$JOB_ID/download" -H "Authorization: Bearer $VIDEO_API_TOKEN"
```

For image-to-video, call `POST /v1/assets` with `{"content_type":"image/png"}`. Upload the image to the returned presigned POST `url` with every returned `fields` entry and the file form field. Then submit `mode: "i2v"` with `input_asset_id` and a prompt, for example `{"mode":"i2v","prompt":"The camera slowly moves toward the lake","input_asset_id":"asset_...","duration_seconds":10,"resolution":"512p"}`. The API verifies the private object's size, format, and dimensions before spawning a GPU call. It does not accept arbitrary image URLs. S3 presigned POST is used so S3 enforces a 10 MB upload limit; input must be JPEG, PNG, or WebP, at least 256×256 and at most 16 million pixels.

The API returns HTTP 202 and a job ID immediately. Poll the status route; when `succeeded`, call the download route for a 15-minute private URL. State is `queued`, `running`, `succeeded`, `failed`, or `cancelled`. `progress` remains null because the pipeline does not expose a reliable percentage. Failure responses expose a sanitized error code. Cancellation is best effort.

## Verification and operating limits

```bash
uv run --extra test python -m pytest -q
uv run python -m compileall -q src modal_app.py
```

The local checks verify validation, authentication, image safety, and API routing. Live smoke tests on 10 October 2026 generated privately stored 768×512 H.264/AAC MP4s and verified downloads through the signed URL endpoint: 5-second T2V (`vid_5418787b72134dfb85619f26ed86a633`, H100, 5.04 seconds, 169.86 seconds of worker execution), 10-second I2V (`vid_2c5d75e0be2842069387246755d737fd`, H200, 10.04 seconds, 142.73 seconds of worker execution), and 20-second T2V (`vid_19b12df19ca342168c703449eea0d3ae`, H200, 20.04 seconds, 110.90 seconds of worker execution). These individual runs are not latency or cost benchmarks; broader reliability cases remain to be verified. The worker currently performs one attempt per job. A scheduled Modal reconciliation function checks stale queued/running jobs every five minutes and marks failed executions with a sanitized code. Per-user active job count is capped at two. Rate limiting beyond that cap and automatic retention cleanup belong in the ingress/storage infrastructure.

The measured runtime estimates and observed Modal billing for the Dream Gold product video are recorded in [the video generation cost report](reports/video_generation_costs_2026-10-10.md).
