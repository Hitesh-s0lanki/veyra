# Creative API

All routes require the same bearer token as the video API. The creative routes
never submit a video job. The user reviews the returned prompt, image, and
video quote before calling `POST /v1/videos`.

## Prices

`GET /v1/creative/pricing` returns `currency`, `prompt_cents`, and
`image_cents`. The price is reserved from the same Clerk-backed account credit
balance used by video jobs before calling Gemini. Successful calls capture the
reservation; failures refund it. Prices are configured in `src/config.py`.

## Optimize a video prompt

`POST /v1/creative/prompt` requires `Idempotency-Key` and JSON:

```json
{"model_id":"ltx-2.3-distilled","mode":"t2v","idea":"A dancer at dusk","duration_seconds":10}
```

For LTX image-to-video, set `mode` to `i2v` and provide an owned
`input_asset_id`. The response is an editable draft:

```json
{"prompt":"...","summary":"...","model_id":"ltx-2.3-distilled","mode":"t2v","duration_seconds":10,"resolution":"512p","parameters":{}}
```

The available models and settings come from `GET /v1/models`. LTX-2.3 supports
text and image modes; Wan 2.2, HunyuanVideo 1.5, and CogVideoX 1.5 currently
support text mode only. The agent uses the repository's video prompting skill
and LTX-2.3 or Wan 2.2 reference for those models. For the other two models it
uses conservative guidance grounded in their available server settings.

## Generate or edit a scene image

`POST /v1/creative/images` requires `Idempotency-Key` and JSON:

```json
{"prompt":"A cinematic still of a dancer at dusk","source_asset_id":null}
```

Set `source_asset_id` to an owned image for editing. The response includes
`asset_id`, `image_url`, `content_type`, and `expires_in`. The generated image is
stored as an owned `video_assets` record and can be reused for LTX image-to-video.
The signed preview URL expires after one hour; request a fresh asset URL through
the asset listing API when it does.

Both POST routes return the stored result on a retry with the same key and same
body. A reused key with a different body is rejected. Requests still processing
return conflict. If a provider call fails, the reservation is refunded and a
new key is needed to retry. Set `GEMINI_API_KEY` only on the server; the frontend
must never receive it.

The credit balance behind these routes is the same wallet video jobs use. The
server needs `CLERK_SECRET_KEY` and Billing credits enabled in the Clerk
dashboard so reservations and refunds also apply to Clerk Billing account
credits; otherwise every priced request returns 503.
