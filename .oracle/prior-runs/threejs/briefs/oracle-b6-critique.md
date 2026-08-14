# Oracle Batch 6 — elegance critique (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: fc0c3cee vs 8723ca05. Do not edit any files.

Critique the Batch 6 delta for elegance. Optimize for KISS, YAGNI, cut scope that is not pulling its weight. Flag overengineering, not just bugs. This is the FINAL batch: docs + packaging + CI gate + two small oracle notes. Zero astrid/core edits.

## Inspect

```bash
git show --stat fc0c3cee
git diff --name-status 8723ca05..fc0c3cee
```

Read:
- `docs/reference/threejs-renderer.md`
- the run.py diffs (dead-code + BLE001)
- the hybrid test assertion
- `tests/core/rendering/test_production_callers.py` allowlist addition
- `scripts/reshape/baselines/ruff_astrid.json` only enough to see if it is a huge dump vs a small count refresh

## Look for

- Leftover dead code in threejs backend / hybrid planner (unused imports, unused helpers after the checkpoint-3 cleanup).
- Duplicated logic that Batch 6 newly introduced (not pre-existing helper dup from earlier batches).
- Over-assertion: finalizer fragment check that freezes incidental shape; allowlist that is broader than the planner's two imports.
- Scope creep: editing generic docs, skills, README, changelog, package-data tests, CLI tests without a gate proving omission.
- Hygiene untrack of .codex/.vscode/mp3 — is that in-scope for T6.6 (yes, if the hygiene gate failed) or a drive-by?
- Regenerating the whole ruff baseline instead of only our files — overkill or required by the tool?
- Doc that over-promises v2 features or duplicates render-adapter.md.

## Frozen Batch 6 scope

T6.1 docs/reference/threejs-renderer.md; T6.2 no broad doc edits unless a gate proves omission; T6.3–T6.6 gates; T6.7 zero core; T6.8 commit; plus dead-code + finalizer-fragment notes.

## Output (<250 words)

```
ELEGANCE: PASS | FAIL
SCOPE_CREEP: none | <what leaked>
OVERENGINEERING: none | <what>
KISS_YAGNI: ok | <cut this>
DEAD_LEFTOVER: none | <cite>
OVER_ASSERTION: none | <cite>
DOC_BLOAT: ok | <what>
HYGIENE_IN_SCOPE: yes | no
RUFF_REGEN: justified | overkill
ISSUES: none | numbered checkpoint-failing problems only
NOTES: non-blocking observations
```

Only put something under ISSUES if it fails Batch 6 acceptance. Take a position. Do not hedge.
