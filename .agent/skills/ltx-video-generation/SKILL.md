---
name: ltx-video-generation
description: Generate and download text-to-video or image-to-video clips through this repository's LTX-2.3 Modal API. Use when the user asks to render a video with this project, submit a generation job, check its status, or download its result.
---

# Generate video with this project

Use the existing API in `src/api.py` and the deployed endpoint documented in `README.md`. Read `src/config.py` before suggesting settings because it is the source of truth. Use the `video-prompting` skill's LTX-2.3 reference when drafting or refining a prompt. If that skill suggests different duration defaults, this project's API defaults to 5 seconds.

## Request constraints

- `mode`: `t2v` or `i2v`.
- `prompt`: nonblank, at most 2,000 characters. Keep one coherent clip's action within the selected duration.
- `duration_seconds`: 5, 10, or 20. Default: 5. These map to 121, 241, or 481 frames at 24 fps.
- `resolution`: currently only `512p` (768×512).
- `seed`: optional unsigned 32-bit integer. Preserve it for reproducible reruns when supplied.
- `i2v` requires `input_asset_id` from this API; arbitrary image URLs are unsupported. Do not include `input_asset_id` for `t2v`.

## Submit and retrieve

1. Obtain the deployed `BASE_URL` and a bearer token for the intended user from the user's existing setup. Do not print or commit credentials. If the service is not deployed, follow `README.md` setup only when deployment is within the user's request.
2. For `i2v`, create an asset with `POST /v1/assets` and its MIME type (`image/jpeg`, `image/png`, or `image/webp`); upload the image using the returned presigned POST `url` and **all** returned `fields` plus the file form field. Use the returned `asset_id` in the video request. The image must meet the size and dimension limits in `src/config.py` and `src/storage.py`.
3. Submit `POST /v1/videos` with bearer authorization, JSON body, and a fresh `Idempotency-Key` for this exact request. Reuse that key only when retrying the same body. Submission starts a billable GPU job, so submit only when the user has asked to generate a video.
4. Poll `GET /v1/videos/{job_id}` until `succeeded`, `failed`, or `cancelled`. Status `progress` is always null. Do not infer a percentage. Avoid rapid polling; every few seconds is enough.
5. After success, call `GET /v1/videos/{job_id}/download`. Its JSON `video_url` is a private signed URL valid for 15 minutes. Download the MP4 to `outputs/` or another user-chosen path, and provide the local path. Do not paste the signed URL in chat.

If a request fails, report the HTTP status or returned `error_code` without exposing credentials. Two active jobs per user are allowed. For longer finished videos, generate separate supported clips and combine them only when requested.

## Text-to-video example

```bash
curl -X POST "$BASE_URL/v1/videos" \
  -H "Authorization: Bearer $VIDEO_API_TOKEN" \
  -H "Idempotency-Key: clip-001" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"t2v","prompt":"A slow dolly toward a mountain at sunrise as cloud shadows cross the valley; quiet wind and distant birds.","duration_seconds":5,"resolution":"512p"}'
```

The full image upload sequence and deployment steps are in `README.md`. Check the implementation before adapting these examples to a changed API.
