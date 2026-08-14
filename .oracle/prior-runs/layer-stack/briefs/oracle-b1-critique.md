# Oracle Batch 1 — elegance + semantics critique (KISS / YAGNI)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Read: `astrid/core/rendering/contracts.py` LayerRef + RenderPlan.__post_init__,
`tests/core/rendering/test_layer_contract.py`, `.oracle/plan.md` §1 rules table.
Commits d5b960d7 + fe7622c7. Read-only. Take a position. <300 words.

Bias: KISS, YAGNI, cut scope that isn't pulling its weight. Flag over-engineering, not just bugs. Do not propose new types, blend modes, or planner work.

## Judge these four calls. Yes/no + one evidence sentence each.

A. **All-or-none** (`every segment.layer is None XOR every segment.layer is set`).
   Plan says mixing is a "second tiling axis". Could a plan want one layer=None full-composite PLUS a stacked overlay? Is rejecting mix correct for v1?

B. **Explicit-z may end early; default (layer=None) must reach target_end.**
   AE/Blender: layers are arbitrary length; composition length is independent; uncovered = background. Must SOME layer (e.g. bottom z=0) span the full timeline? Or is "all explicit layers may end early; compositor fills tail" correct?

C. **First segment of each z must start at target_start (usually 0).**
   A text overlay appearing at 1.0s — is that a LAYER that starts late, or a full-window layer whose CLIP starts at 1.0s? v1 planner emits one full-window segment per z. Should the contract allow a layer whose first segment starts at frame 24? If yes, this is a hole. If no, say why leading-gap reject is right.

D. **LayerRef shape** (z, tracks, blend="normal"-only, opacity). Minimal? Dead fields? Missing validation (empty tracks, duplicate z-track ownership, z gaps, opacity=0)?

Also: is the per-z cursor over-engineered vs a simpler groupby-z then reuse the old exact-tile check (minus trailing for explicit z)? Any test that doesn't actually pin a property?

## Report shape

```
A: correct|wrong — ...
B: correct|wrong — ...
C: late-start-illegal-is-right | hole — ...
D: minimal | overbuilt | underbuilt — ...
CURSOR: clean | overbuilt — ...
MUST-FIX-NOW: none | 1-2 concrete Batch-1 defects (file:line)
DEFER: items that are Batch 3/5 or LEAVE
```
