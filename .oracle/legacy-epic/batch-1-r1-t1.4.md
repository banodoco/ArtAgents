# Rework T1.4R — Fix transitive alias eligibility (oracle issue 9) [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

The Batch 1 oracle review found one issue in your T1.4 registry work. Full
review: `.oracle/checkins/batch-1.md`. Fix ONLY this issue. Your files:
`astrid/core/rendering/registry.py` and `tests/core/rendering/`. Another
agent is reworking contracts in the same `astrid/core/rendering/` tree in
parallel — you MUST coordinate file ownership: you own `registry.py` and
`tests/core/rendering/test_registry*.py`; do NOT edit
`contracts.py`/`provenance.py`/`errors.py`/`schemas/` or
`test_contracts.py`/`test_schema_roundtrip.py` (the other agent owns those;
their changes are additive DTO/schema fixes). If you need a registry test
that imports a changed DTO, write it defensively (tolerate either shape) or
note it in your report.

## Issue 9 — Alias eligibility filtering is only one hop

`_alias_target_can_participate` (registry.py:950) drops a direct alias to a
denied candidate but retains dangling intermediate aliases. A
higher-precedence chain ending at an ineligible environment renderer can
overwrite a lower trusted alias and make resolution fail with
`invalid_alias_target`. Existing coverage tests only direct targets.

Rework:
- Evaluate alias participation TRANSITIVELY against the completed executable
  graph: an alias chain participates only if EVERY hop resolves to an
  execution-eligible terminal (or an eligible alias), walking the full chain
  including intermediate aliases. When a chain terminates missing or
  ineligible, fall through to the next-precedence declaration instead of
  failing resolution with `invalid_alias_target`.
- Preserve the fail-closed contract: resolution NEVER silently serves an
  ineligible implementation; it must either serve an eligible one (possibly
  from a lower-precedence declaration) or report a structured
  unsupported/unknown capability with evidence.
- Add tests: two-hop denied chain (alias → alias → ineligible env renderer)
  falls through to trusted lower-precedence alias; missing-terminal chain
  same; chain with mixed eligible/ineligible hops resolves to the eligible
  terminal; no case regresses to `invalid_alias_target` when an eligible
  alternative exists.

## Acceptance

- `pytest -q tests/core/rendering/test_registry.py tests/core/rendering/test_registry_matrix.py` passes (existing + new transitive cases).
- `pytest -q tests/core/rendering` has no failures (tolerate/coordinate with the parallel contract rework).

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do NOT modify `contracts.py`, `provenance.py`, `errors.py`, `schemas/`,
`test_contracts.py`, `test_schema_roundtrip.py`, `astrid/core/pack/`,
`docs/contracts/`, or production render code. Preserve all existing work.
Report: changes made, test results, the transitive rule you implemented.
