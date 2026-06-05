# Implementation Plan: Formalization Quick-Wins — Bug Batch + Cheap Contracts

## Overview

Seven small, independent formalization fixes from the 2026-06-04 contracts audit land as one coherent commit series on the milestone branch. The changes are additive to public APIs and follow the house fix-pattern: invariant → choke point → conformance test. The env-vars catalog (item 2) lands first because items 1 and 6 reference its canonical constants.

**Branch strategy**: All work on a single milestone branch off `main`. Commit order follows the step order below.

---

## Phase 1: Foundation — Env-Var Catalog (Item 2)

### Step 1: Create `astrid/core/env_vars.py`
**Scope**: Medium — new module cataloging every `ASTRID_*` constant in the codebase
**Complexity: 3**

1. **Create** `astrid/core/env_vars.py` owning every `ASTRID_*` constant with docstrings per var: who sets, who reads, effect.

   **Migrate from `subprocess_env.py`** (delete local definitions after migration):
   - `ASTRID_HOME_ENV = "ASTRID_HOME"` (also defined in `session/paths.py:12`)
   - `ASTRID_SESSION_ID_ENV = "ASTRID_SESSION_ID"` (also defined in `session/binding.py:21`)
   - `ASTRID_ACTOR = "ASTRID_ACTOR"`
   - `ASTRID_INTERNAL_INVOCATION = "ASTRID_INTERNAL_INVOCATION"`
   - `PROJECTS_ROOT_ENV = "ASTRID_PROJECTS_ROOT"`
   - `PROJECT_RUN_ENV = "ASTRID_PROJECT_RUN"`
   - `TASK_RUN_ID_ENV = "ASTRID_TASK_RUN_ID"`
   - `TASK_PROJECT_ENV = "ASTRID_TASK_PROJECT"`
   - `TASK_STEP_ID_ENV = "ASTRID_TASK_STEP_ID"`
   - `TASK_ITEM_ID_ENV = "ASTRID_TASK_ITEM_ID"`
   - `TASK_ITERATION_ENV = "ASTRID_TASK_ITERATION"`

   **Fix** `ASTRID_AUTHOR_TEST`: correct value to `"ASTRID_AUTHOR_TEST"` (currently `"ASTRID...TEST"` at `subprocess_env.py:19`).

   **Add backward-compat** for the old broken name:
   - `ASTRID_AUTHOR_TEST_LEGACY = "ASTRID...TEST"`
   - `get_author_test_env()` helper that reads both (new name first, legacy as fallback with `warnings.warn`).

   **Add constant for bare literal** in `skills/state.py:22`:
   - `ASTRID_STATE_HOME = "ASTRID_STATE_HOME"`

   **Add constants for bare-string-only sites** in core/ modules (currently referenced as string literals, no constant exists):
   - `ASTRID_STRICT_INSTRUCTION_SUBST = "ASTRID_STRICT_INSTRUCTION_SUBST"` (used at `core/task/operator_view.py:292`)
   - `ASTRID_BANODOCO_CATALOG_URL = "ASTRID_BANODOCO_CATALOG_URL"` (used at `core/executor/banodoco_catalog.py:37`)
   - `ASTRID_AGENT_VERSION = "ASTRID_AGENT_VERSION"` (used at `threads/record.py:200` — constant defined in catalog but threads/ files are contract-locked, NOT modified)
   - `ASTRID_REPO_ROOT = "ASTRID_REPO_ROOT"` (used at `threads/cli.py:220` — same, constant defined but threads/ NOT modified)
   - `ASTRID_AUDIT_DISABLED = "ASTRID_AUDIT_DISABLED"` (used at `audit/context.py:39` — constant defined but audit/ NOT modified)
   - `ASTRID_AUDIT_RUN_DIR = "ASTRID_AUDIT_RUN_DIR"` (used at `audit/context.py:41` — same)

2. **Update** `subprocess_env.py` to import constants from `env_vars.py` and re-export them. Delete all 11 local constant definitions. Keep `_SAFE_BASE_ENV`, `_ASTRID_PROPAGATED_ENV`, `build_child_subprocess_env`, and `SubprocessEnvPolicyError` — they reference the constants by name.

3. **Update** `session/paths.py` to import `ASTRID_HOME_ENV` from `env_vars.py` instead of defining locally (delete line 12).

4. **Update** `session/binding.py` to import `ASTRID_SESSION_ID_ENV` from `env_vars.py` instead of defining locally (delete line 21).

5. **Update** `skills/state.py:22` to use `ASTRID_STATE_HOME` constant instead of bare literal `"ASTRID_STATE_HOME"`.

