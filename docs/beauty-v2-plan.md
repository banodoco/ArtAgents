# Astrid Beauty v2 — Holistic Cleanup Plan

> **Base commit:** `2edd0ce` (post beauty-epic `main`, 2026-06-09)
> **Bar:** *downright beautiful at every level.*
> **Method:** 10-agent adversarial beauty audit → 6-agent read-only deep-research wave →
> this sequenced, deploy-ready backlog. Full per-theme instance inventories live in
> [`docs/beauty-v2/inventories/`](beauty-v2/inventories/).

## Why this plan exists

An adversarial 10-agent beauty audit of post-epic `main` returned a median of **4.5/10** —
no slice above 6. The cleanup epic built a beautiful *skeleton* (honest module layout, split
god files, a clean `AstridError` envelope, declarative dispatch tables, a single-method
`BackendAdapter`) but left duplicated *muscle* on it. A 6-agent research wave then turned each
audit theme from *examples* into *complete, verified instance inventories with cross-impact*.
The totals are larger than the audit's spot-checks suggested:

| Workstream | Theme | Instances found | Audit had spotted | Est. LOC |
|---|---|:--:|:--:|:--:|
| **WS-A** | Pack-executor copy-paste | 35 manifest dicts + 7 `_die` + 2 architectures (21/42) | ~20 | 900–1,200 |
| **WS-B** | Executor/Orchestrator/SDK twins | 56 dup fns/consts | ~6 | ~1,600 |
| **WS-C** | Circular-facade "fake splits" | 70 sites / 7 clusters | 4 | ~1,550 |
| **WS-D** | Surviving god files | 7 true + 3 borderline | 4 | ~7,400 tangled |
| **WS-E** | Error-handling bypass | 125 envelope-bypass sites | ~8 | — |
| **WS-F** | Dead code / cruft | ~30 items + 38 empty dirs | ~5 | 800–1,200 |

### The truncated-read lesson — read before trusting any single row

The audit produced one confident **false** BLOCKER (`token=***` "breaking LoRA parsing"); it
was the file-reader redacting `token = token.strip()`. The file parses clean. **Rule for every
agent executing a ticket: never act on a `***`/`...` in a quoted line, or a "syntax error /
corruption" claim, without re-reading the real file (`python3 -c "import ast; ast.parse(...)"`
or `grep -n`).** The inventories are research aids, not ground truth — the ticket scoping in
this master plan is the contract.

### Already verified true (correctness, not just aesthetics)

- `tests/core/util/test_secrets.py:14` imports `astrid.utilities.llm_clients` → **ModuleNotFoundError**. Broken test import. *(WS-F)*
- `packs/video_editing/executors/cut/probe.py` raises `SystemExit` **8×** and is `from . import probe`'d by `run.py` → library code that kills the caller's process. *(WS-E)*
- `editorial/executors/script_pipeline/run.py` has **0** `guard_canonical_entrypoint` calls (+ 2 training orchestrators per WS-A). *(WS-A)*
- `SENSITIVE_ARG_NAMES` (`project/run.py:35`), duplicate `from __future__` (`editorial/refine/run.py:5-6`), `IMAGE_FEATURES` ghost constant — all confirmed dead. *(WS-F)*

## Guiding principles for execution

1. **One ticket, one agent, one pass.** Tickets are sized for a single subagent to complete
   and self-verify in one run. Work the **Global backlog** (below) top-to-bottom.
2. **Behavior-preserving by default.** This is a beauty/dedup pass. Each ticket ends green on
   the existing suite. WS-E is the one place behavior (exception *type*) changes — it carries
   explicit compatibility callouts.
3. **The facade namespace is a test contract.** ~200 tests `mock.patch("astrid.core.<pkg>.<facade>.<name>")`.
   Refactors must **keep the facade re-exports working** and add a real `_shared.py` underneath —
   never move a name *out* of a patched facade path. This gates WS-B/C/D's risky tickets behind
   **P0-1 (the monkeypatch-contract audit)**.
