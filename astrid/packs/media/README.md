# Media

Lossless video clip extraction via ffmpeg stream copy.

## Executors

| Executor | Purpose |
|---|---|
| `media.clip_extract` | Extract a clip segment from a video using `ffmpeg -ss/-t/-c copy`. |

## Quick Start

```bash
python3 -m astrid executors run media.clip_extract \
  -- --input source.mp4 --start 10 --dur 5 --output runs/my_clip/clip.mp4
```

Requires `ffmpeg` on the system PATH.
