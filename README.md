# Video generation API with on-demand Modal workers

The FastAPI service accepts a video request, records a private job in PostgreSQL, and dispatches it to one of four already deployed Modal GPU workers. The API can run on your own server; the main API does not need a Modal deployment. Workers scale to zero when idle. Input images and output MP4s stay in a private S3 bucket.

## Available models

`GET /v1/models` returns the currently accepted settings. The LTX settings follow the existing API; successful jobs have covered 5-second T2V, 10-second I2V, and 20-second T2V. The other three profiles match successful jobs observed in the shared database on 13 October 2026. Wider combinations require worker verification before they are enabled in `src/config.py`.

| `model_id` | Modal app | Modes | Seconds | Resolution | Default `parameters` |
| --- | --- | --- | --- | --- | --- |
| `ltx-2.3-distilled` | `video-pipeline-ltx-23` | `t2v`, `i2v` | 5, 10, 20 | `512p`, `720p` | `{}` |
| `wan-2.2` | `video-pipeline-wan-22` | `t2v` | 5 | `720p` | `{"inference_steps":10,"guidance_scale":5.0}` |
| `hunyuanvideo-1.5` | `video-pipeline-hunyuanvideo-15` | `t2v` | 5 | `480p` | `{"inference_steps":10,"guidance_scale":6.0}` |
| `cogvideox-1.5` | `video-pipeline-cogvideox-15` | `t2v` | 5 | `480p` | `{"inference_steps":10,"guidance_scale":6.0}` |

For the three Diffusers model workers, this API accepts `inference_steps` as an integer from 1 to 100 and `guidance_scale` from 0 to 20. The defaults are the values used by the successful jobs; other parameter values have not been verified in a live render. LTX does not accept either parameter through this API. LTX text-to-video renders 768×512; LTX image-to-video follows the conditioning image's aspect at the same pixel class (832×480 landscape, 480×832 portrait, 640×640 near-square). `model_id` defaults to `ltx-2.3-distilled` for existing callers. `duration_seconds` defaults to 5; `resolution` defaults to the selected model's only enabled preset. The seed is an optional integer from 0 to 4294967295; one is selected when omitted. The prompt must contain 1–2000 nonblank characters.

The model app names and accepted settings live in `src/config.py`. The API calls each deployed app's `VideoWorker.generate(job_id)` through the Modal SDK. It stores `model_id` and normalized `parameters` in `video_jobs` so the worker reads the same request. Startup adds these columns to an older database if needed; existing jobs default to LTX.

## Run the API outside Modal

Use Python 3.12 or 3.13. Configure `.env` privately using `.env.example` as a starting point. The API host needs PostgreSQL and S3 credentials, either `API_TOKENS_JSON` or Clerk OAuth settings, and a Modal token with permission to call the four deployed worker apps. Modal SDK credentials can come from an active local `modal setup` profile or the `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` environment variables on a server. Do not expose these credentials to API clients.

```powershell
uv sync --extra test
$env:MODAL_TOKEN_ID = "<server-side Modal token id>"
$env:MODAL_TOKEN_SECRET = "<server-side Modal token secret>"
uv run uvicorn src.api:api --env-file .env --host 127.0.0.1 --port 8000
```

`GET /health` checks the API process only. It does not start a GPU worker. On first startup, the API creates or migrates the two database tables. Keep the S3 bucket private. The Modal workers must use the same database and bucket settings as this API. The old `modal deploy modal_app.py` path deploys an LTX worker and a web endpoint together; it is not needed for this multi-model API and is not part of these startup steps.

## Request a video

Every `/v1` route needs `Authorization: Bearer <token>`. The API accepts a configured static token or a verified Clerk OAuth access token from the dedicated frontend client. [OAuth setup](docs/AUTH.md) explains account linking and PKCE. `GET /v1/models` lists valid models. A text-to-video request starts a billable GPU job:

```http
POST /v1/videos
Authorization: Bearer <token>
Idempotency-Key: lake-wan-001
Content-Type: application/json

{"model_id":"wan-2.2","mode":"t2v","prompt":"A slow camera move over a lake at sunrise as mist drifts across the water.","duration_seconds":5,"resolution":"720p","seed":42,"parameters":{"inference_steps":10,"guidance_scale":5.0}}
```

