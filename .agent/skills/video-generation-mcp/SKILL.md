---
name: video-generation-mcp
description: Write prompts and use the Video Generation MCP server to create, check, share, download, or cancel video clips. Use when this app's MCP tools are connected or the user asks to use this video generation app. Also handles prompt-only requests for its available models. Do not use for unrelated video services.
---

# Video Generation MCP

This skill is for an agent connected to the **Video Generation** MCP server. The server talks to an authenticated video API and dispatches generation to on-demand workers. The MCP connection must already be configured by the user or client. Use the exposed MCP tools, not a guessed HTTP endpoint or Modal deployment. The hosted connection exposes five tools; the local stdio connection also exposes `upload_video_image` and `download_video`. Discover the available tools before choosing a workflow.

## Decide the task

- **Prompt only:** Write or refine a prompt without calling `generate_video`. Read [prompting.md](references/prompting.md). If the user has not chosen a model and the MCP server is available, `list_video_models` can show the choices.
- **Create a clip:** Read [prompting.md](references/prompting.md), call `list_video_models` for current accepted settings, then use the workflow below. `generate_video` reserves credits and starts a billable GPU job; a request to create a clip authorizes that call. A request to brainstorm, draft a prompt, or quote a clip does not.
- **Existing clip:** Use the supplied `job_id` to check, cancel, share, or download it. Do not generate a replacement unless requested.

The result of `list_video_models` is the source of truth for enabled model IDs, modes, durations, resolutions, and parameter defaults. The prompting reference guides wording; it does not expand API capabilities. Select only combinations returned by the tool. If the requested combination is unavailable, explain the closest supported choice before proceeding when that choice would materially change the result.

## Create and deliver a clip

1. Convert the user's scene into one coherent clip prompt. Keep model names, duration, resolution, and generation settings outside the prompt text. Preserve requested subjects, action, style, camera, and sound. For image-to-video, anchor the scene to the image and describe mainly what moves or changes.
2. For image-to-video, obtain an `input_asset_id` owned by the signed-in user. If `upload_video_image` is available, use it with a **local file accessible to the MCP server**. It accepts JPEG, PNG, or WebP, 1 byte to 10 MB, at least 256 pixels on each side, and at most 16 million pixels. The path must be inside the server's `VIDEO_MCP_IMAGE_ROOT`. The hosted MCP connection has no file upload tool; if no asset ID is available, explain that image upload must happen through the dashboard before an image-to-video request. Currently the app's LTX model is the image-to-video option; confirm with `list_video_models`.
3. Call `generate_video` once with the prompt and supported settings. Its inputs are `prompt`, `mode` (`t2v` or `i2v`), `model_id`, `duration_seconds`, `resolution`, optional `seed`, `input_asset_id`, `inference_steps`, `guidance_scale`, and `idempotency_key`. `inference_steps` and `guidance_scale` belong only to models that expose those parameters. Save the returned `job_id` and `idempotency_key`.
4. Poll `get_video_status(job_id)` every few seconds while status is `queued` or `running`. Stop on `succeeded`, `failed`, or `cancelled`; `progress` is not a percentage. Report the returned error code on failure. Do not submit another billable job automatically after a terminal failure.
5. On success, use `get_video_url(job_id=...)` for a one-hour signed link; `get_video_url(video_key=...)` also works for an owned completed video. The link grants access to anyone holding it. If `download_video` is available in the local stdio connection and the user wants a file, it saves to the MCP server's `VIDEO_MCP_OUTPUT_ROOT` and rejects an existing filename; that path may be on a different machine from the user. Report the usable file path or link and the returned estimated GPU runtime cost, if available.

`cancel_video(job_id)` requests best-effort cancellation. Check the resulting status because cancellation may race with completion. The server limits users to two active jobs. Reuse the **same** `idempotency_key` only to retry the **same** normalized generation request after an uncertain submission outcome. Do not use a new key merely because a response was lost; that may create and charge for another job.

## Output and privacy

- For a prompt-only request, return the prompt and, when useful, supported settings separately. Do not imply that a video was generated.
- For a generation request, report the model, duration, job status, and final artifact. Treat `cost.estimated_gpu_cost_usd` as an estimate, not an invoice.
- Never expose the API bearer token. Share a signed video URL only with the intended recipient. Do not copy it into logs or unrelated messages.
- If a tool reports HTTP 401, reconnect the hosted MCP account through browser authorization or check the local stdio server's API token. HTTP 422 usually means invalid input or unsupported settings; refresh `list_video_models`. HTTP 429 means the active-job limit was reached. HTTP 503 can indicate an unavailable API or dispatch service. Report the actual tool error without inventing a completed clip.
