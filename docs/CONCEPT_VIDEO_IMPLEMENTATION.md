# Concept videos: implementation and delegation plan

## Goal and user flow

Build a single finished video of up to 60 seconds from model-sized clips. The user chooses **Up to 60 seconds** in the main studio, describes an idea in the centered input, and answers only the questions needed to settle the audience, story, look and ending. The storyboard appears in the chat flow as compact scene cards; each card opens a detail sheet for prompts, previews and edits. They can revise it through chat or edit each scene's title, duration, starting image prompt and motion prompt. **Approve & generate** is the billable boundary. Approval opens the video's page in the Videos section, which polls scene progress and displays the final MP4 when ready. The app makes a Gemini image for each scene, submits an LTX image-to-video job for that scene, then combines successful clips into one MP4 with audio.

The target length is currently a multiple of five seconds from 5 to 60. Each scene is 5, 10 or 20 seconds because those are the verified LTX presets in `src/config.py`. A 60-second storyboard can be three 20-second scenes; other splits are allowed if their total is exact. There is no video generation while the user is chatting or editing.

## Current implementation

- [x] Keep the concept opener in the studio at `/app?mode=concept`, then move the conversation to `/chat?id=…`. The storyboard appears in the conversation when ready, with scene details on demand. Clarification questions offer suggested answers and a free-text reply, following the sandbox interaction pattern. The game sandbox, Trigger.dev and Daytona runtime are not copied. See `frontend/src/components/concept-workspace.tsx`.
- [x] Keep one app bar during chat. Show recent concept chats in a dedicated sidebar section and keep the reply box close to the conversation.
- [x] Move approved concepts into the Videos sidebar and open `/app?concept=…`. Poll scene status while generating, show image and clip progress, and display the finished video automatically. Keep individual scene jobs out of the standalone video list.
- [x] Store owner-scoped concepts, messages, plan revisions and scene state in PostgreSQL. Browser reloads recover the conversation and jobs. See `src/concepts.py`.
- [x] Use the Modal GLM-5.3-Flash endpoint for concept chat with `MODAL_PROXY_TOKEN_ID` and `MODAL_PROXY_TOKEN_SECRET` in the ignored root `.env`. The existing `GEMINI_API_KEY` remains the scene image key. Gemini and OpenAI text remain optional providers through `CONCEPT_TEXT_PROVIDER`.
- [x] Use the existing Gemini adapter to create a scene image, center crop it to the selected orientation, save it as a private video asset, and condition the LTX clip on that image. After each completed clip, extract and persist its last frame as the next Gemini image reference. Fall back to the prior scene's starting image if extraction fails. The transition source is recorded on the scene.
- [x] Require explicit approval, enforce the exact target length server-side, show a server-calculated price estimate, check the wallet before starting, and use deterministic idempotency keys for scene image and clip operations.
- [x] Advance clip jobs from the API background loop, one scene at a time. A page reload does not stop the workflow. A PostgreSQL session advisory lock serializes each concept across API replicas and releases after process death. The loop respects the API's active-job limit and exposes each clip's status.
- [x] Normalize orientation, frame rate, scene length and audio in FFmpeg, concatenate the clips, store the final MP4 privately, and renew owner-scoped signed playback links on reads. Missing clip audio becomes silence.
- [x] Provide a user-triggered retry for a failed scene or assembly step. Retrying a failed clip may incur another charge; completed clips remain available.
- [x] Add API proxy routes, the dashboard mode tab, API-host FFmpeg, and focused validation and media tests.

## API and state contract

