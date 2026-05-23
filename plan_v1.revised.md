# Implementation Plan: Milestone 4 — Forks, Overrides, And Agent Updates

## Overview

Extend the existing element-only fork mechanism to executors and orchestrators. Add provenance fields (`forked_from`, `upstream_version`, `compatibility_token`) to `Provenance` and `CapabilityHandle`. Add dirty-edit detection via git status. Build a minimal update workflow that compares local vs upstream, flags safety/cost/permission escalations, and produces auditable reports. Wire new CLI commands (`fork`, `override`, `dirty`, `update`) across all three capability types.

**Key constraint**: Do not break existing `astrid elements fork <kind> <id>` behavior. Do not silently overwrite local user edits. Tests use local fixture packs only and create the `tests/` directory (which does not yet exist in the project).

**Current state**:
- `ElementRegistry.fork()` works: copies element tree into `astrid/packs/local/elements/<kind>/<id>`, calls `ensure_local_pack()` and `_rewrite_pack_id()`. The `local` pack gets priority=10 vs 30 for other packs in `load_pack_elements()`.
- `ElementRegistry` stores all definitions in a list-per-key model sorted by priority — `get()` returns the first element (highest priority). This is the pattern to mirror for executors/orchestrators.
- `ExecutorRegistry` and `OrchestratorRegistry` reject duplicates with errors (no shadowing). No fork methods.
- `load_pack_executors()` and `load_pack_orchestrators()` call `discover_packs()` without arguments (source-tree only). They accept no `project_root` parameter, so there is no local-pack discovery.
- `load_default_registry()` (both executor and orchestrator) does not pass `project_root` down.
- `Provenance` has `source`, `pack_id`, `manifest_path`, `content_root`, `resolved_alias` — no fork fields.
- `CapabilityHandle` has identity/safety fields but no `local_edit_state` or `override_target`.
- `to_capability_handle()` in both `executor/schema.py:196-229` and `orchestrator/schema.py:87-120` constructs `Provenance(source=provenance_source)` with only the `source` argument.
- No git utility module, no dirty detection, no update workflow.

---

## Phase 1: Schema & Foundation

### Step 1: Add provenance fields and update schema adapters
**Complexity: 2** — Multi-file but additive and backward-compatible.

1. **Add fields to `contracts/schema.py`**:
   - Add `forked_from: str = ""`, `upstream_version: str = ""`, `compatibility_token: str = ""` to `Provenance` dataclass (~line 77-86). All default to empty string, preserving backward compatibility.
   - Add `local_edit_state: str = "clean"` and `override_target: str = ""` to `CapabilityHandle` dataclass (~line 109-136).
   - Add `LocalEditState = Literal["clean", "dirty", "conflict"]` type alias alongside existing `PortType`, `OutputMode` etc.
2. **Update `executor/schema.py` — `to_capability_handle()`** (line 196-229):
   - Read `forked_from`, `upstream_version`, `compatibility_token` from `definition.metadata` (if present).
   - Pass them to the `Provenance(...)` constructor.
   - Read `local_edit_state` and `override_target` from `definition.metadata` (if present) and pass to `CapabilityHandle(...)`.
3. **Update `orchestrator/schema.py` — `to_capability_handle()`** (line 87-120):
   - Mirror the executor changes exactly: read fork/provenance fields and edit-state/override from `definition.metadata`, pass to constructors.
4. **Population contract** (implemented in later phases but specified here):
   - `local_edit_state` is populated by `detect_local_edits()` (Phase 1, Step 3) and set on `CapabilityHandle` via `replace()` after construction, or passed through metadata.
   - `override_target` is set on the `CapabilityHandle` when `OverrideStore.resolve()` triggers in the registry's `get()` method (Phase 3, Step 7). The registry wraps the definition with updated metadata before calling `to_capability_handle()`.

### Step 2: Create shared git utility module (`astrid/core/git_util.py`)
**Complexity: 2** — New file; needs git-in-worktree detection.

1. Create `astrid/core/git_util.py` with:
   - `is_git_worktree(path: Path) -> bool` — walk up to find `.git` (file or dir).
   - `git_status(path: Path) -> dict[str, Any]` — run `git status --porcelain`, parse into structured dict with `dirty` bool and per-file status entries. Raise `GitUtilError` if not in a worktree.
   - `git_diff_file(path: Path, against: str = "HEAD") -> str | None` — run `git diff` for a single file, return diff text or None.
   - `git_root(path: Path) -> Path` — return the worktree root.
