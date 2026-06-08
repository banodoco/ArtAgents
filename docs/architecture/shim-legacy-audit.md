# Shim and Legacy Surface Audit — M5

This document catalogs every legacy surface, compatibility shim, and
deprecated alias present in the M5 checkout. Each entry carries an
**evidence-backed disposition**: what it is, where the evidence lives,
whether M5 keeps, removes, or defers it, and what milestone (if any)
owns its eventual removal.

**New for M5**: Every retained shim or escape hatch now includes an
**owner**, **active caller class**, **removal trigger**, and **concrete
target release or milestone**. These fields enable dependency tracking
across milestones and prevent orphaned surfaces from accumulating
without accountability.

**Governing rule for M5**: No legacy surface is removed in M5 unless
every live caller has already migrated. When removal is deferred, the
deferral milestone is explicitly stated. Banodoco timeline removals are
explicitly deferred to M5b (see §5). Pipeline is a permanent public
compatibility surface (SD1).

---

## 1. Deprecated CLI Aliases

### 1.1 `astrid run` → `astrid runs`

- **Evidence**: `astrid/gateway.py` line 614 —
  `"run": lambda args: _dispatch_runs(args),  # deprecated alias for runs`
- **Dispatcher**: `_dispatch_run()` delegates to `_dispatch_runs()`.
- **Comment in help text**: `astrid/gateway.py` line 1208 —
  `"astrid run {...} → astrid runs {ls,show,...} (preferred: astrid runs)"`
- **Live callers**: The deprecated alias is accepted by the CLI router so any
  existing script or muscle-memory invocation continues to work. The
  characterization tests in `tests/test_m2_public_surface.py` explicitly
  verify that `_TOP_LEVEL_HANDLERS["run"]` routes to `_dispatch_runs`.
- **Disposition**: **Retained for M5.**
- **Owner**: CLI/gateway maintainer
- **Active caller class**: Public CLI (external scripts and muscle-memory invocations)
- **Removal trigger**: When gateway dispatch-table refactor removes all deprecated aliases in a single coordinated change
- **Target milestone**: M6+ (gateway dispatch-table cleanup)

### 1.2 `astrid author` → `astrid orchestrate`

- **Evidence**: `astrid/gateway.py` line 628 —
  `"author": _dispatch_orchestrate,  # deprecated alias for orchestrate`
- **Comment in help text**: `astrid/gateway.py` line 1207 —
  `"astrid author → astrid orchestrate (preferred: astrid orchestrate)"`
- **Live callers**: `astrid/core/task/plan_builder.py` line 320 references
  `astrid author compile` in a recovery hint string. This is advisory text,
  not a live code path, but it signals that the alias is still in the
  mental model of the task kernel.
- **Disposition**: **Retained for M5.**
- **Owner**: CLI/gateway maintainer
- **Active caller class**: Public CLI (external scripts) + internal advisory text
- **Removal trigger**: When `plan_builder.py` recovery hint is updated and gateway dispatch-table is cleaned
- **Target milestone**: M6+ (gateway dispatch-table cleanup)

---

## 2. Legacy Environment Variables

### 2.1 `ASTRID_AUTHOR_TEST_LEGACY`

- **Evidence**: `astrid/core/env_vars.py` lines 154–158.
  The constant's **value** differs from its **name** (the only such exception
  in the env-vars registry, verified by `tests/test_env_vars_conformance.py`).
  `get_author_test_env()` checks the canonical `ASTRID_AUTHOR_TEST` first,
  then falls back to the legacy key with a `DeprecationWarning`.
- **Live callers**: `get_author_test_env()` is the sole consumer; all internal
  callers use the function, not the constant directly.
- **Disposition**: **Retained for M5.**
- **Owner**: Platform/infra maintainer
- **Active caller class**: Public environment (user shell profiles and CI configs)
- **Removal trigger**: After a full minor-release deprecation cycle with user-facing warnings; requires coordinated migration of user shell profiles
- **Target milestone**: M13 (alongside `_media.py` / `_paths.py` shim cleanup)

