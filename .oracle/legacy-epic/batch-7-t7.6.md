# Task T7.6 — Run the epic-wide verification and freeze

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T7.1-T7.5 are done before you (CLI, replay, docs).

## Context

Batch 7 (final) of "Pluggable Timeline Renderers". Your job: the epic-wide
verification and freeze — the generic-code backend-name audit, final
success/failure/ledger/sidecar assertions, package-data verification, the
complete matrix, and evidence recorded in `.oracle/verification.md`.

## Change

1. Add the generic-code backend-name audit test: scan `astrid/core/rendering/*`
   (service, provenance, registry, transport, assets, artifacts,
   publication, contracts, sdk) and assert NO concrete backend names
   (`remotion`, `ffmpeg`, `legacy_hybrid`, `ffmpeg-finalizer`) appear in
   generic code except in registry/default wiring and explicit
   compatibility shims. Add it to `tests/core/rendering/`.
2. Add final assertions for the freeze:
   - every built-in path (remotion, ffmpeg, optimized, audio-reactive,
     hybrid, single-segment) → exactly one video + one committed sidecar;
   - failure paths clean temp artifacts and never commit a sidecar;
   - attached renders create only their intended ledger;
   - package data: schemas + manifests + fixtures in the wheel.
3. Run the COMPLETE matrix and record evidence in `.oracle/verification.md`:
   - `pytest -q` (full; note the pre-existing unrelated failures with the
     C5-batch4-done comparison),
   - renderer parity suite,
   - real FFmpeg render,
   - Remotion (optional; explicit skip evidence if the environment blocks),
   - `make check`, `make ci`,
   - `bash scripts/smoke_wheel_install.sh`,
   - `cd remotion && npm run typecheck`.
4. Freeze: verify the git tree is clean of debug artifacts, all batches
   tagged (C0..C7-batchN-done), and the epic README/CHANGELOG updated if
   the repo convention requires.

## Acceptance

- New audit + final assertions pass.
- `.oracle/verification.md` records every matrix command + result with
  exact evidence.
- The full suite matches the pre-existing baseline (no epic-caused
  regressions; the only rendering-area failure is the documented
  model-trends env fixture).

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, or `astrid/sdk/rendering.py`.
Preserve all existing work. Report: files changed, verification evidence.
