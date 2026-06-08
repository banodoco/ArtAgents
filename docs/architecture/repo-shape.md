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
only — executors, orchestrators, elements, `pack.yaml`, `skill/` — with no
top-level Python machinery except `__init__.py`. Gateway subcommand logic lives
in the `astrid/core/gateway/` package. SDK implementation lives in the
`astrid/sdk/` package.

## 1. Public Facades

### 1.1 `import astrid` — The Public SDK Boundary

| Surface | File | Classification |
| --- | --- | --- |
| `import astrid` | `astrid/__init__.py` | **Public SDK facade** — lazy-loads the v1 SDK names via `__getattr__`. The normative v1 contract is [docs/platform-contract.md](../platform-contract.md). |
| `astrid.sdk` | `astrid/sdk/` | **Public SDK package** — DTOs, exception taxonomy, serialization helpers, discovery/invoke/generate facades. Direct imports of private SDK implementation modules are out of contract for v1. |

The 27 names in `astrid.__all__` are:

- **Functions**: `discover`, `get_capability`, `invoke`, `generate`, `read_events`, `subscribe_events`
- **DTOs**: `Capability`, `DiscoveryResult`, `EventStreamRecord`, `InvocationResult`, `CapabilityHandle`, `Port`, `Output`, `AliasRecord`, `Provenance`, `SafetyDeclaration`, `ExecError`
- **Exceptions**: `AstridSDKError`, `CapabilityNotFoundError`, `CapabilityAmbiguousError`, `CapabilityValidationError`, `CapabilityMissingInputError`, `CapabilityPreconditionError`, `CapabilityRuntimeError`, `CapabilityLeaseError`, `CapabilityEventLogError`, `UnsupportedCapabilityError`, `CapabilityInvocationError`

### 1.2 CLI Entrypoints

| Surface | File | Classification |
| --- | --- | --- |
| `python3 -m astrid` | `astrid/__main__.py` | **Executable package gateway** — delegates to `astrid.core.gateway.main()`. |
| `astrid.core.gateway` | `astrid/core/gateway/` | **Subcommand router package** — session gate, command dispatch, brief/video fall-through to `video_editing.hype`. The facade lives in `__init__.py`; implementation modules are `dispatch.py`, `help.py`, `project.py`, and `wait.py`. |
| `astrid.core.orchestrate.cli` | `astrid/core/orchestrate/cli.py` | **Plan compilation and test-running CLI** — CLI entrypoint for orchestrate commands. |
| `astrid.core.doctor` | `astrid/core/doctor.py` | **Repo health diagnostic** — consumes `validate_repo_structure()`. |
| `astrid.skills.cli` | `astrid/skills/cli.py` | **Skills CLI** — skill discovery and harness management. |
| `astrid.core.threads.cli` | `astrid/core/threads/cli.py` | **Threads CLI** — thread index and lineage commands. |
| `astrid.core.timeline.cli` | `astrid/core/timeline/cli.py` | **Timeline CLI** — timeline inspection and manipulation commands. |

### 1.3 Non-Contract Surfaces (v1)

The following are explicitly out of the v1 public contract, even if importable:

- `astrid.sdk` as a direct import target
- Everything under `astrid.core.*`
- Everything under `astrid.packs.*`
- Registry internals, resolver internals, and helper functions
- CLI implementation modules and verb-routing internals
- Internal tests, fixtures, and generated discovery payloads
- Gateway implementation modules under `astrid/core/gateway/` are internal implementation detail

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
| `core/project/` | Project schema, paths, run management, sidecar, JSON I/O, CLI |
| `core/reigh/` | Reigh data provider, Supabase client, task client, timeline I/O, worker JWT |
| `core/runpod/` | RunPod sweeper and storage |
| `core/runtime/` | In-process runtime invoker, log capture |
| `core/session/` | Session identity, binding, lease, lifecycle, discovery, writer |
| `core/task/` | Task kernel: event stream, run store, run audit, gate, lifecycle, CAS, inbox, claim, plan verbs, managed binding |
| `core/timeline/` | Timeline model, CRUD, edits (audio, clip, effect, pool, track, transition), erasure, integrity, migration, projection, undo, observability, event log (local FS, Supabase, projector), banodoco schema |
| `core/util/` | Generic utilities (log-and-swallow, etc.) |
| `core/worker/` | Worker machinery |