### 2.2 `ASTRID_ALLOW_LEGACY_APPEND_EVENT`

- **Evidence**: `astrid/core/env_vars.py` line 117;
  `astrid/core/task/events.py` line 53 defines `LEGACY_APPEND_EVENT_ALLOW_ENV`
  pointing at the same string.
- **Live callers**: `astrid/core/task/events.py` reads the flag to gate a
  migration-era append-event code path that bypasses hash chaining.
- **Disposition**: **Retained for M5.**
- **Owner**: Task kernel maintainer
- **Active caller class**: Internal migration-safety escape hatch (runtime environment flag)
- **Removal trigger**: When the migration code path it guards is proven dead across all projects and the append-event bypass can be removed
- **Target milestone**: M6+ (task event-stream cleanup)

---

## 3. Legacy Task/Plan Constants

### 3.1 `LEGACY_ASSIGNEES`

- **Evidence**: `astrid/core/task/plan.py` line 24 —
  `LEGACY_ASSIGNEES: frozenset[str] = frozenset({"any-agent"})`.
  Consumed in `plan_verbs.py` lines 350 and 559 to treat `"any-agent"` as
  a wildcard assignee.
- **Live callers**: Two sites in `plan_verbs.py` and one in `plan.py` line 434.
  The `"any-agent"` wildcard is exercised by `tests/task/test_plan_mutation_verbs.py`.
- **Disposition**: **Retained for M5 (SD3).** This is active runtime plan-execution
  behavior, not a migration escape hatch. The `"any-agent"` wildcard is still part
  of the plan DSL contract.
- **Owner**: Plan/task model maintainer
- **Active caller class**: Internal runtime (plan execution and mutation verbs)
- **Removal trigger**: When the plan DSL contract is updated to use a non-legacy assignee model and all callers migrate
- **Target milestone**: Plan-model milestone (M6+)

### 3.2 `_LEGACY_RUN_RECORD_STATUS_TOKENS`

- **Evidence**: `astrid/structure.py` line 580 —
  `_LEGACY_RUN_RECORD_STATUS_TOKENS: frozenset[str] = frozenset({"prepared", "success", "succeeded", "error", "orphaned"})`.
  Consumed by `validate_run_record_status_boundary()` to flag writes that use
  pre-m5a status tokens instead of `RunStatus.value`.
- **Live callers**: The validator itself; this is a guardrail, not a runtime
  code path.
- **Disposition**: **Retained for M5.** The validator is the enforcement
  mechanism for the m5a status migration. Remove the guardrail only after the
  migration is proven complete across all projects.
- **Owner**: Structure/validation maintainer
- **Active caller class**: Structure validation guardrail (not runtime)
- **Removal trigger**: When `validate_run_record_status_boundary()` produces zero advisories across all active projects and no legacy token writes remain
- **Target milestone**: M6 (post-migration cleanup)

---

## 4. Legacy Directory Guards (Can't-Exist Checks)

### 4.1 `LEGACY_PUBLIC_DIRS`

- **Evidence**: `astrid/structure.py` line 20 —
  `LEGACY_PUBLIC_DIRS = ("conductors", "performers", "instruments", "primitives", "executors", "orchestrators")`.
  `_validate_legacy_dirs()` (line 206) fails if any of these exist under `astrid/`.
- **Disposition**: **Retained permanently.**
- **Owner**: Structure/validation maintainer
- **Active caller class**: Structure validation guardrail (blocking check)
- **Removal trigger**: Never — these are old Astrid v0 directory names that must never reappear
- **Target milestone**: Permanent

### 4.2 `LEGACY_LOCAL_DIRS`

- **Evidence**: `astrid/structure.py` line 21 —
  `LEGACY_LOCAL_DIRS = ("performers", "conductors", "nodes", "instruments", "primitives")`.
  `_validate_local_state_dirs()` (line 215) fails if any of these exist under
  `.astrid/`.
