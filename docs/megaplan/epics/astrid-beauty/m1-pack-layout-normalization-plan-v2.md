# Implementation Plan: M1 Pack Layout Normalization — Revision 2

## Overview
Astrid currently has two mixed surfaces under `astrid/packs/`: first-party pack data and pack-system machinery (`validate.py`, `cli.py`, `install.py`, `agent_index.py`, `_canonical_entrypoint.py`, `gitignore.py`, and `schemas/v1/`). The checked-in fleet also has layout drift: root pack docs still appear in `media/AGENTS.md`, `media/README.md`; generated artifacts and caches are present in the working tree; flat/root Python shims exist in `builtin/agent_probe.py` (DSL orchestrator), `video_editing/hype.py` (legacy shim with already-canonical `orchestrators/hype/run.py`), and `text_analysis/summarize.py` (DSL orchestrator); and many `__init__.py` files exist in pack data paths even though the requested convention makes packs pure data by default.

The fundamental fix is to make the layout contract explicit in code first, then mechanically move/normalize only what the contract can verify. The high-risk part is not deleting files; it is preserving runtime module imports such as `astrid.packs.<pack>.executors.<name>.run` and helper imports under executor/orchestrator directories.

**Critical architectural constraint:** `astrid/core/pack.py` already exists as a 1171-line module (`PackDefinition`, `discover_packs`, manifest constants, etc.) imported by 46+ call sites. Creating `astrid/core/pack/` as a package would collide with this module. Machinery relocation uses the **new** package name `astrid/core/pack_machinery/` instead, leaving the existing `astrid/core/pack.py` untouched.

**Deferred to M2:** `_canonical_entrypoint.py` has 50+ import sites across pack `run.py` files plus `astrid/core/runtime/in_process.py` and test files. Updating all of those in M1 carries disproportionate regression risk. It stays in `astrid/packs/` for M1 as a documented, validated machinery exception and will be relocated in M2.

## Phase 1: Inventory and Contract Shape

### Step 1: Add a current-state layout inventory test/report (`tests/test_pack_layout_contract.py`)
**Scope:** Medium  
**Complexity: 2**
1. Inventory first-party entries under `astrid/packs/` into categories: pack manifests (19 `pack.yaml` files across media, foley, generation, video_editing, runpod, builtin, moirae, youtube, understanding, fal, iteration, vibecomfy, text_analysis, stream_content, rendering, comfy_wrap, editorial, training, reigh), special skill docs (`_core`), pack-system machinery files, schemas, generated/cache artifacts (`__pycache__/`, `builtin/build/agent_probe.json`), root docs (`media/AGENTS.md`, `media/README.md`, `media/STAGE.md`), root Python files (`builtin/agent_probe.py`, `video_editing/hype.py`, `text_analysis/summarize.py`), and package marker files (`__init__.py`).
2. Add a focused test that fails with a readable list of current non-canonical entries but can be initially written against an explicit allowlist so the migration can proceed stepwise.
3. **Build the import inventory from BOTH static Python imports AND YAML manifest parsing.** Grep for `from astrid.packs.<pack>... import ...` in all `.py` files AND parse every `executor.yaml`/`orchestrator.yaml` for `runtime_module`/`callable_module` fields (resolved via `importlib.import_module()` in `pack_resolver.py`). The combined inventory is the precondition for safe `__init__.py` removal in Step 11.

### Step 2: Define canonical layout metadata and exception model (`astrid/packs/validate.py` new helper)
**Scope:** Medium  
**Complexity: 3**
1. Add a small structured layout-contract helper that knows canonical pack entries:
   - `pack.yaml` (required)
   - Optional `skill/SKILL.md` (pack-level agent-facing docs)
   - `executors/<name>/{executor.yaml, run.py}`, optional `STAGE.md`, optional `skill/SKILL.md` (component-level skill docs already exist in `generation/executors/generate_image/skill/SKILL.md`)
   - `orchestrators/<name>/{orchestrator.yaml, run.py}`, optional `STAGE.md`, optional `skill/SKILL.md`
   - Optional `fixtures/`, `golden/`, `elements/`
   - Ignored generated `build/` (unless explicitly `golden/`)
2. Add an explicit exception declaration format in `pack.yaml` under `metadata.docs`-like fields. It should record path, reason, class, and **lifecycle** (`defer_to: M1 | M2 | permanent`). Classes: `importable_component_code`, `legacy_public_shim`, `dsl_orchestrator_shim`, `domain_exception`, `generated_ignored`, `machinery_shim`, `skill_only_shell`.
3. Keep the validator output agent-friendly: one top-level "pack layout contract failed" style surface with detailed per-path schema/layout errors underneath.

