---
name: fal
description: >
  fal.ai integration — generates Foley audio for short video clips via
  fal.ai's hunyuan-video-foley model.  Single-executor pack requiring
  FAL_KEY for API authentication.
---

# fal

The fal pack provides a single executor that calls fal.ai's hunyuan-video-foley
model to synthesize a Foley audio track for a short video clip.

## Executors

| Executor | What it does |
|---|---|
| `fal.fal_foley` | Send a video clip (≤15s recommended) to fal.ai and receive a Foley audio track matched to the clip's duration. |

## When to use

- Use `fal.fal_foley` to generate Foley audio for a single short video clip.
- Use as a leaf executor in spatial Foley pipelines (the `foley` pack's
  `foley_map` orchestrator calls this executor per tile).

## When NOT to use

- Do not use for orchestrating a full spatial-Foley pass over a whole video —
  use the `foley` pack's `foley_map`.
- Do not use for image or video frame generation — use the `generation` pack.

## Credentials

| Env var | Used by |
|---|---|
| `FAL_KEY` | fal.fal_foley (fal.ai API authentication) |

## CLI quick-start

```bash
python3 -m astrid executors run fal.fal_foley -- --clip ./short_clip.mp4 --out ./foley_audio.mp3
```
