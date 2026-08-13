# Epic Verification — Pluggable Timeline Renderers (M1 + M2 freeze)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
Recorded: 2026-08-13. HEAD: (Batch 7 commits; tags C0..C7).

## Complete matrix

| Gate | Command | Result |
|---|---|---|
| Rendering + SDK consolidated | `pytest -q tests/core/rendering tests/packs/rendering tests/test_sdk_rendering.py tests/test_sdk_public_surface.py tests/test_sdk_render_context.py` | 776 passed / 2 skipped / 1 failed (pre-existing model-trends env fixture, `.oracle/baseline.md`) |
| CLI + contract | `tests/core/rendering/test_cli.py test_cli_contract.py` | 44 passed |
| Replay + bundle | `tests/core/rendering/test_replay.py test_replay_bundle.py` | 17 passed |
| Generic-code audit + freeze | `tests/core/rendering/test_generic_code_audit.py test_freeze.py` | 15 passed |
| Parity (real Remotion/FFmpeg) | `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py` | 18 passed |
| make check | structure, doctor, ruff, mypy, cycles, remotion-typecheck, renderer-parity | PASS |
| Wheel smoke | `bash scripts/smoke_wheel_install.sh` (incl. installed-wheel scaffold golden path) | PASS |
| Remotion typecheck | `cd remotion && npm run typecheck` | PASS |
| Full suite (CI mirror) | `pytest -q -m "not integration and not opt_in"` | 7778 passed / 62 failed — ALL pre-existing at C5-batch4-done in unrelated areas (schema_contract, supabase, reigh, project_cli, timeline, packs_validate); zero epic-caused regressions after the 5 test-contract fixes |
| Docs commands | `bash tests/verify_docs_commands.sh` | PASS |

## Freeze assertions

- Every built-in path (remotion, ffmpeg, optimized, audio-reactive, hybrid,
  single-segment) → exactly one video + one committed sidecar
  (`test_freeze.py`, parity matrix).
- Failure paths clean temp artifacts; never commit a sidecar.
- Attached renders create only their intended ledger (attached-render +
  caller-migration suites).
- Package data: schemas + manifests + fixtures ride in the wheel (wheel
  smoke + `test_package_data.py`).
- Generic core code contains no concrete backend names outside registry
  wiring/compatibility shims (`test_generic_code_audit.py`).

## Epic scope check

- Public renderer contract (`render-backend-v1.md`), dependency inversion
  (core ↔ backends via qualified ids + transport), discovery/selection by
  qualified ID, contract tests, provenance ("why this backend rendered
  this") — M1 complete.
- Developer kit (SDK `render`/`support`/`renderer_main`/`RenderContext`,
  four-file scaffold + CLI verbs, replay bundles, docs) — M2 complete.

## Known pre-existing (not epic regressions)

- `test_render_discovers_fixture_local_effect_assets_without_real_local_pack`
  — missing developer-local `model-trends` fixture (documented baseline).
- 60 distinct full-suite failures in unrelated areas, all reproduced at
  C5-batch4-done.
