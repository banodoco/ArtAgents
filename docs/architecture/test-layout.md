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

## 3. SDK / Public-Contract Rationale

The relocation map's `stay_root_rationale` establishes the principle:

> Tests that are cross-cutting contracts, structure enforcement, platform
> contracts, SDK surface verification, or have no clear single domain should
> stay at `tests/` root.

SDK tests are the most prominent category of root-staying tests because:

1. **The SDK spans all subsystems.** `test_sdk_public_surface.py` imports and
   verifies 27 names from `import astrid` — moving it into any one domain
   directory would create a misleading dependency arrow and make discovery
   harder.
2. **Capability tests are the SDK's runtime surface.** `test_capability_handle.py`,
   `test_capability_runner.py`, and `test_capability_schema.py` exercise the
   public capability lifecycle (discover → get → invoke) which crosses pack,
   core, and session boundaries.
3. **Contract tests are the normative verification layer.** Files like
   `test_platform_contract.py`, `test_schema_contract.py`, and
   `test_run_ledger_conformance.py` encode the v1 platform contract —
   these tests are the contract, and their location at root signals their
   normative status.

**Root helper modules.** In addition to the `test_*.py` files listed above,
two non-test helper modules reside at `tests/` root and must remain there:

| File | Purpose |
| --- | --- |
| `_sdk_contract.py` | SDK contract assertions shared by root contract tests |
| `_lifecycle_fixtures.py` | Lifecycle fixture factories shared by root lifecycle tests |

These helpers are consumed by root-staying tests and are not domain-specific.
They stay at root because moving them into any single domain directory would
force root tests to import across domain boundaries, creating circular
dependency risk and violating the principle that root tests should be
self-contained at the top level.

**Settled decision (SD1):** The relocation map is authoritative for all
`stay_root` designations. SDK/public-contract tests remain at `tests/` root.
No SDK test may be moved into a domain directory without updating both the
relocation map and this document.

## 4. Low-Confidence and Medium-Confidence Mappings

### 4.1 Low-Confidence Mappings

The relocation map contains **zero** low-confidence relocations. The M0
classification strategy was: if a test file's domain is ambiguous, it stays
at root. This is recorded in the map's summary notes:

> No low-confidence relocations — all ambiguous files are kept at root
> (`stay_root`).

This means every test file that was relocated received at least medium
confidence from the M0 classifier. No relocation was forced through
uncertainty.

### 4.2 Medium-Confidence Mappings — Accepted

The relocation map contains **31 medium-confidence relocations** where the
domain assignment is reasonable but the file could plausibly fit multiple
targets. (The map's `summary.by_confidence.medium` field says 19, but the
actual `relocations` array contains 31 entries with `"confidence": "medium"`.
This document uses the authoritative count from the array data.)

M3 reviewed and **accepted all 31 medium-confidence mappings** as mapped.
The settled domain-home decisions (SD2, SD3) are consistent with the
assignments: timeline tests map to `tests/timeline/`, task tests map to
`tests/task/`.

**By target directory:**

| Target | Count | Files |
| --- | --- | --- |
| `tests/agentic/` | 1 | `test_agent_probe_regression.py` |
| `tests/core/` | 14 | `test_asset_cache.py`, `test_component_manifest_parser_parity.py`, `test_elements_cli.py`, `test_elements_install.py`, `test_elements_registry.py`, `test_fork_executor_orchestrator.py`, `test_orchestrator_cli.py`, `test_orchestrator_plan_template_builders.py`, `test_styledoc_schema.py`, `test_supabase_data_provider.py`, `test_update_report.py`, `test_variants_png_atomic.py`, `test_verify_helpers.py`, `test_worker_jwt.py` |
| `tests/orchestrate/` | 1 | `test_brief_frontmatter.py` |
| `tests/packs/` | 4 | `test_arrangement_schema.py`, `test_audio_render.py`, `test_renderer_parity.py`, `test_text_card_render.py` |
| `tests/task/` | 8 | `test_banodoco_claim_loop.py`, `test_banodoco_worker.py`, `test_human_notes.py`, `test_human_review_server.py`, `test_managed_write_paths.py`, `test_quality_floor.py`, `test_quality_zones.py`, `test_refine.py` |
| `tests/timeline/` | 3 | `test_banodoco_baseline.py`, `test_effects_catalog.py`, `test_html_canvas_effect.py` |

**Acceptance rationale per file:**

