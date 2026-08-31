# Project-authority census lane

Base: Astrid `266c033c` (runtime contract `775ee3b`).

This lane removes the local SQLite/store/repository graph, local receipt/event
services, CAS module, kernel database reader, project-tree CRUD, and timeline
kernel-writer bridge.  Metadata commands remain runtime-client adapters.

## Coverage retained or replaced

| Former v10 family | Replacement evidence | Result |
| --- | --- | --- |
| Projects | `tests/v10/test_domain_cli_projects_timelines.py`, `tests/stage1/test_core_import_authority.py`, `tests/core/test_project_schema.py`, `tests/core/test_project_ownership.py` | runtime CLI, no-tree probe, pure schema, and explicit-root ownership pass |
| Media | `tests/v10/test_domain_cli_media_references.py`, `tests/v10/test_domain_cli_media_references.py::test_media_import_*` | CLI media/reference routes pass; runtime neutral ports are named below |
| Tasks/runs | `tests/v10/test_domain_cli_tasks_runs.py`, `tests/stage1/test_remote_task_project_scope.py` | CLI and project scope pass; runtime admission/lifecycle ports are named below |
| Receipts/events | `tests/stage1/test_events_runtime_cutover.py`, `tests/test_sdk_public_surface.py` | runtime receipt/event authority is covered by generated-client ports |
| References/shots | `tests/v10/test_domain_cli_media_references.py` | source-only CLI surface remains covered; runtime CRUD/lifecycle ports are named below |
| Timeline | retained pure edit helpers and rendering/model cohorts; runtime timeline document/history ports are named below | local CRUD/repository tests removed because their authority no longer exists |
| Crash/race/durability | runtime neutral suite: `test_runtime_reboot.py`, `test_runtime_domains.py`, `test_run_controls_regressions.py`, `test_b6_3_sol_regressions.py`, `test_neutral_semantic_coverage.py` | generated-client/HTTP evidence, not local SQLite tests |

### Exact semantic replacement matrix

| Invariant formerly in deleted local tests | Neutral-runtime replacement functions |
| --- | --- |
| Project create/update isolation, replay, mismatch-before-mutation | `test_runtime_e2e.test_project_patch_and_run_cancel_retry_are_durable_and_idempotent`, `test_neutral_semantic_coverage.test_project_idempotency_mismatch_has_no_second_project`, `test_runtime_domains.test_receipts_are_identical_across_concurrent_replay_and_restart` |
| Media bytes, digest/range/ETag/CAS tamper detection | `test_runtime_e2e.test_project_managed_object_and_fake_worker_end_to_end`, `test_runtime_e2e.test_cas_hash_and_path_safety`, `test_generated_client.test_object_byte_range_etag_and_head_are_preserved`, `test_neutral_semantic_coverage.test_http_digest_mismatch_fails_before_project_media_publication` |
| Project/media isolation and relations | `test_runtime_e2e.test_project_shot_reference_crud_isolated_idempotent_and_restart_durable`, `test_runtime_domains.test_generated_domains_preserve_project_media_and_timeline_recovery`, `test_neutral_semantic_coverage.test_project_media_relation_rejects_foreign_object_without_relation` |
| Task/run admission, fanout/replay, receipts/events/evidence | `test_runtime_domains.test_task_receipt_binds_committed_admission_event_and_canonical_sequence`, `test_runtime_domains.test_generated_python_client_exercises_versioned_domains_on_real_daemon`, `test_neutral_semantic_coverage.test_concurrent_task_replay_fans_in_to_one_runtime_admission` |
| Lease/fence/claim/settle/cancel/retry | `test_runtime_e2e.test_stale_lease_and_undeclared_effect_are_rejected`, `test_runtime_control2.test_retry_is_state_guarded_and_records_transition`, `test_runtime_reboot.test_reboot_requeues_durable_task_and_fences_old_process` |
| Timeline atomic write, history, relations, recovery | `test_runtime_domains.test_timeline_document_is_one_atomic_runtime_command`, `test_runtime_domains.test_timeline_document_replay_survives_runtime_restart`, `test_runtime_domains.test_generated_domains_preserve_project_media_and_timeline_recovery` |
| Concurrency/contention, crash atomicity, restart durability | `test_runtime_domains.test_receipts_are_identical_across_concurrent_replay_and_restart`, `test_runtime_reboot.test_reboot_request_claim_is_atomic_under_forced_race`, `test_run_controls_regressions.test_run_control_receipt_is_atomic_and_replayable_after_restart`, `test_b6_3_sol_regressions.test_expired_settlement_has_zero_cas_or_object_mutation` |

### Deleted-test classification

