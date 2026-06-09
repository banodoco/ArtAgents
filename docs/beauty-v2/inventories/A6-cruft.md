# Inventory appendix — A6-cruft

_Read-only DeepSeek V4 Pro research against base `2edd0ce`. Verify any functional claim with ast.parse/grep before acting — one claim per audit class has historically been a truncated-read false positive._

### Theme: Dead code, cruft & cosmetic rot — comprehensive sweep

**Scope of the problem:** Across the ~501 `.py` files in `astrid/`, we surfaced **4 truly dead module-level constants** (never referenced), **2 dead module imports** (aliased then ignored), **1 self-assignment no-op**, **1 duplicate `__future__` import**, **1 commented-out code block** (7 lines of dead function), **17 copy-pasted one-line delegate functions duplicated across 3+ files each** (7 `_utc_now`, 3 `_read_env_value`, 3 `_candidate_env_files`, 4 `_step_dir`), **38 `.DS_Store`-only/empty directories**, **33 files with M4-extraction docstrings** plus **62 M4-ticket inline comments** that are now historical cruft, and **1 broken test import** referencing a nonexistent namespace package (`astrid.utilities`). Estimated ~800–1,200 LOC of dead weight plus 38 directory entries. Most items are mechanical removals; the duplicated-delegate consolidation and M4-comment purge require light verification.

---

**Complete instance inventory:**