2. All git calls use `subprocess.run` with `capture_output=True`, no shell, timeout of 10s. Never modify the repo.

### Step 3: Create dirty-detection module (`astrid/core/dirty.py`)
**Complexity: 2** — New file; compares local files against forked origin.

1. Create `astrid/core/dirty.py` with:
   - `detect_local_edits(capability_root: Path, *, forked_from: str | None = None) -> str` — returns `"clean"`, `"dirty"`, or `"conflict"`.
     - If `forked_from` is empty, return `"clean"`.
     - Try `git_util.git_status(capability_root)` first.
     - If not in a git worktree, fall back to `.astrid_fork_state.json` hash comparison.
   - `write_fork_state(capability_root: Path, forked_from: str, upstream_version: str, file_hashes: dict[str, str]) -> None`.
   - `read_fork_state(capability_root: Path) -> dict[str, Any] | None`.

---

## Phase 2: Fork — Executors & Orchestrators

### Step 4: Extend `ExecutorRegistry` with fork, priority-based shadowing, and project-root awareness
**Complexity: 4** — Multi-file: registry, loader, CLI, and call-chain threading.

1. **`astrid/core/executor/registry.py` — `ExecutorRegistry`**:
   - Change storage from `dict[str, ExecutorDefinition]` to `dict[str, list[ExecutorDefinition]]` (mirroring `ElementRegistry._all`). Each registered definition is stored in a per-ID list.
   - Modify `register()` to ALWAYS append to the list for the ID, then sort by `priority` (from definition metadata, default 30). Never reject on duplicate ID — priority-based resolution replaces duplicate rejection.
   - Modify `get()` to return the first element in the list (highest priority).
   - Add `fork(self, executor_id: str, *, project_root: Path, overwrite: bool = False, deep: bool = False) -> Path`:
     - Resolve executor via `self.get(executor_id)`.
     - Compute target: `<project_root>/astrid/packs/local/executors/<local_id>` (local_id is the part after the dot).
     - Call `ensure_local_pack(project_root=project_root)` (imported from `astrid.core.pack`).
     - Copy the executor's root folder tree to target.
     - Rewrite the manifest's `id` field to `local.<local_id>` and `pack_id` in metadata.
     - Write `forked_from`, `upstream_version`, file hashes to `.astrid_fork_state.json`.
     - If `deep=True`, recursively fork all `depends_on` executors.
2. **`astrid/core/executor/registry.py` — `load_pack_executors()`**:
   - Add `project_root: str | Path` parameter (default `REPO_ROOT` from `astrid._paths`).
   - Mirror `load_pack_elements()` logic: discover source-tree packs (excluding `local`), then conditionally discover project-scoped `local` pack when `project_pack_root != repo_pack_root`.
   - Local pack entries get `priority=10` in metadata; non-local get `priority=30`.
3. **`astrid/core/executor/registry.py` — `load_default_registry()`**:
   - Add `project_root: str | Path = REPO_ROOT` parameter.
   - Pass `project_root` to `load_pack_executors(project_root=project_root)`.
4. **`astrid/core/executor/cli.py` — `main()`**:
   - Add `project_root` acceptance and pass to `load_default_registry(project_root=project_root)`.
   - Default to `Path.cwd()` when not in a megaplan harness, or accept via `--project-root` flag.
5. **`astrid/core/executor/schema.py` — `to_capability_handle()`** (updated in Step 1.2).

### Step 5: Extend `OrchestratorRegistry` with fork, priority-based shadowing, and project-root awareness
**Complexity: 4** — Same pattern as Step 4, applied to orchestrators.

1. **`astrid/core/orchestrator/registry.py` — `OrchestratorRegistry`**:
   - Mirror executor changes: list-per-ID storage, priority-based `register()` (no rejection), priority-sorted `get()`.
   - Add `fork(self, orchestrator_id: str, *, project_root: Path, overwrite: bool = False, deep: bool = False) -> Path`:
     - Compute target: `<project_root>/astrid/packs/local/orchestrators/<local_id>`.
     - Copy orchestrator root folder tree, rewrite manifest.
     - If `deep=True`, resolve `child_executors` and `child_orchestrators` transitively (requires access to both registries).
2. **`load_pack_orchestrators()`**:
   - Add `project_root: str | Path` parameter. Mirror executor local-pack discovery.
3. **`load_default_registry()`**:
   - Add `project_root: str | Path = REPO_ROOT` parameter. Pass to `load_pack_orchestrators()`.