Loose `.py` files at `astrid/core/` are kernel helpers such as `scaffold.py`,
`search.py`, `git_util.py`, `cli_choices.py`, `theme_cli.py`, and `dirty.py`.
Pack machinery does not live in loose root-level core modules; it belongs under
`astrid/core/pack/`.

**Anti-coupling rules enforced by `validate_import_layering()`**:

- `astrid/core` must not import from `astrid.packs` or `astrid.packs.*`
- Core subsystems such as `astrid.core.audit`, `astrid.core.orchestrate`,
  `astrid.core.threads`, and `astrid.core.verify` may import one another as
  internal implementation modules.

### 2.1 Named Import-Layering Exemptions

These exemptions are recorded in `astrid/core/structure.py` under `_IMPORT_LAYERING_EXEMPT_REL`:

| File | Exemption Reason | Milestone |
| --- | --- | --- |
| `astrid/core/runtime/in_process.py` | Sanctioned bridge between framework and pack boundaries for the in-process entrypoint machinery. | Permanent architectural choice |

### 2.2 Contributor Placement Guidance

When adding new code to the repository, follow these placement rules:

- **New pack machinery**: `astrid/core/pack/*` (discovery, resolver, store, manifest, override, alias_resolver, validate, CLI, install, entrypoint, agent_index, gitignore)
- **New internal framework code**: `astrid/core/<domain>/*`
- **New pack data** (executors, orchestrators, elements, skills): `astrid/packs/<pack>/`
- **New public SDK surface**: add to the `astrid/sdk/` package and expose it through the package facade only when it is part of the v1 contract
- **New gateway subcommands**: add to the appropriate `astrid/core/gateway/*.py` module or create a new one; register dispatch in `astrid/core/gateway/dispatch.py`
- **New domain libraries**: `astrid/core/domains/<domain>/`
- **New shared utilities**: `astrid/core/util/`
- **New CLI entrypoints for subsystems**: follow the pattern of `astrid/<subsystem>/cli.py`

**Do not** add new `.py` files directly under `astrid/` — they must be listed in `TOP_LEVEL_ASTRID_FILES` in `astrid/core/structure.py` and approved as canonical top-level modules. Adding a new top-level module requires updating `TOP_LEVEL_ASTRID_FILES` in `structure.py` and this document.

## 3. Retired Compatibility Surfaces

The current checkout has no live Python compatibility shim modules. The old
top-level aliases for `_media`, `_paths`, `pipeline`, timeline re-exports,
pack machinery, and SDK split modules were retired in favor of canonical
imports. Historical milestone briefs may still mention those transitions, but
live architecture docs and tests should point at the canonical modules.

Canonical homes:

| Old surface | Canonical surface |
| --- | --- |
| `astrid._media` | `astrid.core.media` |
| `astrid._paths` | `astrid.core.paths` |
| `astrid.pipeline` | `astrid.core.gateway` |
| `astrid.timeline.*` | `astrid.core.timeline.*` |
| `astrid.core.pack_*`, `astrid.core.manifest`, `astrid.core.alias_resolver` | `astrid.core.pack.*` |
| `astrid.packs.{cli,validate,agent_index,gitignore,install,_canonical_entrypoint}` | `astrid.core.pack.*` |
| `astrid.sdk_*`, `astrid.sdk_results` | `astrid.sdk.*` |

## 4. Domain Subsystems

