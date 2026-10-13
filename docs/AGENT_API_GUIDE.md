# Video generation API: guide for agents

Use this guide to call this repository's LTX-2.3 video service. The FastAPI app accepts a prompt, queues a Modal GPU job, and returns a private MP4 download URL after generation. It does not write or improve prompts automatically. For prompt drafting, use `.agent/skills/video-prompting/SKILL.md` and its LTX-2.3 reference.

## Connection and authorization

- Local base URL, when the local server is running: `http://127.0.0.1:8000`.
- Hosted base URL: use the `web` URL from `modal deploy modal_app.py` or the deployment configuration. Do not assume a local server or a past deployment URL is still available; check `GET /health` first.
- `GET /health` is public and returns `{"status":"ok"}` with HTTP 200. It confirms the API process is responding, not GPU readiness.
- Every `/v1` endpoint requires `Authorization: Bearer <token>`. The token is a key in `API_TOKENS_JSON`; the mapped user ID owns that user's assets and jobs. Obtain a token through the user's existing setup. Never put a token, presigned S3 URL, or download URL in logs, source control, or chat output.
- JSON requests use `Content-Type: application/json`. Browser CORS allows all origins, methods, and headers; CORS does not replace bearer authorization.

Set `BASE_URL` and `VIDEO_API_TOKEN` in the calling environment before using the examples below. Do not commit their values.

## Supported generation settings

| Field | Accepted value | Notes |
| --- | --- | --- |
| `mode` | `t2v` or `i2v` | `i2v` requires an uploaded image asset. |
| `prompt` | Nonblank string, at most 2,000 characters | The API trims surrounding whitespace. Describe one coherent clip. |
| `duration_seconds` | `5`, `10`, or `20` | Optional; defaults to `5`. |
| `resolution` | `512p` | Optional; currently the only preset, 768×512 at 24 fps. |
| `seed` | Integer from `0` to `4294967295` | Optional; otherwise the server picks one. The chosen seed is not returned in the public job response. |
| `input_asset_id` | Asset ID from `POST /v1/assets` | Required for `i2v`; must be omitted for `t2v`. |

The frame counts are 121, 241, and 481 for 5, 10, and 20 seconds, respectively. A 30-second single request and other resolutions are rejected. Check `src/config.py` before using these limits if the code has changed.

## Text-to-video flow

1. Draft a prompt that fits the chosen clip length.
2. Submit `POST /v1/videos`. This starts a billable GPU job. Submit only when video generation is requested.
3. Save the returned `job_id`. Poll its status until it is terminal.
4. On success, request a download URL and fetch the MP4 promptly.

Request:

```http
POST /v1/videos
Authorization: Bearer <token>
Idempotency-Key: unique-request-key-001
Content-Type: application/json

{"mode":"t2v","prompt":"A slow dolly toward a mountain at sunrise as clouds drift across the valley; wind and distant birds are audible.","duration_seconds":5,"resolution":"512p","seed":42}
```

Initial response (HTTP 202):

```json
{"job_id":"vid_...","status":"queued","status_url":"/v1/videos/vid_..."}
```

`Idempotency-Key` is optional but recommended for client retries. It may contain letters, digits, `_`, or `-`, up to 80 characters. Reuse it only for the **same complete JSON request** under the same user. Reusing it with a changed request returns HTTP 409. A distinct generation request needs a new key.

## Image-to-video flow

1. Start with a local JPEG, PNG, or WebP file. Maximum size: 10 MB; minimum dimensions: 256×256; maximum pixel count: 16 million.
2. Call `POST /v1/assets` with `{"content_type":"image/png"}` (or the matching JPEG/WebP MIME type). This returns an `asset_id` and an `upload` object.
3. Send a **multipart/form-data POST directly to `upload.url`**, with every key/value from `upload.fields` as form fields and the image as the `file` field. This S3 upload does not use the API bearer header. Its presigned form expires after 15 minutes. Do not assume the field names or values; use the returned object verbatim.
4. Submit `POST /v1/videos` with `mode: "i2v"` and that `asset_id`. The asset must belong to the same bearer-token user. The API validates the stored image before starting the job.

