# Task T5.4 — Finish facade manifest and stale-resolution cleanup

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T5.2/T5.3 (caller migrations) may be running in parallel — coordinate only
through the files listed below; do not touch their migration targets.

## Context

Batch 5 of "Pluggable Timeline Renderers". Your job: finalize the facade
`render/executor.yaml`, remove the stale executor-runtime module cache, and
add the repository source-topology allowlist test that proves production
code never imports concrete renderers.

## Change

1. Finalize `astrid/packs/rendering/executors/render/executor.yaml`:
   - neutral selector inputs (`engine` + `backend`), namespaced
     `backend_config`, `output_name` input with the `hype.mp4` default;
   - placeholder outputs (`{out}/{output_name}`);
   - declared sidecar output `{out}/{output_name}.provenance.json`;
   - parsing order-independent; no concrete backend references.
2. Remove `@lru_cache` from
   `astrid/core/execution/executor/argv.py::resolve_executor_runtime_module`
   so a stale in-process resolution cannot outlive registry overrides;
   replace with a plain function (keep the same signature/behavior).
3. Add `tests/core/rendering/test_production_callers.py`:
   - repository source-topology allowlist: no production module may import
     `astrid.packs.rendering.backends.*` or the legacy engine, or spawn
     `-m astrid.packs.rendering.executors.render.run`, EXCEPT manifests,
     backend implementations themselves, the facade, and explicitly
     allowlisted tests/debug tools (list them explicitly).
   - grep-based over `astrid/` source (not site-packages).
4. Keep `tests/core/test_executor_registry_snapshot.py` green (the executor
   registry snapshot test).

## Acceptance

- `pytest -q tests/core/rendering/test_production_callers.py` passes.
- `pytest -q tests/core/test_executor_registry_snapshot.py` passes.
- `pytest -q tests/packs/rendering/test_render_facade.py` passes.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `service.py`, `provenance.py`, the backends, `contracts.py`, or
`schemas/`. Preserve all existing work. Report: files changed, test
results, the allowlist shape.