- **Disposition**: **Retained permanently.**
- **Owner**: Structure/validation maintainer
- **Active caller class**: Structure validation guardrail (blocking check)
- **Removal trigger**: Never — same reasoning as §4.1
- **Target milestone**: Permanent

---

## 5. Banodoco Timeline Surfaces — **Explicitly Deferred to M5b**

### 5.1 Timeline Public Re-Export Shims

- **Evidence**: Three files form the thin public re-export surface for the
  canonical core timeline API. All are guarded by
  `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` in `astrid/structure.py` (line 157),
  which requires both the path match AND a `TODO(m5b)` marker string in the file.

| File | Re-exports from | TODO marker |
| --- | --- | --- |
| `astrid/timeline/__init__.py` | `astrid.core.timeline` | `TODO(m5b)` (via exemption list match) |
| `astrid/timeline/timeline_model.py` | `astrid.core.timeline.banodoco_schema` | `TODO(m5b)` (via exemption list match) |
| `astrid/timeline/banodoco_composer.py` | `astrid.core.timeline.banodoco_composer` | `TODO(m5b)` (via exemption list match) |

- **Live callers**: `tests/test_m5b_baseline_public_surface.py` (89 tests)
  comprehensively verifies the Banodoco timeline model and composer re-export
  surfaces. `tests/test_m2_public_surface.py` (39 tests) also covers timeline
  re-export surface and Banodoco integration imports. The enforcement gate does
  not ban `astrid.timeline` imports.
- **Disposition**: **Deferred to M5b (SD2).** M5 does not remove, rename, or
  restructure any Banodoco timeline surface. The `TODO(m5b)` markers in
  `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` are the authoritative deferral
  signal. The three shim files stay as thin re-exports with no runtime logic.
- **Owner**: Timeline/Banodoco integration maintainer
- **Active caller class**: Public API (external consumers) + test suite
- **Removal trigger**: Broader Banodoco integration work completed; all external callers migrated to canonical `astrid.core.timeline` imports
- **Target milestone**: M5b

### 5.2 Canonical Banodoco Modules

- **Evidence**:
  - `astrid/core/timeline/banodoco_schema.py` — Canonical Banodoco schema types
    (Timeline, Arrangement, Clip, Pool, Theme, etc.)
  - `astrid/core/timeline/banodoco_composer.py` — Canonical Banodoco composer
    (load/save/merge operations)
- **Disposition**: **Permanent canonical homes.** These are the implementation,
  not shims. They are not legacy surfaces and require no M5 action.

### 5.3 Banodoco Integration Import Surface

- **Evidence**: `tests/test_m2_public_surface.py` verifies that
  `astrid.core.timeline.banodoco_schema`, `astrid.core.timeline.banodoco_composer`,
  and `astrid.timeline` (the re-export shim) are all importable and return
  the expected types.
- **Disposition**: **No M5 changes.** The integration surface is stable and
  tested.

---

## 6. Pack Machinery Compatibility Shims (M2 Output, M5 Retained)

These shims were created during M2 T4–T11 as the pack machinery implementation
moved from `astrid/packs/` and `astrid/core/pack_machinery/` into the canonical
home `astrid/core/pack/`. They are **intentional M2 output**, retained through
M5 while callers continue to migrate.

### 6.1 `astrid/core/pack_machinery/` Shims

| File | Canonical home | Shim type |
| --- | --- | --- |
| `astrid/core/pack_machinery/__init__.py` | (package marker) | Empty package init |
| `astrid/core/pack_machinery/cli.py` | `astrid/core/pack/cli.py` | Thin re-export with `__all__` |
| `astrid/core/pack_machinery/validate.py` | `astrid/core/pack/validate.py` | Thin re-export with `__all__` |
| `astrid/core/pack_machinery/agent_index.py` | `astrid/core/pack/agent_index.py` | Thin re-export with `__all__` |
| `astrid/core/pack_machinery/gitignore.py` | `astrid/core/pack/gitignore.py` | Thin re-export with `__all__` |
| `astrid/core/pack_machinery/install.py` | `astrid/core/pack/install.py` | `sys.modules` alias shim |

