> **⚠️ OBSOLETE / ARCHIVED — May 2026**
>
> This document (`plan_v2.md`) is an archived implementation plan scoped to the **m4 Dependency Inversion** milestone. It is no longer the active planning document. Its scope was limited to import-layering hygiene (inverting static pack imports from `astrid/core/`, relocating duplicate helpers, and establishing the `PackResolver` infrastructure).
>
> **Canonical planning authority** has moved to [`idea.md`](./idea.md), which captures the full multi-sprint reshape vision including the **m3 code-backed step-model conclusion** that governs all subsequent design:
>
> - **Collapsed step shape**: one step type at runtime (`requires_ack`, `assignee`, `produces`, `repeat`, optional `command` for leaf or `children` for group), collapsing the former `code` / `attested` / `nested` kinds.
> - **`plan_initialized` as genesis event**: the initial plan is the first hash-chained event in `events.jsonl`, so `astrid events verify` covers the plan from byte zero.
> - **`plan.json` as cached projection**: `plan.json` is a cheap-read projection of the genesis event, never an independent authority — if it disagrees with the event log, the log wins.
>
> This file is retained for historical reference only. For current planning, see [`idea.md`](./idea.md).

---

# Implementation Plan: m4 Dependency Inversion (revised v2)

## Overview

The gate audit surfaced 37 significant flags across correctness, completeness, caller analysis,
criteria quality, and prerequisite ordering. This revision resolves all open design questions,
re-baselines the stale state model, completes the duplicate-helper and media-caller inventories,
and hardens the validator specification.

**Settled decisions carried forward from gate feedback:**

- **SD1:** `PackResolver` lives in a new `astrid/core/pack_resolver.py` module (don't convert
  `core/pack.py` into a package).
- **SD2:** The import-layering validator scopes to `astrid/core/` only — `pipeline.py` and
  `orchestrate/` are top-level dispatchers allowed to import from packs.
- **SD3:** The `core → verify` direction (`plan.py:15`, `plan_template.py:20` importing `Check`,
  `canonical_check_params`, `file_nonempty`) is **deferred to m5a/m5b**, not in scope for m4.
  The plan addresses only the `verify → core` direction (media relocation).

**New decisions resolving open questions:**

- **Media relocation:** Move `ffprobe_duration_seconds` to `astrid/_media.py`. Add a thin
  `TODO(m5a)` compatibility shim at `astrid/core/util/media.py` that re-exports from
  `astrid._media` — all pack callers continue to work. Only `verify/checks.py` imports directly
  from `astrid._media`, breaking the verify→core edge. Full pack-caller migration happens in m5a.
- **Callable coordinate field names:** Use **`metadata.callable_module`** and
  **`metadata.callable_name`** for internal callables, separate from the existing CLI-facing
  `metadata.runtime_module` / `metadata.runtime_entrypoint`. These are metadata-only pack edits.
- **Migration-completion guard:** Build `validate_migration_completion()` in m4 alongside
  `validate_import_layering()`, but **unit-test only**. Repo-wide blocking enforcement is
  deferred to m5a per the brief.

## Current state (re-baselined)

### Static pack/orchestrate imports in `astrid/core/`

**Invert now (m4 scope):**
- `astrid/core/executor/runner.py:229` — lazy function-body import of
  `publish_youtube_video` from `astrid.packs.youtube.executors.upload.src.social_publish`
- `astrid/core/executor/cli.py:263` — `from astrid.packs.validate import validate_pack`

**Deferred to m5b (exempted):**
- `astrid/core/task/lifecycle.py:252,267,281` — plan-template imports for hype, event_talks,
  thumbnail_maker
- `astrid/core/task/lifecycle.py:143,1252,1275` — `DEFAULT_PACKS_ROOT` from
  `astrid.orchestrate.compile`

### pipeline.py static pack imports (all deferred to m5b, not in core scope)
- Line 268: `from .packs.reigh.executors.publish import run as publish`
- Line 272: `from .packs.youtube.executors.upload import run as publish_youtube`
- Line 276: `from .packs.youtube.executors.upload import run as publish_youtube`
- Line 284: `from .packs import cli as packs_cli`
- Line 340: `from .packs.reigh.executors.reigh_data import run as reigh_data`

