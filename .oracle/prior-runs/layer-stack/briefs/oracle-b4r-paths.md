# Oracle Batch 4 REWORK — path-binding + compositor resolution

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit 70c5cdee. Read-only. Cite file:line. <350 words. Do not implement.

Question: when remotion/threejs remaps `segment-NNNN.mp4` → `segment-NNNN.mov` inside the backend, does the compositor/concat finalizer still find the file?

## Trace this exact flow

1. Service (`astrid/core/rendering/service.py`):
   - Where `output_name=f"segment-{index:04d}.mp4"` is set. Quote.
   - After the backend returns, what does the service store as the artifact path? Quote the check that compares result path vs request.output_name (if any).
   - If basename differs, does service reject, rewrite, or accept the returned path?

2. Backend result construction (`remotion/run.py` and `threejs/run.py`):
   - What path is put on `RenderResult` / artifact (`video.path`)? The remapped `.mov` or the original `.mp4`?
   - Is `request.output_name` mutated or only the local `output_name` variable?

3. Planner/layer plan: does the layer record store `segment-NNNN.mp4` from the request, or the artifact's actual path?

4. Compositor (`astrid/packs/rendering/finalizers/compositor/run.py`):
   - How is `layer.path` resolved? From the artifact record, from a hardcoded `.mp4`, or from plan JSON?
   - Any extension allowlist that would reject `.mov`?
   - Quote `_safe_protocol_output_path` / layer path usage.
   - `_layer_has_alpha`: would yuva444p12le prores already count? Quote.

5. Concat finalizer: same question — does it look up artifacts by the declared path?

Answer YES or NO: "a stamped remotion/threejs segment rendered as .mov will be found by the compositor/finalizer without service/dispatch changes."

If NO, name the exact mismatch (which writer writes .mp4, which reader looks for .mov).
