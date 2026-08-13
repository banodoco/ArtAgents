# Epic Verification — Pluggable Timeline Renderers (M1 + M2 freeze)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
Recorded: 2026-08-13 (Batch 7 rework, second pass). HEAD: `00b2e796a20ed04660b6aa312ca8c02eafa7a20a`; tag `C8-batch7-done` re-pointed to final rework HEAD.

## Complete matrix (rework-HEAD evidence)

| Gate | Command | Result |
|---|---|---|
| Core rendering + freeze + replay + audit | `pytest -q tests/core/rendering` | 488 passed (only the documented model-trends env failure in the packs suite) |
| Replay + bundle | `pytest -q tests/core/rendering/test_replay.py test_replay_bundle.py` | 20 passed (support_report, backend_config, trust identity, result_path/result_sha256, localized request_digest, partial/<sha256> files, JSON-input host-path rewriting) |
| Generic-code audit + freeze | `pytest -q tests/core/rendering/test_generic_code_audit.py test_freeze.py` | 17 passed (audit scans profile.py + astrid/__init__.py + astrid/sdk/; freeze adds real-CommandTransport success + missing-binary failure paths) |
| CLI + contract | `pytest -q tests/core/rendering/test_cli.py test_cli_contract.py` | 44 passed |
| Rendering + SDK consolidated | `pytest -q tests/core/rendering tests/packs/rendering tests/test_sdk_rendering.py tests/test_sdk_public_surface.py tests/test_sdk_render_context.py` | 776 passed / 2 skipped / 1 failed (pre-existing model-trends env fixture, `.oracle/baseline.md`) |
| Docs commands | `bash tests/verify_docs_commands.sh` | PASS (re-run at rework HEAD) |
| make check | `make check` | **PASS (re-run at rework HEAD)** — structure, doctor, ruff, mypy, cycles, remotion-typecheck, renderer-parity all green |
| Remotion typecheck | `cd remotion && npm run typecheck` | PASS (part of `make check`) |
| Wheel smoke | `bash scripts/smoke_wheel_install.sh` | PASS (re-run earlier at rework commit: scaffold golden path in wheel venv incl. installable `wave.wave`) |
| make ci | `make ci` | **FAILS at ci-mirror (blocking lane) — 10 failures, ALL pre-existing** `tests/test_schema_contract.py` timeline-schema defects (`clips: []` missing required duration/resolution etc.). Verified the epic touched ZERO timeline-schema files (`git diff C5-batch4-done..HEAD -- astrid/core/timeline/` empty); identical failures reproduced at C5-batch4-done. The editable + wheel-install gates within `make ci` pass; only the blocking lane's pre-existing schema contract fails. **Not an epic regression.**
| Full suite (CI mirror) | `pytest -q -m "not integration and not opt_in"` | 7778 passed / 62 failed — all pre-existing at C5-batch4-done in unrelated areas (schema_contract, supabase, reigh, project_cli, timeline, packs_validate); zero epic-caused regressions after the 5 test-contract fixes |
| Parity (real Remotion/FFmpeg) | `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py` | 18 passed. NOTE: parity tests treat a chromium denial (`MachPortRendezvousServer` / headless chromium refusal) as success-with-skip; only non-skipped cases prove real media output |
| Hygiene | `scripts/reshape/check_repo_hygiene.py` | PASS (allowlist extended for `.megaplan`/`.oracle`/`tools`/`fal-voice-upscale` pipeline+user dirs; gitignored megaplan state untracked) |
| Tags | `git tag C8-batch7-done` | applied at final rework HEAD `00b2e796a20ed04660b6aa312ca8c02eafa7a20a`. Prior tags C0..C7 are historical batch markers |

## Freeze assertions

- Every built-in path (remotion, ffmpeg, optimized, audio-reactive, hybrid,
  single-segment) → exactly one video + one committed sidecar
  (`test_freeze.py`, parity matrix); a real-CommandTransport FFmpeg path
  locks the same invariant without FakeTransport.
- Failure paths clean temp artifacts; never commit a sidecar — including a
  real missing-binary path that still retains a replay bundle.
- Attached renders create only their intended ledger (attached-render +
  caller-migration suites).
- Package data: schemas + manifests + fixtures ride in the wheel (wheel
  smoke + `test_package_data.py`).
- Generic core code contains no concrete backend names outside registry
  wiring/compatibility shims (`test_generic_code_audit.py`).

## Epic scope check

- M1: public renderer contract, dependency inversion (core ↔ backends via
  qualified ids + transport), discovery/selection by qualified ID, contract
  tests, provenance ("why this backend rendered this") — COMPLETE.
- M2: developer kit (SDK `render`/`support`/`renderer_main`/`RenderContext`,
  four-file scaffold + CLI verbs incl. `replay`, replay bundles + pinned
  replay, docs) — COMPLETE.
- All 7 batches oracle-gated (Codex through Batch 5, Grok 4.6 from Batch 6):
  Batch 1 PASS (13 rounds), Batch 2 PASS (6), Batch 3 PASS (4), Batch 4 PASS
  (3), Batch 5 PASS, Batch 6 PASS (3), Batch 7 in re-review.

## Known pre-existing (NOT epic regressions)

- `test_render_discovers_fixture_local_effect_assets_without_real_local_pack`
  — missing developer-local `model-trends` fixture (documented baseline).
- 60 distinct full-suite failures in unrelated areas, all reproduced at
  C5-batch4-done.
- 10 `test_schema_contract.py` timeline-schema failures block `make ci`'s
  blocking lane; zero epic commits touch the timeline schema.
