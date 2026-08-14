# Checkpoint 1 — Batch 1 (Layer Stack) — PASS

Oracle: Grok 4.6. Delegated Flash facts + critique (`.oracle/findings/oracle-b1-facts.txt`, `oracle-b1-critique.txt`). Validated cited lines.

## PASS

- Scope clean: `d5b960d7` + `fe7622c7` touch only `contracts.py`, `plan.json`, `test_layer_contract.py`. No service/pack/finalizer edits.
- `LayerRef` (`contracts.py:1316–1366`): z≥0, non-empty string tracks, blend=="normal" only, opacity in (0,1]. Minimal; `blend` is the documented fail-closed seam.
- `RenderSegment.to_dict` (`1416–1424`) omits `layer` when None. Frozen key-set `test_contracts.py:600–603` still `{window,renderer,input_hashes}`.
- Per-z cursor (`1520–1547`) is the old exact-tile check keyed by `z|None`. All-or-none at `1511–1519`.
- `plan.json` `renderSegment.laye```
PASS
- Scope: d5b960d7 + fe7622c7 touch only contracts.py, plan.json, test_layer_contract.py.
- LayerRef (contracts.py:1316–1340): z≥0, non-empty tracks, blend=="normal", opacity (0,1]. to_dict omits layer when None (1416–1424). Frozen key-set test_contracts.py:600–603 unchanged.
- Cursor (1520–1547) is the old exact-tile check keyed by z|None. All-or-none at 1511–1519. plan.json layer optional, additionalProperties:false, required [z,tracks].
- Host pytest 123 passed. Flash facts+critique: .oracle/findings/oracle-b1-{facts,critique}.txt.

Semantics
- All-or-none is correct. layer=None is the full-stack fast path; mixing would double-paint overlay tracks (a second tiling axis).
- Early-end for explicit z is correct. Composition length = plan window; uncovered = compositor background. No layer (incl. z=0) must span. None-layer must still reach target_end. fe7622c7 is the right fix.
- Late-start stays illegal. A 1.0s text overlay is a CLIP on a full-window layer, not a layer starting at frame 24. v1 planner emits one full-window segment per z; z>0 paints transparent head (B4). setdefault(..., target_start) at 1527 is right. Same path already pinned for None (`test_layer_contract.py:171` [1,48) → "gap").

LayerRef is minimal. Cursor is not over-engineered. Tests pin properties, not tautologies.

Batch 2 may start. B3 compositor must pad short layers (incl. z=0).
```
; key-set). Parse-only stacking tests are the capability. Schema looser than dataclass on blend/opacity is the existing wire/runtime split — dataclass is the gate.

Batch 2 may start. Compositor must pad short layers (incl. z=0); do not assume an opaque full-span bottom.
