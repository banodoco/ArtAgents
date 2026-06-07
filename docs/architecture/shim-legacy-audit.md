# Shim and Legacy Surface Audit — M2

This document catalogs every legacy surface, compatibility shim, and
deprecated alias present in the M2 checkout. Each entry carries an
**evidence-backed disposition**: what it is, where the evidence lives,
whether M2 keeps, removes, or defers it, and what milestone (if any)
owns its eventual removal.

**Governing rule for M2**: No legacy surface is removed in M2 unless
every live caller has already migrated. When removal is deferred, the
deferral milestone is explicitly stated. Banodoco timeline removals are
explicitly deferred out of M2 (see §5).

---

## 1. Deprecated CLI Aliases

### 1.1 `astrid run` → `astrid runs`

- **Evidence**: `astrid/gateway.py` line 614 —
  `"run": lambda args: _dispatch_runs(args),  # deprecated alias for runs`
- **Dispatcher**: `_dispatch_run()` (line 696) delegates to `_dispatch_runs()`.
- **Comment in help text**: `astrid/gateway.py` line 1208 —
  `"astrid run {...} → astrid runs {ls,show,...} (preferred: astrid runs)"`
- **Live callers**: The deprecated alias is accepted by the CLI router so any
  existing script or muscle-memory invocation continues to work. The
  characterization tests in `tests/test_m2_public_surface.py` explicitly
  verify that `_TOP_LEVEL_HANDLERS["run"]` routes to `_dispatch_runs`.
- **Disposition**: **Retained for M2.** The alias adds zero maintenance cost
  (a single dict entry) and removing it would break undocumented scripts.
  Defer removal evaluation to M4 (alongside gateway giant-file split).

### 1.2 `astrid author` → `astrid orchestrate`

- **Evidence**: `astrid/gateway.py` line 628 —
  `"author": _dispatch_orchestrate,  # deprecated alias for orchestrate`
- **Comment in help text**: `astrid/gateway.py` line 1207 —
  `"astrid author → astrid orchestrate (preferred: astrid orchestrate)"`
- **Live callers**: `astrid/core/task/plan_builder.py` line 320 references
  `astrid author compile` in a recovery hint string. This is advisory text,
  not a live code path, but it signals that the alias is still in the
  mental model of the task kernel.
- **Disposition**: **Retained for M2.** Same zero-cost reasoning as §1.1.
  Defer removal evaluation to M4.

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
- **Disposition**: **Retained for M2.** The fallback costs one `os.environ.get`
  call. Removing the constant would require a coordinated migration of user
  shell profiles — not appropriate for a repo-structure milestone. Defer
  removal to M13 alongside `_media.py` / `_paths.py` shim cleanup.

### 2.2 `ASTRID_ALLOW_LEGACY_APPEND_EVENT`

- **Evidence**: `astrid/core/env_vars.py` line 117;
  `astrid/core/task/events.py` line 53 defines `LEGACY_APPEND_EVENT_ALLOW_ENV`
  pointing at the same string.
- **Live callers**: `astrid/core/task/events.py` reads the flag to gate a
  migration-era append-event code path that bypasses hash chaining.
- **Disposition**: **Retained for M2.** This is a migration-safety escape
  hatch, not deprecated surface debt. When the migration code it guards is
  removed (target: M5 or later), the env-var constant and its reader should
  be removed together.

---

## 3. Legacy Task/Plan Constants

### 3.1 `LEGACY_ASSIGNEES`

- **Evidence**: `astrid/core/task/plan.py` line 24 —
  `LEGACY_ASSIGNEES: frozenset[str] = frozenset({"any-agent"})`.
  Consumed in `plan_verbs.py` lines 350 and 559 to treat `"any-agent"` as
  a wildcard assignee.
- **Live callers**: Two sites in `plan_verbs.py` and one in `plan.py` line 434.
- **Disposition**: **Retained for M2.** This is runtime plan-execution logic,
  not a repo-structure concern. The `"any-agent"` wildcard is still part of
  the plan DSL contract. Defer removal/replacement to the plan-model milestone
  (M5 or later).

