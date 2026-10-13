# Marketing video prompt set

Ten original animated scenes were written for this app's four enabled text-to-video models. The prompt wording follows published guidance to describe a visible subject, a concrete action, and one simple camera movement. The LTX prompts also follow the repository's LTX-2.3 reference and keep motion to one readable beat for a five-second clip.

Research sources:

- [Runway Academy prompting guide](https://academy.runwayml.com/guides/prompting-guide) — visual and motion components, including camera work and progression.
- [Runway text-to-video prompting guide](https://help.runwayml.com/hc/en-us/articles/42460036199443-Text-to-Video-Prompting-Guide) — clear visual descriptions and observable movement.
- [Runway camera terms and examples](https://help.runwayml.com/hc/en-us/articles/47313504791059-Camera-Terms-Prompts-Examples) — camera movement vocabulary.
- [LTX-2.3 prompting reference](../.agent/skills/video-prompting/references/models/ltx2-3/prompting.md) and [Wan 2.2 prompting reference](../.agent/skills/video-prompting/references/models/wan22/prompting.md) — model-specific direction used in this repository.

The exact prompts, selected models, seeds, job IDs, statuses, output paths, and estimated GPU runtime costs are recorded in [`marketing_videos.json`](marketing_videos.json) by [`generate_marketing_videos.py`](../scripts/generate_marketing_videos.py). The scene set is Paper City, Clay Astronaut, Watercolor Koi, Robot Garden, Balloon Voyage, Pixel Train, Ink Fox, Knitted Whale, Isometric Market, and Glass Butterfly. Each request is five seconds at that model's enabled resolution and default parameters.

## Gemini key-art posters

Each showcase card needs a poster image, and the brief also asked for Gemini to be used for idea and image generation. [`generate_gemini_posters.py`](../scripts/generate_gemini_posters.py) covers both:

1. **Idea step** — `gemini-3.8-flash` turns every clip's video prompt into a key-art brief (hero composition, palette, thumbnail-readable focal subject, no text).
2. **Image step** — `gemini-3.1-flash-image` renders each brief as a 16:9 landscape poster, resized to a 1280-px JPEG, saved as `frontend/public/videos/<slug>.jpg` next to its MP4.

All ten posters come from the same Gemini pass so the gallery stays visually consistent. The `knitted-whale.mp4` artifact is 67 KB because its flat pastel yarn scene compresses extremely well; a full ffmpeg decode pass (`probe_marketing_videos.py`) confirms every clip is a complete, playable file.

## LTX image-to-video refresh and the landscape 720p additions

The first ten clips were later re-rendered as **LTX-2.3 image-to-video**: each clip's Gemini poster is uploaded through the asset flow and used as the conditioning frame, so every video replicates its key art while the prompt adds one motion beat and one camera move ([`rerender_showcase_ltx_i2v.py`](../scripts/rerender_showcase_ltx_i2v.py)). Robot Garden was re-rendered the same way earlier via [`rerender_robot_garden_ltx.py`](../scripts/rerender_robot_garden_ltx.py); the superseded CogVideoX and portrait renders remain in `outputs/`.

Because the previously deployed LTX worker rendered a fixed portrait 512×896 regardless of input, the worker was redeployed from this repository's `modal_app.py` under the API's expected app name `video-pipeline-ltx-23`, with text-to-video at 768×512 and image-to-video following the input aspect. A `720p` preset (1280×704 landscape for i2v) was added to `src/config.py` and verified with [`verify_landscape_worker.py`](../scripts/verify_landscape_worker.py). Five new scenes — Origami Dragon, Neon Jellyfish, Chalk Village, Felt Campfire, and Toy Carousel — were then produced in landscape 720p by [`add_landscape_showcase.py`](../scripts/add_landscape_showcase.py) with the same Gemini idea-plus-poster pipeline, bringing the showcase to fifteen clips.
