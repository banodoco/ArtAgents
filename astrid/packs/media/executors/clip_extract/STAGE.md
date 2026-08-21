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

Via the Astrid SDK (recommended):

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "media.clip_extract",
    inputs={"input": "source.mp4", "start": "10", "dur": "5"},
    out="runs/my_clip",
)
```

Or via `ASTRID_INTERNAL_INVOCATION` for testing:

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.media.executors.clip_extract.run \
  --input source.mp4 --start 10 --dur 5 --output runs/my_clip/clip.mp4
```

## Dependencies

- ffmpeg (system binary)
