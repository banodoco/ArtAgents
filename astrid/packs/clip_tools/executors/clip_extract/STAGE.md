# clip_tools.clip_extract

## Purpose

Extract a segment from a source video using `ffmpeg -ss` (start time) and `-t` (duration) with stream copy (`-c copy`) for lossless, fast extraction. No re-encoding.

## Inputs

- `input` (file, required): Source video file path.
- `start` (number, required): Start time in seconds.
- `dur` (number, required): Duration in seconds.

## Outputs

- `output` (file): The clipped video file, written to `{out}/clip.mp4`.

## Dependencies

- `ffmpeg` must be on PATH.
