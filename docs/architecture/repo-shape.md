# Astrid Repository Shape — M0 Canonical Contract

This document is the **M0 architecture map** for the Astrid repository. It
classifies every top-level surface, documents the enforcement model, and
records settled milestone decisions that shape the current checkout. It is
normative for M0 and should be updated when later milestones reclassify a
surface.

## 1. Public Facades

### 1.1 `import astrid` — The Public SDK Boundary

| Surface | File | Classification |
| --- | --- | --- |
| `import astrid` | `astrid/__init__.py` | **Public SDK facade** — lazy-loads 27 names from `astrid/sdk.py` via `__getattr__`. The normative v1 contract is [docs/platform-contract.md](../platform-contract.md). |
| `astrid.sdk` | `astrid/sdk.py` | **Public SDK implementation** — DTOs, exception taxonomy, serialization helpers, discovery/invoke/generate facades. This is the implementation behind the `import astrid` lazy facade; direct imports of `astrid.sdk` are out of contract for v1. |

The 27 names in `astrid.__all__` are:

- **Functions**: `discover`, `get_capability`, `invoke`, `generate`, `read_events`, `subscribe_events`
- **DTOs**: `Capability`, `DiscoveryResult`, `EventStreamRecord`, `InvocationResult`, `CapabilityHandle`, `Port`, `Output`, `AliasRecord`, `Provenance`, `SafetyDeclaration`, `ExecError`
- **Exceptions**: `AstridSDKError`, `CapabilityNotFoundError`, `CapabilityAmbiguousError`, `CapabilityValidationError`, `CapabilityMissingInputError`, `CapabilityPreconditionError`, `CapabilityRuntimeError`, `CapabilityLeaseError`, `CapabilityEventLogError`, `UnsupportedCapabilityError`, `CapabilityInvocationError`

### 1.2 CLI Entrypoints

| Surface | File | Classification |
| --- | --- | --- |
| `python3 -m astrid` | `astrid/__main__.py` | **Executable package gateway** — delegates to `astrid.gateway.main()`. |
| `astrid.gateway` | `astrid/gateway.py` | **Subcommand router** — session gate, command dispatch, brief/video fall-through to `video_editing.hype`. 1,215 lines; a giant-file split candidate for M4. |
| `astrid.orchestrate.cli` | `astrid/orchestrate/cli.py` | **Plan compilation and test-running CLI** — CLI entrypoint for orchestrate commands. |
| `astrid.doctor` | `astrid/doctor.py` | **Repo health diagnostic** — consumes `validate_repo_structure()`. |
| `astrid.skills.cli` | `astrid/skills/cli.py` | **Skills CLI** — skill discovery and harness management. |
| `astrid.threads.cli` | `astrid/threads/cli.py` | **Threads CLI** — thread index and lineage commands. |
| `astrid.core.timeline.cli` | `astrid/core/timeline/cli.py` | **Timeline CLI** — giant-file split candidate for M4. |

### 1.3 Non-Contract Surfaces (v1)

The following are explicitly out of the v1 public contract, even if importable:

- `astrid.sdk` as a direct import target
- Everything under `astrid.core.*`
- Everything under `astrid.packs.*`
- Registry internals, resolver internals, and helper functions
- CLI implementation modules and verb-routing internals
- Internal tests, fixtures, and generated discovery payloads

These surfaces may change in any minor or patch release without deprecation.

## 2. `astrid/core` — Internal Kernel

`astrid/core` is the **internal kernel** — these modules implement framework
machinery and are not part of the public SDK contract. All core subdirectories
and their purposes:

| Subdirectory | Purpose |
| --- | --- |
| `core/adapter/` | Render adapters (local, manual, remote artifact fetch) |
| `core/element/` | Element schema, registry, catalog, CLI, install |
| `core/executor/` | Executor schema, registry, runner, folder loader, CLI, banodoco catalog |
| `core/generation/` | Generation backends (base, codex, fal, vibecomfy), feature registry, verb dispatch |
| `core/lineage/` | Run lineage variant tracking |
| `core/model_catalog/` | Model registry, schema, CLI |
| `core/orchestrator/` | Orchestrator schema, registry, runner, folder loader, CLI, plan template |
| `core/project/` | Project schema, paths, run management, sidecar, JSON I/O, CLI |
| `core/reigh/` | Reigh data provider, Supabase client, task client, timeline I/O, worker JWT |
| `core/runpod/` | RunPod sweeper and storage |
| `core/runtime/` | In-process runtime invoker, log capture |
| `core/session/` | Session identity, binding, lease, lifecycle, discovery, writer |
| `core/task/` | Task kernel: event stream, run store, run audit, gate, lifecycle, CAS, inbox, claim, plan verbs, managed binding |
| `core/timeline/` | Timeline model, CRUD, edits (audio, clip, effect, pool, track, transition), erasure, integrity, migration, projection, undo, observability, event log (local FS, Supabase, projector), banodoco schema |
| `core/util/` | Generic utilities (log-and-swallow, etc.) |
| `core/worker/` | Worker machinery |