4. **Preserve the foundations** (see §Do not touch) — refactors move *toward* them.
5. **Verify before you delete.** Dead-code removals require a tree-wide grep proving zero
   callers/patchers, pasted into the ticket's evidence.
6. **Serialize tree writes.** One implementation agent at a time on the live tree (or isolated
   worktrees); never two writers at once. Research agents were read-only.

---

## Workstreams

Each workstream's full instance table is in its inventory appendix; here is the scope, the
deploy-ready tickets, and the cross-impact that drives sequencing.

### WS-A · Pack-executor copy-paste → shared scaffold
**[Full inventory →](beauty-v2/inventories/A1-pack-copypaste.md)** · biggest LOC win (900–1,200).
68 executor/orchestrator `run.py` files; runpod's `_common.py`+thin-wrapper is the lone exemplar.
- **35** hand-rolled result-manifest dicts vs **2** using core `build_manifest`; 2 local `_build_manifest` shadows (`generate_image/video`, schema v2 vs core v1).
- **7** `_die()` copies, **2 incompatible types** (`SystemExit` in `boundary_candidates` vs `AstridError` elsewhere).
- **2** competing architectures: 21 `run_pack_main(_run)` closure-style vs 42 bare `def main()`.
- 3 files missing the entrypoint guard (`script_pipeline`, `dataset_build`, `training_run`).

| Ticket | Scope | Risk |
|---|---|---|
| **A-T1** | Additive: add `schema_version` kwarg to core `build_manifest`; create canonical `pack_die` *(merge with E-T1 — same module)* | zero |
| **A-T2** | Retrofit `understanding` pack (4 execs): manifest dicts → `build_manifest`, shared dry-run helper, `_die`→`pack_die` | low |
| **A-T3** | `editorial/_common.py`: hoist `load_api_key` from `transcribe`, fix `editor_review`/`refine` sibling imports | med |
| **A-T4** | Retrofit remaining editorial execs; fix `script_pipeline` shadow `write_manifest` + missing guard | med |
| **A-T5** | `generation/_common.py`: unify `generate_image`/`generate_video` `_build_manifest` via `build_manifest(schema_version=2)` | med |
| **A-T6** | `_common.py` for media/foley/rendering/training (one ticket per pack, independent) | med |
| **A-T7** | Core `@pack_entrypoint('pack.action')` decorator; migrate all 63 guard sites + unify the 2 architectures *(do last)* | high |

*Cross-impact:* `_die` split → **WS-E**; sibling `load_api_key` imports must change atomically; manifest schema v1↔v2 gap; `run_pack_main` `_run` is a test monkeypatch seam.

### WS-B · Executor / Orchestrator / SDK twin duplication
**[Full inventory →](beauty-v2/inventories/A2-exec-orch-sdk-twins.md)** · 56 twins, ~1,600 LOC.
The natural shared homes **already exist**: `contracts/capability_runner.py` (the `CapabilityRunner`
ABC, currently skeleton-only) and `contracts/schema.py` (shared `Port`/`Output`/`CapabilityHandle`).
Includes the private-import leak `orchestrator/runner.py:18 import _has_value,_stringify_value` and
100%-identical CLI helpers (`_eprint`, `_aliases_text`, `_require_qualified_id`, …).