- **Evidence**: `tests/test_m2_pack_machinery.py` §MachineryShimIdentity
  verifies `assertIs` identity between every shim and its canonical module.
- **Disposition**: **Retained for M5.** These shims preserve `mock.patch`
  targets and import paths used by tests and internal consumers. Removal is
  deferred to a later milestone when all callers have migrated to canonical
  paths.
- **Owner**: Pack machinery maintainer
- **Active caller class**: Internal (test suite mock.patch targets, transitional importers)
- **Removal trigger**: When `tests/test_m2_pack_machinery.py` shim-identity tests pass after removing shims (i.e., zero live callers remain)
- **Target milestone**: M6+ (pack machinery cleanup)

### 6.2 `astrid/packs/` Top-Level Shims

| File | Canonical home | Shim type |
| --- | --- | --- |
| `astrid/packs/__init__.py` | (package marker) | Re-exports 11 names from `astrid.core.pack` |
| `astrid/packs/cli.py` | `astrid/core/pack/cli.py` | Thin re-export (≤11 lines) |
| `astrid/packs/validate.py` | `astrid/core/pack/validate.py` | Thin re-export (≤11 lines) |
| `astrid/packs/agent_index.py` | `astrid/core/pack/agent_index.py` | Thin re-export (≤11 lines) |
| `astrid/packs/gitignore.py` | `astrid/core/pack/gitignore.py` | Thin re-export (≤11 lines) |
| `astrid/packs/install.py` | `astrid/core/pack/install.py` | `sys.modules` alias shim |
| `astrid/packs/_canonical_entrypoint.py` | `astrid/core/pack/entrypoint.py` | Thin re-export (4 names) |

- **Enforcement**: `_validate_packs_top_level_modules()` in `astrid/structure.py`
  (added M2 T13) requires every `.py` file under `astrid/packs/` to be a
  documented compatibility shim with ≤12 meaningful lines.
- **Evidence**: `tests/test_structure_contracts.py` packs-top-level tests
  verify enforcement. `tests/test_m2_pack_machinery.py` §PacksShimResolution
  verifies identity for cli, validate, agent_index, gitignore.
- **Disposition**: **Retained for M5.** These are the public compatibility
  layer that keeps `astrid/packs/` a valid import target for legacy callers
  while the canonical implementation lives in `astrid/core/pack/`.
- **Owner**: Pack machinery maintainer
- **Active caller class**: Public/internal (legacy import paths, test mock.patch targets)
- **Removal trigger**: When all downstream callers migrate to `astrid.core.pack.*` imports
- **Target milestone**: M6+ (pack machinery cleanup)

### 6.3 Loose `astrid/core/` Module Shims

| File | Canonical home |
| --- | --- |
| `astrid/core/pack_discovery.py` | `astrid/core/pack/discovery.py` |
| `astrid/core/pack_resolver.py` | `astrid/core/pack/resolver.py` |
| `astrid/core/pack_store.py` | `astrid/core/pack/store.py` |
| `astrid/core/manifest.py` | `astrid/core/pack/manifest.py` |
| `astrid/core/override.py` | `astrid/core/pack/override.py` |
| `astrid/core/alias_resolver.py` | `astrid/core/pack/alias_resolver.py` |

- **Evidence**: `tests/test_m2_pack_machinery.py` §LooseModuleShimCompleteness
  verifies every loose module is importable and returns the same objects as
  its canonical counterpart. All are thin re-export shims (no runtime logic).
- **Disposition**: **Retained for M5.** These shims preserve `mock.patch`
  targets (notably `astrid.core.pack_store.installed_pack_roots`) and import
  paths used by tests.