## Phase 2: Normalize Docs and Scaffolds (BEFORE machinery moves)

### Step 3: Make `skill/SKILL.md` the pack-facing docs convention and downgrade root doc requirements
**Scope:** Medium  
**Complexity: 3**
1. Update `astrid/packs/validate.py` in **both** code paths:
   - `_validate_pack` (lines 226–232): Change AGENTS.md/README.md from warning to silent (or remove the check). Add optional `skill/SKILL.md` check as info-level instead.
   - `extract_trust_summary` (lines 999–1001): Remove the duplicate AGENTS.md/README.md warning.
2. Downgrade component-level `STAGE.md` requirement from ERROR to WARNING (lines 562–565): keep it as an allowed authoring aid but do not reject packs that lack it.
3. Update docs files that encode root-docs convention:
   - `docs/creating-packs.md` (lines 36–56): Replace root `AGENTS.md`/`README.md`/`STAGE.md` with `skill/SKILL.md` in the canonical layout diagram.
   - `docs/personal-packs.md` (line 18): Replace root docs listing with `skill/SKILL.md`.
   - `docs/architecture/repo-shape.md` (lines 177–181): Replace `AGENTS.md` with `skill/SKILL.md`.
   - `docs/git-backed-packs-plan.md` (lines 45–50): Replace root docs in example layout.
   - `docs/architecture/pack-layout-variants.json`: Update pack descriptions after normalization (deferred to Step 14).
4. Migrate `media` pack: Read `media/AGENTS.md` content, create `media/skill/SKILL.md` with that content, remove root `AGENTS.md`, `README.md`, and `STAGE.md`. The `media` pack is the **only** first-party pack with root docs — all other packs either already have `skill/SKILL.md` (foley, generation, understanding, video_editing, reigh, stream_content, editorial, rendering) or lack pack-level docs entirely.

### Step 4: Normalize scaffold output (`astrid/packs/cli.py`, tests)
**Scope:** Medium  
**Complexity: 3**
1. Update `packs new`, `executors new`, and `orchestrators new` templates to emit the canonical physical tree with `skill/SKILL.md` instead of root `AGENTS.md`/`README.md`/`STAGE.md`.
2. Ensure new packs do not create empty content roots unless the manifest declares them intentionally.
3. Adjust `tests/test_packs_cli.py`, `tests/test_packs_validate.py`, and related tests to match the selected canonical docs/layout convention.

## Phase 3: Move Pack-System Machinery in Stages

### Step 5: Move `gitignore.py` and prepare `_canonical_entrypoint.py` exception (`astrid/core/pack_machinery/`)
**Scope:** Small  
**Complexity: 2**
1. Create `astrid/core/pack_machinery/` package with `__init__.py`.
2. Move `astrid/packs/gitignore.py` → `astrid/core/pack_machinery/gitignore.py`.
3. Update `astrid/packs/install.py` (line 35) to import from new location: `from astrid.core.pack.gitignore import gitignore_filter`.
4. Leave `astrid/packs/_canonical_entrypoint.py` **in place** for M1. Document it as an M2-deferred machinery exception in the layout contract (class: `machinery_shim`, `defer_to: M2`). This avoids updating 50+ pack `run.py` import sites, `astrid/core/runtime/in_process.py`, `tests/test_canonical_entrypoint.py`, and `tests/core/runtime/test_in_process.py` in M1.
5. Leave thin compatibility shim at `astrid/packs/gitignore.py` that re-exports from `astrid.core.pack.gitignore`.

### Step 6: Move `validate.py` and `agent_index.py` (`astrid/core/pack_machinery/`)
**Scope:** Medium  
**Complexity: 3**
1. Move `astrid/packs/validate.py` (1046 lines) → `astrid/core/pack_machinery/validate.py`.
2. Move `astrid/packs/agent_index.py` (498 lines) → `astrid/core/pack_machinery/agent_index.py`.
3. Update internal references in `cli.py` and `install.py` that import from `validate` and `agent_index`.
4. Leave thin compatibility shims at `astrid/packs/validate.py` and `astrid/packs/agent_index.py` that re-export from the new location.
5. Update `astrid/gateway.py` (line 398: `from .packs import cli as packs_cli`) — keep pointing at the shim, which still works.