### Existing dynamic resolution (already done — NOT new work)
- `pipeline.py:727` already uses `registry.get("video_editing.hype")` with
  `import_module(metadata.runtime_module)` / `getattr(module, runtime_entrypoint)`.
  All three orchestrator manifests (hype, event_talks, thumbnail_maker) already have
  `metadata.runtime_entrypoint: "main"`. This pattern exists but is only used by the
  pipeline CLI entrypoint; core doesn't use it yet.

### Existing infrastructure
- `core/pack.py:84` already exports `packs_root() → Path`
- `orchestrate/compile.py:31` defines `DEFAULT_PACKS_ROOT = REPO_ROOT / "astrid" / "packs"`
  using `astrid._paths.REPO_ROOT` (no core dependency)
- `astrid/_paths.py:12` already has `resolve_executor_runtime_module()`
- `structure.py` has `validate_repo_structure()` with `StructureReport` / `__all__`;
  called from `doctor.py:_check_repo_structure()`
- `core/util/__init__.py` exists but is empty (no `__all__`, no re-exports)

### Complete duplicate-helper inventory (12 definitions)

**sha256 family (3):**
| File | Name | Chunk size | Notes |
|---|---|---|---|
| `dirty.py:123` | `_sha256_file` | 64 KB | Uses `open(path, "rb")` (string path) |
| `lifecycle.py:179` | `_sha256_file` | 1 MB | Uses `path.open("rb")` — deferred, read-only touch |
| `adapter/remote_artifact_fetch.py:28` | `_sha256` | 1 MB | **Named `_sha256`**, not `_sha256_file` — call sites use `_sha256(...)` |

**timestamp family (9):**
| File | Name | Implementation | Behavioral note |
|---|---|---|---|
| `session/identity.py:25` | `_now_iso` | Delegates to `utc_now_iso()` | Already a wrapper — trivial replace |
| `session/cli.py:81` | `_now_iso` | Delegates to `utc_now_iso()` | Already a wrapper — trivial replace |
| `update.py:404` | `_now_iso` | `datetime.now(timezone.utc).isoformat()` | **Produces `+00:00` not `Z`** |
| `session/lease.py:311` | `_utc_now_iso` | Delegates to `utc_now_iso()` | Already a wrapper — trivial replace |
| `pack_store.py:464` | `_utc_now_iso` | `.isoformat(timespec="seconds")` | **Seconds precision, `+00:00`** |
| `task/events.py:925` | `_utc_now_iso` | Delegates to `utc_now_iso()` | Already a wrapper — trivial replace |
| `runpod/sweeper.py:24` | `_utc_now_iso` | Delegates to `utc_now_iso()` | Already a wrapper — trivial replace |
| `adapter/manual.py:26` | `_utc_now_iso` | Calls `utc_now_milliseconds()` | **Millisecond precision** |
| `adapter/local.py:31` | `_utc_now_iso` | Calls `utc_now_milliseconds()` | **Millisecond precision** |
| `project/schema.py:33` | `utc_now_iso` | Calls `utc_now_seconds()` | **Seconds precision** |

### Media callers (10 files importing `ffprobe_duration_seconds` from `astrid.core.util.media`)
1. `verify/checks.py:23` — will import from `astrid._media`
2. `tests/core/util/test_media.py:7`
3. `packs/video_editing/executors/cut/run.py:277`
4. `packs/video_editing/orchestrators/hype/run.py:507`
5. `packs/video_editing/orchestrators/event_talks/run.py:372`
6. `packs/understanding/executors/audio_understand/run.py:22`
7. `packs/understanding/executors/video_understand/run.py:18`
8. `packs/editorial/executors/scenes/run.py:17`
9. `packs/editorial/executors/transcribe/run.py:19`
10. `packs/editorial/executors/editor_review/run.py:20`

Strategy: move implementation to `astrid/_media.py`, leave a `TODO(m5a)` re-export shim at
`astrid/core/util/media.py`, update only `verify/checks.py` to import from `astrid._media`.
Pack callers and the test file continue to work through the shim.

---

## Phase 1: Re-Baseline And Neutral Utilities

### Step 1: Re-run the import and helper audit
**Complexity: 1**

1. Execute targeted greps for `astrid.packs`, relative `.packs`, and `astrid.orchestrate` imports
   in `astrid/core/`.
2. Confirm the exact invert-now list: `runner.py:229` and `cli.py:263`.
3. Confirm the deferred (TODO(m5b)) exemption list: `lifecycle.py:143,252,267,281,1252,1275`
   and all `pipeline.py` pack imports.
4. Place a comment block at the top of the `validate_import_layering()` function body listing
   these exemptions explicitly with line-number references and `TODO(m5b)` markers.