All endpoints use the existing bearer authentication and owner scoping. The frontend calls them through `/api/video/*`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`, `POST` | `/v1/concepts` | List owned concepts; create with `target_seconds` and `aspect`. |
| `GET` | `/v1/concepts/{id}` | Messages, plan, scene/image/clip status, signed preview and final URL. |
| `POST` | `/v1/concepts/{id}/chat` | Send `{message, revision}` and receive the updated concept. |
| `PUT` | `/v1/concepts/{id}/plan` | Save `{plan, revision}` after manual edits; total duration must match. |
| `POST` | `/v1/concepts/{id}/generate` | Approve the ready plan and start durable orchestration. |
| `POST` | `/v1/concepts/{id}/retry` | Resume one failed step after the user chooses to retry. |

Concept state moves through `draft → ready → generating → assembling → succeeded`, or `failed`. A stale revision returns 409. The plan contains `title`, `summary`, and ordered `scenes`; every scene has `title`, `duration_seconds`, `image_prompt`, and `motion_prompt`. The backend snapshots scenes at approval, so subsequent edits cannot silently change in-flight jobs. Clip failures stop the sequence; completed clips stay stored. The UI polls only while generating or assembling.

## Delegation lanes

The core feature is implemented. Assign the remaining checks below to separate agents at the same time. Each lane has its own file ownership to reduce merge conflicts. Do not ask an agent to submit a real GPU job unless you explicitly authorize a billable video render.

### Agent A — backend workflow and billing review

**Own:** `src/concepts.py`, `tests/test_concepts.py`, and a new `docs/CONCEPT_API.md` if needed. **Do not edit:** frontend files or `src/config.py` without coordinating.

- [x] Replace the expiring lease with a session advisory lock and test that concurrent replicas submit one scene. Test that recovering an already saved image settles its deterministic charge only once.
- [x] Preserve the clip attempt on retry when a queued or completed job already exists for its idempotency key; simulate a lost scene link in PostgreSQL.
- [ ] Audit the image upload to database insert crash window.
- [ ] Verify per-scene Gemini charges, LTX reserves/refunds, wallet changes during a multi-scene run, and the displayed estimated cost. Decide whether a project-level reservation is needed to avoid a partial 60-second sequence when other jobs spend the wallet balance.
- [x] Add an ephemeral PostgreSQL fixture and verify owner-scoped concept lookup.
- [ ] Add authenticated HTTP checks for every concept, scene asset, job and final video lookup.
- [ ] Ensure permanent upstream errors stop cleanly and transient failures retry with bounded backoff. Never repeat a billable job automatically with a new idempotency key.

**Done when:** a two-replica/crash test cannot double-submit a scene, failed paid operations settle correctly, and cross-user reads return 404.

### Agent B — conversation and storyboard UX

**Own:** `frontend/src/components/concept-workspace.tsx`, `frontend/src/app/(protected)/app/concepts/`, and focused frontend tests. **Do not edit:** backend code or the shared API proxy table without coordinating.

- [ ] Run the page signed in on desktop and mobile. Check first message, clarification turns, scene appearance, chat edits after a plan exists, manual edits, stale revision, navigation to another concept and reload during generation.
- [x] Focus and announce the newest assistant reply, add a mobile concept switcher, and require an in-app confirmation showing the server quote before billable generation.
- [ ] Verify keyboard and screen reader flow in a signed-in browser, including focus rings and 320px reflow.
- [x] Warn before switching concepts or asking for a new assistant plan when storyboard edits are unsaved. Retry copy states that a new clip may use credits.
- [ ] Verify draft preservation and stale revision behavior in a signed-in browser.

**Done when:** a user can complete the full flow on keyboard and phone without losing a draft or approving stale prompts.

### Agent C — clip continuity and finishing quality

**Own:** extract the assembly and image-continuity logic from `src/concepts.py` into a new `src/concept_media.py`, then coordinate the small import change with Agent A. **Do not edit:** the chat UI.

- [ ] Validate landscape and portrait output using real worker clips with different source dimensions, with and without audio. Check exact target duration, audio boundaries, orientation and playback in common browsers.
- [x] Extract one end frame from each completed clip, persist an owner-scoped transition asset, record the reference type, and fall back to the prior image on extraction failure.
- [ ] Add optional simple transitions only if they preserve the requested total duration. Keep straight cuts as the default.

**Done when:** a real three-scene, 60-second render has the intended order, length, audio and continuity, and the output is downloaded from the owner-scoped final URL.

### Agent D — deployment and product verification

**Own:** deployment configuration, `.env.example`, `README.md`, release notes, and smoke-test records. **Do not edit:** workflow source or the UI while the other lanes are active.

- [ ] Provision `GEMINI_API_KEY`, `MODAL_PROXY_TOKEN_ID`, `MODAL_PROXY_TOKEN_SECRET`, PostgreSQL, S3, Modal video worker and Clerk settings on the API host. Provision `CONCEPT_GEMINI_API_KEY` or `OPENAI_API_KEY` only when selecting those optional text providers. Do not put provider keys in `frontend/.env.local` or `NEXT_PUBLIC_*` variables. The root `.env` is local and ignored by Git.
- [ ] Deploy the backend image with FFmpeg and the frontend route, then verify schema creation and `/health`.
- [ ] Run a signed-in, nonbillable flow through create → chat → plan → save. Check 401, 404, 409 and 422 paths. A production GPU render needs a separate explicit decision because the video API starts billable work.
- [ ] Record provider model availability and the operational cost of a full 60-second run; confirm the wallet UI and error copy reflect the actual prices.

**Done when:** the deployed app can persist a plan across sessions, provider keys stay server-side, and a release checklist records the separate real-render result.

## Suggested parallel order

1. Agent A and Agent B start immediately; their file ownership does not overlap.
2. Agent C starts with an isolated `src/concept_media.py` and test fixtures, then coordinates the one-line import integration with Agent A.
3. Agent D prepares secrets and deployment at the same time. Deploy only after A, B and C land and automated checks pass.
4. Run the live render check last, after explicit approval for its charges. Record the final job IDs and output metadata without committing signed URLs or secrets.

## Local verification already run

- `PYTHONPATH=. .venv/bin/pytest -q`: 80 tests pass, including plan validation, the Gemini response adapter, FFmpeg mixed-audio assembly and frame extraction, and isolated PostgreSQL billing and concurrency tests.
- `npm run lint -- --quiet`, `npx tsc --noEmit`, `npm run check:routes`, and `npm run build`: pass when Node 22 is used from `/opt/homebrew/opt/node@22/bin`. The default Homebrew Node 25 binary on this machine currently cannot load its `llhttp` library.
- Earlier checks used Gemini text to complete a clarification turn and produce a valid 10-second scene plan. A live Modal GLM-5.3-Flash concept chat request also produced a valid 10-second plan. No live Gemini image or Modal video request was sent during those checks. Production image behavior and visual quality still need the checks above.