### Step 7: Move `cli.py` and `install.py` (`astrid/core/pack_machinery/`)
**Scope:** Medium  
**Complexity: 3**
1. Move `astrid/packs/cli.py` (1761 lines) → `astrid/core/pack_machinery/cli.py`.
2. Move `astrid/packs/install.py` (1930 lines) → `astrid/core/pack_machinery/install.py`.
3. Update `astrid/gateway.py` imports (lines 398–400 and 1089) to use the new machinery path: `from astrid.core.pack import cli as packs_cli` and `from astrid.core.pack.cli import build_parser`.
4. Leave thin compatibility shims at `astrid/packs/cli.py` and `astrid/packs/install.py`.

## Phase 4: Relocate Schemas

### Step 8: Move schemas to machinery home (`astrid/packs/schemas/v1/` → `astrid/core/pack_machinery/schemas/v1/`)
**Scope:** Medium  
**Complexity: 3**
1. Move `astrid/packs/schemas/v1/` → `astrid/core/pack_machinery/schemas/v1/`.
2. Update `KNOWN_SCHEMA_VERSIONS` and schema resolution paths in `validate.py` (now in `pack_machinery/`) plus direct docs references in `docs/creating-packs.md`.
3. Update `docs/architecture/pack-layout-variants.json` to reflect schemas classification change.
4. If moving proves too disruptive, document `schemas` as a public contract exception in the layout contract and add validator coverage. Preference is to move.

## Phase 5: Clean Generated Artifacts

### Step 9: Remove generated and cache artifacts from the pack tree
**Scope:** Small  
**Complexity: 1**
1. Remove all `__pycache__/` directories and `.pyc` files from `astrid/packs/` (found in foley, media, vibecomfy, and other packs).
2. Remove `builtin/build/agent_probe.json` — a generated build artifact, not source.
3. Verify `.gitignore` already ignores `__pycache__/`, `.DS_Store`, and `astrid/packs/*/build/`.
4. Add/strengthen a hygiene test in `tests/test_pack_layout_contract.py` (from Step 1) so generated artifacts and `.DS_Store` cannot re-enter first-party packs.

## Phase 6: Classify and Handle Root Python Shims

### Step 10: Classify and handle root pack Python shims (`builtin/agent_probe.py`, `video_editing/hype.py`, `text_analysis/summarize.py`)
**Scope:** Medium  
**Complexity: 4**
1. **`builtin/agent_probe.py`**: This is a DSL `@orchestrator("builtin.agent_probe")` definition, NOT an executor. The `builtin` pack is already deprecated (`pack.yaml` says `status: deprecated`). Classify as `dsl_orchestrator_shim` with `defer_to: M2` — keep as-is for M1. It supports legacy regression tests (16 test files reference `builtin.agent_probe`).
2. **`video_editing/hype.py`**: This is a legacy author-test DSL shim that duplicates `video_editing.hype` (already canonically at `orchestrators/hype/run.py`, a 1472-line stage-based orchestrator). The `pack.yaml` already declares aliases from `builtin.hype → video_editing.hype`. Classify as `legacy_public_shim` with `defer_to: M2`. Remove the root shim file in M2 once all callers use the canonical path. For M1, document as exception and keep.
3. **`text_analysis/summarize.py`**: This is a DSL `@orchestrator("text_analysis.summarize")` — NOT an executor. Migrate it to `orchestrators/summarize/run.py` (not `executors/`). Fix the hardcoded absolute path on line 30 (`/Users/peteromalley/Documents/reigh-workspace/Astrid/astrid/packs/text_analysis/sample.txt`) to use a pack-relative path. Update `pack.yaml` to create the `orchestrators/` directory on disk (currently declared but absent) and ensure `content.orchestrators: orchestrators` points at it. The `content.executors: executors` declaration can remain as a forward declaration or be removed if empty.
4. Preserve old capability IDs and add alias/characterization tests for `text_analysis.summarize` after the move.

## Phase 7: Handle `__init__.py` Files

### Step 11: Remove pack-root and data-only `__init__.py` files conservatively
**Scope:** Medium  
**Complexity: 4**
1. Use the combined import inventory from Step 1 (static Python imports + YAML manifest `runtime_module`/`callable_module` parsing) as the precondition.
2. Remove pack-root `__init__.py` files that have no import dependency after the inventory check (e.g., `media/__init__.py` if unused).
3. Keep `__init__.py` files under importable executor/orchestrator helper packages where relative imports or tests require package semantics (e.g., `training/orchestrators/training_run/trainer_adapters/__init__.py`, `runpod/executors/session/__init__.py`).
4. **Remove `_core/__init__.py`** (empty, 0 bytes): `_core` is skill documentation only, not importable code.
5. Add compatibility/import tests for required module paths before and after cleanup, especially paths used by `runtime_module`, `callable_module`, and direct tests. The inventory must cover **relative imports within component directories** (e.g., `from .trainer_adapters import ...`), not just `astrid.packs.<pack>...` patterns.

