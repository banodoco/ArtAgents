# SDK invocation / ledger P0 fix

Date: 2026-08-23  
Scope: live `generation.generate_image` usage in an isolated
`poster-lab` project.

## Production changes

- `astrid/core/task_executor/capability_handler.py`
  - Imports and calls the executor runner explicitly; the generic handler no
    longer raises `NameError: ExecutorRunRequest is not defined`.
  - Keeps project-scoped requests' public `out=None` shape while passing the
    kernel staging root as `run_root`; executor path/placeholder expansion now
    falls back to that staging root.
  - Applies the same staging/attached-child semantics to orchestrator requests.
- `astrid/core/execution/executor/runner.py`
  - `build_pipeline_context` and executor placeholder expansion use
    `request.run_root` when `request.out` is absent, and emit a typed runner
    error if neither path exists.
- `astrid/sdk/invocation.py`
  - Uses the canonical `<ASTRID_PROJECTS_ROOT>/.astrid/astrid.sqlite3` path and
    standard schema registry.
  - Creates the managed database parent directory when SDK invocation is the
    first writer.
  - Resolves the caller's project slug/id to the repository's canonical
    project ID before `RunRepository.create`.

## Root causes

1. `CapabilityTaskHandler` referenced `ExecutorRunRequest` and
   `run_executor` without importing them. The first live generation therefore
   failed after admission and before backend execution.
2. `_kernel_invoke` opened `<root>/kernel.sqlite3` with a core-only registry,
   while CLI and typed services used the standard database at
   `<root>/.astrid/astrid.sqlite3`. Returned IDs were consequently written to a
   second authority. Moving invocation to the canonical path also required
   standard pack migrations and slug-to-ID resolution for CLI-created projects.

## Live verification

The final replay created a fresh root with the CLI, then called the public SDK
exactly as a user would:

```text
root: /tmp/astrid-p0-final-MHxgd6
project: poster-lab
capability: generation.generate_image
model/mode/execution: z-image / t2i / local
run: 1bb3174e06302c0c82a1d0fd46
task: f84749937d18a1c15f30068623
attempt: 01m0qmn02p5b8sx2s0v62n71ks
```

The invocation reached the real generation executor. It no longer produced a
`NameError` or path/identity exception; it returned the truthful backend
failure `ModuleNotFoundError: No module named 'vibecomfy'`. The canonical DB
contained the run/task, no legacy root `kernel.sqlite3` was created, and all of
these surfaces returned the same IDs:

- `python3 -m astrid runs list --project poster-lab --json`
- `python3 -m astrid tasks list --project poster-lab --json`
- `python3 -m astrid runs show <run> --project poster-lab --json --evidence`
- `AstridClient.runs.list/show` and `AstridClient.tasks.list`

The typed run show exposed progress with `failed: 1` and the handler/backend
failure was inspectable in the SDK result. No image was expected because the
local VibeComfy dependency is unavailable in this checkout.

## Regression verification

```text
pytest -q tests/test_sdk_public_surface.py::test_invoke_executor_project_routing_allows_out_none_with_in_process_mode
1 passed

python3 -m compileall -q astrid/sdk/invocation.py \
  astrid/core/task_executor/capability_handler.py \
  astrid/core/execution/executor/runner.py
```

## Residual UX

The local generation backend still needs VibeComfy installed/configured (or a
different available backend). A failed child leaves the run row `running`
until the documented explicit `client.runs.close(...)` transition; the read
surface does expose the derived failed progress immediately.
