# EPIC.md — Cross-cutting handoffs and surfaced issues

## m3 Handoff

Items identified during m2 (Test Integrity — make green mean green) that are deferred to m3 or later milestones. These are real product/runtime behaviors that the cleaned test suite may surface; they are NOT to be fixed during m2.

### No regressions surfaced from denylist removal (T3)

The Sprint 1 regression denylist in `tests/test_sprint1_regression.py` contained a single stale entry:

- `test_root_help_explains_canonical_gateway` — previously failing due to help-text drift ("new" subcommand); now passes as-is in the current codebase.

The `KNOWN_FAILURES` class attribute and all failure-filtering logic have been removed. The meta-test `test_existing_regression_suite_passes` is now a plain subprocess assertion (rc=0). No strict xfail annotations were required because no product behavior failure re-emerged.

### Deferred items (populated by later m2 tasks as needed)

- **T4: Attested sentinel-only produces check validation** — `astrid/core/task/plan.py` does not reject attested steps (`requires_ack=True`) whose `produces` checks are all sentinel-only (no semantic check). The test `test_attested_sentinel_only_check_rejected_at_load` was deleted (it was a skipped aspirational test with no matching implementation). The validation contract — that an attested step must have at least one non-sentinel produces check — remains a desirable product gap for a future milestone (m3 or later). See also `tests/test_task_inline_checks.py::test_attested_with_all_of_semantic_check_accepts` for the happy path.

### Out-of-scope sibling double-execution pattern (from T2)

`astrid/packs/video_editing/orchestrators/event_talks/run.py` line 527-549 contains the same `gate_command()` + `subprocess.run(decision.command)` double-execution pattern that was fixed in the test harness during T2 (`astrid/orchestrate/test_runner.py` and `tests/test_task_kernel_e2e.py`). This is a **product runtime** orchestrator (not a test harness), so it was intentionally left untouched during m2 per the milestone constraint of "no product/runtime repair." When `gate_command()` dispatches a code step through its adapter (e.g. `adapter: local`), the adapter already spawns the subprocess; the subsequent `subprocess.run(decision.command)` on line 549 spawns a second instance. Resolution deferred to m3 (runtime-correctness).

### Deferred runtime bug surfaced by default-lane render coverage (T8)

- **Local Remotion bundle import drift** — `tests/test_audio_render.py::AudioRenderTest::test_rendered_mp4_contains_audio_stream` currently fails because the local effect at `astrid/packs/local/elements/effects/model-trends` imports `../../../../builtin/elements/_shared/contracts`, but that module path does not exist at bundle time. The resulting Remotion/Webpack error is `Can't resolve '../../../../builtin/elements/_shared/contracts'`. This is a real runtime/bundling defect in the local element tree, not a test-harness integrity issue, so m2 leaves it as a narrow strict xfail and records the handoff here for m3.

### Fixture-family unification skipped

The plan referenced `tests/_lifecycle_fixtures.py` as a candidate for fixture-family unification across task lifecycle test modules, but this file is a Phase 5 lifecycle-test helper module (not a shared fixture definition). No fixture-family unification was performed because shared fixtures currently live in `tests/conftest.py`. This is a note, not a deferred action item.

## Related epics

- [Harness Polish](docs/megaplan/epics/harness-polish/EPIC.md) — the parent epic governing m2 test-integrity work.
- [Pack Taxonomy](docs/megaplan/epics/pack-taxonomy/EPIC.md)
- [Timeline Event Sourcing](docs/megaplan/epics/timeline-event-sourcing/EPIC.md)