| # | file:line | what | severity |
|---|-----------|------|----------|
| **DEAD CONSTANTS (never referenced)** | | | |
| 1 | `core/project/run.py:35` | `SENSITIVE_ARG_NAMES` set — never used in file or tree | UGLY |
| 2 | `core/project/schema.py:28` | `RUN_STATUSES` — never used | UGLY |
| 3 | `core/task/plan_verbs.py:36` | `STEP_TOMBSTONED_KIND = "plan_step_tombstoned"` — only appears at definition | UGLY |
| 4 | `packs/video_editing/orchestrators/thumbnail_maker/run.py:46` | `MINIMAL_JPEG` — bytes constant, never used | UGLY |
| **DEAD IMPORTS** | | | |
| 5 | `core/gateway/__init__.py:38` | `from . import project as _gateway_project` — unused; specific names imported on :40 | NIT |
| 6 | `core/gateway/__init__.py:39` | `from . import wait as _gateway_wait` — same, specific names imported on :58 | NIT |
| **SELF-ASSIGNMENT / NO-OP** | | | |
| 7 | `core/util/git.py:96` | `filename = filename` inside `if " -> " in filename:` block — dead no-op | UGLY |
| **DUPLICATE IMPORTS** | | | |
| 8 | `packs/editorial/executors/refine/run.py:5-6` | `from __future__ import annotations` appears twice, consecutively | NIT |
| **COMMENTED-OUT CODE** | | | |
| 9 | `core/timeline/cli.py:74-80` | 7 lines of commented-out `def build_parser()` stub with `...` ellipsis | NIT |
| **COPY-PASTED ONE-LINE DELEGATES** | | | |
| 10 | `core/util/llm_clients.py:57` | `def _utc_now() -> str: return utc_now_seconds()` — 1 of 7 identical copies | UGLY |
| 11 | `packs/editorial/executors/quote_scout/run.py:52` | Same `_utc_now` delegate (copy #2) | UGLY |
| 12 | `packs/editorial/executors/triage/run.py:50` | Same `_utc_now` delegate (copy #3) | UGLY |
| 13 | `packs/editorial/executors/arrange/run.py:115` | Same `_utc_now` delegate (copy #4) | UGLY |
| 14 | `packs/training/executors/pool_build/run.py:27` | Same `_utc_now` delegate (copy #5) | UGLY |
| 15 | `packs/training/executors/pool_merge/run.py:24` | Same `_utc_now` delegate (copy #6) | UGLY |
| 16 | `packs/understanding/executors/scene_describe/run.py:48` | Same `_utc_now` delegate (copy #7) | UGLY |
| 17 | `core/util/secrets.py:80` | `def _read_env_value(...) -> return read_env_value(...)` — wrappers for public names | UGLY |
| 18 | `core/util/secrets.py:84` | `def _candidate_env_files(...) -> return candidate_env_files(...)` — same pattern | UGLY |
| 19 | `core/util/llm_clients.py:201` | `def _read_env_value(...) -> return read_env_value(...)` — duplicate of secrets.py:80 | UGLY |
| 20 | `core/util/llm_clients.py:205` | `def _candidate_env_files(...) -> return candidate_env_files(...)` — dup of :84 | UGLY |
| 21 | `core/integrations/reigh/env.py:13` | `def _read_env_value(...) -> return read_env_value(...)` — 3rd copy | UGLY |
| 22 | `core/integrations/reigh/env.py:17` | `def _candidate_env_files(...) -> return candidate_env_files(...)` — 3rd copy | UGLY |
| 23 | `core/adapter/local.py:19` | `def _step_dir(run_ctx) -> Path: return step_dir_for_context(run_ctx)` — 1 of 4 copies | NIT |
| 24 | `core/adapter/manual.py:15` | Same `_step_dir` delegate (copy #2) | NIT |
| 25 | `core/adapter/remote_artifact.py:19` | Same `_step_dir` delegate (copy #3) | NIT |
| 26 | `core/adapter/remote_artifact_fetch.py:26` | Same `_step_dir` delegate (copy #4) | NIT |
| **M4-MIGRATION SCAFFOLDING (representative — 33 docstrings + 62 inline)** | | | |
| 27–59 | 33 files (e.g., `core/pack/cli_basic.py:3`, `core/timeline/cli_edits.py:3`, `core/gateway/wait.py:3`, etc.) | Module docstrings: "Extracted from ... during M4 giant-file split" | NIT |
| 60–121 | 62 inline comments (e.g., `core/pack/install_local.py:80`, `core/session/cli.py:58-83`, etc.) | `# Late import to preserve monkeypatch seams (M4 T20 / SD3)` etc. | NIT |
| **EMPTY DIRECTORIES (.DS_Store-only or truly empty — 38 total)** | | | |
| 122–159 | `astrid/{orchestrate,modalities,contracts,domains,audit,utilities}` (6 top-level) + `packs/_core`, `packs/fal/executors`, `packs/local/{elements,executors, elements/effects}`, `packs/{external,rendering/elements,rendering/elements/{transitions,effects,animations},rendering/executors,rendering/executors/html_canvas_effect/templates}`, `packs/{iteration/executors,moirae/executors,builtin/{orchestrators,fixtures}}`, `packs/{video_editing/{orchestrators,executors},generation/executors,foley/{orchestrators,executors},media/executors}`, `packs/{training/{orchestrators,executors},understanding/executors,youtube/executors,comfy_wrap/executors,reigh/executors,editorial/executors,vibecomfy/executors,text_analysis/orchestrators}`, `core/pack/schemas` | 38 dirs with zero `.py`/non-`.DS_Store` files | NIT |
| **BROKEN TEST IMPORT (dead namespace)** | | | |
| 160 | `tests/core/util/test_secrets.py:14-15` | `from astrid.utilities.llm_clients import ...` — `astrid/utilities/` is an empty namespace package, this import fails | UGLY |

---

**Root cause:** The M4 "giant-file split" epic extracted submodules from monolithic files (`gateway.py` → `gateway/{dispatch,project,wait,help}.py`, `cli.py` → `cli_{parser,edits,events,...}.py`, `run.py` → `{steps,runner,config,...}.py`) and left behind: (a) docstring/changelog comments recording the extraction, (b) re-export imports that monkeypatch seams depend on, (c) duplicated private delegate functions because each extracted executor kept its own `_utc_now`/`_read_env_value` shim rather than importing from `core.util`. Empty directories are the inverse — pack/subsystem directories were scaffolded but never populated with actual executors/orchestrators. The `utilities/` namespace package was apparently intended as a redirect but never wired.

---

**Cross-impact (READ CAREFULLY):**
- **Deleting `_gateway_project`/`_gateway_wait` imports** is safe ONLY if no external `mock.patch('astrid.core.gateway._gateway_project')` exists. The surrounding imports on lines 40+ import specific names from those modules, so the bare module aliases are unused. But check tests.
- **Consolidating `_utc_now` into `core.util.time`** affects 6 executor `run.py` files; each current imports `utc_now_seconds` then wraps it. The fix is replacing `def _utc_now...` + local calls with a direct import. These executors also appear in theme-6 (god-file decomposition), so this touches that cleanup.
- **`_read_env_value`/`_candidate_env_files`** are triplicated. `secrets.py` versions are called by 3 production files (transcribe/run.py, sprite_sheet/upscale.py, animate_image/run.py). `llm_clients.py` versions are called internally by `_load_api_key` + broken tests. `reigh/env.py` versions are called internally by `_env_first` + tests. Consolidation requires verifying all call chains.
- **`_step_dir`** is quadruplicated across 4 adapter files (`local`, `manual`, `remote_artifact`, `remote_artifact_fetch`). Each wraps `step_dir_for_context`. Consolidation into `core.adapter.__init__` or a shared `_adapters_common` module is straightforward.
- **Empty directories** are deceptively risky: deleting `astrid/utilities/` WILL break the namespace package that tests import from (even though the import fails today — deleting the dir would change the error from `ImportError` to `ModuleNotFoundError`). Some empty pack directories may be referenced by pack discovery (`discover_packs_ordered`) — verify before deleting.
- **M4 comments** are safe to delete but their removal touches 33 files, creating merge-conflict risk against any in-flight M4-related branches.

---

**Proposed fix approach:**
- **Dead constants/imports/no-ops:** Straight deletion. No shared module needed.
- **Duplicated delegates:** Table-driven consolidation. Move canonical `_utc_now` into `core/util/time.py`; all 6 executor copies become `from astrid.core.util.time import _utc_now`. Similarly, collapse `_read_env_value`/`_candidate_env_files` to `secrets.py` as single source of truth; `llm_clients.py` and `reigh/env.py` import from there. Collapse `_step_dir` into a shared `core/adapter/_common.py`.
- **Empty directories:** `rm -rf` after verifying no pack-discovery path references them.
- **M4 comments:** Bulk removal via sed/perl — remove every line containing "Extracted from … M4", "M4 giant-file split", "M4 T\\d+", "M4 batch", "during M4".
- **Broken test import:** Fix to `from astrid.core.util.llm_clients import ...`.

---

**Sequencing & risk:**
1. **Safe first** (independent, zero risk): dead constants (#1–4), self-assignment (#7), duplicate import (#8), commented-out code (#9). These touch one file each and nothing imports them.
2. **Verify-then-delete** (medium risk): dead imports (#5–6) — grep tests for `mock.patch` references to `_gateway_project`/`_gateway_wait`.
3. **Delegate consolidation** (medium risk, multi-file): `_utc_now` → `time.py` first (7 files touched, no API change, pure import-path redirect). Then `_read_env_value`/`_candidate_env_files` → `secrets.py` (3 files touched, verify callers don't depend on side effects). Then `_step_dir` → shared adapter module (4 files).
4. **Empty directories** (low risk but requires discovery-path audit): check `discover_packs_ordered` and pack registry for references before `rm -rf`.
5. **M4 comments** (low risk, high churn — 33 files): do last to avoid merge conflicts with other cleanup tickets.
6. **Broken test import** (#160): fix after delegate consolidation so the import path resolves correctly.

---

**Suggested tickets (one-agent-each, sequential):**

- **T1: Delete dead constants and no-ops** — Remove `SENSITIVE_ARG_NAMES` (project/run.py:35), `RUN_STATUSES` (project/schema.py:28), `STEP_TOMBSTONED_KIND` (plan_verbs.py:36), `MINIMAL_JPEG` (thumbnail_maker/run.py:46), `filename = filename` no-op (git.py:96), duplicate `__future__` import (refine/run.py:5-6), and commented-out `build_parser` stub (timeline/cli.py:74-80). 7 files, ~20 LOC removed. Zero risk.

- **T2: Remove dead module imports in gateway** — Delete `from . import project as _gateway_project` and `from . import wait as _gateway_wait` from `gateway/__init__.py:38-39`. First verify no `mock.patch('astrid.core.gateway._gateway_project')` exists in tests. 1 file, 2 lines.

- **T3: Consolidate `_utc_now` into `core.util.time`** — Add `_utc_now` to `core/util/time.py`, then replace all 6 executor copies (quote_scout, triage, arrange, pool_build, pool_merge, scene_describe) + llm_clients.py copy with `from astrid.core.util.time import _utc_now`. 8 files touched, ~14 LOC net reduction.

- **T4: Consolidate `_read_env_value`/`_candidate_env_files`** — Make `secrets.py` the single source of truth. Re-point `llm_clients.py:201-206` to import from `secrets.py` instead of defining its own wrappers. Re-point `reigh/env.py:13-18` similarly (note: reigh's `_candidate_env_files` has a `profile="reigh"` default — preserve that). Fix broken test import in `test_secrets.py:14-15` from `astrid.utilities.llm_clients` → `astrid.core.util.llm_clients`. 4 files.

- **T5: Consolidate `_step_dir` adapters** — Create `core/adapter/_common.py` with shared `_step_dir`, replace 4 copies in `local.py`, `manual.py`, `remote_artifact.py`, `remote_artifact_fetch.py`. 5 files.

- **T6: Purge M4 migration scaffolding comments** — Strip all "Extracted from … during M4" docstrings, "M4 T\\d+" inline comments, "M4 giant-file split" references, and "M4 batch" comments from 33 files. Sed-based mechanical pass; verify no remaining M4 references post-purge. Pure comment removal, zero behavioral change.

- **T7: Remove empty/.DS_Store-only directories** — Audit pack-discovery paths for references to the 38 empty dirs, then `rm -rf` safe ones. Handle `astrid/utilities` specially — it's a namespace package imported by broken tests (fixed in T4). Delete only after T4 lands and CI passes.