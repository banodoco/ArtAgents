---
name: foley
description: >
  Spatial Foley pipeline: tile a video into a grid, generate Foley audio
  per tile via fal.ai, review and flag bad tiles, then build a viewer page
  that mixes Foley tracks anchored to spatial rectangles via Web Audio.
---

# Foley

The foley pack covers two executors and one orchestrator that together
form the spatial Foley pipeline.

## Capabilities

| ID | Kind | What it does |
|---|---|---|
| `foley.tile_video` | Executor | Crop a video into an M×N grid of overlapping spatial tiles, emitting one clip and one first-frame PNG per tile, plus a `tiles.json` manifest. |
| `foley.foley_review` | Executor | Build a static `review.html` pairing each tile clip with its generated Foley audio for sense-checking; reviewers flag bad tiles into `flagged.json`. |
| `foley.foley_map` | Orchestrator | The spatial Foley orchestrator: tiles the video, prompts a VLM for per-tile scene descriptions, generates Foley audio per tile via `fal.fal_foley`, runs review, and emits the spatial audio viewer. |

## Spatial Foley pipeline

The canonical Foley pipeline flows through these stages:

```
tile_video → (per-tile Foley generation via fal.fal_foley) → foley_review → foley_map orchestrator → spatial_audio_page
```

1. **`foley.tile_video`** — Crop the source video into an M×N grid of
   overlapping spatial tiles. Produces tile clips, first-frame PNGs, and
   a `tiles.json` manifest with each tile's rectangle in original-video
   coordinates.

2. **Foley generation per tile** — The `foley_map` orchestrator uses a
   vision-language model (`understanding.visual_understand`) to describe
   each tile's scene, then calls `fal.fal_foley` (fal.ai's
   hunyuan-video-foley model) to generate matching Foley audio for each
   tile clip. Requires `FAL_KEY`.

3. **`foley.foley_review`** — Build a static HTML review page that pairs
   each tile clip with its generated Foley audio. Human reviewers can
   flag bad tiles; flags are written to a `flagged.json` sidecar.

4. **`foley.foley_map` orchestrator** — Coordinates the full pipeline:
   tiles the video, dispatches VLM scene descriptions, generates Foley
   per tile, runs the review gate, and emits the final viewer. This is
   the single entry point for the end-to-end spatial Foley workflow.

5. **`reigh.spatial_audio_page`** — Build a self-contained static page
   that plays the original video with N Foley tracks anchored to spatial
   rectangles, mixed live by viewport position via the Web Audio API.
   This lives in the `reigh` pack but is the final step of the Foley
   pipeline.

## When to use

- Use `foley.tile_video` standalone when you only need to grid a video
  into tiles for downstream processing.
- Use `foley.foley_review` standalone when you have generated Foley audio
  that needs human sense-checking against the tile clips.
- Use `foley.foley_map` as the single entry point for the full spatial
  Foley pipeline — from source video to interactive viewer.

## Credentials

| Env var | Used by |
|---|---|
| `FAL_KEY` | `fal.fal_foley` (called by foley_map orchestrator) |
| `OPENAI_API_KEY` | VLM scene description step in foley_map |

## SDK quick-start

```python
import astrid.sdk as sdk

# Run tile_video standalone
result = sdk.invoke(
    "foley.tile_video",
    inputs={"video": "./input.mp4"},
    out="./tiles",
)

# Run foley_review standalone
result = sdk.invoke(
    "foley.foley_review",
    inputs={"manifest": "./tiles/tiles.json"},
    out="./review",
)

# Run the full spatial Foley pipeline (orchestrator)
result = sdk.invoke(
    "foley.foley_map",
    inputs={"video": "./input.mp4"},
    out="./foley-run",
)
```
