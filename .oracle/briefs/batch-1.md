# Megado Batch 1 — Per-layer plan contract (Layer Stack)

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan` (branch `layer-plan`, HEAD 4c00b2a0). Execute ONLY this batch. Do NOT broaden scope. Do NOT edit the service, packs, or finalizers. Do NOT run the full test suite or formatters. The oracle gates the result.

Environment: `PYENV_VERSION=3.11.11` for python/pytest. This batch is pure Python (contracts) — no node/remotion needed.

## Context — read FIRST

- `.oracle/plan.md` (Grok's Layer Stack plan, sections 1 + Batch 1) and `.oracle/tasklist.md`.
- The swarm findings at `.oracle/findings/02-contract-gap.txt` and `06-core-change-surface.txt` — the exact contract surface.
- This is the FIRST deliberate `astrid/core/` change in the project's rendering history (the pluggable-renderer promise held for 2 epics; layering needs the contract to grow). Keep it MINIMAL and surgical.

## The change (from the plan)

**Goal:** let a `RenderPlan` carry segments that overlap in TIME when they belong to DIFFERENT z-layers, while preserving exact per-layer tiling and the existing fast path.

### 1. `LayerRef` — the only new type (contracts.py)

```python
@dataclass(frozen=True)
class LayerRef:
    z: int                       # 0 = bottom; the tiling key
    tracks: tuple[str, ...]      # visual track ids this layer owns
    blend: str = "normal"        # v1: ONLY "normal" accepted
    opacity: float = 1.0         # compositor applies aa= (batch 3)
```

- `z >= 0` (validate); `tracks` non-empty tuple of non-empty strings (validate); `blend` must be exactly `"normal"` in v1 (reject anything else with a clear error); `opacity` must be `0 < opacity <= 1` (validate).
- Needs `to_dict()` / `from_dict()` (round-trip) — mirror the existing dataclass serialization patterns in contracts.py.

### 2. `RenderSegment.layer: LayerRef | None = None` (contracts.py ~1306)

- Add the optional field AFTER `input_hashes` (default None).
- `to_dict`: **omit `layer` entirely when None** — the fast-path key set stays exactly `{window, renderer, input_hashes}` (frozen test test_contracts.py:600-603 asserts this; `layer=None` must NOT add a key).
- `from_dict`: accept an optional `layer` key; validate via LayerRef.from_dict when present; reject unknown keys as before (add `layer` to the allowed set).

### 3. Per-z cursor in `RenderPlan.__post_init__` (contracts.py ~1429-1445)

Replace the single `expected_start` cursor with a **per-layer cursor**:

```python
cursors: dict[int | None, int] = {}   # layer.z -> expected_start, None -> default layer
```

Rules:
- Every segment has `layer` either ALL None or ALL set (mixing implicit/explicit z is a second tiling axis — reject with a clear error naming the violation).
- Segments with `layer=None` tile against cursor `None` (exactly today's behavior: overlap → "overlaps or is out of order", gap → "leaves a gap", trailing → "trailing gap").
- Segments with `layer=LayerRef(z)` tile per-z: same-z overlap/gap still illegal; **cross-z overlap is the feature (allowed)**.
- Keep the global checks: FPS must match canonical profile FPS (all segments); `end_frame` must not exceed the plan target window.
- The trailing-gap check: each cursor (per z AND None) must land on `target_end` when that layer was used... careful: a layer with NO segments doesn't need to reach target_end. Only layers that HAVE segments must tile exactly to target_end. (Default layer None counts as a layer.)
- Error messages: keep the existing wording for the None layer; for explicit z use `segments[i] layer z=<z> <relation> at frame <expected>`.

### 4. `schemas/v1/plan.json` — add `layer`

Find the `renderSegment` schema (plan.json ~552, `additionalProperties: false`) and add an optional `layer` object property:
```
layer: { type: object, properties: { z: {type: integer, minimum: 0}, tracks: {type: array, items: {type: string}, minItems: 1}, blend: {type: string}, opacity: {type: number} }, required: [z, tracks], additionalProperties: false }
```
Not runtime-enforced (plans validate via dataclasses) but the wire schema must match.

### 5. Reject `blend != "normal"` at LayerRef construction

v1 ships src-over + alpha only. `LayerRef.from_dict` / `__post_init__` raises on any blend value other than `"normal"`.

## Do NOT do (LEAVE)

- No service.py edits (batch 2 handles `_window_timeline` track-filtering).
- No pack/finalizer/planner edits.
- No FrameWindow changes.
- No RenderPlan layer-registry (a top-level layers list) — the plan explicitly says don't.
- No structured SupportReport.features change.

## Verification (run, then report the evidence)

```bash
PYENV_VERSION=3.11.11 python -m pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_provenance.py
```

Also add focused NEW tests (in test_contracts.py or a new test_layer_contract.py — your call, but name it clearly):
1. `layer=None` (all segments) still rejects overlap/gap/out-of-order/trailing-gap — the EXACT existing cases must still pass (they're frozen).
2. Two segments, distinct z, SAME window → plan PARSES (the new capability).
3. Two segments, same z, overlapping → rejected.
4. Two segments, same z, adjacent → parses (per-z tiling works).
5. Mixed (one layer=None, one layer=LayerRef) → rejected (the "all or none" rule).
6. `blend != "normal"` → rejected.
7. `layer` round-trips through to_dict/from_dict; `layer=None` omits the key (fast-path key set unchanged).
8. `z < 0`, empty tracks, `opacity <= 0` or `> 1` → rejected.

Run the plan.json schema through any existing schema-validation test (grep for how plan.json is tested; if there's a schema test file, ensure the new field passes).

Commit: `megado: batch 1 — LayerStack per-layer plan contract (LayerRef, per-z cursor, plan.json)`.

## Report
<350 words: the exact contracts.py changes (types + cursor logic), plan.json field, new test names + counts, the frozen-test evidence (test_contracts + test_provenance pass), the commit sha, final git status. Evidence-first.
