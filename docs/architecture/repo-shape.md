# Astrid Repository Shape — M5 Canonical Contract

This document is the **M5 architecture map** for the Astrid repository. It
classifies every top-level surface, documents the enforcement model, and
records settled milestone decisions that shape the current checkout. It is
normative for M5 and should be updated when later milestones reclassify a
surface.

**M5 key rule**: New internal code belongs under `astrid/core/*`. New pack
machinery (discovery, resolver, store, manifest, override, alias resolution,
validation, CLI, installation, entrypoint, agent indexing, gitignore filtering,
schemas) belongs under `astrid/core/pack/*`. `astrid/packs/` is for pack data
only — executors, orchestrators, elements, `pack.yaml`, `skill/` — plus thin
backward-compatibility re-export shims at the top level. Gateway subcommand
logic lives in `astrid/gateway_*.py` split modules; the root `gateway.py` is
the router/facade. SDK implementation lives in `astrid/sdk_*.py` split modules;
`sdk.py` is the aggregation facade.

## 1. Public Facades

### 1.1 `import astrid` — The Public SDK Boundary

| Surface | File | Classification |
| --- | --- | --- |
| `import astrid` | `astrid/__init__.py` | **Public SDK facade** — lazy-loads 27 names from `astrid/sdk.py` via `__getattr__`. The normative v1 contract is [docs/platform-contract.md](../platform-contract.md). |
| `astrid.sdk` | `astrid/sdk.py` | **Public SDK aggregation facade** (651 lines) — DTOs, exception taxonomy, serialization helpers, discovery/invoke/generate facades. Implementation split across `sdk_discovery.py` (620 lines), `sdk_errors.py` (148 lines), `sdk_generation.py` (330 lines), `sdk_invocation.py` (323 lines), `sdk_results.py` (213 lines). Direct imports of `astrid.sdk` are out of contract for v1. |

The 27 names in `astrid.__all__` are:

- **Functions**: `discover`, `get_capability`, `invoke`, `generate`, `read_events`, `subscribe_events`
- **DTOs**: `Capability`, `DiscoveryResult`, `EventStreamRecord`, `InvocationResult`, `CapabilityHandle`, `Port`, `Output`, `AliasRecord`, `Provenance`, `SafetyDeclaration`, `ExecError`
- **Exceptions**: `AstridSDKError`, `CapabilityNotFoundError`, `CapabilityAmbiguousError`, `CapabilityValidationError`, `CapabilityMissingInputError`, `CapabilityPreconditionError`, `CapabilityRuntimeError`, `CapabilityLeaseError`, `CapabilityEventLogError`, `UnsupportedCapabilityError`, `CapabilityInvocationError`

### 1.2 CLI Entrypoints

| Surface | File | Classification |
| --- | --- | --- |
| `python3 -m astrid` | `astrid/__main__.py` | **Executable package gateway** — delegates to `astrid.gateway.main()`. |
| `astrid.gateway` | `astrid/gateway.py` | **Subcommand router and facade** (367 lines) — session gate, command dispatch, brief/video fall-through to `video_editing.hype`. Giant-file split completed in M4: dispatch logic lives in `gateway_dispatch.py` (578 lines), help text in `gateway_help.py` (139 lines), project commands in `gateway_project.py` (155 lines), wait/lease logic in `gateway_wait.py` (115 lines). |
| `astrid.orchestrate.cli` | `astrid/orchestrate/cli.py` | **Plan compilation and test-running CLI** — CLI entrypoint for orchestrate commands. |
| `astrid.doctor` | `astrid/doctor.py` | **Repo health diagnostic** — consumes `validate_repo_structure()`. |
| `astrid.skills.cli` | `astrid/skills/cli.py` | **Skills CLI** — skill discovery and harness management. |
| `astrid.threads.cli` | `astrid/threads/cli.py` | **Threads CLI** — thread index and lineage commands. |
| `astrid.core.timeline.cli` | `astrid/core/timeline/cli.py` | **Timeline CLI** — timeline inspection and manipulation commands. |

### 1.3 Non-Contract Surfaces (v1)

