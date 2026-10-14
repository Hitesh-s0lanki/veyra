# Video generation API: guide for agents

Read this before calling the project API. The FastAPI service dispatches a job to one of four independently deployed Modal GPU workers. A `POST /v1/videos` request starts billable generation. Do not submit a job unless the user asked for a video. Use `.agent/skills/video-prompting/SKILL.md` and its LTX-2.3 reference when drafting an LTX prompt; use `.agent/skills/ltx-video-generation/SKILL.md` for LTX clip generation and download. `src/config.py` is the source of truth for accepted API settings.

Agents using MCP can use the local FastMCP tools instead of building HTTP requests. See [MCP server setup and tool workflow](MCP_SERVER.md). The same model limits, ownership, billing, and one-hour URL rules apply.

## Connection and authorization

- Use the API base URL supplied by the user's deployment. For a running local API, this is usually `http://127.0.0.1:8000`. The main API need not be deployed on Modal; do not assume an old Modal web URL is live.
- Check `GET /health` first. HTTP 200 `{"status":"ok"}` confirms the API process, not GPU readiness.
- Every `/v1` route, including `GET /v1/models`, requires `Authorization: Bearer <token>`. The API accepts configured static tokens or verified Clerk OAuth access tokens. The mapped static user or Clerk subject owns the assets and jobs. Never put tokens or signed S3 URLs in chat, logs, or source control. See [OAuth account connection](AUTH.md).
- JSON requests use `Content-Type: application/json`. Store the base URL and bearer token in private environment variables such as `BASE_URL` and `VIDEO_API_TOKEN`.

## Models and request fields

Query `GET /v1/models` for the accepted combinations. As of 13 October 2026:

| `model_id` | Modes | `duration_seconds` | `resolution` | Default `parameters` |
| --- | --- | --- | --- | --- |
| `ltx-2.3-distilled` | `t2v`, `i2v` | 5, 10, 20 | `512p`, `512p-portrait`, `720p`, `720p-portrait` | `{}` |
| `wan-2.2` | `t2v` | 5 | `720p`, `720p-portrait` | `{"inference_steps":10,"guidance_scale":5.0}` |
| `hunyuanvideo-1.5` | `t2v` | 5 | `480p`, `480p-portrait` | `{"inference_steps":10,"guidance_scale":6.0}` |
| `cogvideox-1.5` | `t2v` | 5 | `480p`, `480p-portrait` | `{"inference_steps":10,"guidance_scale":6.0}` |

The landscape combinations have successful worker jobs. Portrait presets are configured in source and require redeployment and a live render before relying on the hosted API. Do not infer support for another mode, duration, or resolution from the model's general capabilities. `model_id` defaults to LTX for old clients, `duration_seconds` defaults to 5, and omitted `resolution` uses the selected model's enabled preset. `prompt` is a nonblank string of at most 2,000 characters. `seed` is an optional integer from 0 to 4294967295. For Wan, HunyuanVideo, and CogVideoX, optional `parameters.inference_steps` must be an integer from 1 to 100 and `parameters.guidance_scale` a number from 0 to 20. Omitted parameter values use the table defaults. LTX accepts an empty `parameters` object only. Unknown model IDs, parameters, and unsupported combinations return HTTP 422.

For `i2v`, supply `input_asset_id` from this API's asset upload flow and use a base resolution. For `t2v`, omit the asset and choose a base resolution for landscape or a `-portrait` resolution for portrait. LTX text-to-video renders at 768×512 or 512×768 for `512p`, and 1280×704 or 704×1280 for `720p`, at 24 fps. LTX image-to-video follows the conditioning image's aspect at the base preset's pixel class (`512p`: 832×480 landscape, 480×832 portrait, 640×640 square; `720p`: 1280×704 landscape, 704×1280 portrait, 896×896 square) so inputs are not stretched. Its 5, 10, and 20 second requests use 121, 241, and 481 frames. Do not assume these frame counts apply to the other workers.

## Text-to-video

