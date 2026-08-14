# Megado Batch 2 — Track-filtered host slice + alpha metadata (Layer Stack)

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan` (branch `layer-plan`, HEAD 5f7b1803). Execute ONLY this batch. Do NOT broaden scope. Do NOT edit packs/finalizers/planners. Do NOT run the full test suite or formatters. Oracle gates the result.

Environment: `PYENV_VERSION=3.11.11`. Pure Python — no node/remotion needed.

## Context — read FIRST

- `.oracle/plan.md` (Grok's Layer Stack plan, section 1 + Batch 2) + `.oracle/tasklist.md`.
- Batch 1 (d5b960d7 + fe7622c7) added `LayerRef` + `RenderSegment.layer` + per-z cursor. **The contract now accepts overlapping segments on distinct z-layers.**
- Oracle checkpoint 1 PASSED with the note: "B3 compositor must pad short layers (incl. z=0); do not assume an opaque full-span bottom." (Not your concern this batch, but remember it.)

## The change (from the plan)

**Goal:** when a segment has `layer.tracks`, the host-sliced window timeline must contain ONLY that layer's tracks (so a top-layer renderer doesn't see other layers' clips), and segments on `z > 0` get an alpha hint stamped in the materialized timeline's metadata so their renderer emits transparent output (batch 4 consumes it).

### 1. `_window_timeline` — optional track allowlist (service.py ~1097)

Add a keyword parameter, e.g. `tracks: Sequence[str] | None = None`:
- When `tracks` is None (today's behavior, unchanged): keep the existing `used_tracks = {clip.get("track") ...}` pruning.
- When `tracks` is provided (a layer's track ids): filter `raw_tracks` to ONLY those ids (the layer's tracks), and filter `clips` to only clips whose `track` is in the allowlist. (Both the track list AND the clips must be filtered — a renderer must not see other layers' clips even if its track list is pruned.)

### 2. `_segment_request` — pass layer.tracks + stamp alpha metadata (service.py ~1048)

- When `segment.layer is not None`:
  - Pass `tracks=segment.layer.tracks` into the `_window_timeline` call (the host-slicing branch for `supports_windows: false` renderers).
  - Stamp `metadata["astrid_layer"] = {"z": <z>, "alpha": <z > 0>}` into the materialized timeline's `metadata` dict (the timeline `_window_timeline` already copies `metadata`; merge the stamp in, don't clobber existing metadata).
- When `segment.layer is None` (fast path): NO change — today's behavior byte-for-byte.

### 3. No other service changes

- Do NOT touch the dispatch loop, `output_name`, `validate_output_name`, provenance, or the `supports_windows: false` branch's non-layer path.

## Do NOT do (LEAVE)

- No pack/finalizer/planner/manifest edits.
- No `_window_clip` changes (clips in the window still get their at/from/to rewritten the same way).
- No alpha CONSUMPTION (that's batch 4 — renderers read the stamp).
- No changes to the layer=None path.

## Verification

```bash
PYENV_VERSION=3.11.11 python -m pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_contracts.py
```

Add focused NEW tests (a new `test_service_layer_slice.py` or extend test_service.py — your call, name clearly):
1. A window timeline with two visual tracks; segment with `layer={"z":1, "tracks":["v2"]}` → materialized timeline has ONLY track v2 + only v2's clips.
2. `layer=None` segment → materialized timeline unchanged (both tracks, existing pruning behavior).
3. A segment with `layer={"z":1,"tracks":["v2"]}` where v2 has no clips in the window → empty timeline (valid; the renderer renders background/transparent).
4. Metadata stamp: materialized timeline metadata contains `astrid_layer = {"z":1, "alpha":True}` for z>0 and `{"z":0,"alpha":False}` for z=0; existing metadata keys preserved (merged, not clobbered).
5. `layer.tracks` referencing a track that exists in the ORIGINAL timeline but has no clips in the window → track still present in the materialized timeline (the allowlist adds it back even if pruning would've dropped it — verify this is the intended behavior: the renderer must know its layer exists even with no clips).

Commit: `megado: batch 2 — track-filtered host slice + layer alpha metadata`.

## Report
<300 words: the exact service.py changes, new test names + counts, frozen test evidence (test_service + test_contracts pass), commit sha, git status. Evidence-first.