| Ticket | Scope | Risk |
|---|---|---|
| **B-T1** | Create `contracts/_capability_common.py`; move pure leaf helpers (`_PLACEHOLDER_RE`,`_has_value`,`_stringify_value`,`_eprint`,`_gateway_resolved_project`,`_require_qualified_id`,`_aliases_text`,`_print_ports`,`_banodoco_config_from_args`); **kill the private cross-imports** | low |
| **B-T2** | Move parse/validate helpers (`_parse_cache`,`_parse_isolation`,`_validate_*`,`_definition_pack_id`,`_filter_by_pack`,`_definition_content_root`) to shared | low-med |
| **B-T3** | Collapse `to_capability_handle` into one protocol-based fn in `contracts/schema.py` (add `HasCapabilityFields` protocol) | med |
| **B-T4** | Collapse SDK `_capability_from_executor/orchestrator` + `_resolve_*` into parameterized fns | low |
| **B-T5** | Extract shared runner impl (`_expand_placeholders`,`_validate_required_inputs`,`_output_value`) into the `CapabilityRunner` base via template-method | high (test-coupled) |
| **B-T6** | Table-drive CLI `_cmd_override/dirty/update/list/search` parameterized by component type | high (integration-tested) |

*Cross-impact:* B-T5 touches the runner classes **WS-C**'s monkeypatch seams bolt onto — gated by **P0-1**. SDK collapse (B-T4) ties into `discovery.py` god-file split (**WS-D**).

### WS-C · Circular-facade "fake splits"
**[Full inventory →](beauty-v2/inventories/A3-circular-facades.md)** · 70 sites across 7 clusters
(session, task, pack/install, pack/cli, gateway, **timeline** — 45 back-imports, theme/__init__).
Fix shape: extract genuinely-shared helpers into a module-level `_shared.py` imported by *both*
the facade and the leaves; **keep the facade re-exports** for the test contract.

| Ticket | Scope | Risk |
|---|---|---|
| **C-T1** | Remove dead `_gateway_project`/`_gateway_wait` *(== F-T2 — single ticket)* | zero |
| **C-T2** | Task `operator_view↔operator_render`: move 3 helpers to `operator_render`, drop lazy import (1 cross-link) | low |
| **C-T3** | `session/_shared.py` extraction (14 lazy sites) — **after P0-1** | high |
| **C-T4** | `timeline/_shared.py` extraction (45 lazy sites, `_require_session`) — **after P0-1**, apply C-T3 lessons | highest |
| **C-T5** | `pack/install` barrel collapse (13 lazy sites) — **after P0-1** | high |
| **C-T6** | `pack/cli` facade: move `_pack_payload`/`_print_taxonomy_block` to `cli_basic`/`_shared` (5 sites) | med |
| **C-T7** | `gateway/dispatch.py` → promote 4 session-CLI late imports to module level if no real cycle | low |

*Cross-impact:* `_require_session` (45×) overlaps **WS-B**'s helper-extraction philosophy; every cluster gated by the test-contract audit **P0-1**. Dead imports overlap **WS-F**.

### WS-D · Surviving god files & table-driven collapses
**[Full inventory →](beauty-v2/inventories/A4-god-files.md)** · 7 true god files.
`pack/__init__.py` (1171L, imported by 15+ modules), `inverses.py` (979L / 25 fns — **table-collapse
candidate, ~600→120L**), `banodoco_schema.py` (1067L, types+6 validators), `cli_parser.py` (866L
pure argparse), `executor/cli.py` (967L), `project/cli.py` (1030L), `install_local.py` (1041L).
Model for collapses: `projection.py:569`'s declarative `_DISPATCH`.

| Ticket | Scope | Risk |
|---|---|---|
| **D-T1** | Collapse `inverses.py` 25 fns → declarative `_INVERSE_TABLE` (behavior-preserving) — **sync event-kinds with `projection.py`** | low |
| **D-T2** | Extract `banodoco_schema.py` validators → `validators/{timeline,pool,arrangement,metadata,registry}.py`; **TypedDicts stay put** (circular-import risk) | med |
| **D-T3** | `executor/cli.py`: handlers → `cli_handlers.py`, `build_parser` → table-driven | med |
| **D-T4** | `project/cli.py`: same split | med |
| **D-T5** | `cli_parser.py` (timeline): 829-line `build_parser` → `_COMMANDS` table; **preserve `.cli` monkeypatch indirection** | med (after P0-1) |
| **D-T6** | Split `pack/__init__.py` → `registry/definition/manifest/walkers/permissions`; keep `__init__` as facade | high |
| **D-T7** | Split `pack/install_local.py` → `install/uninstall/update/rollback` + `_diff.py` | med |