4. **`astrid/core/orchestrator/cli.py` — `main()`**:
   - Thread `project_root` through `load_default_registry()`.

### Step 6: Move `ensure_local_pack` to shared location
**Complexity: 1** — Relocate function and update all importers.

1. Add `ensure_local_pack()` to `astrid/core/pack.py` (after `packs_root()` around line 65):
   ```python
   def ensure_local_pack(*, project_root: str | Path) -> Path:
       pack_root = Path(project_root) / "astrid" / "packs" / "local"
       pack_root.mkdir(parents=True, exist_ok=True)
       manifest = pack_root / "pack.yaml"
       if not manifest.exists():
           manifest.write_text("id: local\nname: Local Scratch Pack\nversion: 0.1.0\n", encoding="utf-8")
       return pack_root
   ```
2. Update `astrid/core/element/registry.py`:
   - Remove the local `ensure_local_pack()` definition (lines 186-192).
   - Add import: `from astrid.core.pack import discover_packs, ensure_local_pack, iter_element_roots, validate_element_pack_id` (modifying the existing import on line 20).
   - The internal call at line 104 (`ensure_local_pack(project_root=project_root)`) now resolves to the shared function.
3. Update `astrid/core/executor/registry.py`:
   - Add import: `from astrid.core.pack import discover_packs, ensure_local_pack, iter_executor_roots, validate_content_id_in_pack` (modifying line 15).
4. Update `astrid/core/orchestrator/registry.py`:
   - Add import: `from astrid.core.pack import discover_packs, ensure_local_pack, iter_orchestrator_roots, validate_content_id_in_pack` (modifying line 16).
5. No external test files or other modules import `ensure_local_pack` from element/registry (confirmed by repo-wide search). The only callers are the three registries' `fork()` methods.

---

## Phase 3: Override Declarations

### Step 7: Add override infrastructure
**Complexity: 2** — Registry-level override store + CLI visibility + handle population.

1. **New module `astrid/core/override.py`**:
   - `OverrideStore` class: thread-safe in-memory dict mapping `capability_type/canonical_id → override_target_canonical_id`. Persisted to `<project_root>/astrid/packs/local/.overrides.json`.
   - `set_override(capability_type: str, canonical_id: str, target: str) -> None`.
   - `remove_override(capability_type: str, canonical_id: str) -> None`.
   - `resolve(capability_type: str, canonical_id: str) -> str | None`.
   - `list_overrides() -> list[dict]`.
2. **Wire into all three registries** (`ElementRegistry`, `ExecutorRegistry`, `OrchestratorRegistry`):
   - Accept optional `override_store: OverrideStore | None` parameter.
   - In `get()`, after resolving the highest-priority definition, check `override_store.resolve()`. If an override exists, retrieve the target capability, then set `override_target` on the returned capability's metadata so `to_capability_handle()` populates the field.
   - Specifically: `definition.metadata["override_target"] = target_id` before passing through `to_capability_handle()`.
3. **Add `--show-overrides` flag** to list/inspect commands across all three CLI modules. When set, the output annotates overridden capabilities with their override target.

---

## Phase 4: CLI Commands

### Step 8: Add `fork` subcommand to executor and orchestrator CLIs
**Complexity: 2** — CLI parser entries + handler functions.

1. **`astrid/core/executor/cli.py`**:
   - Add `fork` subparser: `parser.add_parser("fork")`, with positional `executor_id`, `--overwrite` flag, `--deep` flag.
   - Handler `_cmd_fork(args, registry)` calls `registry.fork(args.executor_id, project_root=..., overwrite=..., deep=...)`.
2. **`astrid/core/orchestrator/cli.py`**:
   - Mirror: add `fork` subparser and handler.
3. **`astrid/pipeline.py`**:
   - Update help text: mention fork in executors/orchestrators help strings.

### Step 9: Add `override`, `dirty`, and `update` CLI subcommands
**Complexity: 3** — New CLI commands across elements, executors, orchestrators.

1. **Override commands** (add to all three CLI modules):
   - `override set <capability_id> --target <target_id>`
   - `override remove <capability_id>`
   - `override list [--json]`
2. **Dirty check**:
   - `dirty <capability_id>` — prints `clean`, `dirty`, or `conflict` plus list of modified files. Uses `detect_local_edits()`.
   - `dirty list [--json]` — list all forked capabilities with their edit state.
