# Creator video verification

The two challenges in [`src/data/challenge.json`](../src/data/challenge.json) are concept tests carried over from the sibling `video-pipeline` project. They are not official campaigns or reward decisions. [`src/data/product.json`](../src/data/product.json) provides a tentative trimmer reference. The boAt speaker lacks an approved reference image, and the trimmer's listed name still needs an exact SKU check. Do not treat either product match as confirmed solely from a model response.

## API flow

1. Call authenticated `GET /v1/challenges` to get a challenge ID and its product options.
2. Send multipart `POST /v1/submissions` with `video`, `challenge_id`, and `selected_product` when multiple products are listed. Supported filename extensions are MP4, MOV, WebM, and MKV; the maximum upload is 200 MB.
3. Poll authenticated `GET /v1/submissions/{submission_id}` until `processing_status` is `complete` or `failed`. `GET /v1/submissions` lists your recent submissions.
4. Read the report's `challenge_checks`, `audio`, `additional_checks`, `not_passed_checks`, and `decision`. `GET /v1/submissions/{submission_id}/video` gives a one-hour signed URL to the source video. Ownership is enforced before signing.

The API stores the upload in the private S3 bucket and the submission state and report in the existing PostgreSQL database. The separately deployed `video-pipeline-verification` Modal worker downloads the file, runs FFprobe and FFmpeg, and writes the report. The API's existing reconciliation loop marks abandoned submissions as failed after a worker exits or dispatch is lost. Deploy the worker with `uv run modal deploy src/verification_worker.py` after creating the `video-pipeline` Modal secret from the local `.env`.

## Checks and limits

FFprobe checks display orientation, the 20–30 second rule, and audio presence. FFmpeg checks video decodability and basic audio health. For the speaker challenge, a missing audio track fails the music requirement; the trimmer challenge does not require audio. An unreadable video is excluded under `platform.video_fully_decodable`.

When `GEMINI_API_KEY` is present in the worker secret, the worker uploads the submitted video to Gemini for visual and music observations, then removes the uploaded file after processing. `GEMINI_MODEL` defaults to `gemini-2.5-flash`. The model proposes timestamped findings; code checks their IDs, time ranges, and event order. Uncertain model findings remain `review`, and a model-suggested failure requires human confirmation. With no Gemini key or unavailable model, objective media checks still run and visual checks remain `review`.

Originality, rights to footage and audio, exact product identity, and purchase cannot be proved from video analysis alone. Reports mark those items for human review. The [example report](verification-result.example.json) illustrates the JSON structure; it is not a real assessment. Before using results for production decisions, confirm product references and evaluate the checks against human-reviewed sample videos.