6. **Update** `core/task/env.py`: change imports from `astrid.core.subprocess_env` to `astrid.core.env_vars`. Update `is_author_test_mode()` to use `get_author_test_env()` (reading both old and new names).

7. **Update** `core/task/operator_view.py:292` to import and use `ASTRID_STRICT_INSTRUCTION_SUBST` from `env_vars.py`.

8. **Update** `core/executor/banodoco_catalog.py:37` to import and use `ASTRID_BANODOCO_CATALOG_URL` from `env_vars.py`.

9. **Update** `core/executor/runner.py:246` to import and use `ASTRID_INTERNAL_INVOCATION` from `env_vars.py`.

10. **Update** `core/project/run.py:144` to import and use `ASTRID_SESSION_ID_ENV` from `env_vars.py` instead of bare string `"ASTRID_SESSION_ID"`.

11. **Update** `core/task/session_discovery.py:113` to import and use `ASTRID_SESSION_ID_ENV` from `env_vars.py`.

12. **Update** `core/task/hook.py:46` to import and use `TASK_PROJECT_ENV` from `env_vars.py`.

13. **Update** `orchestrate/test_runner.py` imports (currently imports ASTRID_AUTHOR_TEST from subprocess_env at line 27) to import from `env_vars.py`. Line 183 already writes `os.environ[ASTRID_AUTHOR_TEST] = "1"` — now sets the correct key.