### 3.2 `_LEGACY_RUN_RECORD_STATUS_TOKENS`

- **Evidence**: `astrid/structure.py` line 571 —
  `_LEGACY_RUN_RECORD_STATUS_TOKENS: frozenset[str] = frozenset({"prepared", "success", "succeeded", "error", "orphaned"})`.
  Consumed by `validate_run_record_status_boundary()` to flag writes that use
  pre-m5a status tokens instead of `RunStatus.value`.
- **Live callers**: The validator itself; this is a guardrail, not a runtime
  code path.
- **Disposition**: **Retained for M2.** The validator is the enforcement
  mechanism for the m5a status migration. Remove the guardrail only after the
  migration is proven complete across all projects (target: M5).

---

## 4. Legacy Directory Guards (Can't-Exist Checks)

### 4.1 `LEGACY_PUBLIC_DIRS`

- **Evidence**: `astrid/structure.py` line 20 —
  `LEGACY_PUBLIC_DIRS = ("conductors", "performers", "instruments", "primitives", "executors", "orchestrators")`.
  `_validate_legacy_dirs()` (line 206) fails if any of these exist under `astrid/`.
- **Disposition**: **Retained permanently.** These are old Astrid v0 directory
  names that must never reappear. The validator is cheap insurance.

### 4.2 `LEGACY_LOCAL_DIRS`

- **Evidence**: `astrid/structure.py` line 21 —
  `LEGACY_LOCAL_DIRS = ("performers", "conductors", "nodes", "instruments", "primitives")`.
  `_validate_local_state_dirs()` (line 215) fails if any of these exist under
  `.astrid/`.
- **Disposition**: **Retained permanently.** Same reasoning as §4.1.

---

## 5. Banodoco Timeline Surfaces — **Explicitly Deferred Out of M2**

### 5.1 Timeline Public Re-Export Shims

- **Evidence**: Three files form the thin public re-export surface for the
  canonical core timeline API. All are guarded by
  `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` in `astrid/structure.py` (line 148),
  which requires both the path match AND a `TODO(m5b)` marker string in the file.

| File | Re-exports from | TODO marker |
| --- | --- | --- |
| `astrid/timeline/__init__.py` | `astrid.core.timeline` | `TODO(m5b)` (via exemption list match) |
| `astrid/timeline/timeline_model.py` | `astrid.core.timeline.banodoco_schema` | `TODO(m5b)` (via exemption list match) |
| `astrid/timeline/banodoco_composer.py` | `astrid.core.timeline.banodoco_composer` | `TODO(m5b)` (via exemption list match) |

- **Live callers**: `tests/test_m5b_baseline_public_surface.py` (89 tests)
  comprehensively verifies the Banodoco timeline model and composer re-export
  surfaces. `tests/test_m2_public_surface.py` (39 tests) also covers timeline
  re-export surface and Banodoco integration imports.
- **Disposition**: **Deferred to M5b.** M2 does not remove, rename, or
  restructure any Banodoco timeline surface. The `TODO(m5b)` markers in
  `_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS` are the authoritative deferral
  signal. The three shim files stay as thin re-exports with no runtime logic.

### 5.2 Canonical Banodoco Modules

- **Evidence**:
  - `astrid/core/timeline/banodoco_schema.py` — Canonical Banodoco schema types
    (Timeline, Arrangement, Clip, Pool, Theme, etc.)
  - `astrid/core/timeline/banodoco_composer.py` — Canonical Banodoco composer
    (load/save/merge operations)
- **Disposition**: **Permanent canonical homes.** These are the implementation,
  not shims. They are not legacy surfaces and require no M2 action.

### 5.3 Banodoco Integration Import Surface

- **Evidence**: `tests/test_m2_public_surface.py` verifies that
  `astrid.core.timeline.banodoco_schema`, `astrid.core.timeline.banodoco_composer`,
  and `astrid.timeline` (the re-export shim) are all importable and return
  the expected types.
- **Disposition**: **No M2 changes.** The integration surface is stable and
  tested.

---

## 6. Pack Machinery Compatibility Shims (M2 Output)

