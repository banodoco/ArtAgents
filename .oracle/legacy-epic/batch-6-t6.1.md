# Task T6.1 — Enforce the M1 handoff

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 6 of "Pluggable Timeline Renderers". Before SDK work proceeds, the M1
handoff must be enforced: the frozen protocol, schemas, raw fixture, trusted
discovery, built-ins, service, and conformance suite work from source AND an
installed wheel. This is a VALIDATION task — no protocol changes.

## Change

1. Run the frozen M1 suite from source:
   - `pytest -q tests/core/rendering tests/packs/rendering`
   - Expect exactly ONE failure: the pre-existing model-trends env fixture
     (`test_render_discovers_fixture_local_effect_assets_without_real_local_pack`),
     documented in `.oracle/baseline.md`.
2. Run the wheel handoff:
   - `bash scripts/smoke_wheel_install.sh` — must PASS (schemas, fixtures,
     manifests install and are discoverable).
   - Then, IN the installed wheel venv (the script creates one), run the
     conformance/rendering smoke: discover `rendering.remotion`,
     `rendering.ffmpeg`, `rendering.ffmpeg-finalizer`,
     `rendering.legacy_hybrid` from the installed pack, and run a minimal
     `RenderService` render if feasible.
3. If ANY protocol defect surfaces (wire mismatch, missing schema, broken
   discovery), STOP and report it with full details — the batch returns to
   the prior oracle gate. Do NOT patch protocol code here.
4. Record results in `.oracle/m1-handoff.md` (commands run + pass/fail).

## Acceptance

- Source suite: rendering suites pass except the one documented pre-existing
  failure.
- `bash scripts/smoke_wheel_install.sh` passes.
- Installed-wheel discovery of all four built-ins succeeds.
- `.oracle/m1-handoff.md` written.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, or the facade. Preserve all existing
work. Report: results, the handoff record, any defect found.