**Anti-coupling rules enforced by `validate_import_layering()`**:

- `astrid/core` must not import from `astrid.packs` or `astrid.packs.*`
- `astrid/core` must not import from `astrid.orchestrate` or `astrid.orchestrate.*`
- `astrid/core` must not import from `astrid.audit` (M0 addition — see §2.1)

### 2.1 Named Import-Layering Exemptions

These exemptions are recorded in `astrid/structure.py` under `_IMPORT_LAYERING_EXEMPT_REL`:

| File | Exemption Reason | Milestone |
| --- | --- | --- |
| `astrid/core/runtime/in_process.py` | Sanctioned bridge between framework and pack boundaries for the in-process entrypoint machinery. | Permanent architectural choice |
| `astrid/core/task/event_stream.py` | Imports `astrid.audit.graph` and `astrid.audit.transport` for unified task/audit event stream reading. This is a **file-level exemption** (`_IMPORT_LAYERING_EXEMPT_REL`); M0 is not a refactor milestone, so the audit dependency is exempted rather than removed. Finer-grained exemption mechanics are deferred beyond M0. | M0 (SD2) |

## 3. Stable Compatibility Shims

Stable compatibility shims keep legacy import paths alive while canonical
implementations live in renamed modules. These are NOT stale migration shims
that need removal — they are the intentional public compatibility layer.

### 3.1 `astrid/_media.py`

Backward-compatibility shim for `astrid._media`. All public names now live in
`astrid.media`. This module star-re-exports everything from `astrid.media`.

- **Exemption**: Listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with a `TODO(m13)` removal target.

### 3.2 `astrid/_paths.py`

Backward-compatibility shim for `astrid._paths`. All public names now live in
`astrid.paths`. This module star-re-exports everything from `astrid.paths` plus
explicit belt-and-suspenders re-exports of `PACKAGE_ROOT`, `REPO_ROOT`,
`WORKSPACE_ROOT`, `executor_argv`, and `resolve_executor_runtime_module`.

- **Exemption**: Listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with a `TODO(m13)` removal target.

### 3.3 `astrid/pipeline.py`

Backward-compatibility shim — `astrid.pipeline` is `astrid.gateway`. This
module uses `sys.modules[__name__] = sys.modules["astrid.gateway"]` to alias
itself to the canonical gateway module so every `import astrid.pipeline` and
every `mock.patch("astrid.pipeline.…")` target transparently resolves through
to the gateway. No re-export lists to maintain — the gateway *is* the pipeline.

- **Sys.modules injection**: Because `pipeline.py` mutates `sys.modules`, it triggers the migration-completion `sys.modules` guard in `validate_migration_completion()`. M0 adds it to `_SYS_MODULES_INJECTION_EXEMPTIONS` in addition to `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS`.
- **Why two exemptions are needed**: `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` suppresses the "compatibility shim still has N live import callers" advisory. `_SYS_MODULES_INJECTION_EXEMPTIONS` suppresses the "sys.modules injection remains outside tests" advisory. `pipeline.py` triggers both and needs both.
- **Preferred pattern**: This module's sys.modules aliasing is the **preferred approach** for gateway-level compatibility shims — it avoids fragile re-export lists and guarantees `isinstance` checks pass through. Future shims of this shape should follow the same pattern and be added to both exemption lists.

### 3.4 Timeline Compatibility Re-Export Shims

Three files form the thin public re-export surface for the canonical core
timeline API. Callers can continue to import from `astrid.timeline` while the
implementation lives in `astrid.core.timeline`.

