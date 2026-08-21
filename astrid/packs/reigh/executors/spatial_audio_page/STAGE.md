# Spatial Audio Page Executor

Use `reigh.spatial_audio_page` to build the final viewer: the original video
plays in a pannable/zoomable container; N Foley tracks loop in sync, with each
track's gain driven by the distance between the viewport center and the tile's
anchor rectangle. The original audio is layered on top at a fixed gain.

Output is a self-contained directory: `index.html` plus copies of the original
video and all per-tile audio files. Open `index.html` directly in a browser
(no server required).

Inspect first:

```python
import astrid.sdk as sdk
cap = sdk.get_capability("reigh.spatial_audio_page")
```

Run:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "reigh.spatial_audio_page",
    inputs={"manifest": "runs/foley_map/example/tiles.json"},
    out="runs/foley_map/example/page",
)
```

Manifest must contain a `foley_audio` path on each tile. The executor copies
the source video and audio files into the output directory so the page is
portable.