### Step 2: Relocate media helpers with compatibility shim
**Complexity: 2**

1. Create `astrid/_media.py` by copying the `ffprobe_duration_seconds` function from
   `astrid/core/util/media.py`.
2. Add `"_media.py"` to `TOP_LEVEL_ASTRID_FILES` in `astrid/structure.py`.
3. Replace the body of `astrid/core/util/media.py` with a thin re-export:
   `from astrid._media import ffprobe_duration_seconds  # TODO(m5a): migrate pack callers`.
4. Update `astrid/verify/checks.py` line 23 to import `ffprobe_duration_seconds` from
   `astrid._media` instead of `astrid.core.util.media`.
5. Update `tests/core/util/test_media.py` to test the canonical export from `astrid._media`
   (import both paths or just the new path).
6. Verify: `python -c "import astrid.verify.checks; import sys; assert not any(m.startswith('astrid.core') for m in sys.modules if 'checks' in m or 'verify' in m)"` — this is the
   specific cycle-break check. **Note:** `verify/checks.py` imports only stdlib + the media import;
   there are no other transitive `astrid.core` dependencies through verify. (Verified: imports
   only stdlib plus `astrid.core.util.media`.)

### Step 3: Establish the canonical utility surface
**Complexity: 4**

1. Add `astrid/core/util/hash.py` with:
   ```python
   def sha256_file(path: Path) -> str:
       """Return the SHA-256 hex digest of *path* using 1 MB chunked reads."""
       digest = hashlib.sha256()
       with path.open("rb") as handle:
           for chunk in iter(lambda: handle.read(1024 * 1024), b""):
               digest.update(chunk)
       return digest.hexdigest()
   ```
   (1 MB chunks match the existing lifecycle/remote_artifact_fetch convention; dirty.py's
   64 KB chunk size is a minor I/O difference with no correctness impact — 1 MB is the
   better default.)

2. Populate `astrid/core/util/__init__.py` with explicit `__all__` re-exports:
   ```python
   from astrid.core.util.time import utc_now_iso, utc_now_seconds, utc_now_milliseconds
   from astrid.core.util.hash import sha256_file

   __all__ = [
       "sha256_file",
       "utc_now_iso",
       "utc_now_milliseconds",
       "utc_now_seconds",
   ]
   ```

3. Replace duplicate timestamp helpers — **preserving behavioral equivalence in each case**:

   **Trivial wrappers** (already delegate to canonical helpers, just remove the wrapper):
   - `session/identity.py:25` — replace `def _now_iso(): return utc_now_iso()` with direct
     `utc_now_iso()` at the 2 call sites; remove the helper.
   - `session/cli.py:81` — same pattern; replace at call sites.
   - `session/lease.py:311` — same pattern; replace at call sites.
   - `task/events.py:925` — same pattern; replace at call sites.
   - `runpod/sweeper.py:24` — same pattern; replace at call sites.

   **Behavioral-preserving replacements** (different precision/format):
   - `update.py:404` (`_now_iso` → `+00:00` format): Replace with `utc_now_iso()` which
     produces `Z` suffix. Both are valid ISO-8601; `Z` is the canonical form. The caller
     at line 302 uses `applied_at` for display/comparison — ISO-8601 parsers handle both.
     **Risk accepted:** format change from `+00:00` to `Z` is a normalization, not a break.
   - `pack_store.py:464` (`_utc_now_iso` → seconds precision): Replace with
     `utc_now_seconds()` from `core.util.time` — preserves seconds precision exactly.
   - `adapter/manual.py:26` (`_utc_now_iso` → millisecond precision): Replace with
     `utc_now_milliseconds()` from `core.util.time` — preserves millisecond precision.
   - `adapter/local.py:31` (`_utc_now_iso` → millisecond precision): Replace with
     `utc_now_milliseconds()` from `core.util.time` — preserves millisecond precision.
   - `project/schema.py:33` (`utc_now_iso` → seconds precision): Replace with
     `utc_now_seconds()` from `core.util.time` — preserves seconds precision.

4. Replace duplicate sha256 helpers:
   - `dirty.py:123` — import `sha256_file as _sha256_file` from `core.util.hash`;
     remove the local definition. Call sites unchanged (already use `_sha256_file(...)`).
   - `adapter/remote_artifact_fetch.py:28` — import `sha256_file as _sha256` from
     `core.util.hash` (note the `as _sha256` alias to match existing call sites at lines
     70 and 77 which call `_sha256(...)`). Remove the local definition.
   - `lifecycle.py:179` — **Read-only touch for m4.** Add a comment noting the duplicate
     and `TODO(m5b): import sha256_file from core.util.hash`. Do not change any imports
     or call sites in lifecycle.py (m5b scope).

