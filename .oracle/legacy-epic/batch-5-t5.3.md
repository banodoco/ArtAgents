# Task T5.3 — Migrate Hype, human-notes, and canonical callers [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T5.1 (attached-child helper) may be running in parallel; use
`invoke_attached_render` from `astrid.core.rendering.attached` if present,
otherwise `RenderService`/facade directly per its documented fallback.

## Context

Batch 5 of "Pluggable Timeline Renderers". Your job: migrate the Hype,
human-notes, and canonical render callers to the attached facade/public
service, preserving `tools/render_and_check.py`, and add override +
single-ledger coverage.

## Change

1. `astrid/packs/hype/steps.py` and `plan_template.py`:
   - Route renders through the attached helper/public facade; Hype retains
     the default `hype.mp4` output name and `hype.mp4.provenance.json`.
   - No concrete renderer imports or monolith paths.
2. `astrid/packs/editorial/executors/human_notes/run.py`:
   - Same migration (human-notes renders its media through the facade).
3. Preserve `tools/render_and_check.py` as a canonical caller (it may keep
   using the facade's public `render`).
4. Add/update tests:
   - `tests/packs/hype` — Hype renders via facade; hype.mp4 + sidecar;
     overrides affect the call; only the intended ledger is created.
   - `tests/packs/editorial/test_human_notes_render.py` — human-notes
     render path migrated.
   - `tests/core/rendering/test_caller_overrides.py` — executor overrides
     affect attached facade calls; renderer/planner/finalizer overrides
     affect facade AND public-service calls.

## Acceptance

- `pytest -q tests/packs/hype` passes.
- `pytest -q tests/packs/editorial/test_human_notes_render.py` passes.
- `pytest -q tests/core/rendering/test_caller_overrides.py` passes.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `service.py`, `provenance.py`, the facade, the backends,
`contracts.py`, or `schemas/`. Preserve all existing work. Report: files
changed, test results, the migration shape.