| File | Re-exports from |
| --- | --- |
| `astrid/timeline/__init__.py` | `astrid.core.timeline` |
| `astrid/timeline/timeline_model.py` | `astrid.core.timeline` |
| `astrid/timeline/banodoco_composer.py` | `astrid.core.timeline` |

These are guarded by `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` — the exemption
requires both the path match AND a `TODO(m5b)` marker string in the file. Tests
in `tests/test_structure_contracts.py` enforce that these files are strictly
thin re-exports (no runtime logic, no function/class definitions, no
`_sync_private_hooks`).

### 3.5 `astrid/core/_search.py`

Listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with a `TODO(m13)` removal
target. This is an intentional thin re-export surface.

## 4. Domain Subsystems

| Package | Classification | Notes |
| --- | --- | --- |
| `astrid/contracts/` | **Shared library** | Common schema dataclasses (ports, outputs, cache, commands, isolation, errors, run status). |
| `astrid/domains/` | **Domain libraries** | Domain-specific shared logic (e.g., `astrid/domains/hype/` for arrangement rules, enriched arrangements, text matching). |
| `astrid/utilities/` | **Utility library** | Generic helpers (LLM client construction, environment handling). |
| `astrid/audit/` | **Shared library** | Run-local provenance ledger, graph, transport, and HTML report. |
| `astrid/threads/` | **Lineage and thread management** | Thread index, ID generation (ULID), provenance tracking, record schema. The m5a milestone removed thread wrapper symbols from the public surface; only 10 lineage symbols remain in `astrid.threads.__all__`. |
| `astrid/verify/` | **Verification helpers** | Soft boundary — currently a convention, not a hard gate in M0. |
| `astrid/modalities/` | **Modality helpers** | Modality-specific support code. |
| `astrid/docs/` | **Package-level docs** | Internal documentation within the `astrid` package. |
| `astrid/skills/` | **Skill harnesses** | Agent skill discovery, registry, and harness runtimes (base, codex, claude, hermes). |
| `astrid/orchestrate/` | **Plan compilation and test running** | DSL, compile, test runner, CLI. This is a top-level subsystem, not part of `astrid/core`. |
| `astrid/theme_schema.py` | **Shared library** | Theme schema validation helpers. Soft boundary — convention in M0. |
| `astrid/paths.py` | **Shared library** | Repository and workspace path resolution. |
| `astrid/setup_cli.py` | **Shared library** | Setup CLI support. |

## 5. `astrid/packs` — Capability Surface

`astrid/packs` is the **capability surface** — every executor, orchestrator, and
element ships in a pack under `astrid/packs/<pack>/`. The kernel (`astrid/core`)
provides the framework; packs provide the capabilities.

### 5.1 Pack Layout

Each pack carries a `pack.yaml` with `id`, `name`, and `version`, and may
contain:

| Layout | Contents |
| --- | --- |
| `executors/<name>/` | `executor.yaml`, `run.py`, `STAGE.md`, optional local `src/` |
| `orchestrators/<name>/` | `orchestrator.yaml`, `run.py`, `STAGE.md`, optional local `src/` |
| `elements/<kind>/<id>/` | `component.tsx`, `element.yaml` |
| `skill/` | `SKILL.md` for agent-facing skill documentation |
| `AGENTS.md` | Pack-level agent guidance |

### 5.2 Current Shipped Packs

The shipped packs are: `rendering`, `understanding`, `generation`, `editorial`,
`video_editing`, `foley`, `training`, `reigh`, `youtube`, `fal`, `vibecomfy`,
`runpod`, `moirae`, `iteration`, and `media`.

A gitignored `local` pack at `astrid/packs/local/` is created on first
`elements fork` and holds user-editable copies.

### 5.3 ID Qualification Rules

- Executor and orchestrator IDs are always qualified: `<pack>.<name>` (e.g., `video_editing.cut`). Bare lookups are rejected.
- Element IDs stay bare and are scoped by `kind`, so `animation/fade` and `transition/fade` coexist without collision.

### 5.4 Structure Enforcement

`validate_repo_structure()` enforces:
- Executor folders must contain `executor.yaml`, `run.py`, `STAGE.md`
- Orchestrator folders must contain `orchestrator.yaml`, `run.py`, `STAGE.md`
- Element folders must contain `component.tsx`, `element.yaml`
- Executor folders must not contain orchestrator metadata and vice versa
- The qualified ID's first segment must equal the pack ID
- Custom element kinds declared in `pack.yaml` extensions are accepted