*Cross-impact:* D-T1 must share the event-kind enumeration with `projection.py` to prevent drift. D-T6 touches the public surface **WS-A/C** import. D-T3 overlaps **WS-B-T6** (both touch `executor/cli.py` `_cmd_*`) — **sequence B-T6 and D-T3 together or back-to-back to avoid conflicts.**

### WS-E · Error-handling canonicalization
**[Full inventory →](beauty-v2/inventories/A5-error-handling.md)** · 125 envelope-bypass sites.
**15 in core/** (`http.py` ×7, `secrets.py`, `llm_clients.py`, `install_trust.py` ×2, …), plus 9
`FileNotFoundError`/3 `FileExistsError`/3 `OSError` on core paths; `ProjectError` discards
envelope fields; ~30 packs run bare `main()` (no `run_pack_main` fallback). Several are real
correctness bugs (`probe.py` SystemExit re-exported).

| Ticket | Scope | Risk |
|---|---|---|
| **E-T1** | Canonical `pack_die`/`_die` in `core/contracts` raising `AstridError`; migrate 7 copies + fix `boundary_candidates` `SystemExit` outlier + sprite_sheet cross-import *(merge with A-T1)* | zero |
| **E-T2** | Fix `ProjectError.__init__` to forward `valid_options`/`recovery_command`/`state_snapshot` (additive) | zero |
| **E-T3** | Convert 15 core `SystemExit` → `AstridError`; add `SystemExit` trap in `run_pack_main` for a deprecation window | med (test-coupled) |
| **E-T4** | Convert core `FileNotFoundError`/`FileExistsError`/`OSError` (15 sites) → `AstridError` w/ recovery hints | med |
| **E-T5** | Universal `run_pack_main` adoption across ~30 bare-main packs *(folds into A-T7)* | low/file |
| **E-T6** | Convert pack **library-function** `SystemExit` (`probe.py` ×8 + `asset_cache` clone ×7 + registry/resume/…) → `AstridError`; leave `main()`-body exits as CLI-valid | med |

*Cross-impact:* `_die` consolidation == **A-T1**; `http.py` change hits the secret-scrubbing monkeypatch seam; `probe.py`/`asset_cache` are copy-paste twins (**WS-A**); E-T5 folds into **A-T7**.

### WS-F · Dead code, cruft & cosmetic rot (quick wins)
**[Full inventory →](beauty-v2/inventories/A6-cruft.md)** · mechanical, mostly zero-risk; good warm-up.
4 dead constants, 2 dead imports, 1 self-assignment, 1 dup import, 1 commented stub, **17
copy-paste one-line delegates** (7×`_utc_now`, 3×`_read_env_value`, 3×`_candidate_env_files`,
4×`_step_dir`), **38 empty/`.DS_Store`-only dirs**, M4 scaffolding (33 docstrings + 62 inline),
1 broken test import.

| Ticket | Scope | Risk |
|---|---|---|
| **F-T1** | Delete dead constants/no-op/dup-import/commented stub (7 files) | zero |
| **F-T2** | Remove gateway dead imports *(== C-T1)* — verify no `mock.patch` first | zero |
| **F-T3** | Consolidate `_utc_now` → `core/util/time.py` (8 files) | low |
| **F-T4** | Consolidate `_read_env_value`/`_candidate_env_files` → `secrets.py`; **fix broken `test_secrets.py` import** | low |
| **F-T5** | Consolidate `_step_dir` → `core/adapter/_common.py` (5 files) | low |
| **F-T6** | Purge M4 scaffolding comments (33+62 sites) — **do last, high churn / merge risk** | low |
| **F-T7** | Remove 38 empty dirs after auditing `discover_packs` references; handle `astrid/utilities` after F-T4 | low |

*Cross-impact:* delegate consolidation overlaps **WS-A** (`load_api_key` family) and the executors in **WS-D**; `astrid/utilities` removal gated by F-T4's test-import fix.

---

## Cross-impact map (synthesis)

The single dominant collision across **WS-B, WS-C, WS-D, WS-E** is the **monkeypatch / facade
test contract**. It is promoted to a foundational ticket **P0-1**: produce
`docs/beauty-v2/monkeypatch-contracts.md` enumerating every `mock.patch("astrid.core.<pkg>...")`
and `monkeypatch.setattr(<module>, ...)` target, so every later refactor knows which symbol
paths must keep resolving. Other concrete collisions, deduped into single tickets:

- **Gateway dead imports**: WS-C-T1 ≡ WS-F-T2 → **one ticket**.
- **Canonical `_die`/`pack_die`**: WS-A-T1 ≡ WS-E-T1 → **one ticket** (`core/contracts`).
- **Universal `run_pack_main`**: WS-E-T5 folds into **WS-A-T7**.
- **`probe.py`/`asset_cache` SystemExit**: WS-E-T6 fixes a WS-A copy-paste twin in one pass.
- **`executor/cli.py` `_cmd_*`**: WS-B-T6 (table-drive) and WS-D-T3 (handler-extract) both edit
  it → **schedule adjacent**, B-T6 then D-T3.
- **`inverses.py` ↔ `projection.py`**: D-T1 must reuse projection's event-kind enumeration.
- **`_require_session` (45×, WS-C-T4)** and **WS-B helper extraction** share the "shared-module"
  philosophy — same review pattern, do C after B's pattern is proven.

## Global backlog (deduped, dependency-ordered)

Work top-to-bottom. Each row = one agent. `⟂` = independent (parallelizable across worktrees if
ever desired, but default to serial). Phase gates are hard.

**Phase 0 — Foundations (unblock everything)**
1. **P0-1** Monkeypatch-contract audit → `docs/beauty-v2/monkeypatch-contracts.md`. *(read-only; gates all "after P0-1" tickets)*
2. **P0-2** Canonical `_die`/`pack_die` + `build_manifest(schema_version=)` *(A-T1 + E-T1)* ⟂
3. **P0-3** `ProjectError` envelope fix *(E-T2)* ⟂

**Phase 1 — Safe wins & behavior-preserving collapses** *(all low/zero risk, immediate score lift)*
4. **P1-1** Dead constants/no-op/dup-import/commented stub *(F-T1)* ⟂
5. **P1-2** Gateway dead imports *(F-T2 ≡ C-T1)* ⟂
6. **P1-3** `inverses.py` → table *(D-T1; sync with projection)* ⟂
7. **P1-4** `_utc_now` consolidation *(F-T3)* ⟂
8. **P1-5** `_read_env_value`/`_candidate_env_files` + fix broken test import *(F-T4)* ⟂
9. **P1-6** `_step_dir` consolidation *(F-T5)* ⟂
10. **P1-7** Task `operator_view↔render` cycle break *(C-T2)* ⟂

**Phase 2 — Twin dedup into existing shared homes** *(WS-B, mostly low-risk)*
11. **P2-1** `_capability_common.py` leaf helpers + kill private cross-imports *(B-T1)*
12. **P2-2** Shared parse/validate helpers *(B-T2)*
13. **P2-3** `to_capability_handle` protocol collapse *(B-T3)*
14. **P2-4** SDK `_capability_from_*` / `_resolve_*` collapse *(B-T4)*

**Phase 3 — Pack scaffold rollout** *(WS-A; per-pack, serial)*
15. **P3-1** understanding pack *(A-T2)*
16. **P3-2** editorial `_common.py` + sibling imports *(A-T3)*
17. **P3-3** editorial retrofit + `script_pipeline` fixes *(A-T4)*
18. **P3-4** generation `_common.py` (schema v2) *(A-T5)*
19. **P3-5** media/foley/rendering/training `_common.py` *(A-T6, one per pack)*

**Phase 4 — Error envelope** *(WS-E; behavior change, compat windows)*
20. **P4-1** Core `SystemExit` → `AstridError` *(E-T3)*
21. **P4-2** Core `FileNotFoundError`/`FileExistsError`/`OSError` → `AstridError` *(E-T4)*
22. **P4-3** Pack library-function `SystemExit` incl. `probe.py`/`asset_cache` *(E-T6)*

**Phase 5 — God-file splits & table-driven CLIs** *(after P0-1; highest structural risk)*
23. **P5-1** `banodoco_schema` validators split *(D-T2)*
24. **P5-2** `executor/cli.py` handler extract + CLI table-drive *(D-T3 with B-T6)*
25. **P5-3** `project/cli.py` split *(D-T4)*
26. **P5-4** timeline `cli_parser.py` table *(D-T5)*
27. **P5-5** `pack/__init__.py` split *(D-T6)*
28. **P5-6** `pack/install_local.py` split *(D-T7)*

**Phase 6 — Facade cycle breaks** *(after P0-1; needs the contract map)*
29. **P6-1** `session/_shared.py` *(C-T3)*
30. **P6-2** `timeline/_shared.py` *(C-T4)*
31. **P6-3** `pack/install` barrel collapse *(C-T5)*
32. **P6-4** `pack/cli` facade *(C-T6)*
33. **P6-5** `gateway/dispatch` decouple *(C-T7)*

**Phase 7 — Final sweeps** *(highest churn; do last to avoid conflicts)*
34. **P7-1** Core `@pack_entrypoint` + universal `run_pack_main` + unify architectures *(A-T7 + E-T5)*
35. **P7-2** Purge M4 scaffolding comments *(F-T6)*
36. **P7-3** Remove empty dirs incl. `astrid/utilities` *(F-T7)*

> Run each phase to green before starting the next. Within a phase, ⟂ rows are independent;
> non-⟂ rows assume the prior rows in the phase have landed.

## How to deploy a ticket

Per ticket, dispatch one subagent (DeepSeek for mechanical/low-risk, **Claude for high-risk**:
P0-1, B-T5/B-T6, C-T3/T4/T5, D-T6, E-T3) with a self-contained brief:
working dir, the exact files (from the inventory appendix), the verification command
(`pytest <targeted suite>` + `ast.parse`), the cross-impact callout, and the truncated-read rule.
Update this file's backlog row to ☑ when green. Re-run the 10-agent audit at each phase boundary
to watch the median climb.

## Definition of done

- Re-run the 10-agent adversarial beauty audit on the new `main`: **target median ≥ 8/10, no
  slice below 7**; no surviving copy-paste twin, no circular-facade lazy-import, no god file
  >700L mixing 3+ concerns, no envelope-bypassing exception on a library path.
- Full suite green at each phase boundary; the broken `test_secrets.py` import fixed.
- The "Do not touch" foundations intact and demonstrably the pattern every refactored slice
  now matches.

## Do not touch (the reference standard)

- `contracts/errors.py` — `AstridError`/envelope normalization pipeline.
- `timeline/projection.py:569` — declarative dispatch table (the model for D-T1 and CLI tables).
- `task/events.py` — hash-chained append log.
- `generation/backends/base.py` `BackendAdapter` — single-method interface.
- `sdk/exceptions.py`, `sdk/dto.py` — clean hierarchy + honest re-export facade.
- `packs/runpod/executors/_common.py` + thin wrappers — the scaffold pattern WS-A adopts.
- `contracts/run_status.py`, `contracts/schema_validators.py`, `contracts/capability_runner.py`
  (the ABC WS-B fills in).