These shims were created during M2 T4–T11 as the pack machinery implementation
moved from `astrid/packs/` and `astrid/core/pack_machinery/` into the canonical
home `astrid/core/pack/`. They are **intentional M2 output**, not unfinished
work.

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
- **Disposition**: **Retained for M2.** These shims preserve `mock.patch`
  targets and import paths used by tests and internal consumers. Removal is
  deferred to a later milestone when all callers have migrated to canonical
  paths.

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
- **Disposition**: **Retained for M2.** These are the public compatibility
  layer that keeps `astrid/packs/` a valid import target for legacy callers
  while the canonical implementation lives in `astrid/core/pack/`. Removal is
  deferred to a later milestone when all callers migrate.

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
- **Disposition**: **Retained for M2.** These shims preserve `mock.patch`
  targets (notably `astrid.core.pack_store.installed_pack_roots`) and import
  paths used by tests. Removal is deferred to a later milestone.

---

## 7. Stable Long-Term Compatibility Shims

### 7.1 `astrid/_media.py` → `astrid/media.py`

- **Evidence**: `astrid/structure.py` line 142 —
  listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with `TODO(m13)`.
- **Live callers**: The shim has live import callers; the exemption suppresses
  the "shim with N live callers" advisory.
- **Disposition**: **Deferred to M13.** Not an M2 concern.

### 7.2 `astrid/_paths.py` → `astrid/paths.py`

- **Evidence**: `astrid/structure.py` line 143 —
  listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with `TODO(m13)`.
- **Live callers**: The shim has live import callers.
- **Disposition**: **Deferred to M13.** Not an M2 concern.

### 7.3 `astrid/pipeline.py` ↔ `astrid/gateway.py`

- **Evidence**: `astrid/structure.py` lines 133 and 145 —
  listed in both `_SYS_MODULES_INJECTION_EXEMPTIONS` and
  `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS`. Uses
  `sys.modules[__name__] = sys.modules["astrid.gateway"]` so every
  `import astrid.pipeline` and `mock.patch("astrid.pipeline.…")` target
  transparently resolves to the gateway.
- **Disposition**: **Retained permanently (SD1).** The `sys.modules`
  injection pattern is the preferred approach for gateway-level
  compatibility shims. Removal would require coordinated migration of
  all `astrid.pipeline` callers — a breaking change with no M2 benefit.

### 7.4 `astrid/core/_search.py`

- **Evidence**: `astrid/structure.py` line 144 —
  listed in `_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS` with `TODO(m13)`.
- **Disposition**: **Deferred to M13.** Not an M2 concern.

---

## 8. Shells and Hidden Packs

### 8.1 `_core/` — Skill-Only Shell

- **Evidence**: `astrid/packs/_core/skill/SKILL.md` exists; no `pack.yaml`
  exists. Coupled to `astrid/skills/registry.py`, `astrid/skills/harnesses/*`,
  `astrid/skills/discovery.py`, `astrid/skills/__init__.py`, and
  `astrid/core/pack/validate.py`.
- **Classification**: `skill_only_shell` (per `docs/architecture/top-level-inventory.json`).
  Not a runtime pack. Permanent visible exception.
- **Disposition**: **Permanent visible exception.** The `_core/` directory
  contains the root Astrid gateway skill. It is not a pack and never will be.
  No M2 action.

### 8.2 `builtin` — Hidden Compatibility Shell

- **Evidence**: `astrid/packs/builtin/pack.yaml` declares `visibility: hidden`,
  `status: deprecated`, `install_tier: core`. Contains `agent_probe.py` (DSL
  orchestrator shim with 16+ regression test references) and `fixtures/`/
  `golden/` test infrastructure.
- **Classification**: `pack_compatibility_shell` (per `docs/architecture/top-level-inventory.json`).
- **Disposition**: **Retained for M2.** The `builtin` pack preserves
  backward-compatible pack-level aliases mapping legacy `builtin.*` capability
  IDs to canonical homes. `agent_probe.py` is deferred to M2 per its
  `pack.yaml` exception declaration (`defer_to: M2`). The pack itself is not
  removed — only its root shim file may be relocated in a future milestone.

