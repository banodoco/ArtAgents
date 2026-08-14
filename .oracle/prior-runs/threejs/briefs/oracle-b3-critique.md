# Oracle Batch 3 — elegance critique (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: fdf6dfae vs previous 963060ee
Do not edit any files.

Critique the Batch 3 delta for elegance. Optimize for KISS, YAGNI, cut scope that is not pulling its weight. Flag overengineering, not just bugs.

## Frozen Batch 3 scope

Thin rendering.threejs backend. Own identity (engine=threejs, never remotion). Reuses remotion's _execute_remotion + shared lock. ZERO astrid/core edits. v1 = text-only + empty/background.

Files: backends/threejs/{__init__,renderer.yaml,run.py}, pack.yaml +1, test_freeze.py +1, test_threejs_backend.py.

Allowed remotion reuse: _execute_remotion, _serialize_timeline, _render_provenance_payload, narrow theme/registry. Forbidden remotion reuse: support, _protocol_render, _settings_from_request, remotion backend fragment.

## What to inspect

- git show fdf6dfae and read backends/threejs/run.py + renderer.yaml + test_threejs_backend.py
- Compare (read-only) against astrid/packs/rendering/backends/remotion/run.py: is threejs duplicating logic it should have reused? Or correctly owning what it must own?
- Config surface: only required operational project/theme/free-space overrides? Extra knobs?
- Dead code, extra abstractions, protocol wrappers, second lock, second capture stack, model.py, planner leak, docs leak
- 668-line run.py: is the size justified by owning support/render/eligibility/identity, or is it a copy-paste of remotion _protocol_render?
- Test file 727 lines: necessary coverage vs gold-plating
- Comments/noise vs load-bearing

## Output (<250 words)

Take a position. Do not hedge.

```
ELEGANCE: PASS | FAIL
SCOPE_CREEP: none | <what leaked>
OVERENGINEERING: none | <what>
KISS_YAGNI: ok | <cut this>
DUPLICATION: justified-identity-ownership | unjustified-copy of remotion <cite>
CONFIG_SURFACE: required-only | extra=<...>
RUN_PY_SIZE: justified | bloated
TEST_SIZE: justified | bloated
ISSUES: none | numbered list of checkpoint-failing problems only
NOTES: non-blocking observations
```

Only put something under ISSUES if it fails Batch 3 acceptance.