| Package | Classification | Notes |
| --- | --- | --- |
| `astrid/core/contracts/` | **Shared library** | Common schema dataclasses (ports, outputs, cache, commands, isolation, errors, run status). |
| `astrid/core/domains/` | **Domain libraries** | Domain-specific shared logic (e.g., `astrid/core/domains/hype/` for arrangement rules, enriched arrangements, text matching). |
| `astrid/core/util/` | **Utility library** | Generic helpers (LLM client construction, environment handling). |
| `astrid/core/audit/` | **Shared library** | Run-local provenance ledger, graph, transport, and HTML report. |
| `astrid/core/threads/` | **Lineage and thread management** | Thread index, ID generation (ULID), provenance tracking, record schema. The m5a milestone removed thread wrapper symbols from the public surface; only 10 lineage symbols remain in `astrid.core.threads.__all__`. |
| `astrid/core/verify/` | **Verification helpers** | Soft boundary — currently a convention, not a hard gate. |
| `astrid/core/modalities/` | **Modality helpers** | Modality-specific support code. |
| `astrid/docs/` | **Package-level docs** | Internal documentation within the `astrid` package. |
| `astrid/skills/` | **Skill harnesses** | Agent skill discovery, registry, and harness runtimes (base, codex, claude, hermes). |
| `astrid/core/orchestrate/` | **Plan compilation and test running** | DSL, compile, test runner, CLI. |
| `astrid/core/theme_schema.py` | **Shared library** | Theme schema validation helpers. Soft boundary — convention. |
| `astrid/core/paths.py` | **Shared library** | Repository and workspace path resolution. |
| `astrid/core/setup_cli.py` | **Shared library** | Setup CLI support. |

### 4.1 CLI/Domain/Import-Layering Convention

The repository enforces a strict import layering convention:

- **CLI modules** live as `<subsystem>/cli.py` for each subsystem (skills, core/threads, core/orchestrate, core/timeline, core/pack). CLI modules may import from their subsystem's internals and from shared libraries, but must not be imported by non-CLI code.
- **Domain libraries** under `astrid/core/domains/` may import from `astrid/core/contracts/`, `astrid/core/util/`, and other core shared libraries. They must not import from `astrid/packs/`.
- **Core kernel** (`astrid/core/`) must not import concrete pack implementation modules except through named runtime bridge exemptions.
- **Pack data** (`astrid/packs/<pack>/`) must not import from `astrid/core/` except through sanctioned entrypoints.

These rules are enforced by `validate_import_layering()` in `astrid/core/structure.py`.

## 5. `astrid/packs` — Capability Surface

`astrid/packs` is the **capability surface** — every executor, orchestrator, and
element ships in a pack under `astrid/packs/<pack>/`. The pack machinery kernel
(`astrid/core/pack/`) provides the framework; packs provide the capabilities.

**M5 rule**: `astrid/packs/` is for pack data only. Top-level Python files are
not allowed under `astrid/packs/` except `__init__.py`. New pack machinery must
go under `astrid/core/pack/*`, not under `astrid/packs/`.

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

The `builtin` pack is hidden and deprecated. It remains only for legacy test
fixtures and historical pack-level aliases; new capability work should use the
canonical shipped packs.

The `_core/` directory is a **skill-only shell** — it contains only
`skill/SKILL.md` (the root Astrid gateway skill), has no `pack.yaml`, and is
not a runtime pack. It is coupled to `astrid/skills/` and treated as a
permanent visible exception.

### 5.3 Top-Level Pack Files

The only Python file directly under `astrid/packs/` is the package marker:

| File | Classification |
| --- | --- | --- |
| `__init__.py` | Package init |

`_validate_packs_top_level_modules()` in `astrid/core/structure.py` rejects any other
top-level module under `astrid/packs/`.

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
- Top-level `.py` files under `astrid/packs/` are rejected except `__init__.py`

## 6. `astrid/elements/` — Planned-Absent Canonical Concept

`TOP_LEVEL_ASTRID_DIRS` in `astrid/core/structure.py` includes `"elements"` as a
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

`tests/test_m2_public_surface.py` — public surface characterization updated to
the canonical gateway, paths, media, timeline, thread, and SDK surfaces.

