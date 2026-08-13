# Rework T1.3R — Fix pack validation for new alias kinds (oracle issue 8) [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

The Batch 1 oracle review found one issue in your T1.3 pack-extension work.
Full review: `.oracle/checkins/batch-1.md`. Fix ONLY this issue. Your files:
`astrid/core/pack/` (schema, normalizer, validation, walkers if needed) and
their tests. Another agent is reworking `astrid/core/rendering/` in parallel
— do NOT touch `astrid/core/rendering/`, `tests/core/rendering/`, or
`docs/contracts/`.

## Issue 8 — New alias kinds crash public pack validation

`astrid/core/pack/validate.py:237` initializes resolver/capability maps only
for executors and orchestrators, then indexes them using the newly accepted
alias kind at `validate.py:830`. Running `validate_pack` on a pack declaring
a renderer alias raises `KeyError: 'renderer'`; such a pack cannot follow the
normal validation/install path.

Reproduce first: run `validate_pack` on the committed rendering fixture
(`tests/fixtures/renderer_packs/` — find the one declaring renderer aliases,
or the rendering pack extension fixture) and confirm the KeyError.

Rework:
- Integrate renderer/planner/finalizer manifests (and their alias kinds)
  into static pack validation and capability-location registration in
  `validate.py` (and any walker/structure code that enumerates capability
  kinds, e.g. `walkers.py`, `cli_inspect.py`, `structure.py` if they hardcode
  executor/orchestrator — follow the pattern you used in T1.3 for the
  normalizer, extended to validation).
- `validate_pack` must succeed on a pack declaring
  `extensions.rendering` manifests AND renderer aliases, and must still
  reject malformed ones.
- Add regressions: public `validate_pack` on a valid rendering-extension
  pack (succeeds), on a pack with renderer alias kinds (succeeds), on one
  with an escaping manifest path (fails), and on a malformed manifest
  (fails). Also confirm the normal `astrid packs` validation/install path
  works for such a pack (install regression where feasible without network).

## Acceptance

- `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py` passes.
- New tests asserting `validate_pack` (and pack validation entrypoints) succeed on rendering-extension packs with renderer/planner/finalizer aliases pass.
- `pytest -q tests/packs` has no NEW failures.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do NOT modify `astrid/core/rendering/`, `tests/core/rendering/`,
`docs/contracts/`, or production render code. Preserve all existing work.
Report: the KeyError reproduction, files changed, test results.
