# iteration.clip_extract

## Purpose

Extract a clip segment from a source video using ffmpeg with stream copy (`-c copy`)
for fast, lossless extraction. Use when you need to trim a video to a specific
start time and duration without re-encoding.

## Inputs

- `input` (file, required): Source video file path.
- `start` (number, required): Start time in seconds.
- `dur` (number, required): Duration in seconds.

## Outputs

- `output` (file): The clipped video file, written to `{out}/clip.mp4`.

## Canonical Command

```bash
python3 -m astrid executors run iteration.clip_extract \
  --input source.mp4 --start 10 --dur 5 --out runs/my_clip
```

## Dependencies

- ffmpeg (system binary)