The following are explicitly out of the v1 public contract, even if importable:

- `astrid.sdk` as a direct import target
- Everything under `astrid.core.*`
- Everything under `astrid.packs.*`
- Registry internals, resolver internals, and helper functions
- CLI implementation modules and verb-routing internals
- Internal tests, fixtures, and generated discovery payloads
- Split gateway modules (`gateway_dispatch`, `gateway_help`, `gateway_project`, `gateway_wait`) are internal implementation detail

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
| `core/pack/` | **Canonical pack machinery** (M2): discovery, resolver, store, manifest, override, alias_resolver, validate, CLI, install, entrypoint, agent_index, gitignore, schemas/v1/ |
| `core/pack_machinery/` | **Thin compatibility shims** (M2): cli.py, validate.py, agent_index.py, gitignore.py, install.py are re-export shims pointing into `core/pack/`. Deprecated schemas/ copy retained for reference. Retained for M5; removal deferred to M6+. |
| `core/project/` | Project schema, paths, run management, sidecar, JSON I/O, CLI |
| `core/reigh/` | Reigh data provider, Supabase client, task client, timeline I/O, worker JWT |
| `core/runpod/` | RunPod sweeper and storage |
| `core/runtime/` | In-process runtime invoker, log capture |
| `core/session/` | Session identity, binding, lease, lifecycle, discovery, writer |
| `core/task/` | Task kernel: event stream, run store, run audit, gate, lifecycle, CAS, inbox, claim, plan verbs, managed binding |
| `core/timeline/` | Timeline model, CRUD, edits (audio, clip, effect, pool, track, transition), erasure, integrity, migration, projection, undo, observability, event log (local FS, Supabase, projector), banodoco schema |
| `core/util/` | Generic utilities (log-and-swallow, etc.) |
| `core/worker/` | Worker machinery |

Loose `.py` files at `astrid/core/` that are pack-machinery shims (all thin
re-exports pointing into `astrid/core/pack/`):

| File | Canonical home |
| --- | --- |
| `core/pack_discovery.py` | `core/pack/discovery.py` |
| `core/pack_resolver.py` | `core/pack/resolver.py` |
| `core/pack_store.py` | `core/pack/store.py` |
| `core/manifest.py` | `core/pack/manifest.py` |
| `core/override.py` | `core/pack/override.py` |
| `core/alias_resolver.py` | `core/pack/alias_resolver.py` |

Other loose `.py` files at `astrid/core/` are non-pack kernel modules
(`scaffold.py`, `search.py`, `_search.py`, `git_util.py`, `cli_choices.py`,
`theme_cli.py`, `dirty.py`). `_search.py` is additionally listed in
`_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` as an intentional thin re-export.

**Anti-coupling rules enforced by `validate_import_layering()`**:

- `astrid/core` must not import from `astrid.packs` or `astrid.packs.*`
- `astrid/core` must not import from `astrid.orchestrate` or `astrid.orchestrate.*`
- `astrid/core` must not import from `astrid.audit` (M0 addition — see §2.1)

### 2.1 Named Import-Layering Exemptions

These exemptions are recorded in `astrid/structure.py` under `_IMPORT_LAYERING_EXEMPT_REL`:

| File | Exemption Reason | Milestone |
| --- | --- | --- |
| `astrid/core/runtime/in_process.py` | Sanctioned bridge between framework and pack boundaries for the in-process entrypoint machinery. | Permanent architectural choice |
| `astrid/core/task/event_stream.py` | Imports `astrid.audit.graph` and `astrid.audit.transport` for unified task/audit event stream reading. This is a **file-level exemption** (`_IMPORT_LAYERING_EXEMPT_REL`); finer-grained exemption mechanics are deferred beyond M0. | Audit refactor milestone |

### 2.2 Contributor Placement Guidance

When adding new code to the repository, follow these placement rules:

