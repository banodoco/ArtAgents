# Task T5.7 — Package and run the M1 gate

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 5 of "Pluggable Timeline Renderers" (final task). T5.1-T5.6 are done
(attached helper, iteration/cut/hype/human-notes migrations, facade manifest,
parity suite, docs). Your job: package the M1 deliverable so schemas,
manifests, and fixtures ride in installed wheels, then run and record the
complete M1 gate.

## Change

1. `pyproject.toml`: include package data for
   `astrid/core/rendering/schemas/v1/*`, `astrid/packs/rendering/**/*.yaml`,
   `astrid/packs/rendering/**/renderer.yaml`/`planner.yaml`/`finalizer.yaml`,
   and `tests/fixtures/renderer_parity/*` (or move fixtures into an installed
   package path if wheels must not carry tests). Ensure the built wheel
   carries the JSON schemas and rendering manifests.
2. CI lanes: add/adjust `.github/workflows/ci.yml` and
   `scripts/reshape/run_ci_checks.sh` to run the rendering contract tests +
   parity suite (`-m renderer_parity`) and the Remotion typecheck
   (`cd remotion && npm run typecheck`) as blocking gates (T5.5 already
   wired these; verify they are consistent).
3. `scripts/smoke_wheel_install.sh` (or equivalent): build the wheel,
   install into a venv, and verify `import astrid; astrid.core.rendering.schemas`
   resolves and the rendering manifests are discoverable (pack discovery
   finds `rendering.remotion`, `rendering.ffmpeg`,
   `rendering.ffmpeg-finalizer`, `rendering.legacy_hybrid`).
4. Add/update `tests/` package-data tests that assert the schemas/manifests/
   fixtures are present in the built wheel or source tree (whichever is
   authoritative), and run the FULL M1 matrix:
   - `pytest -q` (full suite)
   - `make check`, `make ci`
   - `bash scripts/smoke_wheel_install.sh`
   - `cd remotion && npm run typecheck`
5. Record the M1 gate results in `.oracle/` (a short md summary file named
   `m1-gate.md` with the exact commands run and their pass/fail).

## Acceptance

- `pytest -q` passes (except the one pre-existing env-dependent model-trends
  fixture failure, which is documented in `.oracle/baseline.md` and MUST be
  the ONLY failure).
- `make check` and `make ci` pass.
- `bash scripts/smoke_wheel_install.sh` passes.
- `cd remotion && npm run typecheck` passes.
- `.oracle/m1-gate.md` records the matrix.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, or the schemas. Preserve all existing work. Report:
files changed, gate results, the recorded matrix.