5. Verify: `rg "def (_now_iso|_utc_now_iso|_sha256|_sha256_file)" astrid/core/` returns
   only the lifecycle.py entry (exempted) and `core/util/hash.py:sha256_file` (canonical).
   The `_now_iso` / `_utc_now_iso` definitions should all be gone from core.

6. Add `DEFAULT_PACKS_ROOT = packs_root()` to `astrid/core/pack.py` alongside the existing
   `packs_root()` function. Update `astrid/orchestrate/compile.py` to import
   `DEFAULT_PACKS_ROOT` from `astrid.core.pack` instead of defining it locally from
   `REPO_ROOT`. Update `astrid/orchestrate/cli.py`'s re-import accordingly.
   **Rationale:** This creates an `orchestrate → core` dependency for a constant, which
   is in the allowed direction (top-level can import from core). The circular-risk concern
   (scope-3) is mitigated because `core.pack.packs_root()` is a pure path-computation
   that will never need orchestrate. The lifecycle.py callers (deferred to m5b) continue
   to work because `compile.py` still exports the constant.

---

## Phase 2: Manifest Callable Resolution

### Step 4: Add the PackResolver and registry callable helpers
**Complexity: 5**

1. Create `astrid/core/pack_resolver.py` with:
   - `PackResolver` Protocol: `resolve_callable(module: str, name: str) -> Callable[..., Any]`
   - A concrete `importlib_resolve(module: str, name: str) -> Callable[..., Any]` function
     that uses `importlib.import_module()` + `getattr()`.
   - Custom error classes: `PackResolverError` (base), `CallableNotFoundError` (missing
     module or attribute), each carrying `module`, `callable_name`, and `capability_id`
     context. No silent skips — always raise a named error on failure.

2. Add a `resolve_callable_from_metadata(metadata: dict, capability_id: str) -> Callable`
   helper that reads `metadata.callable_module` and `metadata.callable_name`, validates
   both are non-empty strings, and delegates to `importlib_resolve()`.

3. Add to `astrid/core/executor/registry.py` (or a companion helper): a
   `resolve_executor_callable(executor: ExecutorDefinition) -> Callable` that reads
   the executor's metadata and calls `resolve_callable_from_metadata()`.

4. Acknowledge and integrate with the existing `astrid/_paths.py:resolve_executor_runtime_module()`:
   that function resolves *runtime modules* for CLI command execution; the new resolver
   resolves *internal callables* for in-process use. They serve different purposes and
   coexist — the new resolver reads different metadata keys (`callable_module`/`callable_name`
   vs `runtime_module`/`runtime_entrypoint`).

### Step 5: Add sanctioned manifest metadata
**Complexity: 2**

All additions go into the existing freeform `metadata` dict — pack schemas do not enforce
`additionalProperties: false` on `metadata`, so no schema changes are needed.

1. Add to the three orchestrator manifests (`video_editing.hype`, `video_editing.event_talks`,
   `video_editing.thumbnail_maker`):
   ```yaml
   metadata:
     callable_module: "astrid.packs.video_editing.orchestrators.<name>.plan_template"
     callable_name: "build_plan_v2"
   ```
   (These are separate from the existing `runtime_module`/`runtime_entrypoint` which point
   at `run.py::main` for CLI dispatch.)

2. Add to `astrid/packs/youtube/executors/upload/executor.yaml`:
   ```yaml
   metadata:
     callable_module: "astrid.packs.youtube.executors.upload.src.social_publish"
     callable_name: "publish_youtube_video"
   ```
   This is separate from the existing `runtime_module: "astrid.packs.youtube.executors.upload.run"`
   and `runtime_entrypoint: "main"` which route CLI invocations.

3. No pack runtime logic changes. These are metadata-only additions.

---

## Phase 3: Remove Invert-Now Static Imports

### Step 6: Invert `runner.py` and `cli.py`
**Complexity: 3**