- **Owner**: Pack machinery maintainer
- **Active caller class**: Internal (test suite mock.patch targets)
- **Removal trigger**: When `test_m2_pack_machinery.py` loose-module tests pass without the shims
- **Target milestone**: M6+ (pack machinery cleanup)

---

## 7. Stable Long-Term Compatibility Shims

### 7.1 `astrid/_media.py` → `astrid/media.py`

- **Evidence**: `astrid/structure.py` line 151 —
  listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with `TODO(m13)`.
- **Live callers**: The shim has live import callers; the exemption suppresses
  the "shim with N live callers" advisory.
- **Disposition**: **Deferred to M13.**
- **Owner**: Platform maintainer
- **Active caller class**: Public (external consumers using `astrid._media` import path)
- **Removal trigger**: Full deprecation cycle (two minor releases) after all known callers migrate to `astrid.media`
- **Target milestone**: M13

### 7.2 `astrid/_paths.py` → `astrid/paths.py`

- **Evidence**: `astrid/structure.py` line 152 —
  listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with `TODO(m13)`.
- **Live callers**: The shim has live import callers.
- **Disposition**: **Deferred to M13.**
- **Owner**: Platform maintainer
- **Active caller class**: Public (external consumers using `astrid._paths` import path)
- **Removal trigger**: Full deprecation cycle (two minor releases) after all known callers migrate to `astrid.paths`
- **Target milestone**: M13

### 7.3 `astrid/pipeline.py` ↔ `astrid/gateway.py`

- **Evidence**: `astrid/structure.py` lines 142 and 154 —
  listed in both `_SYS_MODULES_INJECTION_EXEMPTIONS` and
  `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS`. Uses
  `sys.modules[__name__] = sys.modules["astrid.gateway"]` so every
  `import astrid.pipeline` and `mock.patch("astrid.pipeline.…")` target
  transparently resolves to the gateway.
- **Disposition**: **Retained permanently (SD1).** The `sys.modules`
  injection pattern is the preferred approach for gateway-level
  compatibility shims. Pipeline is a permanent public compatibility
  surface with zero internal callers. The shim-import enforcement
  gate does not ban it. Removal would require coordinated migration of
  all `astrid.pipeline` callers — a breaking change with no benefit.
- **Owner**: Gateway maintainer
- **Active caller class**: Public (external consumers, test mock.patch targets)
- **Removal trigger**: Never — permanent public compatibility surface
- **Target milestone**: Permanent (SD1)

### 7.4 `astrid/core/_search.py`

- **Evidence**: `astrid/structure.py` line 153 —
  listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with `TODO(m13)`.
- **Disposition**: **Deferred to M13.**
- **Owner**: Platform maintainer
- **Active caller class**: Internal (legacy importers within the codebase)
- **Removal trigger**: Full deprecation cycle after all internal callers migrate
- **Target milestone**: M13

---

## 8. Shells and Hidden Packs

### 8.1 `_core/` — Skill-Only Shell

- **Evidence**: `astrid/packs/_core/skill/SKILL.md` exists; no `pack.yaml`
  exists. Coupled to `astrid/skills/registry.py`, `astrid/skills/harnesses/*`,
  `astrid/skills/discovery.py`, `astrid/skills/__init__.py`, and
  `astrid/core/pack/validate.py`.
- **Classification**: `skill_only_shell` (per `docs/architecture/top-level-inventory.json`).
  Not a runtime pack. Permanent visible exception.
- **Disposition**: **Permanent visible exception.**
- **Owner**: Skills maintainer
- **Active caller class**: Internal (skills registry and harness infrastructure)
- **Removal trigger**: Never — the `_core/` directory contains the root Astrid gateway skill and is a permanent architectural fixture
- **Target milestone**: Permanent

### 8.2 `builtin` — Hidden Compatibility Shell

- **Evidence**: `astrid/packs/builtin/pack.yaml` declares `visibility: hidden`,
  `status: deprecated`, `install_tier: core`. Contains `agent_probe.py` (DSL
  orchestrator shim with 16+ regression test references) and `fixtures/`/
  `golden/` test infrastructure.
