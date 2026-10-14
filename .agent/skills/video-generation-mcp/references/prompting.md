# Prompting for this app's video models

Use this reference for both prompt-only requests and prompts sent through `generate_video`. First check `list_video_models` when connected: available modes and settings can change. This file describes how to write the scene, not which API combinations are enabled.

## Shared rules

- Write one self-contained, coherent clip. Put the subject and setting first, followed by observable action in temporal order, camera movement, visual style, and relevant sound.
- Use concrete verbs and a small number of clear action beats. Fit complexity to the selected duration: about one main beat for 5 seconds, two or three for 10 seconds, and up to four for 20 seconds.
- Do not put model names, clip length, aspect ratio, resolution, seed, `inference_steps`, or `guidance_scale` in the prompt. Supply supported settings as separate tool arguments or a separate recommendation.
- Use an image-to-video input as the visual anchor. Describe changes in motion, expression, camera, lighting, or sound; avoid restating fixed visual details from the image. Do not claim an image was inspected unless it was actually available to the agent.
- Avoid contradictory camera moves and dense lists of style adjectives. Keep character appearance, location, and lighting consistent within one clip.
- Return a single paragraph by default. If the user asks for variants, make each variant complete enough to use on its own.

## LTX-2.3 distilled

For text-to-video, state the subject and setting, their spatial relationships, distinctive materials or textures, then a clear action progression and one purposeful camera move. Add specific ambience or dialogue only when the user wants sound. For image-to-video, focus on who or what moves, how it moves, the camera path, and what remains stable. The conditioning image supplies appearance and composition.

When the user gives no duration, 10 seconds is a useful prompting default for LTX; pass it explicitly if it is enabled and fits the request. A short or simple requested action may justify 5 seconds. Do not mention the duration in the prompt. LTX through this MCP tool does not accept `inference_steps` or `guidance_scale`.

Example, text-to-video: `A weathered red fishing boat crosses a quiet lake at dawn, reeds in the foreground and misty hills behind it. The boat leaves a widening wake as the camera slowly tracks alongside; soft wind and water lap against the hull.`

Example, image-to-video with an uploaded lake still: `Ripples spread from the boat as it glides slowly toward the far shore. The camera gently pushes forward while the distant hills remain steady; light wind moves the reeds and water laps softly.`

## Wan 2.2

This app currently exposes Wan as text-to-video; confirm its mode with `list_video_models`. Use a compact sequence of **subject + scene + motion**, then a few compatible style anchors such as shot size, lighting, lens feel, or atmosphere. Describe camera direction and pace explicitly when they matter. Prefer one opening action and one payoff in a short clip. Pass `inference_steps` and `guidance_scale` only as separate tool arguments when supported; there is no negative-prompt field in this MCP tool.

Example: `A courier weaves through a rain-soaked night market while steam rises from food stalls. The camera tracks behind her at walking pace, then eases left as she turns into a narrow lane; neon reflections shimmer across the wet pavement.`

## HunyuanVideo 1.5 and CogVideoX 1.5

Use direct text-to-video prompts with a clearly identifiable subject, setting, one primary action, and one camera move. These models currently have short, text-only profiles in this app; confirm with `list_video_models`. Keep the scene physically plausible and the number of moving subjects small unless the user asks otherwise. Their supported `inference_steps` and `guidance_scale` values are tool arguments, not prompt text.

Example: `A ceramic artist turns a clay bowl on a pottery wheel in a sunlit studio. Her hands lift the rim as the camera slowly moves closer; fine clay dust catches the warm side light.`

## If the requested model is different

If `list_video_models` does not return the requested model, do not send it to `generate_video`. For a prompt-only request, write a model-neutral scene prompt or ask for the intended model when its format matters. For generation, offer an available model with any meaningful change in mode or visual result made clear.
