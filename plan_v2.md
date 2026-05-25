# Implementation Plan v2: Port PR #8 operational substrate into pack-system

## Overview

**Goal.** Bring PR #8's *operational substrate* (installed-pack store, `packs install/uninstall/update/rollback` CLI, gitignore copytree filter, agent index, the executor/orchestrator directory restructure, stricter JSON schemas, and parity/install tests) onto the current `main`-based pack-system branch — **without** disturbing pack-system's identity/governance layer (`CapabilityHandle`/`Provenance`/`SafetyDeclaration`/`AliasRecord`/`AliasResolver`/`OverrideStore`/`fork`/`override`/`dirty`/`update`). Then close PR #8.

**Settled decisions (replaces unanswered questions from v1):**

1. **Restructure approach.** Re-execute flat→nested moves on main's tree with `git mv` — NOT copy PR #8's tree wholesale. Main has more packs (generate_image_openai, generate_video, script_pipeline, search_loras, dataset_build, training_run, and others) that PR #8 lacks. Copying PR #8's tree would drop them. This is settled; no confirmation needed.

2. **Deletion scope.** Delete ONLY `astrid/packs/builtin/clip_extract/` (the builtin executor). The other 5 clip_extract copies (media/executors/, clip_tools/executors/, file_summarizer/executors/, text_review/executors/, video_tools/clip_extract/) serve different packs and are left untouched. Deduplication of clip_extract across packs is a separate concern, out of scope for this port.

3. **PR #8 close + branch deletion.** Leave as a manual final step (info-only in the success criteria). This plan executes all the port work and full validation. Closing PR #8 and deleting remote branches is an irreversible outward action the user must perform.