## Phase 8: Classify Special Directories

### Step 12: Classify special non-manifest directories (`_core`, `external`, absent shell packs, `schemas`)
**Scope:** Small  
**Complexity: 2**
1. Treat `_core` as skill documentation/special agent surface, not normal pack data. Document that exception in the layout contract with class `skill_only_shell`.
2. Verify whether any `external` or referenced-but-absent shell pack IDs are still expected by discovery or tests; preserve behavior with explicit shell directories or remove stale references.
3. Add tests proving pack discovery, skill discovery, and shipped pack IDs remain stable after these classifications.
4. After Step 8 (schema relocation), verify no remaining `schemas/` directory under `astrid/packs/` — or document why it remains.

## Phase 9: Validation and Discovery Hardening

### Step 13: Enforce layout validation across all first-party packs
**Scope:** Large  
**Complexity: 3**
1. Turn the layout inventory from Step 1 into a hard validation path for first-party packs. The 19 packs with `pack.yaml` are: media, foley, generation, video_editing, runpod, builtin, moirae, youtube, understanding, fal, iteration, vibecomfy, text_analysis, stream_content, rendering, comfy_wrap, editorial, training, reigh.
2. Keep schema validation and layout validation separate internally, but present a single friendly failure surface through `packs validate`.
3. Split enforcement into two sub-passes: (a) mechanical allowlist expansion for all 19 packs (most already conform after earlier steps), (b) per-pack content normalization for any remaining drift.
4. Update `docs/architecture/pack-layout-variants.json` to reflect the normalized state.

### Step 14: Preserve capability discovery and runtime execution behavior
**Scope:** Medium  
**Complexity: 3**
1. Run and update tests around shipped IDs, pack discovery (`tests/test_pack_discovery.py`, `tests/test_pack_discovery_canonical.py`, `tests/test_pack_discovery_metadata.py`, `tests/test_packs_shipped_ids.py`), executor/orchestrator registries, alias resolution, skills sync (`tests/test_skills_sync_registry.py`), and representative pack execution.
2. Add targeted characterization for old IDs/imports that remain as aliases after root shim migration (e.g., `text_analysis.summarize`).
3. Ensure no executor/orchestrator behavior changes beyond file placement and metadata references.
4. Verify `tests/packs/test_portfolio_parity.py` covers all packs.

## Execution Order
1. Build inventory and exception model (Steps 1–2) before deleting or moving files.
2. Normalize docs/scaffolds in the existing code locations (Steps 3–4) BEFORE moving machinery, to avoid merge conflicts with `validate.py` and `cli.py`.
3. Move machinery in stages: gitignore first (Step 5), then validate + agent_index (Step 6), then cli + install (Step 7). Each stage includes compatibility shims.
4. Relocate schemas (Step 8).
5. Remove generated artifacts (Step 9).
6. Classify and handle root Python shims (Step 10).
7. Clean `__init__.py` files only after import inventory and compatibility tests exist (Step 11).
8. Classify special directories (Step 12).
9. Expand validation to hard-gated all-pack enforcement and update catalog (Step 13).
10. Final verification of discovery and execution (Step 14).

## Validation Order
1. Cheap inventory checks: `find astrid/packs -name __pycache__ -o -name .DS_Store`, `find astrid/packs -maxdepth 1`, and targeted import inventory tests from Step 1.
2. Focused tests: `pytest tests/test_pack_layout_contract.py tests/test_packs_validate.py tests/test_packs_cli.py tests/test_pack_discovery.py tests/test_packs_shipped_ids.py tests/packs/test_portfolio_parity.py`.
3. Runtime/import checks: `pytest tests/test_pack_resolver.py tests/core/test_pack_resolver.py tests/test_pack_run_cli_choices.py tests/test_skills_sync_registry.py`.
4. Broader pack execution and authoring checks after fleet moves: representative executor/orchestrator tests already importing pack modules.
5. Final gate: full test suite if practical, `python3 -m astrid packs validate <pack>` for every first-party `pack.yaml`, and `git status --short` clean.

## Ticket Link Proposal
No listed open ticket directly matches pack layout normalization. I would not propose `resolves_on_complete=true` links for the provided ticket list unless the owner wants to attach this milestone to broader repo-shape cleanup work.
