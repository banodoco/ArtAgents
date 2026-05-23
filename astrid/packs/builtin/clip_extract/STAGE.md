# Clip Extract

Extract a segment from a source video using `ffmpeg -ss` (start time) and `-t` (duration) with stream copy (`-c copy`) for lossless, fast extraction. No re-encoding.

## Pipeline

1. **Validate** — confirm the source file exists; resolve start/duration to seconds.
2. **Extract** — `ffmpeg -ss <start> -i <src> -t <duration> -c copy <out>`.
3. **Emit** — write the extracted clip to the output path and record its duration in the manifest.
