# Task T5.2 — Migrate iteration and cut callers [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T5.1 (attached-child helper) may be running in parallel; use
`invoke_attached_render` from `astrid.core.rendering.attached` if present,
otherwise `RenderService`/facade directly per its documented fallback.

## Context

Batch 5 of "Pluggable Timeline Renderers". The render executor is now a
neutral facade over `RenderService`; production callers must stop depending
on the old monolith behavior. Your job: migrate the iteration and cut
callers to the attached facade/public service.

## Change

1. `astrid/packs/video_editing/orchestrators/iteration_video/run.py` and
   `plan_template.py`:
   - Call the attached render helper (or the public facade) instead of any
     legacy concrete path; route through `rendering.render` capability.
   - Iteration must produce `iteration.mp4` AND
     `iteration.mp4.provenance.json` directly (declare the iteration
     sidecar in the manifest/plan).
   - Remove rename-only behavior and broken imports; preserve the deprecated
     `--renderer` selector mapping to the neutral engine selector.
   - Every migrated path creates ONLY its intended ledger (no stray
     project/run records).
2. `astrid/packs/video_editing/executors/cut/run.py` and `resume.py`:
   - Same migration; cut/resume preserve deprecated `--renderer`.
3. Add/update tests:
   - `tests/packs/iteration/test_iteration_video.py` — iteration.mp4 +
     sidecar exist, ledger correct, deprecated selector preserved, overrides
     honored.
   - `tests/packs/video_editing/test_cut_render_migration.py` — cut and
     resume render through the attached facade/service; no concrete renderer
     imports.

## Acceptance

- `pytest -q tests/packs/iteration/test_iteration_video.py` passes.
- `pytest -q tests/packs/video_editing/test_cut_render_migration.py` passes.
- `pytest -q tests/packs/iteration tests/packs/video_editing` has no NEW
  failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `service.py`, `provenance.py`, the facade, the backends,
`contracts.py`, or `schemas/`. Preserve all existing work. Report: files
changed, test results, the migration shape.
