# Media — Agent Guide

## When to Use This Pack

Use when you need to trim a segment from a video file quickly and losslessly
without re-encoding. The pack provides a single ffmpeg stream-copy executor.

## Entrypoints

This pack has no orchestrators. Agents should invoke the executor directly via
the SDK:

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

- **`media.clip_extract`** — Clip extraction via `ffmpeg -ss/-t/-c copy`.
  Inputs: `input` (file), `start` (number), `dur` (number). Outputs: `output`
  (file). Requires `ffmpeg` on PATH.
