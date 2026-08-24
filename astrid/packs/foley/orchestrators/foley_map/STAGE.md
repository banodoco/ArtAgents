# Foley Map Orchestrator

Use `foley.foley_map` to turn one video into a spatial Foley soundscape: the
original video plays in the browser, with N Foley tracks anchored to spatial
regions of the frame, mixed by viewport position.

Pipeline:

1. **`foley.tile_video`** — split the video into an MxN grid of overlapping
   tile clips + first-frame PNGs.
2. **`understanding.visual_understand`** on the global first frame → one-paragraph
   scene description used as shared context.
3. **`understanding.visual_understand`** on each tile's first frame, with the global
   context injected → a focused Foley prompt per tile.
4. **`fal.fal_foley`** for each tile clip + prompt → one audio file per
   tile.
5. **`foley.foley_review`** → static review page for sense-checking. Pause
   here, eyeball the tracks, optionally re-run with `--retry-flagged`.
6. **`reigh.spatial_audio_page`** → final viewer page.

Dry-run (no API calls; writes the plan + tile crops + frames):

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "foley.foley_map",
        kind="orchestrator", project="demo",
    orchestrator_args=(
        "--video", "~/Downloads/DeepSeaBaby_444_TurbulentDisplace.mp4",
        "--grid", "4x4", "--overlap", "0.25", "--trim", "15",
    ),
    dry_run=True,
)
```

Run end-to-end:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "foley.foley_map",
        kind="orchestrator", project="demo",
    orchestrator_args=(
        "--video", "~/Downloads/DeepSeaBaby_444_TurbulentDisplace.mp4",
        "--grid", "4x4", "--overlap", "0.25", "--trim", "15",
        "--env-file", ".env",
    ),
)
```

Stop after Foley + review (skip the final viewer):

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "foley.foley_map",
        kind="orchestrator", project="demo",
    orchestrator_args=("--video", "...", "--stop-after", "review"),
)
```

Re-roll only tiles flagged in `flagged.json` (downloaded from `review.html`):

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "foley.foley_map",
        kind="orchestrator", project="demo",
    orchestrator_args=(
        "--video", "...",
        "--retry-flagged", "runs/foley_map/deepsea/flagged.json",
    ),
)
```

Cost: 16 tiles × ~$0.10 per 10s ≈ ~$30/pass at trim=15, plus 17 cheap VLM
calls. Reruns are content-cached: tiles with unchanged `(clip_hash, prompt)`
won't re-call fal.

Outputs (under `--out`):

```
tiles.json              # final manifest with prompts and audio paths
tiles/<r>_<c>.mp4       # per-tile video (input to Foley)
frames/<r>_<c>.png      # per-tile first frame (input to VLM)
frames/global.png       # global first frame
prompts.json            # global context + per-tile prompts
audio/<r>_<c>.wav       # per-tile Foley audio
review.html             # sense-check page
page/index.html         # final spatial-audio viewer
```
