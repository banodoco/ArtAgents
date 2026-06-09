# Test Layout — M3 Canonical Map

This document is the **M3 architecture note** that defines the canonical test
directory layout. It is derived from `docs/architecture/test-relocation-map.json`
(the M0 relocation artifact) and records the settled decisions from the M3
test-relocation milestone. It is normative for M3 and should be updated when
later milestones reclassify a test home.

**M3 key rule**: Tests that exercise a single domain subsystem move into that
domain's canonical test directory. Tests that are cross-cutting contracts,
SDK/public-surface verification, structure enforcement, platform contracts, or
have no clear single domain **stay at `tests/` root**. The relocation map is
authoritative for all `stay_root` designations.

## 1. Canonical Test Directories

The following test directories are the canonical homes for domain-specific
tests after M3 relocation. Each directory corresponds to one domain subsystem
and contains only tests for that domain.

| Directory | Purpose | Source of Tests |
| --- | --- | --- |
| `tests/agentic/` | Agentic scenario and UX tests | 3 root files relocated |
| `tests/audit/` | Audit subsystem tests | 1 root file relocated |
| `tests/core/` | Core kernel tests (generation, model_catalog, runtime, task, util, project, executor, element) | 47 root files relocated |
| `tests/fixtures/` | Test fixtures and fixture-related tests | 1 root file relocated |
| `tests/orchestrate/` | Orchestrate DSL, compile, and test-runner tests | 8 root files relocated |
| `tests/packs/` | Pack-specific tests (builtin, editorial, event_talks, external, foley, hype, runpod, stream_content, thumbnail_maker, and others) | 60 root files relocated |
| `tests/session/` | Session lifecycle tests | 2 root files relocated |
| `tests/task/` | Task kernel tests — **sole canonical home** for all task tests | 46 root files relocated |
| `tests/timeline/` | Timeline tests — **sole canonical home** for all timeline tests | 15 root files relocated |
| `tests/spikes/` | Spike/exploratory tests | Existing directory, no new relocations |

**Pre-existing directories** that received no root-level relocations but remain
active: `tests/adapter/`, `tests/concurrency/`, `tests/golden/`, `tests/helpers/`,
`tests/migrations/`.

### 1.1 Settled Home Ambiguities

Two domain-split ambiguities were resolved during M3 planning:

- **Timeline**: `tests/timeline/` is the **sole canonical home** for all timeline
  tests. `tests/core/timeline/` is **not created**. The source tree has
  `astrid/core/timeline/` as the canonical implementation home, but the test
  convention uses `tests/<domain>/` rather than mirroring the `core/` nesting.
- **Task**: `tests/task/` is the **sole canonical home** for all task tests.
  Root task tests move to `tests/task/`, not `tests/core/task/`. Same rationale
  as timeline: tests use flat domain directories.

## 2. Root Tests That Stay (`stay_root`)

The relocation map designates **67 test files** to remain at `tests/` root because
they are cross-cutting, enforce structural contracts, verify the SDK public surface,
or have no clear single domain. These are listed below, categorized by concern.

### 2.1 SDK Public Surface Tests

These tests verify the normative `import astrid` public API. They belong at root
because the SDK surface spans all subsystems and must be verified from the
top-level entrypoint.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_capability_handle.py` | 533 | SDK capability handle — public surface test |
| `test_capability_runner.py` | 327 | SDK capability runner — public surface test |
| `test_capability_schema.py` | 283 | SDK capability schema — public surface test |
| `test_result_manifest.py` | 300 | Result manifest — SDK/public surface |
| `test_sdk_public_surface.py` | 3,422 | SDK public surface — normative public API verification (large file) |

### 2.2 Cross-Cutting Contract Tests

These tests verify contracts that apply across multiple subsystems. Moving
them into any single domain directory would misrepresent their scope.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_astrid_error_contract.py` | 392 | Cross-cutting error contract — applies to SDK and all subsystems |
| `test_env_vars_conformance.py` | 166 | Environment variables conformance — cross-cutting contract |
| `test_event_hash_conformance.py` | 112 | Event hash conformance — cross-cutting contract |
| `test_exec_error_contract.py` | 119 | Exec error contract — cross-cutting |
| `test_external_app_contract.py` | 392 | External app contract — cross-cutting integration contract |
| `test_external_pack_contract.py` | 322 | External pack contract — cross-cutting integration contract |
| `test_platform_contract.py` | 743 | Platform contract — normative v1 contract verification |
| `test_recoverability_conformance.py` | 787 | Recoverability conformance — cross-cutting contract |
| `test_recovery_command_conformance.py` | 274 | Recovery command conformance — cross-cutting contract |
| `test_run_ledger_conformance.py` | 388 | Run ledger conformance — cross-cutting contract |
| `test_run_status_contract.py` | 486 | Run status contract — cross-cutting |
| `test_schema_contract.py` | 431 | Schema contract — cross-cutting |
| `test_uuid_str_conformance.py` | 99 | UUID string conformance — cross-cutting contract |

### 2.3 Structure Enforcement Tests

