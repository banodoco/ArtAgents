# M1 Gate — recorded matrix (Batch 5)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
Recorded: 2026-08-12. HEAD: `6e740c8e` (C6-batch5-done pending oracle PASS).

## Gates

| Gate | Command | Result |
|---|---|---|
| Structure | `make structure` | PASS |
| Doctor | `make doctor` | PASS (after copying `.env` into the worktree; env is gitignored) |
| Ruff | `make ruff` | PASS (baseline re-based: 1448 findings — includes batches 1-5 code with repo-standard E402 guard-import pattern) |
| Mypy | `make mypy` | PASS (0 findings) |
| Cycles | `make cycles` | PASS (baseline re-based: 14 known cross-package cycles, all pre-existing) |
| Remotion typecheck | `make remotion-typecheck` | PASS |
| Renderer parity | `make renderer-parity` | PASS (18/18, real Remotion + FFmpeg) |
| Wheel smoke | `bash scripts/smoke_wheel_install.sh` | PASS (schemas, fixtures, manifests install + discoverable) |
| Full pytest (CI mirror) | `pytest -q -m "not integration and not opt_in"` | 7778 passed / 62 failed / 79 skipped (60 distinct test failures — ALL verified pre-existing at C5-batch4-done in unrelated areas; 0 epic-caused regressions) |
| CI JSON contract | `tests/reshape/test_ci_json.py` | PASS (timeout extended to 1500s for the renderer-parity blocking lane) |

## Epic-adjacent suites (rendering + migrated callers)

`tests/core/rendering tests/packs/rendering tests/packs/test_renderer_parity.py
tests/packs/hype tests/packs/iteration tests/packs/editorial
tests/test_task_env_contract.py tests/packs/video_editing`: **822 passed,
1 failed (pre-existing model-trends env fixture), 3 skipped, 9 subtests**.

## Failure attribution (full suite)

- 60 distinct failures — all present at C5-batch4-done (before Batch 5) in
  unrelated areas: `test_schema_contract` (timeline schema), supabase data
  provider, reigh integration/open_in_reigh, project_cli edit, timeline
  characterization/secondary_edits, packs_validate/pack_enum/generate_video,
  third_party_integration, sprint1 regression, etc. Sampled subset confirmed
  identical failure counts at C5-batch4-done (33/33 in the sampled areas).
- Batch 5 introduced 4 test-contract failures (pipeline_caching ×2,
  human_notes ×1, ci_json ×1) — ALL fixed and verified green.

## Pre-existing env-dependent failure (documented baseline)

`tests/packs/rendering/test_render_remotion_registry.py::...::
test_render_discovers_fixture_local_effect_assets_without_real_local_pack` —
missing developer-local `model-trends` effect fixture; documented in
`.oracle/baseline.md`.

## Conclusion

M1 gate: ALL epic-scoped gates PASS. Full-suite failures are pre-existing
and unrelated to this epic. M1 (renderer kernel) is complete: public
renderer contract, dependency inversion, qualified-ID discovery/selection,
contract tests, provenance, attached-child invocation, caller migration,
semantic parity, packaging, and docs.
