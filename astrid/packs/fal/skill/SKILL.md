---
name: fal
description: >
  fal.ai integration for short-clip Foley plus MiniMax H3 text-to-video and
  multimodal reference-to-video generation. Requires FAL_KEY.
---

# fal

The fal pack provides focused executors for hunyuan-video-foley and MiniMax H3.

## Executors

| Executor | What it does |
|---|---|
| `fal.fal_foley` | Send a video clip (≤15s recommended) to fal.ai and receive a Foley audio track matched to the clip's duration. |
| `fal.h3_video` | Generate a 2K MiniMax H3 clip from text or ordered image/video/audio references. |

## When to use

- Use `fal.fal_foley` to generate Foley audio for a single short video clip.
- Use as a leaf executor in spatial Foley pipelines (the `foley` pack's
  `foley_map` orchestrator calls this executor per tile).
- Use `fal.h3_video` when H3's exact fal schema or multimodal reference inputs
  are needed. H3 prompts are limited to 2,000 characters and output duration
  to 5–15 seconds; output resolution is fixed at 2K.

## When NOT to use

- Do not use for orchestrating a full spatial-Foley pass over a whole video —
  use the `foley` pack's `foley_map`.
- For ordinary single-prompt video models already in Astrid's model catalog,
  prefer the `generation` pack.

## Credentials

| Env var | Used by |
|---|---|
| `FAL_KEY` | fal.fal_foley, fal.h3_video |

## CLI quick-start

```bash
python3 -m astrid executors run fal.fal_foley -- --clip ./short_clip.mp4 --out ./foley_audio.mp3
```

```bash
python3 -m astrid executors run fal.h3_video --project <slug> \
  --input mode=text-to-video --input prompt_file=./prompt.txt \
  --input duration=15 --input aspect_ratio=16:9
```