- `test_agent_probe_regression.py` — could also fit `tests/core/` or stay root. Accepted: agentic regression is primarily an agent-scenario concern.
- `test_arrangement_schema.py` — could fit `tests/core/` or `tests/packs/`. Accepted as packs (arrangement schema is pack-level).
- `test_asset_cache.py` — likely core infrastructure. Accepted.
- `test_audio_render.py` — could be packs or timeline. Accepted as packs (audio render is a pack capability).
- `test_banodoco_baseline.py` — could fit timeline or task. Accepted as timeline per SD2.
- `test_banodoco_claim_loop.py` — involves task kernel and timeline. Accepted as task per SD3 (task kernel is primary).
- `test_banodoco_worker.py` — involves task kernel, could also be core. Accepted as task per SD3.
- `test_brief_frontmatter.py` — likely orchestrate-related. Accepted.
- `test_component_manifest_parser_parity.py` — could be core or packs. Accepted as core infrastructure parity.
- `test_effects_catalog.py` — could be timeline or packs. Accepted as timeline per SD2.
- `test_elements_cli.py` — could be core or packs. Accepted: elements CLI is core/element machinery.
- `test_elements_install.py` — could be core or packs. Accepted: elements install is core/element machinery.
- `test_elements_registry.py` — could be core or packs. Accepted: elements registry is core/element machinery.
- `test_fork_executor_orchestrator.py` — could be core or packs. Accepted: fork executor/orchestrator is core infrastructure.
- `test_html_canvas_effect.py` — could be timeline or packs. Accepted as timeline per SD2.
- `test_human_notes.py` — could be task or session. Accepted as task per SD3.
- `test_human_review_server.py` — could be task or session. Accepted as task per SD3.
- `test_managed_write_paths.py` — could be task or core. Accepted as task per SD3.
- `test_orchestrator_cli.py` — could be core or orchestrate. Accepted: orchestrator CLI is core/orchestrator machinery.
- `test_orchestrator_plan_template_builders.py` — could be core or orchestrate. Accepted: plan template builders are core/orchestrator machinery.
- `test_quality_floor.py` — could be task or core. Accepted as task per SD3.
- `test_quality_zones.py` — could be task or core. Accepted as task per SD3.
- `test_refine.py` — could be task or packs. Accepted as task per SD3.
- `test_renderer_parity.py` — could be packs or core. Accepted as packs (renderer parity is pack-level).
- `test_styledoc_schema.py` — could be core or stay root. Accepted as core schema.
- `test_supabase_data_provider.py` — could be core or packs/reigh. Accepted as core infrastructure.
- `test_text_card_render.py` — could be packs or timeline. Accepted as packs (text card render is a pack capability).
- `test_update_report.py` — could be core or stay root. Accepted as core.
- `test_variants_png_atomic.py` — could be core or task. Accepted as core/util.
- `test_verify_helpers.py` — could be core or stay root. Accepted as core.
- `test_worker_jwt.py` — could be core or task. Accepted as core infrastructure.

### 4.3 No Overridden Mappings

No medium-confidence mapping was overridden. The settled decisions SD2 and
SD3 (timeline and task as sole canonical homes) are consistent with the
medium-confidence assignments: `test_banodoco_baseline.py` maps to
`tests/timeline/` (not `tests/task/`), and no task-test ambiguity required
an override because all task-kernel files received high confidence.

## 5. Relocation Summary

The counts below are derived from the authoritative `relocations` and `stay_root`
arrays in `test-relocation-map.json`. The map's embedded `summary` object is stale
(183 actual relocations vs. 126 in the summary; 152 high vs. 107). This document
uses array-derived counts throughout.

| Metric | Count |
| --- | --- |
| Total root `test_*.py` files inventoried | 250 (183 relocations + 67 stay_root) |
| Recommended relocations to domain directories | 183 |
| Stay at `tests/` root | 67 |
| High-confidence relocations | 152 |
| Medium-confidence relocations (all accepted) | 31 |
| Low-confidence relocations (none, all ambiguous files stay root) | 0 |

### 5.1 Relocations by Target Directory

| Target Directory | Relocated Files |
| --- | --- |
| `tests/packs/` | 60 |
| `tests/core/` | 47 |
| `tests/task/` | 46 |
| `tests/timeline/` | 15 |
| `tests/orchestrate/` | 8 |
| `tests/agentic/` | 3 |
| `tests/session/` | 2 |
| `tests/audit/` | 1 |
| `tests/fixtures/` | 1 |

## 6. Related Documents

- **`docs/architecture/test-relocation-map.json`** — M0 relocation artifact
  with per-file target, confidence, and rationale. This is the authoritative
  source consumed by this document.
- **`docs/architecture/repo-shape.md`** — M2 canonical repo-shape contract.
  §7 covers the pre-M3 test layout and §7.4 references the relocation map.
- **`docs/platform-contract.md`** — Normative v1 platform contract verified
  by the SDK public surface tests at root.

## 7. M3 Settled Decisions

| Decision | Description |
| --- | --- |
| **SD1** | The relocation map (`test-relocation-map.json`) is authoritative for all `stay_root` designations. SDK/public-contract tests remain at `tests/` root. |
| **SD2** | `tests/timeline/` is the sole canonical home for all timeline tests. `tests/core/timeline/` is not created. |
| **SD3** | `tests/task/` is the sole canonical home for all task tests. Root task tests move to `tests/task/`, not `tests/core/task/`. |

## 8. Notes for Future Milestones

- **Threads tests** (§2.8): Currently 13 threads test files stay at root
  because no `tests/threads/` directory exists. If M3 or a later milestone
  creates `tests/threads/`, these files should move there and this document
  updated.
- **`tests/spikes/`**: This directory exists but received no root-level
  relocations. It remains available for exploratory tests.
- **Giant files**: Several root tests are very large (e.g.,
  `test_sdk_public_surface.py` at 3,422 lines). M4 may consider splitting
  these as part of the giant-file workstream tracked in
  `docs/architecture/giant-file-split-candidates.json`.