### 8.3 Shipped Pack Data (`stream_content`, `comfy_wrap`, `text_analysis`)

- **Evidence**: These are real shipped packs with `pack.yaml`, stable pack IDs,
  and capability IDs. Their pack IDs and capability IDs must not change (M2
  success criterion).
- **Disposition**: **No M2 changes.** These are pack data, not legacy surfaces.
  Their pack IDs (`stream_content`, `comfy_wrap`, `text_analysis`) and
  capability IDs (e.g., `comfy_wrap.*`, `text_analysis.*`) are stable.

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
- **Disposition**: **Permanent exemption.** This is a sanctioned architectural
  bridge, not legacy debt. No M2 action.

### 9.2 `astrid/core/task/event_stream.py`

- **Evidence**: `astrid/structure.py` line 113 comment —
  "Imports `astrid.audit.graph` and `astrid.audit.transport` for unified
  task/audit event stream reading. This is a file-level exemption."
- **Disposition**: **Retained for M0/M2.** The audit dependency is exempted
  rather than removed because M0 is not a refactor milestone. Defer
  resolution to the milestone that refactors the audit subsystem.

---

## 10. Pack Machinery Schemas (Deprecated Copy)

### 10.1 `astrid/core/pack_machinery/schemas/v1/`

- **Evidence**: After M2 T10, the canonical schemas live at
  `astrid/core/pack/schemas/v1/`. The `astrid/core/pack_machinery/schemas/v1/`
  directory still exists as a deprecated reference copy.
- **Disposition**: **Retained for M2 as a deprecated copy.** The canonical
  schemas are resolved from `astrid/core/pack/schemas/v1/` via
  `_SCHEMAS_ROOT` in `validate.py`. The old copy remains for any tooling
  that may still reference the `pack_machinery` path. Defer cleanup to the
  milestone that removes the `pack_machinery` shims entirely.

---

## 11. Summary Disposition Table

| Surface | Status in M2 | Removal milestone |
| --- | --- | --- |
| `astrid run` CLI alias | Retained | M4 (gateway split) |
| `astrid author` CLI alias | Retained | M4 (gateway split) |
| `ASTRID_AUTHOR_TEST_LEGACY` | Retained | M13 |
| `ASTRID_ALLOW_LEGACY_APPEND_EVENT` | Retained | M5+ (with migration code) |
| `LEGACY_ASSIGNEES` | Retained | M5+ (plan-model milestone) |
| `_LEGACY_RUN_RECORD_STATUS_TOKENS` | Retained | M5 (post-migration cleanup) |
| `LEGACY_PUBLIC_DIRS` guard | Retained | Permanent |
| `LEGACY_LOCAL_DIRS` guard | Retained | Permanent |
| Banodoco timeline shims | **Deferred out of M2** | M5b |
| Banodoco canonical modules | Permanent | N/A |
| `pack_machinery/` shims (6 files) | Retained (M2 output) | Later milestone |
| `packs/` top-level shims (7 files) | Retained (M2 output) | Later milestone |
| Loose `core/` module shims (6 files) | Retained (M2 output) | Later milestone |
| `_media.py` shim | Retained | M13 |
| `_paths.py` shim | Retained | M13 |
| `pipeline.py` shim | Retained | Permanent (SD1) |
| `core/_search.py` shim | Retained | M13 |
| `_core/` skill-only shell | Retained | Permanent |
| `builtin` hidden compatibility shell | Retained | Later milestone |
| `stream_content` / `comfy_wrap` / `text_analysis` | Pack data (not legacy) | N/A |
| `runtime/in_process.py` import exemption | Retained | Permanent |
| `task/event_stream.py` import exemption | Retained | Audit refactor milestone |
| `pack_machinery/schemas/v1/` deprecated copy | Retained | Shim cleanup milestone |

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

**M2 scope boundary**: This audit is documentation. No physical removals of
legacy surfaces occur in M2. Every disposition is evidence-backed with file
paths and line numbers. Banodoco timeline removals are explicitly deferred
to M5b.
