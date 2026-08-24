# Tile Video Executor

Use `foley.tile_video` when a downstream stage needs spatial sub-clips of a
video (per-region Foley, per-region understanding, per-region edits). Pure
ffmpeg, no network. Output is a `tiles.json` manifest plus N tile clips and N
first-frame PNGs under `{out}/tiles/` and `{out}/frames/`.

Run through the SDK:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "foley.tile_video",
    kind="executor",
    project="demo",
    inputs={
        "video": "path/to/source.mp4",
        "grid": "4x4",
        "overlap": "0.25",
        "trim": "15",
    },
)
```

Internal runner invocation (not a public entrypoint):

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.foley.executors.tile_video.run \
  --video path/to/source.mp4 \
  --out runs/tile_video/example \
  --grid 4x4 --overlap 0.25 --trim 15
```

Manifest shape (`tiles.json`):

```jsonc
{
  "video": "abs/path/source.mp4",
  "video_size": [W, H],
  "duration": 18.79,
  "trimmed_duration": 15.0,
  "fps": 24.0,
  "grid": {"cols": 4, "rows": 4, "overlap": 0.25},
  "tiles": [
    {
      "id": "tile_0_0",
      "row": 0, "col": 0,
      "rect": [x, y, w, h],         // pixels in original video coords
      "rect_norm": [nx, ny, nw, nh], // 0..1 normalized
      "tile_clip": "tiles/0_0.mp4",
      "first_frame": "frames/0_0.png"
    }
  ]
}
```
