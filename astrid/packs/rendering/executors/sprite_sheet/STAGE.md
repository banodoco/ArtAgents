# Sprite Sheet Executor

Use `rendering.sprite_sheet` to create animation sprite sheets and sliced frame
previews from a subject plus animation description.

Dry-run first:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.sprite_sheet",
    inputs={"animation": "wave", "subject": "neon courier"},
    out="runs/sprites/wave",
    dry_run=True,
)
```

To preserve a specific character or object, pass a reference image. The
executor sends the reference image to the image-edit endpoint, keeps grid
instructions in the prompt, then uses the existing slice/preview/export path:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.sprite_sheet",
    inputs={
        "animation": "right claw pincer open-close snap loop",
        "subject": "blue circuit crab mascot",
        "reference_image": "refs/crab.png",
    },
    out="runs/sprites/crab-pincer",
)
```

Requires image API credentials for generation and `ffmpeg` for slicing/preview
exports.

## Outputs

Expected files include:

- `{out}/sprite_manifest.json`
- `{out}/sprite_sheet.png`
- `{out}/sprite_sheet_alpha.png`
- `{out}/frames/frame_001.png` and sibling frame PNGs
- `{out}/sprite_preview.mp4`
- `{out}/web/sprite_sheet.webp` and web preview outputs when web export is enabled

Safety-edge warnings mean one or more sliced frames touch the configured edge
margin. Treat that as a soft QA warning for prototypes and a prompt/layout retry
signal for production sprites.
