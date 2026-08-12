# Task T4.2 — Neutral facade and output-name awareness

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". T4.1 (before or parallel) built
`astrid/core/rendering/service.py::RenderService`. Your job: reduce
`astrid/packs/rendering/executors/render/run.py` to a thin facade adapter
over the service, make `executor.yaml` backend-neutral and output-name
aware, and remove the argv-order shim.

## Change

1. `astrid/packs/rendering/executors/render/run.py`:
   - Keep the public `render(...)` signature and the `rendering.render`
     capability id; delegate to `RenderService` for dispatch (legacy engine
     translation happens in the service). The facade no longer contains
     concrete Remotion/FFmpeg branches.
   - `--engine` still accepted (legacy values + qualified ids) and passed to
     the service.
2. `astrid/packs/rendering/executors/render/executor.yaml`:
   - Neutral selector input (`engine` or `backend`), namespaced config input
     (map keyed by qualified backend id), `output_name` input (validated:
     reject separators, traversal, non-`.mp4` extension; preserve declared
     names; Hype's default `hype.mp4` sentinel unchanged), placeholder
     output path (`{out}/{output_name}` or similar).
   - Parsing order-independent.
3. `astrid/core/execution/executor/runner.py::_normalize_render_command_compat`:
   remove it AFTER its characterization passes (the characterization test
   locks the current behavior; the new facade must produce the same final
   argv without the shim).
4. Add `tests/packs/rendering/test_render_facade.py` (facade delegates to
   service, legacy values translate, output_name validated) and
   `tests/core/rendering/test_output_name.py` (separators/traversal/
   extension rejection, default hype.mp4 preserved).

## Acceptance

- `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py` passes.
- `pytest -q tests/packs/rendering tests/packs/hype` has no NEW failures.
- `_normalize_render_command_compat` removed; no regression in Hype/iteration
  render argv tests.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `service.py`
(T4.1), `provenance.py` (T4.3), the backends, or Batch-1 frozen files.
Preserve all existing work. Report: files changed, test results, the facade
shape.
