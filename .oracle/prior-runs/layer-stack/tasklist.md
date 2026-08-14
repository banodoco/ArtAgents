# Tasklist: Layer Stack (generalized renderer stacking)

Frozen. Architecture: RenderSegment.layer (optional LayerRef), per-z tiling,
track-filtered host slices, rendering.ffmpeg-compositor, alpha_output on
remotion+threejs, opt-in rendering.layer-stack planner. Single-layer fast path
unchanged (layer=None -> concat). Blend modes NOT shipped (src-over + alpha
only). Zero changes to dispatch/provenance/FinalizeRequest 1:1/validate_output_name.

Constraint: no ruff findings above 1469; test_schema_contract.py untouched.
## 2. Batches

Do not start N+1 until N passes.

### Batch 1 — Per-layer plan contract `[XHARD]`
`LayerRef` + optional `RenderSegment.layer` + per-z cursor in `RenderPlan.__post_init__` + `plan.json` field. `to_dict` omits `layer` when None (fast-path key set stays `{window,renderer,input_hashes}`).

**Checkpoint:** distinct-z overlap parses; `layer=None` still rejects overlap/gap/out-of-order; `blend≠normal` rejected; no service/pack edits.

**Verify:** `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_provenance.py`

### Batch 2 — Track-filtered host slice
`_window_timeline` takes an optional track allowlist. `_segment_request` passes `layer.tracks` and stamps `metadata.astrid_layer` for `z>0`. Dispatch/provenance/`output_name` untouched.

**Checkpoint:** same-window segments receive disjoint track slices; `layer=None` prune is unchanged.

**Verify:** `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_contracts.py`

### Batch 3 — `rendering.ffmpeg-compositor` `[XHARD]`
New finalizer. Filtergraph: `libvpx-vp9` on alpha inputs, `scale`/`fps`/`setpts`, `overlay=format=auto` (straight alpha), opacity via `colorchannelmixer`. Frame count = `plan.total_frames`, **never** `sum(durations)`. Audio from the owning artifact.

**Checkpoint:** synthetic opaque-bottom + yuva-top composites; concat finalizer unchanged; `support()` rejects `layer=None` / mixed windows / `<2` z.

**Verify:** `pytest -q tests/packs/rendering/test_ffmpeg_compositor.py tests/packs/rendering/test_ffmpeg_finalizer.py tests/core/rendering/test_freeze.py`

### Batch 4 — Alpha output on remotion + threejs
Honor the stamp only: remotion `--image-format=png --pixel-format=yuva420p --codec=vp9`; threejs skips `<color attach="background">`. `features.alpha_output: true`. Default jpeg/h264 path untouched. `remotion.config.ts` stays jpeg.

**Checkpoint:** unstamped = yuv420p; stamped = alpha plane; text-only corner alpha == 0.

**Verify:** `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_threejs_backend.py`

### Batch 5 — `rendering.layer-stack` planner `[XHARD]`
Registry `support()` routing. Full-stack support → fast path. Else per-track claim + greedy adjacent merge. Fail closed on `blendMode≠normal` and unsupported tracks.

**Checkpoint:** remotion-capable timeline → one `layer=None` segment + concat; ffmpeg media + text → two full-window segments + compositor; hybrids untouched.

**Verify:** `pytest -q tests/core/rendering/test_layer_stack.py tests/core/rendering/test_threejs_hybrid.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_freeze.py`

### Batch 6 — Real stack + docs + gate
One real 2-layer render (ffprobe + pixel proof + sidecar). Remotion-only still takes concat. Docs: `docs/reference/layer-stack.md` + a short section in `render-backend-v1.md`. Ruff ≤ 1469. Wheel contains the new planner and finalizer.

**Verify:** `pytest -q tests/core/rendering tests/packs/rendering` · `ruff check astrid tests` · wheel inspect. Do not touch `test_schema_contract.py`.

