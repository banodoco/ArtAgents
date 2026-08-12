# M1 Handoff — Batch 6 T6.1

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
Recorded: 2026-08-12. HEAD: `b4fa4f91` (C6-batch5-done).

## Source handoff

- `pytest -q tests/core/rendering tests/packs/rendering` →
  **570 passed, 2 skipped, 1 failed** — the ONLY failure is the documented
  pre-existing env-dependent fixture
  (`test_render_discovers_fixture_local_effect_assets_without_real_local_pack`,
  missing developer-local `model-trends` effect fixture; `.oracle/baseline.md`).
- Frozen protocol, schemas, raw fixture, trusted discovery, built-in
  registration (Remotion, FFmpeg, legacy_hybrid, ffmpeg-finalizer), and the
  generic `RenderService` all pass from source.

## Wheel handoff

- `bash scripts/smoke_wheel_install.sh` → **PASS** (recorded in
  `.oracle/m1-gate.md`; 2026-08-12): wheel installs, and
  `load_default_registries` in the installed venv discovers
  `rendering.remotion`, `rendering.ffmpeg`,
  `rendering.legacy_hybrid`, and `rendering.ffmpeg-finalizer`.
- Installed-wheel smoke: schemas, parity fixtures, and rendering manifests
  are packaged (`pyproject.toml` package-data) and resolvable.

## Protocol defects found

**None.** No wire mismatch, missing schema, or discovery break surfaced.
M1 handoff is enforced clean; SDK work (T6.2+) may proceed.
