# Rework T1.1R — Fix baseline characterization issues (oracle issues 1–2)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. You
MAY edit files (file, web, terminal toolsets). Python:
`PYENV_VERSION=3.11.11`.

## Context

The Batch 1 oracle review found two issues in your T1.1 baseline work. The
full review is at `.oracle/checkins/batch-1.md`. Fix ONLY these two issues.

## Issue 1 — Run ownership characterized at the wrong boundary

The baseline and your test prove only that the private leaf module
(`astrid/packs/rendering/executors/render/run.py`) does not create a ledger.
But the PUBLIC facade `rendering.render` (invoked as `astrid executors run
rendering.render`) DOES call `prepare_project_run` — `requires_timeline:
false` does not disable run ownership.

Minimum rework:
- Correct `.oracle/baseline.md` to distinguish: (a) leaf module `run.py`
  `main()` — no `run.json`; (b) public facade via the executor runner — the
  runner creates a project run when a project is resolved (see
  `astrid/core/execution/executor/runner.py` around `prepare_project_run`,
  `astrid/core/project/run.py`, and the gate in
  `astrid/core/contracts/capability_runner.py`).
- Add characterization tests at the FACADE boundary covering, at minimum:
  - standalone facade invocation with a project → creates exactly one
    `run.json` at the run root, output rewritten to run root;
  - task-attached reuse (`ASTRID_TASK_*` env set, matching project/run/step)
    → reuses the orchestrator's run context, no NEW `run.json`;
  - `project=None` (no project resolved) → behavior (no ledger? error?);
  - retained caller-selected output under attachment;
  - `run_root` in the request is ignored/replaced for run creation.
  Follow the pattern of existing runner tests (e.g.
  `tests/core/test_executor_runner_errors.py`,
  `tests/core/test_project_runs.py`). Use a fast/no-op executor or mock the
  render leaf so no real render happens. Put these in
  `tests/packs/rendering/test_legacy_renderer_characterization.py` (extend)
  or a sibling `tests/packs/rendering/test_render_facade_run_ownership.py`.

## Issue 2 — Remaining baseline characterization incomplete

Minimum rework:
- `.oracle/baseline.md` callsite inventory: ADD
  `astrid/packs/video_editing/orchestrators/iteration_video/plan_template.py`
  (line ~98, direct `python -m ...render.run --out iteration.mp4` spawn) and
  `astrid/packs/video_editing/orchestrators/hype/plan_template.py` (line
  ~437, `_executor_cmd("rendering.render", ...)` — canonical). CORRECT the
  records for `cut/run.py:368` and `cut/resume.py:165`: both import a
  NONEXISTENT sibling module (`from ..render.run import render`) — they are
  latent `ModuleNotFoundError` bugs under `--render`, NOT working imports.
- Transition characterization: your current transition tests construct NO
  transition, so add real cases locking: `duration` vs `durationFrames`,
  default 8-frame transition duration (8/fps), handle padding (0.25 s), clip
  precedence, and frame rounding (`_round_frame_time`, `_clip_duration_seconds`,
  `_clip_timeline_end_seconds`, `_timeline_duration_seconds` in run.py).
- Props/theme/registry/staging/environment/generated-source behavior: either
  add characterization tests or explicitly MAP each to existing tests
  (`test_render_remotion_registry.py`, `test_url_pipeline_smoke.py`,
  `tests/golden/hype/`, `test_audio_reactive_colour.py`) with file:line
  references in baseline.md. For any behavior with NO existing coverage, add a
  small characterization test (mock heavy deps; no real render).
- C0 baseline: record in baseline.md the pass/fail/skip counts for the
  general pack/executor suites at C0 (run `pytest -q tests/packs
  tests/core` — or the relevant subset — and record; note the 2 known
  env-dependent failures). Then RE-RUN the Hype/iteration suites
  (`pytest -q tests/packs/hype tests/packs/iteration tests/packs/editorial`)
  and record C1 evidence in baseline.md.
- Sprint 08 record: correct the fixture path in baseline.md (find the actual
  path — the real parity test is `tests/packs/test_renderer_parity.py` and
  the fixture dir is `tests/fixtures/sprint08/`; record that the parity test
  is OPT-IN (skipped by default / not in CI), hashes timeline JSON without
  rendering, and its fixture dir contains only a README).

## Acceptance

- `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering/test_render_facade_run_ownership.py` passes (new facade/transition cases green).
- `pytest -q tests/packs/hype tests/packs/iteration tests/packs/editorial` shows no NEW failures vs recorded baseline.
- `.oracle/baseline.md` updated with all corrections above.

Run ONLY those commands. Do NOT run the full suite, formatters, or linters.
Do NOT modify `astrid/core/rendering/` (other agents are reworking contracts
in parallel — avoid touching it or `tests/core/rendering/`). Do not touch
`astrid/packs/rendering/executors/render/run.py` or production code: this is
characterization only (tests + docs), except you MAY add test-only mocks.
Preserve all existing work. Report: changes made, test results, corrected
records.