`tests/test_m2_pack_machinery.py` — pack machinery characterization updated to
the canonical `astrid.core.pack.*` layout: exports, CLI/install surfaces,
discovery, resolver, store, schema-root relocation, and no-shim enforcement.

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
| `docs/architecture/shim-legacy-audit.md` | Current no-shim audit and retired-surface map |
| `docs/platform-contract.md` | Normative v1 platform contract (SDK exports, SemVer, deprecation window). |
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
| `astrid/gateway.py` | 1,215 | Package | Folded into `astrid/core/gateway/` (`__init__.py`, `dispatch.py`, `help.py`, `project.py`, `wait.py`) |
| `astrid/sdk.py` | 1,833 | Package | Folded into the `astrid/sdk/` package (`discovery.py`, `dto.py`, `events.py`, `exceptions.py`, `generation.py`, `invocation.py`, `results.py`) |

The gateway and SDK implementations now live in packages rather than top-level
split modules.

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
| Timeline canonicalization | **Complete** | §3 — retired timeline re-export surfaces |
| Internal threads lineage (m5a) | **Complete** | §4 — Threads subsystem with removed wrapper symbols |
| Public compatibility shim removal | **Complete** | §3 — retired surface map |
| Top-level module rationalization (M2) | **Complete** | §2 — `core/pack/` canonical pack machinery; §5 — `packs/` as pack data only; §5.3 — no top-level pack modules; §5.5 — structure enforcement |
| Giant-file split (M4) | **Complete** | §9.1 — Gateway and SDK folded into packages |
| M5 boundary enforcement | **Complete** | §2.2 — Contributor placement guidance; §4.1 — CLI/domain/import-layering convention; §12.1 — Structure enforcement model |
| Shim and legacy surface audit (M5) | **Complete** | `docs/architecture/shim-legacy-audit.md` — M5 dispositions with retention metadata |

## 11. Soft Boundary Conventions (Not Hard-Gated)

The following boundaries are conventions documented here for awareness. They are
not enforced with hard gates:

| Boundary | Notes |
| --- | --- |
| `threads.ids` | Should not be imported outside the threads package; currently a convention |
| `verify` | Verification helpers should not depend on packs or orchestrate |
| `theme_schema` | Theme schema validation should remain a leaf utility |

Later milestones may choose to enforce these as hard gates.

## 12. Structure Enforcement Model

### 12.1 Validator

`astrid/core/structure.py` is the **single source of truth** for repository
structure enforcement. It exposes:

- `validate_repo_structure()` — top-level entry check, pack layout, import layering, migration completion (returns `StructureReport`)
- `validate_import_layering()` — core→packs import prohibition
- `validate_migration_completion()` — DEPRECATED markers, sys.modules injections, dangling `__all__` aliases, compatibility shim detection
- `validate_run_record_status_boundary()` — legacy run-record status token detection

### 12.2 Exemption Lists

All exemptions are colocated in `astrid/core/structure.py`:

| Constant | Purpose |
| --- | --- |
| `TOP_LEVEL_ASTRID_FILES` | Allowed top-level `.py` files under `astrid/` |
| `TOP_LEVEL_ASTRID_DIRS` | Allowed top-level directories under `astrid/` |
| `_IMPORT_LAYERING_EXEMPT_REL` | Files exempt from core import-layering rules |

### 12.3 Consumption

`astrid/core/doctor.py` consumes `validate_repo_structure()` and fails when
canonical repository structure drifts.

## 13. M3, M4, and M5 Inventory Consumption

- **M3** consumes `docs/architecture/test-relocation-map.json` to guide
  root-level test file relocation into domain-specific test directories.
  Ambiguous cases are flagged for owner review.

- **M4** consumed `docs/architecture/giant-file-split-candidates.json` to
  split `gateway.py` and `sdk.py`. Later cleanup folded both split surfaces into
  packages.

- **M5** updates this document to reflect the post-split layout, adds
  contributor placement guidance, formalizes the CLI/domain/import-layering
  convention, and replaces stale references with current-state documentation.
