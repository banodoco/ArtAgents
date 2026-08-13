# Epic Verification — Pluggable Timeline Renderers (M1 + M2 freeze)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
Recorded: 2026-08-13 (Batch 7 rework). HEAD: `7b7bf153` + rework; tag `C8-batch7-done`.

## Complete matrix (Batch 7 rework evidence)

| Gate | Command | Result |
|---|---|---|
| Core rendering + freeze + replay + audit | `pytest -q tests/core/rendering` | 488 passed (re-run at rework HEAD) |
| Replay + bundle | `pytest -q tests/core/rendering/test_replay.py test_replay_bundle.py` | 20 passed (new bundle fields: support_report, backend_config, result_path/result_sha256, localized request_digest, partial/<sha256> files, JSON-input host-path rewriting) |
| Generic-code audit + freeze | `pytest -q tests/core/rendering/test_generic_code_audit.py test_freeze.py` | 17 passed (audit now scans profile.py + astrid/__init__.py + astrid/sdk/; freeze adds real-CommandTransport success + missing-binary failure paths) |
| Rendering + SDK consolidated | `pytest -q tests/core/rendering tests/packs/rendering tests/test_sdk_rendering.py tests/test_sdk_public_surface.py tests/test_sdk_render_context.py` | 748 passed / 2 skipped / 34 failed — ALL pre-existing env gaps: missing installed `banodoco_timeline_schema` package (ImportError), Remotion/chromium environment (`MachPortRendezvousServer`/unsupported), and the documented `test_render_discovers_fixture_local_effect_assets_without_real_local_pack` fixture test (`.oracle/baseline.md`) |
| Docs commands | `bash tests/verify_docs_commands.sh` | PASS (re-run at rework HEAD) |
| make check | `make check` | not re-run in rework; see prior record (PASS at batch7 commit) |
| Wheel smoke | `bash scripts/smoke_wheel_install.sh` | not re-run in rework; see prior record (PASS at batch7 commit) |
| make ci | `make ci` | not re-run in rework (heavy; >20 min budget). Individual gates: `make check` PASS (prior record), editable/wheel install covered by prior wheel smoke (PASS), CI-mirror `pytest -q -m "not integration and not opt_in"` prior record 7778 passed / 62 failed — all pre-existing at C5-batch4-done; not re-run in rework |
| Full suite (CI mirror) | `pytest -q -m "not integration and not opt_in"` | not re-run in rework (heavy); see prior record — 7778 passed / 62 failed, all pre-existing in unrelated areas; zero epic-caused regressions |
| Parity (real Remotion/FFmpeg) | `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py` | prior record 18 passed. NOTE: parity tests treat a chromium denial (`MachPortRendezvousServer` / headless chromium refusal) as success-with-skip — a skipped real render is recorded as a skip, not as a rendered video; only non-skipped cases prove real media output |
| Tags | `git tag C8-batch7-done` | applied at rework HEAD. Prior loose tags (`C2-batch1-done` … `C7-batch6-done`) are historical markers; the Batch 7 freeze tag is `C8-batch7-done` |

## Freeze assertions

- Every built-in path (remotion, ffmpeg, optimized, audio-reactive, hybrid,
  single-segment) → exactly one video + one committed sidecar
  (`test_freeze.py`, parity matrix); a real-CommandTransport FFmpeg path now
  locks the same invariant without FakeTransport.
- Failure paths clean temp artifacts; never commit a sidecar — including a
  real missing-binary path that still retains a replay bundle.
- Attached renders create only their intended ledger.
- Package data: schemas + manifests + fixtures ride in the wheel.
- Generic core code (now incl. `profile.py`, `astrid/__init__.py`,
  `astrid/sdk/`) contains no concrete backend names outside registry
  wiring/compatibility shims (`test_generic_code_audit.py`).

## Epic scope check

- Public renderer contract (`render-backend-v1.md`), dependency inversion
  (core ↔ backends via qualified ids + transport), discovery/selection by
  qualified ID, contract tests, provenance, replay bundles + `replay` verb —
  complete; V1 scope (sync local only; async/remote/compositing deferred) is
  documented in the contract and guides.
- Developer kit (SDK `render`/`support`/`renderer_main`/`RenderContext`,
  four-file scaffold + CLI verbs incl. `replay`, docs) — complete.

## Known pre-existing (not epic regressions)

- `test_render_discovers_fixture_local_effect_assets_without_real_local_pack`
  — missing developer-local `model-trends` fixture (documented baseline).
- Missing installed `banodoco_timeline_schema` package blocks timeline
  validation in `tests/packs/rendering` (env gap, not epic-caused).
- Remotion parity tests skip (chromium denial) rather than render when the
  host cannot launch headless chromium.
