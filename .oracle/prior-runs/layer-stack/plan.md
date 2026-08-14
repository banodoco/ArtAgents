# Layer Stack — architecture + implementation plan

A layer is one renderer-owned contiguous visual-track range, stacked in z,
composited once. The timeline already stores the stack. The render contract
currently forbids it. This plan opens that contract the smallest amount that
lets renderers stack — not an AE clone.

## 1. Architecture decision

**Name:** Layer Stack

**One-sentence model:** `RenderSegment.layer` is an optional `LayerRef`; the
plan tiles in time *per z*; cross-z overlap is stacking; a new finalizer
does one bottom→top `overlay` pass; today's concat path is unchanged when
there is only one layer.

```
timeline.tracks[]  ──paint──►  first visual = TOP (unchanged)
        │
        ▼
 rendering.layer-stack
   1. any renderer supports the full visual stack? → one segment, layer=None,
      p# Layer Stack

A layer is one renderer-owned contiguous visual-track range. The timeline already stores the stack. The render contract currently forbids it. Open the contract just enough that renderers can stack — not an AE clone.

Written to `.oracle/plan.md` and `.oracle/tasklist.md`.

## 1. Architecture

```
timeline.tracks[]  ──paint──►  first visual = TOP (unchanged)
        │
        ▼
 rendering.layer-stack
   1. any renderer supports the full visual stack?
        → one segment, layer=None, pin ffmpeg-finalizer     ← FAST PATH
   2. else claim each visual track via registry support(),
      greedy-merge adjacent tracks won by the same renderer,
      emit one full-window segment per layer,
      pin rendering.ffmpeg-compositor
        │
        ▼
 service renders N segments independently (already can)
   _window_timeline keeps only layer.tracks
   z>0 stamps metadata.astrid_layer.alpha; renderer skips theme bg
        │
        ▼
 ffmpeg-compositor
   dst = bottom (opaque)
   for src in layers by z: dst ← overlay(src, dst, opacity)
   mux audio from the owning (usually bottom) artifact
   H.264 yuv420p AAC → public .mp4
```

**The only new type:**

```python
@dataclass(frozen=True)
class LayerRef:
    z: int                      # 0 = bottom; tiling key
    tracks: tuple[str, ...]     # visual track ids this layer owns
    blend: str = "normal"       # v1: only "normal"
    opacity: float = 1.0        # compositor applies aa=