For LTX, omit `model_id` and `parameters` if the defaults are suitable. To animate an image with LTX, first call `POST /v1/assets` with `{"content_type":"image/png"}` (or `image/jpeg` or `image/webp`). POST the image directly to the returned S3 `upload.url` as multipart form data with **all** returned `upload.fields` and a `file` field. Then request `{"model_id":"ltx-2.3-distilled","mode":"i2v","prompt":"The camera moves toward the lake as reeds sway.","input_asset_id":"asset_...","duration_seconds":10,"resolution":"512p"}`. The image must be at most 10 MB, at least 256×256, and at most 16 million pixels.

Submission returns HTTP 202 with `job_id`, `model_id`, `status: queued`, and `status_url`. Poll `GET /v1/videos/{job_id}` every few seconds until `succeeded`, `failed`, or `cancelled`. A successful status includes the stable `video_key`, a private S3 `video_url` signed for one hour, file metadata, and an estimated GPU runtime cost in USD. `GET /v1/videos/{job_id}/download` renews the URL by job ID; `POST /v1/videos/url` with `{"video_key":"..."}` renews it by key after an owner-scoped database lookup. `POST /v1/videos/{job_id}/cancel` requests best-effort cancellation. The API permits two active jobs per user. `Idempotency-Key` is optional but recommended; reuse it only for an identical normalized request. Do not log bearer tokens or signed S3 URLs.

The bucket stays private; the signed URL is usable by anyone holding it until expiry. A key alone cannot be used to sign another user's video. The cost value is **GPU runtime estimate only**, based on the worker's recorded seconds and the hourly rate snapshotted on first successful retrieval. It is not an exact per-job bill and excludes startup, warm idle, CPU, memory, storage, and transfer. The API cannot report exact per-job Modal billing because Modal's billing report aggregates spend by app and hour. See the client-facing [public API contract](docs/PUBLIC_API.md) for request and response examples. [Modal billing documentation](https://modal.com/docs/guide/billing) and [AWS presigned URL documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html) explain the billing granularity and URL expiry behavior.

The worker runs on demand, so a cold start can take time. `progress` remains `null`; the API does not report a percentage. A stopped API process does not stop an already submitted Modal worker. While the API is running, it checks stale jobs every five minutes and resolves worker calls that ended without updating the database. If the API is offline for a long period, this check resumes when it starts again.

## Credits and pricing

Every Clerk-signed-in user starts with a one-time `STARTER_CREDIT_CENTS` grant (200 cents = $2.00) recorded in a PostgreSQL wallet and mirrored into Clerk Billing account credits. `GET /v1/wallet` returns the balance; `GET /v1/wallet/transactions` returns the ledger. A submission reserves the quoted price before dispatch; a failed or cancelled operation refunds it. Prices live in `src/config.py` (`VIDEO_BASE_PRICES_CENTS`, `CREATIVE_PRICES_CENTS`): LTX 5s/10s/20s clips cost $0.25/$0.40/$0.70, the Diffusers models cost $0.35–$0.45, prompt optimization $0.02, and image generation $0.20. Static-token users get no grant and no Clerk sync.

The Clerk mirror requires `CLERK_SECRET_KEY` on the API host and Billing credits enabled for the Clerk instance; without them paid requests fail with 503. See [docs/CREATIVE_API.md](docs/CREATIVE_API.md) for the creative endpoints and [docs/AUTH.md](docs/AUTH.md) for OAuth setup.

## Agent tools with FastMCP

The optional local FastMCP server exposes model discovery, image upload, asynchronous generation, status, one-hour URL renewal, download, and cancellation as agent tools. Install it with `uv sync --extra mcp` and connect your MCP client to the stdio launcher `mcp_server.py`. See [docs/MCP_SERVER.md](docs/MCP_SERVER.md) for a client configuration and tool workflow. Keep the API running separately; only a generation request starts a billable Modal worker.

## Verification

```powershell
uv run --extra test python -m pytest -q
uv run python -m compileall -q src modal_app.py
```

These checks validate request profiles and dispatch routing without starting a GPU job. A full render is billable and should be run separately when required. The API behavior for agents is documented in [docs/AGENT_API_GUIDE.md](docs/AGENT_API_GUIDE.md). Earlier LTX-only live run costs remain in [reports/video_generation_costs_2026-10-10.md](reports/video_generation_costs_2026-10-10.md).
