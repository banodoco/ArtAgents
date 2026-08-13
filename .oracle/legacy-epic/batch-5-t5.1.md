# Task T5.1 — Attached-child render invocation [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 5 of "Pluggable Timeline Renderers". Batches 1-4 froze the renderer
contracts, transport, assets, profiles, publication, provenance, the generic
`RenderService`, the neutral facade, and the legacy_hybrid planner. Your job:
the attached-child render invocation helper that production callers (Hype,
iteration, cut) will use so a render inside a project/run ledger is recorded
as a child step with scoped environment, retained outputs, and override
propagation — while unbound callers fall back to the public service.

## Change

Add `astrid/core/rendering/attached.py`:

1. `invoke_attached_render(...)` over existing task/executor primitives:
   - Requires a validated parent project/run ledger and a unique step id.
   - Scopes and restores all three `ASTRID_TASK_*` environment variables
     around the invocation (save current values, set the child step's, then
     restore exactly, including when the child raises).
   - Preserves the caller-selected output path/name.
   - Honors facade overrides (executor-level override of `rendering.render`
     must affect the attached call).
   - Falls back to the PUBLIC `RenderService` (no ledger) only when no
     project ledger is bound — never silently.
   - Records the child step in the parent run's ledger with the output
     artifact and provenance sidecar path.
2. Reuse existing primitives: `RenderService`, the facade
   `astrid.packs.rendering.executors.render.run`, task lifecycle/step
   helpers in `astrid/core/task/` (inspect what exists — `operator`/`gate`/
   `lifecycle` modules), and executor invocation helpers. Do NOT build a new
   ledger format; extend what exists.
3. Add `tests/core/rendering/test_attached_render.py`:
   - attached invocation records a child step with unique id;
   - the three `ASTRID_TASK_*` vars are scoped and restored after success
     AND after failure (crash-safe restore);
   - caller-selected output name preserved;
   - executor override of `rendering.render` changes the attached behavior;
   - unbound (no ledger) falls back to public RenderService;
   - bound-with-invalid-parent is rejected;
   - no ledger written for the unbound fallback path.
4. Extend `tests/test_task_env_contract.py` only if the attached helper
   changes the task env contract (add cases, don't weaken existing ones).

## Acceptance

- `pytest -q tests/core/rendering/test_attached_render.py` passes.
- `pytest -q tests/test_task_env_contract.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `service.py`, `provenance.py`, the facade, the backends,
`contracts.py`, or `schemas/`. Preserve all existing work. Report: files
changed, test results, the helper's API shape.