**Current repo shape (verified on 2026-05-23):**
- Working dir: throwaway worktree `pack-system-pr8-port` off `main`.
- PR #8 branch: `origin/megaplan/git-backed-packs/sprint-02-resolver-runtime`.
- **Packs needing restructure** (flat layout): `builtin/` (33+ subdirs + 5 standalone .py files), `upload/` (youtube/ subdir), `iteration/` (assemble/, prepare/ subdirs), `video_tools/` (clip_extract/ subdir).
- **Packs already nested** (no restructure needed): `media/`, `clip_tools/`, `file_summarizer/`, `text_review/`, `text_digest/`, `external/`.
- **5 standalone .py files at builtin root**: `hype.py`, `mini_research.py`, `iterate_review.py`, `agent_probe.py`, `classify_grid.py`. `hype.py` collides with `hype/` directory. These are NOT discoverable as executors/orchestrators (not named `executor.py`/`orchestrator.py`). They need explicit disposition.
- **6 clip_extract locations**: builtin/clip_extract (flat, to be deleted), media/executors/clip_extract, clip_tools/executors/clip_extract, file_summarizer/executors/clip_extract, text_review/executors/clip_extract, video_tools/clip_extract (flat). Only builtin/clip_extract is deleted; the rest stay.
- **New files to port** (absent on main, source = PR #8): `astrid/core/pack_store.py`, `astrid/packs/install.py`, `astrid/packs/gitignore.py`, `astrid/packs/agent_index.py`, `astrid/core/orchestrator/plan_v2.py`, `astrid/core/orchestrator/runtime.py`.
- **12 merge targets** exist on main and diverge from PR #8: `astrid/core/{element,executor,orchestrator}/{registry,schema,cli}.py` (9 files) + `astrid/core/pack.py` + `astrid/packs/cli.py` + `astrid/packs/validate.py`.
- **pack.yaml content roots**: builtin, iteration, upload, video_tools, external have NO `content:` section (discovery is rglob-based, path-agnostic). media, clip_tools, file_summarizer, text_review, text_digest HAVE `content: { executors: executors, ... }` but are already nested — no change needed.
- **Schemas**: main already has `astrid/packs/schemas/v1/{_defs,element,executor,orchestrator,pack}.json` (runtime-aligned, `_defs.json` refs, `html` PortType).
- **Test suite**: `pytest.ini` sets `testpaths = tests, scripts/migrations`. Identity-layer tests exist (test_capability_handle, test_capability_alias_resolver, test_canonical_aliases, test_fork_executor_orchestrator, test_override, test_dirty_detection, test_update_report, test_provenance_fields, test_pack_discovery*, test_pack_local_priority, test_packs_shipped_ids, test_pack_yaml_schema, test_pack_parser_binding).
- **Index generator**: `scripts/gen_capability_index.py` imports from element/executor/orchestrator registries.

---

## Phase 0: Pre-flight verification + reference worktree

### Step 0: Create reference worktree + verify PR #8 file inventory
**Scope:** Small — Complexity: 1

1. **Create** the PR #8 reference worktree: `git worktree add ../pr8-ref origin/megaplan/git-backed-packs/sprint-02-resolver-runtime` (skip if it already exists).
2. **Verify** each new file exists on PR #8 branch:
   - `ls ../pr8-ref/astrid/core/pack_store.py`
   - `ls ../pr8-ref/astrid/packs/install.py`
   - `ls ../pr8-ref/astrid/packs/gitignore.py`
   - `ls ../pr8-ref/astrid/packs/agent_index.py`
   - `ls ../pr8-ref/astrid/core/orchestrator/plan_v2.py`
   - `ls ../pr8-ref/astrid/core/orchestrator/runtime.py`
3. **Verify** the 4 ported test files exist: `tests/packs/test_portfolio_parity.py`, `tests/packs/test_public_id_resolution.py`, `tests/test_git_pack_install.py`, `tests/test_pack_install.py`.
4. **Verify** example packs exist: `examples/packs/media/`, `examples/packs/minimal/`.
5. **Capture** line counts of each 12 merge-target file on PR #8 (`wc -l ../pr8-ref/<file>`) to scope the merge work.
6. **If any file is missing or at a different path**, record it and adjust the plan before proceeding to Phase 1.

---

## Phase 1: Restructure + orphan file disposition + low-risk wholesale ports

### Step 1: Audit restructure move set + classify every builtin directory
**Scope:** Small — Complexity: 1

1. **Enumerate** `astrid/packs/builtin/*/` subdirectories (excluding files).
2. **Classify** each: has `executor.yaml` → goes to `executors/<slug>/`; has `orchestrator.yaml` → goes to `orchestrators/<slug>/`.
3. **Identify main-only packs** that PR #8 lacks — these must survive the restructure. From the verified listing, this includes at minimum: `generate_image_openai`, `generate_video`, `script_pipeline`, `search_loras`, `dataset_build`, `training_run`, plus any others PR #8 doesn't have listed in its tree.
4. **List** the flat packs needing restructure: `builtin/` (all subdirs), `upload/youtube/`, `iteration/{assemble,prepare}/`, `video_tools/clip_extract/`.
5. **Confirm** that packs already nested (media, clip_tools, file_summarizer, text_review, text_digest, external) need NO structural changes.

### Step 2: Execute directory restructure + deletions + orphan disposition
**Scope:** Large — Complexity: 3

**2a. Create target directories.**
```
mkdir -p astrid/packs/builtin/executors
mkdir -p astrid/packs/builtin/orchestrators
mkdir -p astrid/packs/upload/executors
mkdir -p astrid/packs/iteration/executors
mkdir -p astrid/packs/video_tools/executors
```

**2b. Move builtin executor subdirs** (has `executor.yaml`). For each, `git mv astrid/packs/builtin/<slug> astrid/packs/builtin/executors/<slug>`. This includes: youtube_audio, generate_video, spatial_audio_page, shots, asset_cache, transcribe, boundary_candidates, sprite_sheet, human_notes, audio_understand, refine, inspect_cut, arrange, publish, pool_build, scene_describe, visual_understand, tile_video, video_understand, scenes, quality_zones, human_review, understand, generate_image, pool_merge, open_in_reigh, editor_review, cut, html_canvas_effect, reigh_data, triage, foley_review, validate, quote_scout, search_loras, generate_image_openai, render, script_pipeline.

**2c. Move builtin orchestrator subdirs** (has `orchestrator.yaml`). For each, `git mv astrid/packs/builtin/<slug> astrid/packs/builtin/orchestrators/<slug>`. This includes: animate_image, foley_map, iteration_video, logo_ideas, hype, dataset_build, training_run, thumbnail_maker, vary_grid, event_talks.

**2d. Delete** `astrid/packs/builtin/clip_extract` (this builtin executor is removed per the brief — it's superseded by the clip_extract copies in media/clip_tools/file_summarizer/text_review/video_tools packs).

**2e. Add `__init__.py`** files to new directories matching the pattern used in already-nested packs:
```
touch astrid/packs/builtin/executors/__init__.py
touch astrid/packs/builtin/orchestrators/__init__.py
```

**2f. Handle the 5 standalone .py files at builtin root.** These are NOT discoverable as executors or orchestrators (they don't live in subdirectories with manifests). They are legacy/orphan scripts. **Move them into `astrid/packs/builtin/_legacy/`** as a holding area:
```
mkdir -p astrid/packs/builtin/_legacy
git mv astrid/packs/builtin/hype.py astrid/packs/builtin/_legacy/hype.py
git mv astrid/packs/builtin/mini_research.py astrid/packs/builtin/_legacy/mini_research.py
git mv astrid/packs/builtin/iterate_review.py astrid/packs/builtin/_legacy/iterate_review.py
git mv astrid/packs/builtin/agent_probe.py astrid/packs/builtin/_legacy/agent_probe.py
git mv astrid/packs/builtin/classify_grid.py astrid/packs/builtin/_legacy/classify_grid.py
touch astrid/packs/builtin/_legacy/__init__.py
```
This resolves the `hype.py` vs `hype/` collision and keeps the files from polluting the restructured root.

**2g. Restructure other flat packs.**
```
# upload
git mv astrid/packs/upload/youtube astrid/packs/upload/executors/youtube
touch astrid/packs/upload/executors/__init__.py

# iteration
git mv astrid/packs/iteration/assemble astrid/packs/iteration/executors/assemble
git mv astrid/packs/iteration/prepare astrid/packs/iteration/executors/prepare
touch astrid/packs/iteration/executors/__init__.py

# video_tools
git mv astrid/packs/video_tools/clip_extract astrid/packs/video_tools/executors/clip_extract
touch astrid/packs/video_tools/executors/__init__.py
```

**2h. Validate cheaply.** Run `python scripts/gen_capability_index.py` — must succeed with the new layout. Then run the discovery tests:
```
python -m pytest tests/test_pack_discovery.py tests/test_pack_discovery_canonical.py tests/test_pack_discovery_excludes_ai_toolkit.py tests/test_packs_shipped_ids.py tests/test_pack_local_priority.py -q
```

### Step 3: Port `astrid/core/pack_store.py` wholesale (new file)
**Scope:** Medium — Complexity: 2

1. **Copy** `../pr8-ref/astrid/core/pack_store.py` → `astrid/core/pack_store.py`.
2. **Adjust imports** to match pack-system's module layout. Read the file, identify every `from astrid.*` import, and verify the target exists on main. If PR #8 references discarded identity modules, replace with pack-system equivalents or stub.
3. **Smoke:** `python -c "import astrid.core.pack_store"`.

### Step 4: Port `astrid/packs/gitignore.py` wholesale (new file)
**Scope:** Small — Complexity: 1

1. **Copy** `../pr8-ref/astrid/packs/gitignore.py` → `astrid/packs/gitignore.py`.
2. **Smoke-import:** `python -c "import astrid.packs.gitignore"`.

### Step 5: Port `astrid/packs/install.py` (new file, deferred CLI wiring)
**Scope:** Medium — Complexity: 3

1. **Copy** `../pr8-ref/astrid/packs/install.py` → `astrid/packs/install.py`.
2. **Audit imports.** Read the file and check every import against main's module tree. Key expected dependencies:
   - `astrid.core.pack_store` (just ported in Step 3)
   - `astrid.packs.gitignore` (just ported in Step 4)
   - Possibly `astrid.core.pack` (exists on main with pack-system enrichments)
   - Possibly `astrid.core.registry` or similar (check against main)
3. **Fix any import** that points to a PR #8-only module path — map to main's equivalent.
4. **Defer** the `build_parser()` grafting of `install/uninstall/update/rollback` subcommands into `astrid/packs/cli.py` to Step 11.
5. **Smoke:** `python -c "import astrid.packs.install"` (must succeed even before CLI wiring).

---

## Phase 2: The 12-file registry/schema/CLI merge

*Concrete merge method for every file in this phase: (a) create the `../pr8-ref` worktree in Step 0, (b) diff main→PR8 with `git diff HEAD -- <file> > /tmp/diff_<file>.patch` from the PR8 worktree, (c) classify each hunk as "operational" (port it) or "identity" (discard it), (d) apply only operational hunks using targeted `patch` tool edits. Operational hunks = install/store/index/restructure/resolution wiring. Identity hunks = anything touching CapabilityHandle/Provenance/AliasRecord/OverrideStore/fork/override/dirty/update. Re-run the relevant targeted tests after each file.*

### Step 6: Merge `astrid/core/{element,executor,orchestrator}/schema.py` (3 files)
**Scope:** Medium — Complexity: 3

**What PR #8 adds (operational, port these):**
- Stricter field validations (additional `"required"`, `"minLength"`, `"pattern"` constraints)
- Any new schema types related to install/restructure (e.g., pack-source descriptors)

**What PR #8 may change (identity, DISCARD):**
- Any removal or rewrites of `PackDefinition` enrichments
- Changes to port types that would regress the runtime-aligned shape

**Targeted tests:** `tests/test_pack_yaml_schema.py`, `tests/test_packs_validate.py`, `tests/test_executor_schema_capabilities.py`.

### Step 7: Merge `astrid/core/{element,executor,orchestrator}/registry.py` (3 files)
**Scope:** Large — Complexity: 4

**What PR #8 adds (operational, port these):**
- Store/discovery hooks that wire into `pack_store`
- Path-based lookup methods that complement (not replace) canonical resolution
- Any new registry methods for install/uninstall/update/rollback operations

**What PR #8 may change (identity, DISCARD):**
- Changes that replace canonical resolution with path-based resolution
- Removal of `AliasResolver` integration
- Removal of `OverrideStore` hooks

**Adaptation rule:** Where PR #8 adds a new discovery path, make it an additional code path that calls into pack-system's canonical resolver, not a replacement.

**Targeted tests:** `tests/test_pack_discovery.py`, `tests/test_pack_discovery_canonical.py`, `tests/test_pack_local_priority.py`, `tests/test_canonical_aliases.py`.

### Step 8: Merge `astrid/core/{element,executor,orchestrator}/cli.py` (3 files)
**Scope:** Large — Complexity: 3

**What PR #8 adds (operational, port these):**
- New CLI verbs/flags for install/uninstall/update/rollback
- Store-status output formatting
- Trust-summary display

**What PR #8 may change (identity, DISCARD):**
- Changes to identity-aware output (CapabilityHandle display)
- Removal of fork/override/dirty/update CLI verbs
- Changes to the canonical-id display format

**Adaptation rule:** Graft PR #8's new subcommands alongside (not replacing) existing pack-system CLI verbs.

**Targeted tests:** `tests/test_elements_install.py`, `tests/test_executor_cli.py`, `tests/test_canonical_cli.py`, plus a `--help` smoke per module.

### Step 9: Merge `astrid/core/pack.py` (1 file)
**Scope:** Large — Complexity: 4

**What PR #8 adds (operational, port these):**
- Install/store-facing helpers (e.g., pack source resolution, installed-pack metadata)
- Any new fields needed by `pack_store.py`/`install.py`

**What PR #8 may change (identity, DISCARD):**
- Changes to `PackDefinition` structure that remove pack-system enrichments
- Removal of `Provenance`/`SafetyDeclaration` fields
- Changes to canonical-id resolution logic

**Adaptation rule:** Keep pack-system's `PackDefinition` as the spine; add PR #8's operational fields as optional additions.

**Targeted tests:** `tests/test_pack_parser_binding.py`, `tests/test_pack_discovery_canonical.py`, `tests/test_provenance_fields.py`.

### Step 10: Merge `astrid/packs/cli.py` + `astrid/packs/validate.py` (2 files)
**Scope:** Large — Complexity: 4

**packs/cli.py:**
- **Operational (port):** Graft `install`, `uninstall`, `update`, `rollback` subcommands into `build_parser()`, wiring to `astrid.packs.install` functions.
- **Identity (discard):** Any removal of existing pack-system subcommands.

**packs/validate.py:**
- **Operational (port):** Stricter validation logic from PR #8.
- **Identity (discard):** Any validation that rejects pack-system's identity fields.

**Targeted tests:** `tests/test_packs_cli.py`, `tests/test_packs_validate.py`, `tests/test_packs_shipped_ids.py`.

### Step 11: Reconcile `astrid/core/executor/folder.py` + `astrid/core/orchestrator/folder.py` (2 files)
**Scope:** Medium — Complexity: 3

**What main has (MUST preserve):**
- Subprocess metadata-extraction via `_RESULT_PREFIX` and `_load_folder_*` extractors
- `rglob`-based discovery that walks content roots

**What PR #8 may add (port if operational, discard if it replaces main's mechanism):**
- Any additional discovery paths or metadata fields
- Any install/store integration hooks

**Adaptation rule:** Main's subprocess + rglob mechanism wins. Only add PR #8 code that is strictly additive (new fields, new hooks) — never replace main's discovery mechanism.

**Targeted tests:** The discovery tests from Step 2h already cover the nested layout. Additionally verify `python -m pytest tests/test_pack_discovery.py -q`.

---

## Phase 3: Remaining ports + agent index + schemas + examples

### Step 12: Port `astrid/core/orchestrator/plan_v2.py` + `runtime.py` (new files)
**Scope:** Medium — Complexity: 2

1. **Copy** `../pr8-ref/astrid/core/orchestrator/plan_v2.py` → `astrid/core/orchestrator/plan_v2.py`. Smoke-import.
2. **Copy** `../pr8-ref/astrid/core/orchestrator/runtime.py` → `astrid/core/orchestrator/runtime.py`.
3. **Audit `runtime.py`'s module resolution.** Read the file to identify how it resolves module paths. If it uses a PR #8-specific resolver, repoint it to pack-system's canonical resolver (`astrid.core.pack` or the appropriate registry). If it's self-contained, just verify imports.
4. **Smoke:** `python -c "import astrid.core.orchestrator.runtime"`.

### Step 13: Port + reconcile `astrid/packs/agent_index.py` (new file)
**Scope:** Medium — Complexity: 3

1. **Copy** `../pr8-ref/astrid/packs/agent_index.py` → `astrid/packs/agent_index.py`.
2. **Adapt** it to consume pack-system's canonical resolver as its enumeration source. PR #8's agent_index likely has its own discovery mechanism — keep it as a fallback but make the primary path use pack-system's registries.
3. **Document** in a module docstring when each discovery mechanism applies.
4. **Smoke:** generate the index (`python -m astrid.packs.agent_index` or equivalent entry point) and confirm it lists the merged layout's executors/orchestrators/elements.

### Step 14: Merge strict JSON schemas (`astrid/packs/schemas/v1/*.json`)
**Scope:** Medium — Complexity: 3

1. **Fold** PR #8's stricter validations into the existing `_defs.json`, `element.json`, `executor.json`, `orchestrator.json`, `pack.json`.
2. **Do not change** the v1 layout, `_defs.json` refs, or `html` PortType (main's runtime-aligned shape is the baseline).
3. **Targeted test:** `tests/test_pack_yaml_schema.py`.

### Step 15: Port example packs (`examples/packs/media/`, `examples/packs/minimal/`)
**Scope:** Small — Complexity: 1

1. **Copy** `../pr8-ref/examples/packs/media/` → `examples/packs/media/` (already nested on PR #8).
2. **Merge** `../pr8-ref/examples/packs/minimal/` with main's existing `examples/packs/minimal/` — keep main's extra content, add PR #8's additions.

### Step 16: Update `__init__.py` exports
**Scope:** Small — Complexity: 1

1. **Check** `astrid/core/__init__.py` — if it exports submodules, add `pack_store` if needed.
2. **Check** `astrid/packs/__init__.py` — add exports for `install`, `gitignore`, `agent_index` if other code imports them via `astrid.packs.*`.
3. **Check** `astrid/core/orchestrator/__init__.py` — add exports for `plan_v2`, `runtime` if needed.
4. **Verify** by running `python -c "import astrid; import astrid.core; import astrid.packs"` and any known importers.

---

## Phase 4: M3 cleanup, tests, validation, close

### Step 17: Apply M3 cleanup on top of the new layout
**Scope:** Small — Complexity: 2

1. **Remove `comfy_t2i_ds1`** external wrapper (`astrid/packs/external/comfy_t2i_ds1/`). The brief says to delete comfy_* external wrappers. Verify: `ls astrid/packs/external/comfy_t2i_ds1/` exists. `git rm -r astrid/packs/external/comfy_t2i_ds1`.
2. **Confirm** scaffold packs are `visibility: hidden`. Verified: `file_summarizer`, `text_digest`, `clip_tools`, `video_tools` all have `visibility: hidden` already. No change needed.
3. **Verify** no moved pack ids need aliasing. Since the restructure moves subdirectories but pack ids are pack-qualified (e.g., `builtin.transcribe`), and pack.yaml content roots for non-builtin packs reference `executors: executors` (relative), ids should be unchanged. Run `tests/test_canonical_aliases.py` to confirm.

### Step 18: Port parity/install tests
**Scope:** Medium — Complexity: 2

1. **Copy** the 4 test files from PR #8:
   - `../pr8-ref/tests/packs/test_portfolio_parity.py` → `tests/packs/test_portfolio_parity.py`
   - `../pr8-ref/tests/packs/test_public_id_resolution.py` → `tests/packs/test_public_id_resolution.py`
   - `../pr8-ref/tests/test_git_pack_install.py` → `tests/test_git_pack_install.py`
   - `../pr8-ref/tests/test_pack_install.py` → `tests/test_pack_install.py`
2. **Audit each** for PR #8-specific imports, fixtures, or conftest.py dependencies. Fix any that reference PR #8-only paths.
3. **Run** each ported file individually to localize failures: `python -m pytest <file> -q`.

### Step 19: Full validation
**Scope:** Medium — Complexity: 3

1. **Run** `python scripts/gen_capability_index.py` (must succeed; index reflects merged layout). Confirm idempotence: re-run, verify `git diff` shows no changes to the index target files.
2. **Run** the identity-layer test cluster:
   ```
   python -m pytest tests/test_capability_handle.py tests/test_capability_alias_resolver.py \
     tests/test_canonical_aliases.py tests/test_canonical_cli.py \
     tests/test_fork_executor_orchestrator.py tests/test_override.py \
     tests/test_dirty_detection.py tests/test_update_report.py \
     tests/test_provenance_fields.py tests/test_pack_discovery.py \
     tests/test_pack_discovery_canonical.py tests/test_pack_local_priority.py \
     tests/test_packs_shipped_ids.py tests/test_pack_yaml_schema.py \
     tests/test_pack_parser_binding.py -q
   ```
   Must be green (these are the invariant baseline).
3. **Run** the 4 ported parity/install tests: `python -m pytest tests/packs/test_portfolio_parity.py tests/packs/test_public_id_resolution.py tests/test_git_pack_install.py tests/test_pack_install.py -q`. Must pass.
4. **Run** full suite: `python -m pytest tests scripts/migrations -q`. Record any failures and triage against the known pre-existing set (golden-drift / generated-fixture / cloud-env). **No new failures permitted.**
5. **Manual smoke (info):** `packs install/uninstall/update/rollback` end-to-end, local + Git-URL.

### Step 20: Close PR #8 (MANUAL — user performs)
**Scope:** Small — Complexity: 0 (not automated)

This step is info-only in this plan. After all validation passes, the user should:
1. Close PR #8 on the remote.
2. Delete `origin/megaplan/git-backed-packs/sprint-02-resolver-runtime`.
3. Delete residual `origin/megaplan/git-backed-packs/sprint-00-architecture-gate`.
4. Clean up the `../pr8-ref` worktree: `git worktree remove ../pr8-ref`.

---

## Execution Order
1. **Step 0 first** — create pr8-ref worktree and verify all files exist. Gate: if any file is missing, adjust plan before proceeding.
2. **Steps 1–2** — restructure + deletion + orphan disposition. Gate on discovery tests and `gen_capability_index.py`.
3. **Steps 3–5** — wholesale new-file ports. These set up dependencies for the merge.
4. **Steps 6–11** — 12-file merge in dependency order: schema → registry → cli → pack → packs.cli/validate → folder reconcile. Gate each step on its targeted tests.
5. **Steps 12–16** — remaining ports, agent index, schema fold, examples, __init__.py updates.
6. **Steps 17–18** — M3 cleanup, test port.
7. **Step 19** — full validation.
8. **Step 20** — user performs PR #8 close manually.

## Validation Order (at each checkpoint)
1. **Cheapest signal:** `python scripts/gen_capability_index.py` (must succeed and be idempotent).
2. **Discovery cluster:** `test_pack_discovery*`, `test_packs_shipped_ids`, `test_pack_local_priority`.
3. **Identity cluster:** `test_capability_handle`, `test_capability_alias_resolver`, `test_canonical_aliases`, `test_fork_executor_orchestrator`, `test_override`, `test_dirty_detection`, `test_update_report`, `test_provenance_fields`, `test_pack_parser_binding`.
4. **Schema:** `test_pack_yaml_schema`, `test_packs_validate`, `test_executor_schema_capabilities`.
5. **CLI:** `test_packs_cli`, `test_elements_install`, `test_executor_cli`, `test_canonical_cli`.
6. **Ported tests:** `test_portfolio_parity`, `test_public_id_resolution`, `test_git_pack_install`, `test_pack_install`.
7. **Full suite:** `pytest tests scripts/migrations` — no new failures.