1. **`runner.py:219-240` (`_run_upload_youtube`):**
   Replace the function-body lazy import:
   ```python
   from astrid.packs.youtube.executors.upload.src.social_publish import publish_youtube_video
   ```
   with manifest-backed resolution using the new helpers from Step 4:
   ```python
   from astrid.core.pack_resolver import resolve_callable_from_metadata
   # ... inside _run_upload_youtube, after dry_run check:
   publish_youtube_video = resolve_callable_from_metadata(executor.metadata, executor_id)
   ```
   **Note:** `_run_upload_youtube` currently receives only `(request, executor_id)` but
   needs the executor's metadata. Change the signature to also accept `executor` (or pass
   metadata directly). Update the sole call site at `runner.py:190` to pass `executor`.
   Preserve dry-run behavior (early return at lines 221-227 unchanged).

2. **`cli.py:263` (`_cmd_scaffold_component`):**
   Replace:
   ```python
   from astrid.packs.validate import validate_pack
   ```
   with:
   ```python
   from importlib import import_module
   _validate_mod = import_module("astrid.packs.validate")
   validate_pack = _validate_mod.validate_pack
   ```
   This is a dynamic `importlib` call, not a static `from astrid.packs...` import.
   The call site at line ~362 uses `validate_pack(pack_root)` — no change needed.

3. Update `tests/test_executor_runner_errors.py` tests that monkeypatch
   `social_publish.publish_youtube_video`:
   - Keep the `from astrid.packs.youtube.executors.upload.src import social_publish`
     import in the test (needed for `unittest.mock.patch`).
   - Add a test that asserts: (a) with correct `callable_module`/`callable_name` metadata,
     the callable resolves and is invoked; (b) with missing or incorrect metadata,
     a `CallableNotFoundError` (or `PackResolverError`) is raised with the youtube.upload
     capability id in context.

---

## Phase 4: Enforce The Contract

### Step 7: Add structure validators and wire them in
**Complexity: 5**

1. Add `validate_import_layering()` to `astrid/structure.py`:
   - Uses AST parsing (`ast.parse`) to extract all `Import` and `ImportFrom` nodes from
     every `.py` file under `astrid/core/`.
   - Resolves relative imports to absolute module paths using the file's package context
     (e.g., `from .packs.foo import bar` in `astrid/core/executor/runner.py` resolves to
     `astrid.packs.foo`).
   - Flags any import that resolves to `astrid.packs` or `astrid.orchestrate`.
   - Exemptions (hardcoded with `TODO(m5b)` comments):
     - `astrid/core/task/lifecycle.py` — all pack and orchestrate imports (5 locations:
       lines 143, 252, 267, 281, 1252, 1275)
   - **Does NOT scan `astrid/pipeline.py`** — scoped to `astrid/core/` only (SD2).
   - Returns a list of violation strings; empty list = clean.

2. Add `validate_migration_completion()` to `astrid/structure.py`:
   - Scans `astrid/` (excluding `packs/` and `tests/`) for:
     - `DEPRECATED` markers without a `TODO(mXa/mXb)` removal-target comment
     - `sys.modules[...]` injections outside test files
     - Dangling `__all__` aliases where both names are in the same `__all__`
     - No-op compatibility shims imported by >0 live callers
   - **Unit-tested in m4; repo-wide enforcement deferred to m5a.**
   - Returns a list of advisory strings; `validate_repo_structure()` logs them as warnings
     (not errors) until m5a.