- **Classification**: `pack_compatibility_shell` (per `docs/architecture/top-level-inventory.json`).
- **Disposition**: **Retained for M5.** The `builtin` pack preserves
  backward-compatible pack-level aliases mapping legacy `builtin.*` capability
  IDs to canonical homes.
- **Owner**: Pack/test infrastructure maintainer
- **Active caller class**: Test suite (16+ regression test references to `agent_probe.py`)
- **Removal trigger**: When all regression tests referencing `builtin.agent_probe` are migrated to canonical paths and the legacy alias map is no longer needed
- **Target milestone**: M6+ (test infrastructure cleanup)

### 8.3 Shipped Pack Data (`stream_content`, `comfy_wrap`, `text_analysis`)

- **Evidence**: These are real shipped packs with `pack.yaml`, stable pack IDs,
  and capability IDs. Their pack IDs and capability IDs must not change.
- **Disposition**: **No M5 changes.** These are pack data, not legacy surfaces.

---

## 9. Import Layering Exemptions (Legacy Bridges)

### 9.1 `astrid/core/runtime/in_process.py`

- **Evidence**: `astrid/structure.py` line 112 comment —
  "Sanctioned bridge between framework and pack boundaries for the in-process
  entrypoint machinery. Permanent architectural choice."
- **File-level exemption**: Listed in `_IMPORT_LAYERING_EXEMPT_REL`.
- **What it imports**: `from astrid.core.pack.entrypoint import
  canonical_runtime_entrypoint` — crosses from `core` into pack entrypoint
  machinery.
- **Disposition**: **Permanent exemption.**
- **Owner**: Runtime maintainer
- **Active caller class**: Internal (in-process runtime invoker)
- **Removal trigger**: Never — sanctioned architectural bridge
- **Target milestone**: Permanent

### 9.2 `astrid/core/task/event_stream.py`

- **Evidence**: `astrid/structure.py` line 113 comment —
  "Imports `astrid.audit.graph` and `astrid.audit.transport` for unified
  task/audit event stream reading. This is a file-level exemption."
- **Disposition**: **Retained for M5.** The audit dependency is exempted
  rather than removed.
- **Owner**: Task/audit maintainer
- **Active caller class**: Internal (unified task/audit event-stream reader)
- **Removal trigger**: When the audit subsystem is refactored to remove the import dependency
- **Target milestone**: Audit refactor milestone

---

## 10. Pack Machinery Schemas (Deprecated Copy)

### 10.1 `astrid/core/pack_machinery/schemas/v1/`

- **Evidence**: After M2 T10, the canonical schemas live at
  `astrid/core/pack/schemas/v1/`. The `astrid/core/pack_machinery/schemas/v1/`
  directory still exists as a deprecated reference copy.
- **Disposition**: **Retained for M5 as a deprecated copy.**
- **Owner**: Pack machinery maintainer
- **Active caller class**: Possibly external tooling referencing the `pack_machinery` path
- **Removal trigger**: When `pack_machinery/` shim directory is removed entirely
- **Target milestone**: M6+ (alongside `pack_machinery/` removal)

---

## 11. Summary Disposition Table