- **New pack machinery**: `astrid/core/pack/*` (discovery, resolver, store, manifest, override, alias_resolver, validate, CLI, install, entrypoint, agent_index, gitignore)
- **New internal framework code**: `astrid/core/<domain>/*`
- **New pack data** (executors, orchestrators, elements, skills): `astrid/packs/<pack>/`
- **New public SDK surface**: add to `astrid/sdk.py` (aggregation facade) and the appropriate `astrid/sdk_*.py` split module
- **New gateway subcommands**: add to the appropriate `astrid/gateway_*.py` split module or create a new one; register the dispatch in `gateway_dispatch.py`
- **New domain libraries**: `astrid/domains/<domain>/`
- **New shared utilities**: `astrid/utilities/`
- **New CLI entrypoints for subsystems**: follow the pattern of `astrid/<subsystem>/cli.py`

**Do not** add new `.py` files directly under `astrid/` — they must be listed in `TOP_LEVEL_ASTRID_FILES` in `astrid/structure.py` and approved as canonical top-level modules. Adding a new top-level module requires updating `TOP_LEVEL_ASTRID_FILES` in `structure.py` and this document.

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

- **Disposition**: **Retained permanently (SD1)**. Pipeline is a permanent public compatibility surface with zero internal callers.
- **Sys.modules injection**: Because `pipeline.py` mutates `sys.modules`, it triggers the migration-completion `sys.modules` guard in `validate_migration_completion()`. It is listed in both `_SYS_MODULES_INJECTION_EXEMPTIONS` and `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS`.
- **Why two exemptions are needed**: `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` suppresses the "compatibility shim still has N live import callers" advisory. `_SYS_MODULES_INJECTION_EXEMPTIONS` suppresses the "sys.modules injection remains outside tests" advisory. `pipeline.py` triggers both and needs both.
- **Preferred pattern**: This module's sys.modules aliasing is the **preferred approach** for gateway-level compatibility shims — it avoids fragile re-export lists and guarantees `isinstance` checks pass through. Future shims of this shape should follow the same pattern and be added to both exemption lists.

### 3.4 Timeline Compatibility Re-Export Shims (M5b-Deferred)

Three files form the thin public re-export surface for the canonical core
timeline API. Callers can continue to import from `astrid.timeline` while the
implementation lives in `astrid.core.timeline`. Removal requires broader
Banodoco integration work outside M5 scope.

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

- **Disposition**: **Deferred to M5b.** The enforcement gate does not ban `astrid.timeline` imports. Public tests may keep importing it.

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
| `astrid/verify/` | **Verification helpers** | Soft boundary — currently a convention, not a hard gate. |
| `astrid/modalities/` | **Modality helpers** | Modality-specific support code. |
| `astrid/docs/` | **Package-level docs** | Internal documentation within the `astrid` package. |
| `astrid/skills/` | **Skill harnesses** | Agent skill discovery, registry, and harness runtimes (base, codex, claude, hermes). |
| `astrid/orchestrate/` | **Plan compilation and test running** | DSL, compile, test runner, CLI. This is a top-level subsystem, not part of `astrid/core`. |
| `astrid/theme_schema.py` | **Shared library** | Theme schema validation helpers. Soft boundary — convention. |
| `astrid/paths.py` | **Shared library** | Repository and workspace path resolution. |
| `astrid/setup_cli.py` | **Shared library** | Setup CLI support. |

### 4.1 CLI/Domain/Import-Layering Convention

The repository enforces a strict import layering convention:

- **CLI modules** live as `astrid/<subsystem>/cli.py` for each subsystem (skills, threads, orchestrate, core/timeline, core/pack). CLI modules may import from their subsystem's internals and from shared libraries, but must not be imported by non-CLI code.
- **Domain libraries** under `astrid/domains/` may import from `astrid/contracts/`, `astrid/utilities/`, and other shared libraries. They must not import from `astrid/core/`, `astrid/packs/`, or `astrid/orchestrate/`.
- **Core kernel** (`astrid/core/`) is the innermost layer. It must not import from `astrid/packs`, `astrid/orchestrate`, or `astrid/audit` (with named exemptions in §2.1). It may import from `astrid/contracts/` and `astrid/utilities/`.
- **Pack data** (`astrid/packs/<pack>/`) must not import from `astrid/core/` except through sanctioned entrypoints.
- **Orchestrate** (`astrid/orchestrate/`) is a top-level subsystem that may import from shared libraries but must not be imported by `astrid/core/`.

