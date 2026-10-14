# Video generation MCP server

## Hosted connection

Run `uv run --extra mcp uvicorn src.hosted_app:app --env-file .env --host 127.0.0.1 --port 8000` to serve the video API and hosted MCP from one origin. The hosted app serves Streamable HTTP at `https://your-mcp-origin/mcp`; put HTTPS in front of it before exposing it to users. Set the following on the host:

```text
MCP_PUBLIC_ORIGIN=https://your-mcp-origin
MCP_FRONTEND_ORIGIN=https://your-frontend-origin
MCP_JWT_SIGNING_KEY=<stable random secret>
CLERK_OAUTH_ISSUER=https://your-instance.clerk.accounts.dev
CLERK_OAUTH_CLIENT_ID=<client-id>
CLERK_OAUTH_CLIENT_SECRET=<client-secret>
MCP_API_INTERNAL_ORIGIN=http://127.0.0.1:8000
```

`MCP_API_INTERNAL_ORIGIN` is the private address of the Python video API from the MCP process; for the combined app above, keep it at `http://127.0.0.1:8000`. `MCP_FRONTEND_ORIGIN` is the public origin of the Next.js frontend. Set `MCP_PUBLIC_ORIGIN`, `CLERK_OAUTH_ISSUER`, and `CLERK_OAUTH_CLIENT_ID` on the Next.js server too. The `/mcp` page shows the connection URL, and `/api/mcp/authorize` sends signed-in users on to Clerk consent. Keep `MCP_JWT_SIGNING_KEY` stable. FastMCP's default encrypted OAuth client store needs persistent storage and a single instance; configure a shared encrypted store before running multiple replicas.

Configure the Clerk OAuth application with `profile offline_access` scopes, PKCE enabled, and callback `https://your-mcp-origin/auth/callback`. The video API must use the same `CLERK_OAUTH_CLIENT_ID` and `CLERK_OAUTH_CLIENT_SECRET` to verify these tokens. The browser authorization flow is: the MCP client connects to `/mcp`, receives an OAuth challenge, opens the frontend's `/api/mcp/authorize` route, signs in on the frontend if needed, continues to Clerk consent, and returns to the MCP client with a client-specific token. FastMCP validates the upstream Clerk token on every request and passes that token to the video API. The user's Clerk subject owns their jobs and assets. No static API token or `VIDEO_API_BASE_URL` is entered in the remote MCP client.

The hosted endpoint exposes `list_video_models`, `generate_video`, `get_video_status`, `get_video_url`, and `cancel_video`. File path tools are available only in the local stdio server because a path on the hosted machine is not a path on the user's computer. Use `get_video_url` to obtain a one-hour download link for a completed clip.

Example client settings for clients that accept JSON remote MCP entries:

```json
{"mcpServers":{"video-generation":{"url":"https://your-mcp-origin/mcp"}}}
```

## Local stdio connection

This local [FastMCP](https://gofastmcp.com/getting-started/quickstart) server gives agents tools for the existing authenticated video API. It runs as a stdio process launched by an MCP client. The API must be running separately; the MCP server does not deploy the API or any Modal app. Generation calls the API's on-demand Modal worker and incurs GPU cost.

## Agent skill for connected users

Install the self-contained [video-generation-mcp skill](../.agent/skills/video-generation-mcp/SKILL.md) in your agent client's skills directory when connecting this server. Copy the entire `video-generation-mcp` folder, including `references/prompting.md`; the skill does not require the rest of this repository at runtime. It tells the agent when to use each MCP tool, how to write prompts for the models exposed by this app, and how to handle jobs, files, signed links, and billing. The MCP connection and its token are configured separately below; installing the skill does not connect the server.

## Install and connect

From the project directory, install the optional MCP dependency:

```powershell
uv sync --extra mcp
```

Start the API as described in [README.md](../README.md). Check `http://127.0.0.1:8000/health` before using the tools. Add a stdio server to your MCP client's configuration, replacing the paths with absolute paths on the client machine:

```json
{
  "mcpServers": {
    "video-generation": {
      "command": "C:\\path\\to\\video-generation-pipeline\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\video-generation-pipeline\\mcp_server.py"],
      "env": {
        "VIDEO_API_BASE_URL": "http://127.0.0.1:8000",
        "VIDEO_API_TOKEN": "<your-api-bearer-token>"
      }
    }
  }
}
```

`VIDEO_API_TOKEN` must be one key from the API host's `API_TOKENS_JSON`. Keep it in private client settings or a secret manager. If `VIDEO_API_TOKEN` is unset and this server runs on the API host, it can read `.env` when `API_TOKENS_JSON` contains exactly one token. Set `VIDEO_API_TOKEN` explicitly when there are multiple users or the server is on another machine. Remote `VIDEO_API_BASE_URL` values must use HTTPS.

Optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VIDEO_MCP_IMAGE_ROOT` | Project directory | Restricts local files accepted by `upload_video_image` to this directory and its children. |
| `VIDEO_MCP_OUTPUT_ROOT` | Project `outputs` directory | Directory for `download_video` MP4 files. Existing filenames are rejected. |

The MCP server is intended for a trusted local client. The bearer token stays on the MCP server and is sent only to the API. Signed video links returned by `get_video_url` grant access to anyone holding them until they expire; show them only to the intended recipient. Do not expose this stdio process as an unauthenticated network service.

## Tools and workflow

| Tool | What it does |
| --- | --- |
| `list_video_models` | Reads accepted model IDs, modes, durations, resolutions, and parameter defaults. |
| `upload_video_image` | Uploads a local JPEG, PNG, or WebP image and returns its `asset_id`; use it for LTX image-to-video. |
| `generate_video` | Starts one billable asynchronous job and returns `job_id` and `idempotency_key`. |
| `get_video_status` | Polls job state, output key, file details, and estimated USD GPU cost; omits the signed link. |
| `get_video_url` | Returns a fresh one-hour signed MP4 URL by `job_id` or owned `video_key`. |
| `download_video` | Downloads a completed MP4 to the configured local output directory and returns its path and cost. |
| `cancel_video` | Requests best-effort cancellation of a queued or running job. |

For text-to-video, call `list_video_models`, then `generate_video` with a supported model and settings. Poll `get_video_status` every few seconds until `succeeded`, `failed`, or `cancelled`. After success, use `get_video_url` when the user needs a one-hour link or `download_video` when the user needs a local MP4. For image-to-video, call `upload_video_image` first and pass its `asset_id` as `input_asset_id` with `mode: "i2v"` and `model_id: "ltx-2.3-distilled"`.

`generate_video` accepts `prompt`, `mode`, `model_id`, `duration_seconds`, `resolution`, `seed`, `input_asset_id`, `inference_steps`, `guidance_scale`, and `idempotency_key`. Omit model-specific fields you do not need. The API validates all settings against `src/config.py`; check `list_video_models` for current combinations. Reuse an `idempotency_key` only when retrying the exact same request. A failed job is not automatically retried.

The `cost.estimated_gpu_cost_usd` value is a GPU runtime estimate, not an exact Modal bill. It can be `null` when runtime data is unavailable. See [the public API contract](PUBLIC_API.md) for output fields and limits, and [the agent API guide](AGENT_API_GUIDE.md) for agent use and prompting guidance.