| Surface | Status in M5 | Removal milestone | Owner | Active caller class | Removal trigger |
| --- | --- | --- | --- | --- | --- |
| `astrid run` CLI alias | Retained | M6+ | CLI/gateway | Public CLI | Gateway dispatch-table cleanup |
| `astrid author` CLI alias | Retained | M6+ | CLI/gateway | Public CLI + advisory text | Gateway dispatch-table cleanup |
| `ASTRID_AUTHOR_TEST_LEGACY` | Retained | M13 | Platform/infra | Public environment | Full deprecation cycle |
| `ASTRID_ALLOW_LEGACY_APPEND_EVENT` | Retained | M6+ | Task kernel | Internal escape hatch | Migration code path proven dead |
| `LEGACY_ASSIGNEES` (SD3) | Retained | Plan-model (M6+) | Plan/task model | Internal runtime | Plan DSL contract update |
| `_LEGACY_RUN_RECORD_STATUS_TOKENS` | Retained | M6 | Structure/validation | Guardrail (non-runtime) | Zero legacy token writes remain |
| `LEGACY_PUBLIC_DIRS` guard | Retained | Permanent | Structure/validation | Guardrail (blocking) | Never |
| `LEGACY_LOCAL_DIRS` guard | Retained | Permanent | Structure/validation | Guardrail (blocking) | Never |
| Banodoco timeline shims (SD2) | **Deferred to M5b** | M5b | Timeline/Banodoco | Public API + test suite | Banodoco integration work complete |
| Banodoco canonical modules | Permanent | N/A | Timeline/Banodoco | N/A | N/A |
| `pack_machinery/` shims (6 files) | Retained (M2 output) | M6+ | Pack machinery | Internal (tests + transitional) | Zero live callers |
| `packs/` top-level shims (7 files) | Retained (M2 output) | M6+ | Pack machinery | Public/internal (legacy paths) | Downstream callers migrated |
| Loose `core/` module shims (6 files) | Retained (M2 output) | M6+ | Pack machinery | Internal (test mock.patch) | Tests pass without shims |
| `_media.py` shim | Retained | M13 | Platform | Public | Full deprecation cycle |
| `_paths.py` shim | Retained | M13 | Platform | Public | Full deprecation cycle |
| `pipeline.py` shim (SD1) | **Permanent** | Permanent | Gateway | Public | Never — permanent SD1 |
| `core/_search.py` shim | Retained | M13 | Platform | Internal | Full deprecation cycle |
| `_core/` skill-only shell | Retained | Permanent | Skills | Internal | Never |
| `builtin` hidden compatibility shell | Retained | M6+ | Pack/test infra | Test suite | Regression tests migrated |
| `stream_content` / `comfy_wrap` / `text_analysis` | Pack data (not legacy) | N/A | N/A | N/A | N/A |
| `runtime/in_process.py` import exemption | Retained | Permanent | Runtime | Internal | Never |
| `task/event_stream.py` import exemption | Retained | Audit refactor | Task/audit | Internal | Audit subsystem refactored |
| `pack_machinery/schemas/v1/` deprecated copy | Retained | M6+ | Pack machinery | Possibly external tooling | `pack_machinery/` removal |

---

## 12. Verification

Characterization tests covering these surfaces:

- `tests/test_m2_public_surface.py` (39 tests) — root imports, pipeline-gateway
  identity, deprecated CLI alias routing, Banodoco integration imports,
  timeline re-export surface.
- `tests/test_m2_pack_machinery.py` (46 tests) — core.pack exports,
  pack_machinery submodules, packs shim resolution, machinery-shim identity,
  loose-module shim completeness.
- `tests/test_m5b_baseline_public_surface.py` (89 tests) — Banodoco timeline
  model and composer re-export surfaces.
- `tests/test_env_vars_conformance.py` — verifies `ASTRID_AUTHOR_TEST_LEGACY`
  is the sole constant whose value differs from its name.
- `tests/test_structure_contracts.py` — packs top-level module enforcement,
  timeline facade exemption guards, migration completion advisories.
- `tests/task/test_plan_mutation_verbs.py` — exercises `LEGACY_ASSIGNEES`
  `"any-agent"` wildcard behavior.

**M5 scope boundary**: This audit is documentation. No physical removals of
legacy surfaces occur in M5. Every disposition is evidence-backed with file
paths and line numbers. Every retained item carries an owner, active caller
class, removal trigger, and concrete target milestone. Banodoco timeline
removals are explicitly deferred to M5b (SD2). Pipeline is a permanent
public compatibility surface (SD1). `LEGACY_ASSIGNEES` is active runtime
behavior (SD3).