These tests enforce repository structure rules (import layering, migration
completion, compatibility shims). They scan the entire repo and cannot be
scoped to a single domain.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_boundary_candidates.py` | 90 | Structure boundary analysis — belongs with structure contracts |
| `test_structure_contracts.py` | 838 | Structure contracts — primary structure enforcement test file |

### 2.4 Agent and Canonical CLI Contract Tests

These tests verify the agent-facing CLI contract and canonical entrypoint
behavior. The agent CLI contract spans multiple subsystems.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_agent_cli_contract.py` | 252 | Cross-cutting agent CLI contract — applies to multiple subsystems |
| `test_agent_cli_kernel.py` | 243 | Cross-cutting agent CLI kernel contract |
| `test_canonical_aliases.py` | 46 | Canonical alias verification — cross-cutting |
| `test_canonical_cli.py` | 341 | Canonical CLI contract — cross-cutting |
| `test_canonical_entrypoint.py` | 66 | Canonical entrypoint verification — cross-cutting |
| `test_cli_choices.py` | 297 | CLI choices — cross-cutting CLI infrastructure |
| `test_stream_discipline.py` | 209 | Stream discipline — cross-cutting CLI contract |

### 2.5 Milestone Contract and Regression Tests

These tests guard milestone-level end-state contracts and broad regression
surfaces. They are intentionally broad and cannot be domain-scoped.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_m5b_baseline_public_surface.py` | 1,233 | M5b baseline public surface — milestone contract verification |
| `test_m5b_end_state_regression.py` | 110 | M5b end state regression — milestone contract verification |
| `test_sprint1_regression.py` | 805 | Sprint 1 regression — broad regression guard |

### 2.6 Capability and Alias Resolution Tests

These tests exercise cross-cutting capability machinery (alias resolution,
handle lifecycle) that spans packs, core, and the SDK surface.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_alias_resolver_cycles.py` | 100 | Cross-cutting alias resolution cycles |
| `test_capability_alias_resolver.py` | 1,949 | Cross-cutting capability alias resolution (large file) |

### 2.7 Pipeline and Gateway Tests

Pipeline and gateway tests exercise top-level request routing that spans
multiple subsystems. They belong at root because the pipeline is the
top-level gateway, not a single domain.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_pipeline_caching.py` | 133 | Pipeline caching — top-level gateway/pipeline concern |
| `test_pipeline_dispatch_aliases.py` | 68 | Pipeline dispatch aliases — top-level gateway/pipeline concern |
| `test_pipeline_editor_loop.py` | 495 | Pipeline editor loop — top-level gateway/pipeline concern |
| `test_pipeline_error_rendering.py` | 249 | Pipeline error rendering — top-level gateway/pipeline concern |
| `test_pure_generative_pipeline.py` | 34 | Pure generative pipeline — top-level pipeline concern |
| `test_url_pipeline_smoke.py` | 177 | URL pipeline smoke — top-level pipeline concern |

### 2.8 Threads Tests

Threads tests stay at root because no `tests/threads/` directory exists.
M3 may create one in a later phase; until then these remain at root.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_threads_attribute.py` | 147 | Threads attribute — threads subsystem, no `tests/threads/` exists |
| `test_threads_cli.py` | 168 | Threads CLI — threads subsystem |
| `test_threads_dependencies.py` | 16 | Threads dependencies |
| `test_threads_docs_skill_inspect.py` | 77 | Threads docs skill inspect |
| `test_threads_ids.py` | 17 | Threads IDs |
| `test_threads_index.py` | 170 | Threads index |
| `test_threads_prefix.py` | 25 | Threads prefix |
| `test_threads_producer_optins.py` | 57 | Threads producer opt-ins |
| `test_threads_provenance.py` | 163 | Threads provenance |
| `test_threads_reaper.py` | 65 | Threads reaper |
| `test_threads_record.py` | 294 | Threads record |
| `test_threads_variants.py` | 162 | Threads variants |
| `test_threads_variants_help.py` | 13 | Threads variants help |

### 2.9 Repo-Level and Miscellaneous Tests

These tests exercise repo-level concerns (health checks, onboarding, docs
verification, runtime inventory) or have no clear single domain.

| File | Lines | Rationale |
| --- | --- | --- |
| `test_doctor_setup.py` | 453 | Doctor/setup diagnostic — repo-level health check |
| `test_gateway_status_routing.py` | 118 | Gateway status routing — top-level gateway |
| `test_logo_ideas.py` | 98 | Logo ideas — miscellaneous, no clear domain |
| `test_onboarding_docs.py` | 230 | Onboarding docs — cross-cutting documentation verification |
| `test_onboarding_parity.py` | 212 | Onboarding parity — cross-cutting |
| `test_provenance_fields.py` | 109 | Provenance fields — cross-cutting threads/lineage concern |
| `test_publish.py` | 174 | Publish — cross-cutting, no single domain |
| `test_quote_scout.py` | 21 | Quote scout — miscellaneous, no clear domain |
| `test_reviewers.py` | 170 | Reviewers — cross-cutting, no single domain |
| `test_runtime_correctness_inventory.py` | 75 | Runtime correctness inventory — repo-level scan, not domain-specific |
| `test_skills.py` | 158 | Skills — cross-cutting skills infrastructure |
| `test_skills_sync_registry.py` | 34 | Skills sync registry — cross-cutting |
| `test_social_publish.py` | 77 | Social publish — cross-cutting |
| `test_third_party_integration.py` | 153 | Third-party integration — cross-cutting |
| `test_triage.py` | 125 | Triage — cross-cutting |
| `test_validate.py` | 77 | Validate — cross-cutting validation |

## 3. M3 Settled Decisions

| Decision | Description |
| --- | --- |
| **SD1** | The relocation map (`test-relocation-map.json`) is authoritative for all `stay_root` designations. SDK/public-contract tests remain at `tests/` root. |
| **SD2** | `tests/timeline/` is the sole canonical home for all timeline tests. `tests/core/timeline/` is not created. |
| **SD3** | `tests/task/` is the sole canonical home for all task tests. Root task tests move to `tests/task/`, not `tests/core/task/`. |


