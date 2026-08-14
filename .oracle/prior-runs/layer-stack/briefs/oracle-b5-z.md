# Oracle Batch 5 — z-convention / LayerRef / stamp contract

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit: f9f8c120. Read-only. Do not edit. Cite file:line. <400 words.

This is the critical cross-batch contract. Answer YES/NO with evidence.

Batch 2 (PASSED): service `_segment_request` stamps `metadata.astrid_layer` for `z>0`. z=0 is NOT stamped (opaque). Stamped remotion/threejs emit ProRes 4444 `.mov` with a real alpha plane.

Batch 3 (PASSED): compositor overlays by z order. Lowest z is bottom; highest z is top. `overlay=0:0:format=auto`. Opacity via colorchannelmixer. Frame count = plan.total_frames.

Visual-track paint order (Remotion / AGENTS.md): `tracks` array reversed — FIRST visual track in `timeline.tracks` is the TOP layer.

## Do this

1. LayerRef emission in `astrid/packs/rendering/planners/layer_stack/run.py`:
   - How is `z` assigned? Quote. First visual track = highest z or lowest z?
   - What is in `layer.tracks` per segment?
   - What `opacity` / `blend` are written?

2. Service stamp (do not assume — read current `astrid/core/rendering/service.py`):
   - Exact condition for `metadata.astrid_layer` stamp. Is it `z>0`?
   - Therefore: which z is opaque (unstamped, h264) and which z(s) get ProRes alpha?

3. Compositor order (current `astrid/packs/rendering/finalizers/compositor/run.py`):
   - Are layers sorted by z ascending (paint bottom→top)?
   - Does highest-z land last in the overlay chain (visually on top)?

4. CONTRACT CHECK — answer each:
   - If planner assigns first visual track the HIGHEST z, then first visual (the Remotion TOP) is stamped alpha. Correct for overlay-on-top?
   - If planner assigns first visual track z=0, then the visual TOP is opaque unstamped and a lower track gets alpha. That is a CONTRACT BUG.
   - Fast path `layer=None`: no stamp, concat, remotion jpeg/h264. Confirm planner emits layer=None (not z=0 LayerRef) on remotion-capable full stack.

5. Tests: does any B5 test assert the actual z numbers / which track is highest z / that the top overlay is the one with z>0? Quote.

6. Forced-split case (overlay track + source track, threejs+ffmpeg registry): which track gets which z? Which renderer? Which will be stamped?

## Report shape

```
Z-ASSIGN: first-visual = highest|lowest — formula + line
TRACKS: layer.tracks contents
BLEND/OPACITY: written fields
STAMP: condition (z>0?) — z=0 opaque? z>0 ProRes?
COMPOSITOR: sort order — highest last?
CONTRACT: OK | BUG — one sentence
FAST-NONE: layer=None on remotion full-stack? Y/N
TEST-Z: asserted? Y/N — what
SPLIT-CASE: overlay-z= / source-z= / who-stamped
```