## 6. `astrid/elements/` — Planned-Absent Canonical Concept

`TOP_LEVEL_ASTRID_DIRS` in `astrid/structure.py` includes `"elements"` as a
top-level canonical directory. However, **no `astrid/elements/` directory exists
on disk** and M0 does not create it.

This is a **planned-but-not-materialized** canonical concept: the constant
allows it, the directory is absent, and creating it would be unnecessary scope
growth for M0. Source-layout smoke tests treat `elements/` as the only allowed
planned-absent canonical directory.

## 7. Tests

### 7.1 Test Layout

Tests live under `tests/` at the repository root. Key directories:

| Directory | Purpose |
| --- | --- |
| `tests/` (root) | Broad functional and regression tests |
| `tests/core/` | Core kernel tests (generation, model_catalog, runtime, task, util) |
| `tests/packs/` | Pack-specific tests (builtin, editorial, event_talks, external, foley, hype, runpod, stream_content, thumbnail_maker) |
| `tests/session/` | Session lifecycle tests |
| `tests/timeline/` | Timeline tests |
| `tests/task/` | Task kernel tests |
| `tests/adapter/` | Adapter tests |
| `tests/agentic/` | Agentic scenario tests |
| `tests/audit/` | Audit tests |
| `tests/concurrency/` | Concurrency tests |
| `tests/fixtures/` | Test fixtures (themes, external_pack, iteration_video, reshape, multitrack_cut) |
| `tests/golden/` | Golden output tests (hype) |
| `tests/helpers/` | Test helpers |
| `tests/migrations/` | Migration regression tests |
| `tests/orchestrate/` | Orchestrate tests |
| `tests/spikes/` | Spike/exploratory tests |

### 7.2 Structure Contract Tests

`tests/test_structure_contracts.py` is the primary test file for repository
structure enforcement. It tests:
- Import layering violations (core→packs, core→orchestrate)
- Migration completion advisories (DEPRECATED markers, sys.modules injections, `__all__` aliases)
- Compatibility shim detection and exemptions
- Timeline facade exemption guards (TODO(m5b) marker requirements)
- Thread wrapper removal regression (m5a)
- Synthetic violation cases before real-repo smoke tests

### 7.3 Public Surface Tests

`tests/test_m5b_baseline_public_surface.py` — baseline public surface contract
verification.

`tests/test_m5b_end_state_regression.py` — end-state regression guards.

### 7.4 Test Relocation Map (M3)

Root-level `tests/test_*.py` files will be classified and mapped to target
domains in `docs/architecture/test-relocation-map.json`. Ambiguous cases are
marked for M3 owner review rather than forcing low-confidence moves in M0.

M3 consumes `test-relocation-map.json`.

## 8. Docs

Documentation lives under `docs/` at the repository root. Key architecture and
contract documents:

| Document | Purpose |
| --- | --- |
| `docs/architecture.md` | User-facing architecture overview (orchestrators, executors, elements, shared libraries, structure enforcement) |
| `docs/architecture/repo-shape.md` | **This document** — M0 canonical repo-shape contract |
| `docs/architecture/top-level-inventory.json` | Machine-readable top-level entry inventory (M0) |
| `docs/architecture/pack-layout-variants.json` | Machine-readable pack variant catalog (M0) |
| `docs/architecture/test-relocation-map.json` | Test relocation target map (consumed by M3) |
| `docs/architecture/giant-file-split-candidates.json` | Giant-file split candidates with line counts (consumed by M4) |
| `docs/platform-contract.md` | Normative v1 platform contract (SDK exports, SemVer, deprecation window) |
| `docs/cli-contract.md` | Agent CLI contract (stream discipline, output modes, error signaling) |
| `docs/sdk.md` | User-facing SDK walkthrough |
| `docs/run-ledger-contract.md` | Run ledger contract |
| `docs/integration_contracts.md` | Integration contracts |
| `docs/output-result-contract.md` | Output result contract |

## 9. Migration Candidates

### 9.1 Giant-File Split Candidates (M4)

M4 consumes `docs/architecture/giant-file-split-candidates.json`. Known
candidates with current line counts:

| File | Approx. Lines | Notes |
| --- | --- | --- |
| `astrid/sdk.py` | 1,833 | Public SDK implementation |
| `astrid/gateway.py` | 1,215 | Subcommand router |
| `astrid/core/timeline/cli.py` | TBD | Timeline CLI |
| `astrid/packs/install.py` | TBD | Pack installation logic |
| `astrid/packs/cli.py` | TBD | Pack CLI |

The giant-file inventory records current line counts from the checkout and does
not split code in M0.

### 9.2 Test Relocation Candidates (M3)

Root-level `tests/test_*.py` files that could move to domain-specific test
directories are inventoried in `docs/architecture/test-relocation-map.json`.
M3 consumes this inventory.

### 9.3 Runtime Correctness Inventory

`docs/runtime-correctness-m3-inventory.md` records every non-pack `astrid/`
Python `except` and runtime `assert` site, classified for follow-up in later
milestones. This inventory is maintained outside M0 scope.

## 10. Completed Roadmap Contracts

The following `astrid-roadmap` contracts are settled and reflected in this
document:

| Contract | Status | Reflected In |
| --- | --- | --- |
| Platform contract v1 (`docs/platform-contract.md`) | **Complete** | §1.1 — Public SDK boundary and `__all__` exports |
| CLI contract (`docs/cli-contract.md`) | **Complete** | §1.2 — CLI entrypoints |
| Run ledger contract (`docs/run-ledger-contract.md`) | **Complete** | §4 — Audit subsystem |
| Integration contracts (`docs/integration_contracts.md`) | **Complete** | §5 — Pack capability surface |
| Output result contract (`docs/output-result-contract.md`) | **Complete** | §1.1 — SDK DTOs |
| Timeline compatibility re-exports (m5b) | **Complete** | §3.4 — Timeline shims |
| Internal threads lineage (m5a) | **Complete** | §4 — Threads subsystem with removed wrapper symbols |
| Public compatibility shims (m13-targeted) | **Complete** | §3.1–3.3 — `_media.py`, `_paths.py`, `pipeline.py` |

## 11. Soft Boundary Conventions (Not Hard-Gated in M0)

The following boundaries are conventions documented here for awareness. M0 does
not enforce them with hard gates:

| Boundary | Notes |
| --- | --- |
| `threads.ids` | Should not be imported outside the threads package; currently a convention |
| `_paths` | Underscore-prefixed module; callers should prefer `paths` |
| `verify` | Verification helpers should not depend on packs or orchestrate |
| `theme_schema` | Theme schema validation should remain a leaf utility |

Later milestones may choose to enforce these as hard gates.

## 12. Structure Enforcement Model

### 12.1 Validator

`astrid/structure.py` is the **single source of truth** for repository
structure enforcement. It exposes:

- `validate_repo_structure()` — top-level entry check, pack layout, import layering, migration completion (returns `StructureReport`)
- `validate_import_layering()` — core→packs/orchestrate/audit import prohibition
- `validate_migration_completion()` — DEPRECATED markers, sys.modules injections, dangling `__all__` aliases, compatibility shim detection
- `validate_run_record_status_boundary()` — legacy run-record status token detection

### 12.2 Exemption Lists

All exemptions are colocated in `astrid/structure.py`:

| Constant | Purpose |
| --- | --- |
| `TOP_LEVEL_ASTRID_FILES` | Allowed top-level `.py` files under `astrid/` |
| `TOP_LEVEL_ASTRID_DIRS` | Allowed top-level directories under `astrid/` (includes `elements` as planned-absent) |
| `_IMPORT_LAYERING_EXEMPT_REL` | Files exempt from core import-layering rules |
| `_SYS_MODULES_INJECTION_EXEMPTIONS` | Files exempt from sys.modules injection guard |
| `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` | Stable shims exempt from shim-with-live-callers advisory |
| `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` | Milestone-gated shims (require TODO marker + path match) |

### 12.3 Consumption

`astrid/doctor.py` consumes `validate_repo_structure()` and fails when
canonical repository structure drifts.

## 13. M3 and M4 Inventory Consumption

- **M3** consumes `docs/architecture/test-relocation-map.json` to guide
  root-level test file relocation into domain-specific test directories.
  Ambiguous cases are flagged for owner review rather than forced in M0.

- **M4** consumes `docs/architecture/giant-file-split-candidates.json` to
  guide splitting of oversized files. Current line counts are recorded from the
  M0 checkout; no code splitting occurs in M0.