3. **Update workflow** (new module `astrid/core/update.py`):
   - `update check <capability_id>` — compare local fork against upstream:
     - Diff metadata fields (version, description, keywords, inputs, outputs, isolation, safety).
     - Flag escalations: `network: false → true`, new `secrets_required`, new `permissions`, new binaries.
     - Print report: local changes, upstream changes, safety/cost deltas.
   - `update apply <capability_id> [--force] [--skip-safety]` — apply upstream changes that are deemed safe (no escalations) or force-apply all. Write report to `<capability_root>/.astrid_update_report.json`.
   - Deterministic: no real LLM calls, no network.
4. Wire `update check` and `update apply` into all three CLIs.

---

## Phase 5: Tests

### Step 10: Write comprehensive tests with fixture packs
**Complexity: 3** — Create `tests/` directory and populate with test files.

**Note**: The project currently has no `tests/` directory and no test files. This phase creates them.

1. Create `tests/` directory with `__init__.py` and `conftest.py` (pytest fixtures for tempdir-based pack scaffolding).
2. **`tests/test_fork_executor_orchestrator.py`**:
   - Use `tempfile.TemporaryDirectory` to create fixture packs.
   - Test shallow fork: fork one executor, verify target exists, manifest rewritten, `.astrid_fork_state.json` written.
   - Test deep fork: executor with `depends_on`, verify transitive closure.
   - Test overwrite flag.
   - Test that original element fork still works (`ElementRegistry.fork()` unchanged).
   - Test priority-based shadowing: register a non-local executor at priority=30, then register a local executor at priority=10 with the same ID; verify `get()` returns the local one.
   - Test reverse registration order: local registered first at priority=10, non-local second at priority=30; verify local still wins.
3. **`tests/test_dirty_detection.py`**:
   - Create forked fixture, verify initial state is `clean`.
   - Modify a manifest file, verify `detect_local_edits()` returns `dirty`.
   - Test fallback hash-based detection when not in git worktree.
4. **`tests/test_override.py`**:
   - Set override, verify `get()` returns overridden target with `override_target` field populated.
   - Remove override, verify original returns.
   - List overrides.
   - Test override persistence (`.overrides.json`).
5. **`tests/test_update_report.py`**:
   - Create fixture packs simulating "upstream" and "local fork".
   - Test `update check`: verify report flags version bump, description change.
   - Test safety escalation detection: upstream adds `network: true`, `secrets_required`, new permissions.
   - Test `update apply`: verify safe changes are applied, unsafe ones are blocked without `--skip-safety`.
   - Test that report is written to `.astrid_update_report.json`.
6. **`tests/test_pack_local_priority.py`**:
   - Verify that local pack executors/orchestrators get priority=10 (shadow non-local packs at priority=30).
   - Verify that both registration orders (local-first or local-second) result in local winning.

---

## Execution Order

1. **Phase 1 first** (Steps 1–3): Schema changes, `to_capability_handle()` updates, and git/dirty utilities must land before anything depends on them.
2. **Step 6 immediately after Phase 1**: Moving `ensure_local_pack` to `pack.py` is a prerequisite for the fork methods in Steps 4–5.
3. **Phase 2** (Steps 4–5): Fork for executors/orchestrators depends on Phase 1 and Step 6.
4. **Phase 3** (Step 7): Overrides build on the priority-based model from Phase 2.
5. **Phase 4** (Steps 8–9): CLI wiring comes after registry work is stable.
6. **Phase 5** (Step 10): Tests written last to exercise all features end-to-end.

---

## Validation Order

1. After Phase 1–Step 6: Verify schema imports still work:
   ```bash
   python -c "from astrid.contracts.schema import Provenance, CapabilityHandle, LocalEditState; print('OK')"
   python -c "from astrid.core.git_util import is_git_worktree, git_status; print('OK')"
   python -c "from astrid.core.pack import ensure_local_pack; print('OK')"
   ```
2. After Phase 2: Verify existing element fork still works:
   ```bash
   python -m astrid elements fork effects text-card
   ```
3. After Phase 4: Smoke-test CLI registration:
   ```bash
   python -m astrid executors fork --help
   python -m astrid orchestrators fork --help
   python -m astrid executors override --help
   python -m astrid executors dirty --help
   ```
4. After Phase 5: Run the full test suite:
   ```bash
   python -m pytest tests/ -xvs
   ```
5. Final verification: `python -m astrid elements fork effects text-card` must still work unchanged.
