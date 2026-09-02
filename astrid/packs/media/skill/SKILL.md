---
name: media
description: >
  Media pack — lossless clip extraction, GIF and sticker search, and weak-mic
  speech repair for downstream timeline and media workflows.
---

# Media — Agent Guide

## When to Use This Pack

Use this pack for lossless clip extraction, GIF or sticker lookup, and repair
of weak-mic speech before it is used in downstream media workflows.

## Entrypoints

This pack has no orchestrators. Agents should invoke one of its executors
directly through the SDK:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "media.clip_extract",
    inputs={
        "input": "<video>",
        "start": "<seconds>",
        "dur": "<seconds>",
        "output": "<clip.mp4>",
    },
)
```

## Executors

| Executor | What it does |
|---|---|
| `media.clip_extract` | Extract a video segment with `ffmpeg -ss/-t/-c copy` without re-encoding. Inputs: `input`, `start`, `dur`, and `output`. Requires `ffmpeg` on PATH. |
| `media.gif_search` | Search GIPHY for GIF or sticker assets and optionally download one rendition for timeline use. |
| `media.speech_repair_lavasr` | Extract a video section, repair weak speech with fal.ai LavaSR, then remux and loudness-master the result. |