1. Draft one coherent prompt for the selected clip length.
2. Submit `POST /v1/videos` with a fresh `Idempotency-Key` for this complete normalized request. Reuse that key only when retrying the same request for the same user. Changing the request with the same key returns HTTP 409.
3. Save `job_id` and poll `GET /v1/videos/{job_id}` every few seconds until the status is `succeeded`, `failed`, or `cancelled`.
4. On success, the status response contains `output.video_key`, `output.video_url`, `output.expires_at`, and an estimated GPU cost. The signed URL is valid for one hour. Call `GET /v1/videos/{job_id}/download` to renew it when needed. Do not expose the URL beyond the intended recipient.

Example for Wan:

```http
POST /v1/videos
Authorization: Bearer <token>
Idempotency-Key: wan-lake-001
Content-Type: application/json

{"model_id":"wan-2.2","mode":"t2v","prompt":"A slow camera move over a lake as morning mist drifts above the water.","duration_seconds":5,"resolution":"720p","parameters":{"inference_steps":10,"guidance_scale":5.0},"seed":42}
```

For the other models, change `model_id` and use the corresponding preset from the table. The initial HTTP 202 response contains `job_id`, `model_id`, `status: queued`, and `status_url`. Status responses also contain `progress: null`; there is no reliable percentage. A successful status adds `download_url`, `output`, and `cost`. `cost.estimated_gpu_cost_usd` is a six-decimal USD string or `null`; it is an estimate for worker GPU runtime, not exact billed spend. A failure adds a sanitized `error_code` such as `dispatch_failed`, `generation_failed`, `out_of_memory`, `dispatch_lost`, or `worker_lost`. Do not blindly submit a new job after failure because that can incur another GPU charge.

## LTX image-to-video

1. Prepare a JPEG, PNG, or WebP image of at most 10 MB, at least 256×256 pixels, and no more than 16 million pixels.
2. Call `POST /v1/assets` with `{"content_type":"image/png"}` or the matching JPEG/WebP MIME type. The response contains `asset_id` and `upload`.
3. Send a multipart form POST directly to `upload.url`. Include **every** key/value in `upload.fields` and the image as the `file` field. This S3 upload does not use the API bearer header. The presigned form expires after 15 minutes.
4. Submit the LTX request with the returned asset ID:

```json
{"model_id":"ltx-2.3-distilled","mode":"i2v","prompt":"The camera moves slowly toward the lake as ripples spread outward.","input_asset_id":"asset_...","duration_seconds":10,"resolution":"512p"}
```

The asset must belong to the same bearer-token user. The API validates the stored image before starting the job. An arbitrary image URL cannot replace `input_asset_id`.

## Status, cancellation, and limits

- `GET /v1/videos/{job_id}` returns the owner-scoped job status and `model_id`. Status is `queued`, `running`, `succeeded`, `failed`, or `cancelled`.
- `GET /v1/videos/{job_id}/download` returns `video_key`, `video_url`, `expires_in: 3600`, `expires_at`, file metadata, and `cost` after success. It returns HTTP 409 before the video is ready.
- `POST /v1/videos/url` with `{"video_key":"..."}` returns the same fields after an owner-scoped lookup. It returns HTTP 404 for a missing or another user's key. The key cannot sign arbitrary objects.
- `POST /v1/videos/{job_id}/cancel` requests best-effort cancellation. Cancellation can race with completion; check the final status.
- HTTP 401 means missing/invalid bearer token; 404 means a job or asset is not found for this user; 422 means invalid settings or image; 429 means the user already has two active jobs; 503 means Modal dispatch failed.

The API handles one clip per request. It does not merge clips, rewrite prompts, expose percentage progress, or automatically retry failed jobs. The worker runs on demand and may take time to start. Storage retention and wider rate limiting belong in the deployment infrastructure.

## Source of truth

- `src/config.py`: model IDs, Modal app names, accepted profiles, and shared limits.
- `src/api.py`: authorization, validation, job creation, and Modal dispatch.
- `src/db.py`: job state and schema migration.
- `src/storage.py`: private S3 upload, download, and image validation.
- `README.md`: startup and deployment context.
- `docs/PUBLIC_API.md`: client-facing request and response contract.