```

`RenderSegment.layer: LayerRef | None = None`

| Rule | Why |
|---|---|
| `layer` is None on **every** segment, or on **none** | Mixing implicit/explicit z is a second tiling axis |
| Cursor is `dict[z\|None → expected_start]` | Same-z overlap still illegal; cross-z overlap is the feature |
| `FrameWindow` stays time-only | Layering is a segment concern |
| Fast path emits `layer=None` | Compositor is not a new default |
| Distinct-z ≥ 2 → pin compositor | That's the only time stacking exists |
| Planner v1: one full-window segment per z | Intra-layer time-slicing is allowed by the contract, unused |
| Compositor v1: one segment per z, windows == plan window | Filtergraph is a loop, not a scheduler |

**F6 correction.** Dispatch, provenance, FinalizeRequest 1:1, and manifest schemas stay. The hole F6 missed: `_window_timeline` (service.py:1117–1121) keeps every clip in the window, so two same-window layers would both get the full stack. The one justified service edit is in `_segment_request` / `_window_timeline` — already receives `segment`; honor `layer.tracks`; stamp alpha metadata for `z>0`. Do not change the dispatch loop, `output_name`, or `validate_output_name`. Intermediate alpha may be VP9/yuva bytes at `segment-NNNN.mp4`; compositor probes and decodes with `libvpx-vp9`.

**Blend modes: do not ship.** User intent is src-over + alpha, not multiply/screen. The 8 schema modes have never been consumed. `LayerRef.blend` exists, accepts only `"normal"`, compositor uses `overlay`. `track.blendMode ≠ normal` → planner fails closed. Opacity is `colorchannelmixer=aa=`.

**N>2 is free** (the merge pass is a loop). Do not cap the contract or compositor at 2. The first product will usually be 2; that is an outcome, not a limit.

**Planner is new and opt-in** (`rendering.layer-stack`). Do not replace `legacy_hybrid` / `threejs_hybrid` (those are temporal split). Routing is registry `support()`, not `_complex_frame_windows`. Audio stays a parallel axis; overlay audio is discarded.

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

## 3. LEAVE

- AE blend-mode matrix, track mattes, nesting, adjustment layers
- Clip-level `blendMode`; clip `opacity≠1` stays renderer-rejected
- `FrameWindow` layer fields; `RenderPlan` layer registry
- Structured `SupportReport.features` (keep `bool|str`)
- Dispatch rewrite, provenance.py, FinalizeRequest 1:1, `validate_output_name`, public container
- Making `layer-stack` the default planner
- Combining temporal hybrid + spatial stack; replacing the existing hybrids
- Intra-layer time-slicing in v1 planner/compositor (contract allows, v1 does not emit)
- Per-window intra-layer overlaps
- Cap at 2 layers
- Hyperframes alpha; Ray / Anyscale / distributed layer DAGs
- Teaching every renderer `supports_windows: true` to dodge host-slicing
- CSS `mix-blend-mode` / remotion-internal inter-engine composite
- Audio spatially mixed; background-as-track

## 4. Risks

| Risk | Catch |
|---|---|
| Overlapping layers double-count via concat `sum(duration)` | Compositor uses `plan.total_frames`. Test both. |
| Native VP9 decode drops alpha | Always `-c:v libvpx-vp9` on alpha inputs. Probe `yuva*`. |
| Premultiplied vs straight | `overlay` default = straight. Do not pass `alpha=premultiplied`. |
| Same-window layers see every track | B2 asserts materialized track ids == `layer.tracks`. |
| `plan.json` `additionalProperties: false` | Add `layer` in the same commit as the dataclass. |
| `test_freeze.py:396-398` exact id sets | Update only in the batch that registers the new id. |
| Upper remotion still paints theme bg | B4 still-proof: corner alpha == 0. |
| Accidental default-planner switch | `layer-stack` is opt-in; default-selection tests stay green. |
core/rendering/test_freeze.py tests/packs/rendering/test_ffmpeg_finalizer.py`
- **B4** `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_threejs_backend.py`
- **B5** `pytest -q tests/core/rendering/test_layer_stack.py tests/core/rendering/test_threejs_hybrid.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_freeze.py`
- **B6** one real stacked render (ffprobe + pixel proof + sidecar) then
  `pytest -q tests/core/rendering tests/packs/rendering` and
  `ruff check astrid tests` (baseline 1469, no new findings).
  `test_schema_contract.py` pre-existing failures: do not touch.

## 5. Risks

| Risk | Catch |
|---|---|
| Overlapping layers double-count in concat `sum(duration)` | Compositor uses `plan.total_frames`, never the sum. Test both. |
| Native VP9 decode drops alpha | Always `-c:v libvpx-vp9` on alpha inputs. Probe `yuva*`. |
| Premultiplied vs straight | `overlay` default = straight. Do not pass `alpha=premultiplied`. PNG/Remotion stills are straight. |
| Same-window layers see every track | B2 asserts materialized timeline track ids == `layer.tracks`. |
| `plan.json` `additionalProperties: false` rejects `layer` | Add the field in the same commit as the dataclass. Plans validate via dataclasses at transport, but the wire schema must match. |
| `test_freeze.py:396-398` exact finalizer/planner sets | Update only those frozen id sets, in the batch that registers the new id. |
| `test_contracts.py:600-603` exact segment key set | Allow `layer` when present; `layer=None` omits the key (fast-path bytes stay `{window,renderer,input_hashes}`). |
| Upper remotion still paints theme bg → opaque overlay | B4 still-proof: corner pixel alpha == 0. |
| Filtergraph scale/fps mismatch | Compositor scales every input to plan profile; `fps`+`setpts` align. |
| Ruff creep | `ruff check` vs 1469 at B6. |
| Accidental default-planner switch | `layer-stack` is opt-in; default selection tests stay green. |