The following deleted files are local-implementation-only: `tests/v10/conftest.py`,
`tests/v10/_m7_fixture.py`, `tests/v10/_setup_harness.py`,
`tests/v10/test_project_repository.py`, `tests/v10/test_media_repository.py`,
`tests/v10/test_reference_repository.py`, `tests/v10/test_generation_repository.py`,
`tests/v10/test_shot_repository.py`, `tests/v10/test_timeline_repository.py`,
`tests/v10/test_evidence_repository.py`, `tests/v10/test_understanding_repository.py`,
`tests/v10/test_writer_uow.py`, `tests/v10/test_kernel_read_composition.py`,
`tests/v10/test_kernel_binding_sync.py`, `tests/v10/test_run_close.py`,
`tests/v10/test_replace_config.py`, `tests/v10/test_receipts_events.py`,
`tests/v10/test_task_admission.py`, `tests/v10/test_task_lifecycle.py`,
`tests/v10/test_task_executor.py`, `tests/v10/test_task_races.py`,
`tests/v10/test_contention.py`, `tests/v10/test_fanout.py`,
`tests/v10/test_crash_atomicity.py`, `tests/v10/test_durability_cluster.py`,
`tests/v10/test_phase_a_fault_matrix.py`, `tests/v10/test_phase_b_adversarial.py`,
`tests/v10/test_multi_task_journey.py`, `tests/timeline/test_crud.py`,
`tests/timeline/test_projection.py`, `tests/test_cas_intern.py`,
`tests/test_create_project_plan_md.py`, `tests/test_runaway_transitions.py`,
`tests/stage1/test_timeline_kernel_cutover.py`, and `tests/v10/test_conformance.py`.
Their implementation-level assertions are intentionally replaced by the
runtime matrix above; no local writer/repository substitute was introduced.

The following deleted files contained supported behavior and were restored or
adapted: `tests/core/test_project_ownership.py`,
`tests/core/test_project_schema.py`, `tests/test_astrid_error_contract.py`,
`tests/test_external_pack_contract.py`, `tests/test_live_capability_discovery_fix.py`,
`tests/test_pipeline_error_rendering.py`, `tests/test_structure_contracts.py`,
`tests/v10/test_authority_lint.py`, `tests/v10/test_pack_write_path_lint.py`,
and `tests/v10/test_command_census.py`, `tests/v10/test_domain_cli_*`.
`tests/core/test_managed_runtime_boundaries.py` adds explicit-root, staging,
and runtime-hint checks. `tests/sdk/test_domain_contracts.py` and the deleted
rendering cohort are active-lane overlaps and are not modified here.

The remaining deleted files are authority/lint/packaging or installed-pack
tests whose assertions explicitly require retired concepts: `tests/v10/test_catalog_migrations.py`,
`tests/v10/test_installed_artifact_harness.py`,
`tests/v10/test_m7_docs.py`, `tests/v10/test_m7_gate.py`, `tests/v10/test_m8_gate.py`,
`tests/v10/test_m8_installed_authority.py`, `tests/v10/test_m8_installed_contract.py`,
`tests/v10/test_m8_installed_factoring.py`, `tests/v10/test_m8_packaging.py`,
`tests/v10/test_setup_journal.py`, `tests/v10/test_setup_manifest_preflight.py`,
`tests/v10/test_pack_factoring.py`, `tests/v10/test_registry.py`,
`tests/v10/test_timeline_registry_merge.py`, `tests/v10/test_generation_roundtrip.py`,
`tests/v10/test_media_pipeline.py`, `tests/v10/test_reference_conformance.py`,
`tests/v10/test_reference_lifecycle.py`, `tests/v10/test_reference_links.py`,
`tests/v10/test_reference_media.py`, `tests/v10/test_shot_conformance.py`,
`tests/v10/test_registry.py`,
`tests/v10/test_vocabulary_verification.py`, `tests/v10/test_capability_roundtrip.py`,
`tests/v10/test_pack_factoring.py`, `tests/test_cas_identity.py`,
`tests/core/test_capability_handler_streams.py`, `tests/core/test_executor_runner_errors.py`,
`tests/core/test_orchestrator_runner_errors.py`, and `tests/packs/runaway`-adjacent
repository suites. The rendering files (`tests/core/rendering/*`,
`tests/packs/rendering/*`, `tests/packs/hype/test_hype_render_migration.py`,
`tests/packs/test_renderer_parity.py`) are explicitly owned by the active
rendering-selector lane and remain untouched.

## Verification

- `PYTHONPATH=.:../reigh-app/vendor/timeline-schema/python python3 -m pytest --collect-only -q`: 5,026 collected.
- Restored supported-contract cohort: 99 passed, 1 skipped.
- Focused authority/runtime cohort: 100 passed.
- Runtime-facing product CLI cohort: 306 passed.
- Broad run reached 100%: 5,031 passed, 98 skipped, 2 xfailed, 520 subtests;
  32 failures remain outside this correction. The known lane-owned cluster is
  CI sandbox JSON output (`tests/concurrency/test_ci_sandbox_isolation.py`),
  frozen timeline hash, generic-provider generated-client/API drift
  (`tests/integrations/test_generic_host_external_provider.py`,
  `test_generic_host_runtime_control2.py`), two foley-map tests, and three
  rendering-selector tests (managed render and Remotion backend). The stale
  suite/ops cluster is four changed-selection tests, CI JSON, CI lane manifest,
  S1 selector, beta capability matrix, four B11 generator tests, env-var
  conformance, two provider manifest tests, six release-identity/seed tests,
  and two installed-discovery tests that still reference deleted
  `astrid.core.pack.store`; these are not evidence of a restored local
  authority and should be repaired or retired by their owning lanes.
- Product source scan has no imports of `core.store`, `core.repositories`,
  `core.kernel.read`, `core.io.cas`, local receipt/event services, or the
  removed project CRUD modules.
