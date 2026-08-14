# Oracle Batch 4 REWORK — elegance critique (KISS / YAGNI)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit 70c5cdee vs parent 2a2ba6b8. Read-only. Take a position. <300 words.

Bias: KISS, YAGNI, cut scope that isn't pulling its weight. Flag over-engineering, not just bugs. Do not implement.

CONTEXT: Previous oracle ISSUES mandated path (a) — 4 fixes:
1. Flags/profile → ProRes 4444 (probed mov/prores/yuva444p12le).
2. Theme bg neutralization so BOTH DOM TimelineComposition and threejs paint nothing.
3. Naming: backend remaps .mp4→.mov; service/dispatch/validate_output_name frozen.
4. Tests: .mov/prores/yuva444p12le; threejs dict→RenderRequest; un-xfail corner[3]==0.

USER GOAL: "stack renderers, transparent or not." Checkpoint is real alpha plane + corner alpha 0.

Judge only the REWORK delta (70c5cdee), not whether we should have chosen path (a).

Also judge:
1. Is `_timeline_alpha` + `_alpha_output_name` in `_shared` clean/reusable, or premature abstraction? Any core import leak?
2. Theme `"transparent"` — is mutating `theme_color["bg"]` the smallest correct fix, or does it risk unstamped/error paths (mutates merged_props in place)?
3. `.mov` remap only in backend — any path-binding risk the compositor/finalizer will miss the file?
4. Scope creep: did they touch frozen files? Editing `.oracle/checkins/batch-4.md` — YAGNI?
5. Anything to cut before PASS?

## Report shape

```
VERDICT-LEAN: pass|issues — one sentence
THEME: ok|defect — ...
NAMING: ok|path-bind-risk — ...
SHARED: clean|leaky — ...
SCOPE: clean|creep — ...
YAGNI-CUT: anything to delete
MUST-FIX-NOW: numbered issues (empty if none)
BATCH5-NOTE: remotion/threejs emit ProRes 4444 .mov with real alpha; vp9 is not alpha
```
