# media.clip_extract

## Purpose

Extract a clip segment from a source video using ffmpeg with stream copy (`-c copy`)
for fast, lossless extraction. Use when you need to trim a video to a specific
start time and duration without re-encoding.

This executor invokes ffmpeg for real via an injectable `runner` callable
(default: `subprocess.run`).  Return codes are propagated: 0 on success,
nonzero on ffmpeg failure or validation errors.

## Inputs

- `input` (file, required): Source video file path.
- `start` (number, required): Start time in seconds.
- `dur` (number, required): Duration in seconds.

## Outputs

- `output` (file): The clipped video file, written to `{out}/clip.mp4`.

## Canonical Command

```bash
# Via the Astrid runner (recommended):
python3 -m astrid executors run media.clip_extract \
  --input source.mp4 --start 10 --dur 5 --out runs/my_clip

# Or via ASTRID_INTERNAL_INVOCATION for testing:
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.media.executors.clip_extract.run \
  --input source.mp4 --start 10 --dur 5 --output runs/my_clip/clip.mp4
```

## Dependencies

- ffmpeg (system binary)