These rules are enforced by `validate_import_layering()` in `astrid/structure.py`.

## 5. `astrid/packs` — Capability Surface

`astrid/packs` is the **capability surface** — every executor, orchestrator, and
element ships in a pack under `astrid/packs/<pack>/`. The pack machinery kernel
(`astrid/core/pack/`) provides the framework; packs provide the capabilities.

**M5 rule**: `astrid/packs/` is for pack data only. The top-level `.py` files
are thin backward-compatibility re-export shims whose canonical implementations
live in `astrid/core/pack/`. New pack machinery must go under
`astrid/core/pack/*`, not under `astrid/packs/`.

### 5.1 Pack Layout

Each pack carries a `pack.yaml` with `id`, `name`, and `version`, and may
contain:

| Layout | Contents |
| --- | --- |
| `executors/<name>/` | `executor.yaml`, `run.py`, `STAGE.md`, optional local `src/` |
| `orchestrators/<name>/` | `orchestrator.yaml`, `run.py`, `STAGE.md`, optional local `src/` |
| `elements/<kind>/<id>/` | `component.tsx`, `element.yaml` |
| `skill/` | `SKILL.md` for agent-facing skill documentation |

### 5.2 Current Shipped Packs

The shipped packs are: `rendering`, `understanding`, `generation`, `editorial`,
`video_editing`, `foley`, `training`, `reigh`, `youtube`, `fal`, `vibecomfy`,
`runpod`, `moirae`, `iteration`, `media`, `stream_content`, `comfy_wrap`, and
`text_analysis`.

A gitignored `local` pack at `astrid/packs/local/` is created on first
`elements fork` and holds user-editable copies.

The `builtin` pack is a **hidden compatibility shell** (`visibility: hidden`,
`status: deprecated`) that preserves backward-compatible pack-level aliases
mapping legacy `builtin.*` capability ids to canonical homes. It also contains
`agent_probe.py` (a legacy DSL orchestrator shim used by 16+ regression tests)
and `fixtures/`/`golden/` test infrastructure. It is not a capability-producing
pack.

The `_core/` directory is a **skill-only shell** — it contains only
`skill/SKILL.md` (the root Astrid gateway skill), has no `pack.yaml`, and is
not a runtime pack. It is coupled to `astrid/skills/` and treated as a
permanent visible exception.

### 5.3 Top-Level Pack Shims

The following `.py` files directly under `astrid/packs/` are thin
backward-compatibility re-export shims. Their canonical implementations live
in `astrid/core/pack/`:

| File | Classification | Canonical home |
| --- | --- | --- |
| `__init__.py` | Package init | (package marker) |
| `cli.py` | Compatibility re-export shim | `astrid/core/pack/cli.py` |
| `validate.py` | Compatibility re-export shim | `astrid/core/pack/validate.py` |
| `agent_index.py` | Compatibility re-export shim | `astrid/core/pack/agent_index.py` |
| `gitignore.py` | Compatibility re-export shim | `astrid/core/pack/gitignore.py` |
| `install.py` | sys.modules alias shim | `astrid/core/pack/install.py` |
| `_canonical_entrypoint.py` | Compatibility re-export shim | `astrid/core/pack/entrypoint.py` |

These shims are enforced by `_validate_packs_top_level_modules()` in
`astrid/structure.py` (added M2 T13). Any new `.py` file under `astrid/packs/`
must be a documented compatibility shim with ≤12 meaningful lines.

### 5.4 ID Qualification Rules

- Executor and orchestrator IDs are always qualified: `<pack>.<name>` (e.g., `video_editing.cut`). Bare lookups are rejected.
- Element IDs stay bare and are scoped by `kind`, so `animation/fade` and `transition/fade` coexist without collision.

### 5.5 Structure Enforcement

