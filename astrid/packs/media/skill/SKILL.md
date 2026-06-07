# Media — Agent Guide

## When to Use This Pack

Use when you need to trim a segment from a video file quickly and losslessly
without re-encoding. The pack provides a single ffmpeg stream-copy executor.

## Entrypoints

This pack has no orchestrators. Agents should invoke the executor directly:

```bash
python3 -m astrid executors run media.clip_extract \
  -- --input <video> --start <seconds> --dur <seconds> --output <clip.mp4>
```

## Executors

- **`media.clip_extract`** — Clip extraction via `ffmpeg -ss/-t/-c copy`.
  Inputs: `input` (file), `start` (number), `dur` (number). Outputs: `output`
  (file). Requires `ffmpeg` on PATH.