3. Wire both validators into `validate_repo_structure()` in `astrid/structure.py`:
   - Add calls after the existing `_validate_*` calls.
   - `validate_import_layering()` violations are **errors** (fail the report).
   - `validate_migration_completion()` advisories are **warnings** (logged but don't fail)
     with a `TODO(m5a): promote to errors`.

4. Add a **pre-deployment smoke test**: before running on the post-m4 tree, verify the
   import-layering validator flags the known pre-m4 violations (`runner.py:229`,
   `cli.py:263`). This proves the validator's detection capability before SC2 depends on it.

5. Update `astrid/structure.py`'s `__all__` to include the new public functions.
   Update `astrid/doctor.py` if needed (the existing `_check_repo_structure()` calls
   `validate_repo_structure()` which will now include the new checks automatically).

6. Add `"_media.py"` to `TOP_LEVEL_ASTRID_FILES` in `astrid/structure.py` (ensuring
   `astrid doctor` doesn't flag the new top-level file).

### Step 8: Wire tests and focused regression coverage
**Complexity: 3**

1. Add `tests/test_structure_contracts.py`:
   - Test `validate_import_layering()` detects known violations:
     - Pre-m4: with a temp file mimicking `runner.py:229`'s static pack import → flagged
     - Post-m4: with clean core files → no violations
     - Relative import resolution: `from .packs.foo import bar` in a core file → correctly
       resolved to `astrid.packs.foo` and flagged
   - Test `validate_import_layering()` does NOT flag:
     - Dynamic `importlib.import_module("astrid.packs.foo")` (AST sees a string, not an import)
     - Exempted lifecycle.py imports
   - Test `validate_migration_completion()` detects DEPRECATED markers without milestones

2. Add `tests/test_core_util_surface.py`:
   - Verify `astrid/core/util/__init__.py` has an explicit `__all__`
   - Verify `sha256_file`, `utc_now_iso`, `utc_now_seconds`, `utc_now_milliseconds` are
     all importable from `astrid.core.util`
   - Verify that `rg "def (_now_iso|_utc_now_iso)" astrid/core/` (excluding lifecycle.py)
     returns no matches — this is a positive assertion that duplicates are gone

3. Add happy-path resolver test in `tests/test_pack_resolver.py`:
   - Test `importlib_resolve()` successfully resolves a known callable
   - Test `resolve_callable_from_metadata()` with valid metadata → returns callable
   - Test `resolve_callable_from_metadata()` with missing `callable_module` → raises
     `CallableNotFoundError` with capability id context
   - Test `resolve_callable_from_metadata()` with wrong `callable_name` → raises
     `CallableNotFoundError`

4. Update `tests/test_executor_runner_errors.py`:
   - Add test: youtube.upload with valid callable metadata → callable resolved and invoked
   - Add test: youtube.upload with missing callable metadata → structured error raised
   - Update existing monkeypatch tests to work with manifest-based resolution (the
     `social_publish` import in the test stays for `unittest.mock.patch`)

5. Update `tests/core/util/test_media.py` to test `ffprobe_duration_seconds` imported
   from `astrid._media` (the canonical location).

---

## Execution Order

1. **Re-baseline** (Step 1) — confirm the exact violation list before touching code.
2. **Neutral utility moves** (Steps 2–3) — land the media shim and canonical util surface
   before import-layer enforcement so tests can validate the clean state.
3. **Resolver helpers + manifest metadata** (Steps 4–5) — build the resolution infrastructure
   and annotate manifests before rewriting runner.py.
4. **Invert runner.py and cli.py** (Step 6) — remove the last static pack imports from core.
5. **Structure validators** (Step 7) — add after the code is clean; run the pre-deployment
   smoke test to confirm the validator catches known violations.
6. **Tests** (Step 8) — comprehensive coverage after all code changes land.
7. **Full test suite** — final validation pass.

## Validation Order

1. **Smoke test: validator detects pre-m4 violations** — `python -m pytest tests/test_structure_contracts.py -k "pre_m4"` — confirms the import-layering validator catches `runner.py:229` and `cli.py:263` static imports.
2. **Cycle-break check:** `python -c "import sys; import astrid.verify.checks; raise SystemExit(any(m.startswith('astrid.core') for m in sys.modules))"` — exits 0 (no core modules loaded through verify).
3. **Duplicate helper check:** `rg "def (_now_iso|_utc_now_iso)" astrid/core/ --glob '!**/lifecycle.py'` — no matches. `rg "def _sha256" astrid/core/ --glob '!**/lifecycle.py'` — only `core/util/hash.py:sha256_file`.
4. **Targeted tests:** `tests/test_structure_contracts.py`, `tests/test_core_util_surface.py`, `tests/test_pack_resolver.py`, `tests/test_executor_runner_errors.py`, `tests/core/util/test_media.py`.
5. **Import-layering validator green:** `python -c "from astrid.structure import validate_import_layering; violations = validate_import_layering(); assert not violations, violations"` — exits 0.
6. **Registry parity:** executor/orchestrator/element list outputs remain identical before vs after (aside from added `callable_module`/`callable_name` metadata fields).
7. **Full test suite:** `python -m pytest` exits 0 (all non-flaky tests pass).

## Proposed Ticket Links
- `01KRF15VFMCN7SYZ9K4NANXTAT`: related; only mark `resolves_on_complete=true` if the final implementation unifies the divergent resolution paths enough despite lifecycle deferral.
- `01KRF15VTT59Q0P8N6R2619TRG`: related schema pressure, not fully resolved.
- `01KRF16MX3VWY2Q993VHHAKNTG`: related, not resolved because plan-template consolidation is out of scope.