`validate_repo_structure()` enforces:
- Executor folders must contain `executor.yaml`, `run.py`, `STAGE.md`
- Orchestrator folders must contain `orchestrator.yaml`, `run.py`, `STAGE.md`
- Element folders must contain `component.tsx`, `element.yaml`
- Executor folders must not contain orchestrator metadata and vice versa
- The qualified ID's first segment must equal the pack ID
- Custom element kinds declared in `pack.yaml` extensions are accepted
- Top-level `.py` files under `astrid/packs/` must be documented compatibility shims (added M2 T13)

## 6. `astrid/elements/` — Planned-Absent Canonical Concept

`TOP_LEVEL_ASTRID_DIRS` in `astrid/structure.py` includes `"elements"` as a
top-level canonical directory. However, **no `astrid/elements/` directory exists
on disk** and M5 does not create it.

This is a **planned-but-not-materialized** canonical concept: the constant
allows it, the directory is absent, and creating it would be unnecessary scope
growth. Source-layout smoke tests treat `elements/` as the only allowed
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
- Packs top-level module enforcement (M2 T13): thin documented shims allowed, active implementations rejected
- Synthetic violation cases before real-repo smoke tests

### 7.3 Public Surface and Pack Machinery Tests

`tests/test_m5b_baseline_public_surface.py` — baseline public surface contract
verification.

`tests/test_m5b_end_state_regression.py` — end-state regression guards.

`tests/test_m2_public_surface.py` — M2 public surface characterization (39 tests
across 12 test classes: root imports, pipeline-gateway identity, pipeline patch
seams, deprecated CLI aliases, __main__ delegation, Banodoco integration imports,
paths/_paths identity, media/_media identity, theme_schema import, thread import
surface, timeline re-export surface, SDK public surface).

`tests/test_m2_pack_machinery.py` — M2 pack machinery characterization (46 tests
across 11 test classes: core.pack exports, core.pack_machinery submodules,
packs shim resolution, packs.install canonical surface, machinery-shim identity,
loose-module shim completeness, core.pack submodule exports, discovery pipeline,
resolver pipeline, store pipeline, schema-root relocation).

`tests/test_pack_layout_contract.py` — pack layout contract verification
(updated M2 T10 for schema relocation to `astrid/core/pack/schemas/v1/`).

### 7.4 Test Relocation Map (M3)

Root-level `tests/test_*.py` files will be classified and mapped to target
domains in `docs/architecture/test-relocation-map.json`. Ambiguous cases are
marked for M3 owner review rather than forcing low-confidence moves.

M3 consumes `test-relocation-map.json`.

## 8. Docs

Documentation lives under `docs/` at the repository root. Key architecture and
contract documents:

| Document | Purpose |
| --- | --- |
| `docs/architecture.md` | User-facing architecture overview (orchestrators, executors, elements, shared libraries, structure enforcement) |
| `docs/architecture/repo-shape.md` | **This document** — M5 canonical repo-shape contract |
| `docs/architecture/top-level-inventory.json` | Machine-readable top-level entry inventory (M5) |
| `docs/architecture/pack-layout-variants.json` | Machine-readable pack variant catalog |
| `docs/architecture/test-relocation-map.json` | Test relocation target map (consumed by M3) |
| `docs/architecture/giant-file-split-candidates.json` | Giant-file split candidates with line counts (consumed by M4, now completed) |
| `docs/architecture/shim-legacy-audit.md` | M5 shim and legacy surface audit with retention metadata |
| `docs/platform-contract.md` | Normative v1 platform contract (SDK exports, SemVer, deprecation window). Note: this M2-era document references `pack_machinery/schemas/v1/` as the canonical schema path; canonical schemas now live at `astrid/core/pack/schemas/v1/`. A future milestone should refresh this document. |
| `docs/cli-contract.md` | Agent CLI contract (stream discipline, output modes, error signaling) |
| `docs/sdk.md` | User-facing SDK walkthrough |
| `docs/run-ledger-contract.md` | Run ledger contract |
| `docs/integration_contracts.md` | Integration contracts |
| `docs/output-result-contract.md` | Output result contract |

## 9. Migration Candidates

### 9.1 Giant-File Split Candidates (M4 — Completed)

M4 consumed `docs/architecture/giant-file-split-candidates.json` and completed
the following splits:

| File | Pre-Split Lines | Post-Split Lines | Result |
| --- | --- | --- | --- |
| `astrid/gateway.py` | 1,215 | 367 | Split into `gateway.py` (router, 367), `gateway_dispatch.py` (578), `gateway_help.py` (139), `gateway_project.py` (155), `gateway_wait.py` (115) |
| `astrid/sdk.py` | 1,833 | 651 | Split into `sdk.py` (facade, 651), `sdk_discovery.py` (620), `sdk_errors.py` (148), `sdk_generation.py` (330), `sdk_invocation.py` (323), `sdk_results.py` (213) |

The split modules are listed in `TOP_LEVEL_ASTRID_FILES` in `astrid/structure.py`.

### 9.2 Test Relocation Candidates (M3)

Root-level `tests/test_*.py` files that could move to domain-specific test
directories are inventoried in `docs/architecture/test-relocation-map.json`.
M3 consumes this inventory.

### 9.3 Runtime Correctness Inventory

`docs/runtime-correctness-m3-inventory.md` records every non-pack `astrid/`
Python `except` and runtime `assert` site, classified for follow-up in later
milestones. This inventory is maintained outside M5 scope.

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
| Timeline compatibility re-exports (m5b) | **Deferred to M5b** | §3.4 — Timeline shims |
| Internal threads lineage (m5a) | **Complete** | §4 — Threads subsystem with removed wrapper symbols |
| Public compatibility shims (m13-targeted) | **Complete** | §3.1–3.3 — `_media.py`, `_paths.py`, `pipeline.py` |
| Top-level module rationalization (M2) | **Complete** | §2 — `core/pack/` canonical pack machinery; §5 — `packs/` as pack data only; §5.3 — top-level shim classification; §5.5 — structure enforcement |
| Giant-file split (M4) | **Complete** | §9.1 — Gateway split into 4 sub-modules; SDK split into 5 sub-modules |
| Pipeline as permanent SD1 | **Complete** | §3.3 — Pipeline retained permanently as public compatibility surface |
| M5 boundary enforcement | **Complete** | §2.2 — Contributor placement guidance; §4.1 — CLI/domain/import-layering convention; §12.1 — Structure enforcement model |
| Shim and legacy surface audit (M5) | **Complete** | `docs/architecture/shim-legacy-audit.md` — M5 dispositions with retention metadata |

## 11. Soft Boundary Conventions (Not Hard-Gated)

The following boundaries are conventions documented here for awareness. They are
not enforced with hard gates:

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
| `TOP_LEVEL_ASTRID_FILES` | Allowed top-level `.py` files under `astrid/` (22 files including gateway/sdk split modules) |
| `TOP_LEVEL_ASTRID_DIRS` | Allowed top-level directories under `astrid/` (15 dirs including `elements` as planned-absent) |
| `_IMPORT_LAYERING_EXEMPT_REL` | Files exempt from core import-layering rules (2 files) |
| `_SYS_MODULES_INJECTION_EXEMPTIONS` | Files exempt from sys.modules injection guard (3 files: compile.py, in_process.py, pipeline.py) |
| `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` | Stable shims exempt from shim-with-live-callers advisory (4 files: `_media.py`, `_paths.py`, `_search.py`, `pipeline.py`) |
| `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` | Milestone-gated shims (require TODO marker + path match; 3 timeline files) |

### 12.3 Consumption

`astrid/doctor.py` consumes `validate_repo_structure()` and fails when
canonical repository structure drifts.

## 13. M3, M4, and M5 Inventory Consumption

- **M3** consumes `docs/architecture/test-relocation-map.json` to guide
  root-level test file relocation into domain-specific test directories.
  Ambiguous cases are flagged for owner review.

- **M4** consumed `docs/architecture/giant-file-split-candidates.json` to
  split `gateway.py` (into 4 sub-modules) and `sdk.py` (into 5 sub-modules).
  The split is complete; the pre-split files now serve as router/facade modules.

- **M5** updates this document to reflect the post-split layout, adds
  contributor placement guidance, formalizes the CLI/domain/import-layering
  convention, and replaces stale references with current-state documentation.
