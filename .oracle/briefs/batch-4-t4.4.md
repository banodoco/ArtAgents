# Task T4.4 — Port rendering.legacy_hybrid planner [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". T4.1's `RenderService` dispatches
via the frozen selection order. T4.3 handled provenance. Your job: port the
current hybrid planner from the render monolith into
`astrid/packs/rendering/planners/legacy_hybrid/` as a real planner behind
the planner contract, registered as `rendering.legacy_hybrid`. It must
produce a `RenderPlan` with integer half-open `[start_frame,end_frame)`
windows, qualified renderer ids, support-based assignment, an explicit
finalizer, and non-recursive dispatch (the service executes the plan).

## Change

1. Create `astrid/packs/rendering/planners/legacy_hybrid/`:
   - `__init__.py`, `run.py` (raw-command adapter for the `plan` verb:
     reads `--request`, writes a `RenderPlan`-shaped result), `planner.yaml`
     (id `rendering.legacy_hybrid`, protocol_version 1, command
     `[python3, run.py]`, operations `[plan, support]`, capabilities,
     required_permissions).
2. Port the current hybrid heuristics (from
   `astrid/packs/rendering/executors/render/run.py` — `_complex_clip_windows`,
   `_hybrid_segments`, handle/transition math) as the planner's core:
   - resolve the canonical canvas/FPS from the merged theme/timeline view
     (SAME source Remotion uses — profile.py `resolve_render_profile`);
   - convert every segment to integer half-open `[start_frame, end_frame)`;
   - preserve characterized transition units/handles;
   - assign renderers by SUPPORT REPORTS (a segment goes to a backend only
     if that backend's support says it can render the window) — qualified
     ids only;
   - emit an explicit finalizer (`rendering.ffmpeg-finalizer`) and the
     canonical output profile;
   - NEVER recursively call `render()` — the service executes the plan.
3. The `support` verb reports whether hybrid planning can handle the
   request.
4. Add `tests/core/rendering/test_legacy_hybrid.py`:
   - empty plan (zero-frame);
   - single segment;
   - multiple segments;
   - all-FFmpeg hybrid;
   - mixed raw-fixture/built-in plan (the deterministic fixture from Batch 2
     + a built-in);
   - frame rounding (integer windows, exact tiling);
   - transition/handle preservation;
   - speed/overlap rejection (moved to planner support);
   - segment failure cleanup + aligned segment provenance (with T4.3).
5. Register in `astrid/packs/rendering/pack.yaml`
   (`extensions.rendering.planners`).

## Acceptance

- `pytest -q tests/core/rendering/test_legacy_hybrid.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.
- The old `_hybrid_segments` in the monolith is removed or becomes a thin
  re-export.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `service.py`
(T4.1), `provenance.py` (T4.3), the backends/finalizer, or Batch-1 frozen
files. Preserve all existing work. Report: files changed, test results, the
planner protocol.
