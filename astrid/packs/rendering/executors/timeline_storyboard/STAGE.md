# Timeline Storyboard

Use `rendering.timeline_storyboard` to inspect the image inputs associated with
timeline pinned shots without rendering video or mutating the timeline.

The executor reads `pinnedShotGroups`, member clips, and the separate asset
registry. It resolves inputs in this order:

1. Ordered `clip.generation.references` entries using `asset`, `assetKey`, or
   `id`.
2. Discord-compatible `clip.generation.input_media`,
   `input_media_2` … `input_media_10`.
3. Ordered member clip assets for `mode: "images"`.
4. `imageClipSnapshot[].assetKey` for `mode: "video"`.

`asset:<id>` and bare registry ids are both accepted. Broken references remain
visible as missing-image placeholders.

Build all pinned shots:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.timeline_storyboard",
    inputs={"timeline": "path/to/timeline.json", "assets_registry": "path/to/assets.json"},
    out="runs/timeline-storyboard",
)
```

Build one shot:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.timeline_storyboard",
    inputs={
        "timeline": "path/to/timeline.json",
        "assets_registry": "path/to/assets.json",
        "shot_id": "shot-1",
    },
    out="runs/timeline-storyboard",
)
```

Outputs:

- `preview.json` — normalized shot/range and input-image view model.
- `preview.png` — deterministic two-column contact sheet with numbered image
  cards and visible missing-image placeholders.
- `preview.html` — static responsive two-column storyboard.
- `manifest.json` — universal result-manifest sidecar.

The executor starts no server and never writes to the timeline or asset
registry.