Asset request and representative response (HTTP 201):

```http
POST /v1/assets
Authorization: Bearer <token>
Content-Type: application/json

{"content_type":"image/png"}
```

```json
{"asset_id":"asset_...","upload":{"url":"https://...","fields":{"key":"...","Content-Type":"image/png","policy":"...","x-amz-algorithm":"...","x-amz-credential":"...","x-amz-date":"...","x-amz-signature":"..."}}}
```

The `fields` object varies with S3 signing; the example is illustrative. A Python upload with `httpx` looks like this:

```python
import os
from pathlib import Path
import httpx

base_url = os.environ["BASE_URL"].rstrip("/")
token = os.environ["VIDEO_API_TOKEN"]
image = Path("input.png")
with httpx.Client(timeout=120) as client:
    asset = client.post(
        f"{base_url}/v1/assets",
        headers={"Authorization": f"Bearer {token}"},
        json={"content_type": "image/png"},
    )
    asset.raise_for_status()
    result = asset.json()
    with image.open("rb") as stream:
        upload = client.post(
            result["upload"]["url"],
            data=result["upload"]["fields"],
            files={"file": (image.name, stream, "image/png")},
        )
        upload.raise_for_status()
    asset_id = result["asset_id"]
```

Then submit:

```json
{"mode":"i2v","prompt":"The camera moves slowly toward the lake as ripples spread outward; reeds sway in the breeze.","input_asset_id":"asset_...","duration_seconds":10,"resolution":"512p"}
```

The prompt should describe movement and change from the input image. The API does not accept an arbitrary image URL in place of `input_asset_id`.

## Status, download, and cancellation

Call `GET /v1/videos/{job_id}` with the bearer token. Responses have `job_id`, `status`, `status_url`, and `progress`. Status is `queued`, `running`, `succeeded`, `failed`, or `cancelled`; `progress` is always `null`. Poll every few seconds, with a reasonable overall timeout. Stop polling at a terminal state.

On success, the status response also contains `"download_url":"/v1/videos/{job_id}/download"`. Call that route with the bearer token. It returns JSON such as:

```json
{"video_url":"https://...signed-S3-URL...","expires_in":900}
```

Fetch `video_url` to save the MP4. The URL expires after 900 seconds; request a new one if it expires. The `/download` route returns HTTP 409 until the job succeeds. It returns a URL, not video bytes.

On failure, status includes an `error_code`, such as `dispatch_failed`, `generation_failed`, `out_of_memory`, `dispatch_lost`, or `worker_lost`. Do not retry blindly with a new idempotency key: that starts another GPU job. Report the code and choose a retry only when appropriate to the user's request.

`POST /v1/videos/{job_id}/cancel` requests best-effort cancellation. A job that is already terminal returns its current state. Cancellation can race with a worker finishing, so check the final status.

## HTTP errors and limits

| Status | Meaning |
| --- | --- |
| `401` | Bearer token missing or invalid. |
| `404` | Job or asset not found for this user. |
| `409` | Idempotency key reused with different request, or download requested before success. |
| `422` | Invalid body, unsupported settings/image, or missing image upload. |
| `429` | The user already has two active jobs. Wait for one to finish. |
| `503` | Modal dispatch failed after job creation. |

The service handles one clip per request. It does not merge clips, generate prompts, expose percentage progress, or automatically retry failed jobs. Output and uploads are private S3 objects. Storage retention and broader rate limiting are external infrastructure concerns.

## Source of truth

- `src/api.py`: endpoint behavior and request validation.
- `src/config.py`: current generation settings.
- `src/storage.py`: S3 upload, download, and image validation.
- `modal_app.py`: GPU worker, web deployment, and job reconciliation.
- `README.md`: setup, deployment, and verified live examples.
