# Oracle Batch 5 — elegance critique (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: 8723ca05 vs previous af907878
Do not edit any files.

Critique the Batch 5 delta for elegance. Optimize for KISS, YAGNI, cut scope that is not pulling its weight. Flag overengineering, not just bugs.

## Frozen Batch 5 scope

Prove mixed Three/Remotion/ffmpeg-finalizer render + regressions. Tests only. Zero astrid/core edits. No production changes. One mixed real render, remotion-under-ANGLE identity, one shared lock, offline npm, regression suite.

Files should be only the three test files.

## What to inspect

- `git show 8723ca05`
- Read the new test functions in:
  - tests/core/rendering/test_threejs_hybrid.py
  - tests/packs/rendering/test_remotion_backend.py
  - tests/packs/rendering/test_threejs_backend.py
- Compare helpers: did they duplicate ffprobe/sidecar/preflight helpers that already exist in test_threejs_backend.py or test_remotion_backend.py? Duplicated helpers are an elegance note; they FAIL the checkpoint only if they hide a vacuous assertion or a second lock/preflight policy.
- Test bloat: +612 across 3 files. Is each assertion load-bearing for T5.1–T5.6?
- Over-assertion: asserting incidental remotion internals that Batch 5 does not freeze?
- Fake sophistication: multiprocessing lock test that doesn't actually contend; npm offline that never hits npx; mixed timeline that is two text clips.
- Scope creep: new fixtures committed, new production helpers, new planner behavior, second compositor.

## Output (<250 words)

Take a position. Do not hedge.

```
ELEGANCE: PASS | FAIL
SCOPE_CREEP: none | <what leaked>
OVERENGINEERING: none | <what>
KISS_YAGNI: ok | <cut this>
HELPER_DUP: shared | duplicated <cite> (blocking? yes/no)
TEST_BLOAT: justified | bloated <what to cut>
VACUOUS_OR_FAKE: none | <what>
PRODUCTION_TOUCHED: none | <paths>
CORE_EDITS: none | <paths>
ISSUES: none | numbered list of checkpoint-failing problems only
NOTES: non-blocking observations
```

Only put something under ISSUES if it fails Batch 5 acceptance.
