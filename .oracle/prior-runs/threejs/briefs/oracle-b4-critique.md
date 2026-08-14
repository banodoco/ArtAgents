# Oracle Batch 4 — elegance critique (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: af907878 vs previous fdf6dfae
Do not edit any files.

Critique the Batch 4 delta for elegance. Optimize for KISS, YAGNI, cut scope that is not pulling its weight. Flag overengineering, not just bugs.

## Frozen Batch 4 scope

Opt-in `rendering.threejs-hybrid` planner. Text-only connected components → `rendering.threejs`; anything else → `rendering.remotion`; pin `rendering.ffmpeg-finalizer`. Exact half-open tiling. Real support evidence. ZERO astrid/core edits. Reuse the backend's pure text eligibility helpers — do NOT duplicate.

Files: planners/threejs_hybrid/{__init__,planner.yaml,run.py}, pack.yaml +1, test_threejs_hybrid.py, test_freeze.py, test_builtin_registration.py.

## What to inspect

- git show af907878 and read planners/threejs_hybrid/run.py + planner.yaml + test_threejs_hybrid.py
- Compare against:
  - `astrid/packs/rendering/planners/legacy_hybrid/run.py` — is this a justified fork of the planner pattern, or a copy-paste god file?
  - `astrid/packs/rendering/backends/threejs/run.py` eligibility helpers — IMPORT or DUPLICATE? Duplicate is a checkpoint-relevant elegance issue because T4.3 requires reuse.
- Dead code, extra abstractions, second compositor, spatial compositing, scene DSL, new schema fields, duplicated finalizer ownership matrix
- 709-line run.py: justified by owning plan/support/tiling, or bloated copy of legacy_hybrid?
- 540-line test file: necessary exact-window coverage vs gold-plating
- Comments/noise vs load-bearing
- Does empty-timeline reject live only in support, or leak into the renderer?

## Output (<250 words)

Take a position. Do not hedge.

```
ELEGANCE: PASS | FAIL
SCOPE_CREEP: none | <what leaked>
OVERENGINEERING: none | <what>
KISS_YAGNI: ok | <cut this>
ELIGIBILITY: imports-backend | DUPLICATE <cite>
DUPLICATION_VS_LEGACY: justified-planner-pattern | unjustified-copy <cite>
CONFIG_SURFACE: required-only | extra=<...>
RUN_PY_SIZE: justified | bloated
TEST_SIZE: justified | bloated
SPATIAL_COMPOSITOR: none | present
CORE_EDITS: none | <paths>
ISSUES: none | numbered list of checkpoint-failing problems only
NOTES: non-blocking observations
```

Only put something under ISSUES if it fails Batch 4 acceptance. Duplicated eligibility helpers FAIL T4.3 and belong in ISSUES.
