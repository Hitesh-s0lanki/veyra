# Video Generation API

Use the base URL supplied by the API operator. Send `Authorization: Bearer <your-token>` on every `/v1` request and `Content-Type: application/json` for JSON bodies. The token can be an operator-issued static token or a Clerk OAuth access token obtained by the frontend's authorization-code flow with PKCE. Keep your token and video URLs private. See [OAuth account connection](AUTH.md).

## 1. Choose a model

`GET /v1/models` lists accepted modes, durations, resolutions, and default parameters. Currently available:

| `model_id` | Modes | Seconds | Resolution | Optional `parameters` defaults |
| --- | --- | --- | --- | --- |
| `ltx-2.3-distilled` | `t2v`, `i2v` | 5, 10, 20 | `512p` | `{}` |
| `wan-2.2` | `t2v` | 5 | `720p` | `{"inference_steps":10,"guidance_scale":5.0}` |
| `hunyuanvideo-1.5` | `t2v` | 5 | `480p` | `{"inference_steps":10,"guidance_scale":6.0}` |
| `cogvideox-1.5` | `t2v` | 5 | `480p` | `{"inference_steps":10,"guidance_scale":6.0}` |

`model_id` defaults to LTX, `duration_seconds` defaults to 5, and `resolution` defaults to the selected model's listed preset. `prompt` must contain 1–2000 nonblank characters. `seed` is optional, from 0 to 4294967295. For the other three models, `inference_steps` is an integer from 1 to 100 and `guidance_scale` is a number from 0 to 20. Only the listed modes, lengths, and resolutions are currently enabled.

## 2. Submit a video

```http
POST /v1/videos
Authorization: Bearer <your-token>
Idempotency-Key: unique-request-001
Content-Type: application/json

{"model_id":"wan-2.2","mode":"t2v","prompt":"A slow camera move over a lake at sunrise as mist drifts above the water.","duration_seconds":5,"resolution":"720p","seed":42,"parameters":{"inference_steps":10,"guidance_scale":5.0}}
```

HTTP 202 returns:

```json
{"job_id":"vid_...","model_id":"wan-2.2","status":"queued","status_url":"/v1/videos/vid_..."}
```

Submission starts a paid generation job. Keep the `job_id`. An optional `Idempotency-Key` prevents duplicate work when retrying the same request; use a new key for a changed request.

For image-to-video with LTX, first call `POST /v1/assets` with `{"content_type":"image/png"}` (or JPEG/WebP). The response gives `asset_id` and a presigned `upload` form. POST the image to `upload.url` as multipart form data with **all** `upload.fields` and a `file` field. The image must be at most 10 MB, at least 256×256 pixels, and at most 16 million pixels. Then submit a video with `"mode":"i2v"` and `"input_asset_id":"asset_..."`. Omit `input_asset_id` for `t2v`.

## 3. Poll for completion

`GET /v1/videos/{job_id}` returns `queued`, `running`, `succeeded`, `failed`, or `cancelled`. Poll every few seconds; `progress` is always `null`.

On success, the response includes an `output` object and a `cost` object:

```json
{
  "job_id": "vid_...",
  "model_id": "wan-2.2",
  "status": "succeeded",
  "status_url": "/v1/videos/vid_...",
  "progress": null,
  "download_url": "/v1/videos/vid_.../download",
  "output": {
    "video_key": "videos/user_123/vid_.../output.mp4",
    "video_url": "https://<signed-download-url>",
    "expires_in": 3600,
    "expires_at": "2026-10-13T12:00:00Z",
    "size_bytes": 12345678,
    "content_type": "video/mp4"
  },
  "cost": {
    "estimated_gpu_cost_usd": "0.063210",
    "currency": "USD",
    "basis": "generation_worker_runtime",
    "is_exact_bill": false
  }
}
```

The `video_url` allows anyone holding it to download the MP4 until its one hour expiry. The underlying object remains private. A new status request creates a fresh one hour URL. Do not cache or share the signed URL beyond the intended recipient. The `video_key` is stable and can be used to request another URL. A failed job returns `error_code` instead of `output` and `cost`.

`estimated_gpu_cost_usd` is an estimate based on recorded worker runtime and a GPU hourly rate. It is **not the exact billed amount** and does not include startup, warm idle, CPU, memory, storage, transfer, taxes, credits, or failed attempt usage. If runtime data is unavailable, its value is `null`. The amount is stored on first successful retrieval so it does not change later when rates are updated.

## 4. Renew a download URL

There are two authenticated ways to generate a fresh one hour URL for a completed video:

```http
GET /v1/videos/{job_id}/download
Authorization: Bearer <your-token>
```

```http
POST /v1/videos/url
Authorization: Bearer <your-token>
Content-Type: application/json

{"video_key":"videos/user_123/vid_.../output.mp4"}
```

Both return `video_key`, `video_url`, `expires_in`, `expires_at`, `size_bytes`, `content_type`, and `cost`. The key lookup only works for a completed video owned by your bearer token. It returns 404 for any other user's key. Downloading the MP4 from `video_url` does **not** require the API bearer token.

## Errors and limits

- `401`: missing or invalid bearer token.
- `404`: job, asset, or video key not found for this user.
- `409`: idempotency key reused for a different request, or download requested before completion.
- `422`: invalid request, unsupported model settings, or invalid uploaded image.
- `429`: two jobs are already active for this user.
- `503`: the generation worker could not be dispatched or a completed video is temporarily unavailable.

`POST /v1/videos/{job_id}/cancel` requests best-effort cancellation. The API handles one clip per request and does not merge clips. A fresh URL can expire earlier if the signing credentials are revoked or expire; request another URL when needed.