14. **Do NOT touch** `astrid/threads/` (contract-locked per idea), `astrid/audit/` (separate concern), or `astrid/packs/` (executor run.py files that don't import astrid core). The constants for their env vars are defined in the catalog for documentation purposes only.

### Step 2: Write `docs/env-vars.md`
**Scope**: Small — documentation
**Complexity: 1**

1. **Create** `docs/env-vars.md` listing every `ASTRID_*` variable with: name constant, env-var string, who sets it, who reads it, effect. Reference `astrid/core/env_vars.py` as canonical source of truth. Note which sites are allowlisted (threads/, audit/, packs/) and why.

### Step 3: Conformance test for env-vars
**Scope**: Small — test file
**Complexity: 2**

1. **Create** `tests/test_env_vars_conformance.py` with these assertions:
   * (a) Every constant defined in `env_vars.py` has `value == name` (i.e., `ASTRID_HOME_ENV = "ASTRID_HOME"`). Exception: `ASTRID_AUTHOR_TEST_LEGACY` which is explicitly documented as a backward-compat alias.
   * (b) No constant name defined in `env_vars.py` is also defined/assigned in any other file in `astrid/`. The conformance test scans the AST of all `astrid/**/*.py` files and asserts exactly one definition site per constant name.
   * (c) Scan `astrid/core/**/*.py` for `os.environ.get("ASTRID_…")` or `os.environ["ASTRID_…"]` bare-string usages. Flag any that reference a constant catalogued in `env_vars.py` but use the bare string instead of importing the constant. **Allowlist**: `astrid/packs/` (executor run.py files that don't import astrid core), `astrid/threads/` (contract-locked), `astrid/audit/` (separate concern), and any occurrence inside a string/docstring/comment (not an actual environ access).

---

## Phase 2: Core Fixes (Items 1, 3, 4, 5, 6)

### Step 4: Fix gateway.py recovery commands (Item 1 gateway half)
**Scope**: Small — two lines changed
**Complexity: 1**

1. **Fix** `gateway.py:196` — SessionBindingError raise site: extract project from `raw` argv (reuse `_extract_project_slug`), use `f"astrid attach {project_hint}"` when a hint exists, fall back to `"astrid status"` when it doesn't.

2. **Fix** `gateway.py:211` — "no session bound" raise site: `project_hint` is already computed at line 202. The existing `attach_hint` variable at lines 203-206 is a **display string with backticks** (f"`` `astrid attach {project_hint}` ``") for the prose error message. **Create a separate variable** `recovery_cmd` that holds the actionable CLI command WITHOUT backticks: `f"astrid attach {project_hint}"` when project_hint exists, `"astrid status"` otherwise. Use `recovery_cmd` for the `recovery_command=` parameter.

3. **Verify** claim.py item 1 half: already fixed (line 191 reads `f"astrid attach {getattr(args, 'project', '<project>')}"`). Confirm no regression needed.

### Step 5: Recovery-command conformance test (Item 1 test half)
**Scope**: Medium — comprehensive scanner test
**Complexity: 3**

1. **Create** `tests/test_recovery_command_conformance.py` that:
   * Scans every `recovery_command=` raise-site in `astrid/` (via AST, ~339 total matches, ~86 in core+gateway, rest in packs/ executors).
   * For each recovery command string (or f-string with known interpolation patterns), performs offline argparse dry-validation: splits the command into tokens, matches against known astrid subcommand parsers.
   * Uses env-var constants from `astrid/core/env_vars.py` (item 2) — does NOT hardcode any env var name.
   * Validates syntax/parsability only, not end-to-end execution.
   * **Allowlists** (commands NOT validated as CLI):
     - Commands containing `<` angle-bracket placeholders (these are templates, not literal commands)
     - Commands that are shell builtins (`export`, `mkdir`, `mv`, `ls`, `rm`, `cat`)
     - Non-astrid recovery hints (prose like `"check --help for usage and try again"`, `"Fix the validation errors..."`, `"Pick a pack id..."`)
     - All recovery commands in `astrid/packs/**/run.py` (executor run.py files that use prose guidance, not astrid CLI commands)
   * Focus validation on commands starting with `astrid ` or `python3 -m astrid ` — these must parse against the registered CLI subcommand tree.

### Step 6: Extract shared event-hash module (Item 3)
**Scope**: Medium — new module, two migrated call sites, golden test
**Complexity: 4** (hash algorithm sensitivity + golden fixture requirement)

**CRITICAL**: The golden fixture `tests/fixtures/event_hash_golden.json` ALREADY EXISTS in the repo (14 lines, generated 2026-06-05). It is FROZEN per the locked decision. Do NOT regenerate it. The conformance test must assert against this exact file.

The fixture confirms the two hash formats:
- `timeline_embedded_digest`: bare hex (no `sha256:` prefix) — matches what `with_event_hash` currently stores
- `task_prepended_digest`: `sha256:<hex>` — matches what `_event_hash` currently returns

1. **Create** `astrid/contracts/event_hash.py` exposing two named functions:
   * `hash_embedded(prev_hash: str | None, event: TimelineEvent) -> str` — the timeline algorithm: embeds `prev_hash` in payload JSON, hashes with `sha256_hex(payload, exclude_hash=True)`, returns **bare hex digest** (no `sha256:` prefix). Docstring: used by timeline event serialization (`serialize.py`).
   * `hash_prepended(prev_hash: str, event: dict[str, Any]) -> str` — the task algorithm: prepends `prev_hash` raw string to `canonical_event_json(event)`, SHA-256 hashes, returns **`f"sha256:{digest}"`** (WITH prefix). Docstring: used by task event log (`events.py`).

2. **Migrate** `serialize.py:64-69` (`with_event_hash`): delegate only the **digest computation** to `hash_embedded`. `with_event_hash` continues to return `TimelineEvent` and construct the full event object. Replace lines 66-68 (the payload+hash computation) with a call to `hash_embedded` for the digest value only. The function signature and return type do NOT change.

3. **Migrate** `events.py:827-829` (`_event_hash`): replace the body with a call to `hash_prepended`. Since both return `str` with the same format, this is a direct delegation.

4. **Do NOT** change either algorithm, do NOT migrate on-disk logs, do NOT unify the two algorithms.

5. **Create** `tests/test_event_hash_conformance.py` with:
   * Golden test: loads `tests/fixtures/event_hash_golden.json`, feeds each fixture through both hash functions, asserts byte-identical output. The golden file is read-only; regenerating it is forbidden and the test documents this.
   * Round-trip test: verifies that the same (prev_hash, event) pair produces the same hash before and after consolidation.

### Step 7: Deduplicate `_require_uuid_str` (Item 4)
**Scope**: Small — shared validator, two call sites
**Complexity: 2**

1. **Create** `astrid/contracts/schema_validators.py` with `require_uuid_str(value: object, field: str, error_cls: type[Exception]) -> str`. The function accepts the error class as a parameter so each caller preserves its own exception type.

2. **Replace** `project/schema.py:353-361` with a call to the shared validator, passing `ProjectValidationError`.

3. **Replace** `timeline/events/schema/types.py:119-126` with a call to the shared validator, passing `TimelineEventSchemaError`.

4. **Create** `tests/test_uuid_str_conformance.py`: same invalid input → both callers raise their respective error types, both error types share a common base class (`Exception`).

### Step 8: Document session role authority (Item 5)
**Scope**: Small — docstring + test
**Complexity: 2**

1. **Update** `session/model.py:42-52` `Session` docstring: document that `role` is a **snapshot/hint** recorded at session creation/open time; the **authoritative** role is always derived from the lease at `lifecycle.py:316-335` (`_derive_role_and_run_id`). Reading `Session.role` without re-deriving from the lease may be stale after takeover.

2. **No code changes** to `lifecycle.py:316-335` (already lease-authoritative) or `cli.py:863-882` (already reads `session.agent_id` from session record, role display is informational).

3. **Create** test in `tests/session/test_session_role_authority.py`:
   * Simulate a takeover: create session A (writer), create session B that takes over (writer), verify `astrid status` for session A reports `reader` (derived from lease, not the stale `writer` snapshot).
   * Verify no silent divergence: the displayed role matches the SDK-resolved role (both lease-derived).

### Step 9: Delete dead `_write_session_pointer` in cli.py (Item 6)
**Scope**: Small — deletion + conformance test
**Complexity: 1**

1. **Delete** `session/cli.py:182-191` (`_write_session_pointer`). Confirmed dead code: zero callers in the entire repo (verified by codebase scan — only 3 matches: the definition itself and 2 documentation references). `cmd_attach` already uses `attach_session(write_project_pointer=True)` which delegates to `lifecycle.write_session_pointer`.

2. **Verify** `cmd_attach` at `cli.py:245-350` passes `write_project_pointer=True` to `attach_session` and `attach_session` → `create_session`/`open_session` → `lifecycle.write_session_pointer` writes `.astrid-session`.

3. **Create** `tests/test_session_pointer_conformance.py`: AST-scan `astrid/` for any function body that writes to a file named `.astrid-session` or uses `SESSION_FILE_NAME` with a write call. Assert exactly one function body exists: `lifecycle.write_session_pointer`.

---

## Phase 3: Pack Quality (Item 7)

### Step 10: Promote STAGE.md warning → error (Item 7)
**Scope**: Small — one-line change + test update
**Complexity: 1**

1. **Change** `validate.py:562-565`: promote `self.warnings.append(...)` to `self.errors.append(...)` for missing `STAGE.md`. This makes `packs validate` fail (non-zero exit) when a component is missing its STAGE.md.

2. **Do NOT add a required-headings check.** The original scope is "promote missing STAGE.md warning → error." A required-headings check for `## Purpose`, `## Inputs`, `## Outputs` would break `packs validate` for ~48 of ~50 existing STAGE.md files (only 2 files have `## Purpose`; the official template at `docs/templates/executor/STAGE.md` uses none of these headings). Adding heading validation is a separate, larger effort that requires grandfathering existing files and template updates — out of scope for this quick-win.

3. **No comfy_wrap STAGE.md needed.** There is no `packs/comfy_wrap/` or `packs/vibecomfy/` pack directory in this repo. The ComfyUI escape-hatch functionality lives in `astrid/core/generation/backends/vibecomfy.py` as a generation backend, not as a pack component. Per the factual repo state, no STAGE.md needs to be created for a nonexistent pack.

4. **Update** related tests that assert warning counts for missing STAGE.md to expect errors instead. Search `tests/` for assertions referencing `"STAGE.md not found"` in warning lists and update to error assertions.

5. **Keep** pack-root `AGENTS/README` as warnings (unchanged — the scope explicitly says warnings, not errors).

---

## Execution Order

1. **Step 1** — Create `env_vars.py` (item 2 foundation, blocks steps 3, 5, 9)
2. **Step 2** — Write `docs/env-vars.md`
3. **Step 3** — Env-vars conformance test (validates step 1)
4. **Step 4** — Fix gateway.py recovery commands (item 1, depends on env_vars.py for constants in test)
5. **Step 5** — Recovery-command conformance test (item 1 test, depends on steps 1 + 4)
6. **Step 6** — Extract event-hash module (item 3, independent)
7. **Step 7** — Deduplicate `_require_uuid_str` (item 4, independent)
8. **Step 8** — Document session role authority (item 5, independent)
9. **Step 9** — Delete dead `_write_session_pointer` (item 6, depends on env_vars.py for conformance test imports)
10. **Step 10** — Promote STAGE.md warning → error (item 7, independent)

Steps 6-8 and 10 can run in parallel (no dependencies between them). Steps 1-5 and 9 are sequenced.

## Validation Order

1. Run `tests/test_env_vars_conformance.py` after step 3
2. Run `tests/test_recovery_command_conformance.py` after step 5
3. Run `tests/test_event_hash_conformance.py` after step 6
4. Run `tests/test_uuid_str_conformance.py` after step 7
5. Run `tests/session/test_session_role_authority.py` after step 8
6. Run `tests/test_session_pointer_conformance.py` after step 9
7. Run existing pack validation tests after step 10
8. Run full `pytest` suite as final gate

## Anti-Regression Gates

- `tests/test_run_ledger_conformance.py` must stay green (exists, 786 lines, perimeter characterization)
- `tests/test_recoverability_conformance.py` must stay green (exists, 559 lines, zero-mode scanner)
- `tests/test_run_status_contract.py` must stay green (exists, 150 lines, STEP_TERMINAL_KINDS contract)
- All existing session tests in `tests/session/` must stay green
