# Inventory appendix — A4-god-files

_Read-only DeepSeek V4 Pro research against base `2edd0ce`. Verify any functional claim with ast.parse/grep before acting — one claim per audit class has historically been a truncated-read false positive._

### Theme: God files mixing 3+ distinct concerns

**Scope of the problem:** Across the ~118k LOC Astrid codebase, 7 files above 700 lines qualify as true god files (mixing 3+ distinct responsibilities), with 3 more being borderline. Combined, these files represent ~7,400 LOC where concerns are tangled. Two structural anti-patterns dominate: (a) monolithic CLI modules that embed argparse construction alongside command-handler logic, and (b) hand-written function families (25 near-identical inverse planners, 6 validation subdomains in one file) where a table-driven collapse à la `projection.py:569` would eliminate 40–60% of the code. The remaining ~27 files >700 lines earn their size legitimately (pure TypedDict suites, single-domain validators, executor runners).

**Complete instance inventory:**

| # | file:line | what | severity |
|---|-----------|------|----------|
| 1 | `astrid/core/pack/__init__.py` (entire, 1171L) | 6 concerns fused: ElementKindRegistry (L70–244), PackDefinition dataclass (L366–424), manifest parser (L477–540, L1032–1056), flat-YAML parser (L1058–1091), path walkers (L426–1010), permission normalizers (L600–685) | BLOCKER |
| 2 | `astrid/core/timeline/inverses.py` (entire, 979L) | 25 hand-written `_inverse_*` fns (L132–839, 596L total) + dispatch table (L108–124) + InverseRequest dataclass (L59–86) + plan_inverse/plan_inverses orchestration (L847–958) — decorator-registered instead of table-driven | BLOCKER |
| 3 | `astrid/core/timeline/banodoco_schema.py` (entire, 1067L) | 37 TypedDicts (L47–364) + fallback stub TypedDicts for missing import (L47–133) + 6 validation domains: timeline (L724–800), pool (L845–910), arrangement (L959–1067), metadata (L802–819), registry (L697–722), clip transitions (L649–678) + effect/animation ID registries (L522–537) | BLOCKER |
| 4 | `astrid/core/timeline/cli_parser.py` (entire, 866L) | `build_parser()` is 829 lines of repetitive argparse construction (L38–866) with 210 `add_argument`/`add_parser` calls for ~40 subcommands; 0 handler logic — pure boilerplate | UGLY |
| 5 | `astrid/core/executor/cli.py` (entire, 967L) | `build_parser()` (L67–217, 12 subcommands) + 12 command handlers (`_cmd_fork`, `_cmd_new`, `_cmd_list`, `_cmd_search`, `_cmd_inspect`, `_cmd_validate`, `_cmd_install`, `_cmd_run`, `_cmd_override`, `_cmd_dirty`, `_cmd_update`, `_cmd_*`) + gateway resolution (L687–701) + formatting helpers (L810–870) | BLOCKER |
| 6 | `astrid/core/project/cli.py` (entire, 1030L) | `build_parser()` (L78–215, 9 subcommands) + 9 command handlers (`_cmd_create`, `_cmd_ls`, `_cmd_default`, `_cmd_theme`, `_cmd_show`, `_cmd_source_add`, `_cmd_register_source`, `_cmd_list`, `_cmd_edit`) + OpsHelperResponse TypedDict (L62) + cost-merging (L935–955) + JSON printing (L1029) | BLOCKER |
| 7 | `astrid/core/pack/install_local.py` (1041L) | 4 major lifecycle operations: `install_pack` (L36–272), `uninstall_pack` (L468–514), `update_pack` (L670–804), `rollback_pack` (L811–1041) + `_diff_component_inventories` (L650–668) + `_format_update_diff` (L521–648). Each is substantial enough to be its own module | UGLY |

**Borderline (large but single-concern, not true god files):**
| # | file:line | what | severity |
|---|-----------|------|----------|
| B1 | `astrid/core/task/plan.py` (949L) | Task plan parsing + validation — cohesive pipeline, earned size | NIT |
| B2 | `astrid/core/task/operator_view.py` (941L) | Operator status display — 2 commands (`cmd_status`, `cmd_next`) but cohesive domain | NIT |
| B3 | `astrid/core/project/run.py` (774L) | Project run lifecycle — single concern, earned size | NIT |

**Root cause:** The M4 giant-file split moved command handlers out of monolithic CLI files but left `build_parser()` and handler logic colocated in the new modules (`executor/cli.py`, `project/cli.py`) — a half-split. Meanwhile, `inverses.py` and `banodoco_schema.py` grew organically via copy-paste (each new event kind → new `_inverse_*` function; each new validation domain → new `validate_*` function in the same file). The `projection.py:569` `_DISPATCH` table shows the team already knows the right pattern — it just wasn't back-applied to sibling modules.

**Cross-impact (READ CAREFULLY):**
- **inverses.py ↔ projection.py collision:** Both maintain per-event-kind dispatch. `projection.py:569` uses a declarative `_DISPATCH` table; `inverses.py` uses decorator-based `_register`. If inverses is collapsed to a table-driven pattern, the two tables should share the same event-kind enumeration to avoid drift. Any refactor of inverses MUST sync with projection's dispatch entries.
- **cli_parser.py ↔ cli.py (timeline) monkeypatch seam:** `cli_parser.py:38–108` documents a critical compatibility case: all command handlers are imported through the `.cli` facade (not canonical modules) to preserve `monkeypatch.setattr(timeline_cli, "cmd_ls", fake)` compatibility for ~50+ tests. Any split of `cli_parser.py` must preserve this indirection or coordinate with test migration (theme: monkeypatch seams).
- **executor/cli.py ↔ executor/runner.py:** `executor/cli.py:_cmd_run` (L594) calls `run_executor` from `runner.py`. Moving handler logic out of `cli.py` must not break this import chain.
- **pack/__init__.py ↔ install_local.py ↔ cli_inspect.py:** These three form a pack-management triad. Splitting `__init__.py` touches the public API surface that `install_local.py` and `cli_inspect.py` import heavily. `PackDefinition`, `ElementKindRegistry`, and `discover_packs` are imported by 15+ modules across the tree.
- **banodoco_schema.py ↔ projection.py ↔ inverses.py:** All three import from `banodoco_schema.py`. Splitting its validators into submodules may create circular imports (validators import TypedDicts, which live in the same file today).

**Proposed fix approach:**

1. **pack/__init__.py** → split into `pack/registry.py` (ElementKindRegistry + ElementKindDescriptor), `pack/definition.py` (PackDefinition + PackPermission), `pack/manifest.py` (YAML/JSON loading + flat-YAML parser), `pack/walkers.py` (path walkers), `pack/permissions.py` (permission normalizers). Re-export from `__init__.py` for backward compatibility.

2. **inverses.py** → collapse 25 `_inverse_*` functions into a declarative `_INVERSE_TABLE: list[tuple[str, Callable[[TimelineEvent, dict, dict], InverseRequest]]]` following `projection.py:569` pattern. 10 of 25 functions are structurally identical (14–17 lines of payload-extract + InverseRequest construction); the remaining 15 differ only in which payload fields they extract. A unified `_build_inverse(kind, inverse_kind, payload_extractor)` factory covers all.

3. **banodoco_schema.py** → extract `validators/timeline.py`, `validators/pool.py`, `validators/arrangement.py`, `validators/metadata.py`, `validators/registry.py`. Keep TypedDicts in `banodoco_schema.py` as the single type authority.

4. **cli_parser.py** → replace 829-line `build_parser()` with a declarative command table: `_COMMANDS: list[CommandDef]` where each `CommandDef` specifies name, help, args list, handler ref. A generic `_build_parser_from_table()` (~50 lines) iterates the table.

5. **executor/cli.py** and **project/cli.py** → extract command handlers into `executor/cli_handlers.py` and `project/cli_handlers.py`; keep `build_parser()` in `cli.py` as a thin table-driven constructor.

**Sequencing & risk:**

- **Highest risk:** `pack/__init__.py` — `PackDefinition` and `discover_packs` are imported by 15+ modules. Must split internally while keeping `__init__.py` as a re-export facade.
- **Contract-locked:** `cli_parser.py`'s monkeypatch indirection through `.cli` must be preserved exactly.
- **Safest first:** `inverses.py` table-driven collapse — pure refactor with identical behavior, no import changes.
- **Independent:** `banodoco_schema.py` validator extraction — no cross-module breakage if TypedDicts stay put.
- **Must sequence before others:** `inverses.py` and `banodoco_schema.py` are independent of each other. `cli_parser.py` table-driven collapse should follow `executor/cli.py` and `project/cli.py` handler extraction to avoid merge conflicts on the CLI files.
- **Safe ordering:** inverses.py → banodoco_schema.py → executor/cli.py + project/cli.py → cli_parser.py → pack/__init__.py → install_local.py.

**Suggested tickets (one-agent-each, sequential):**

- **T1:** Collapse `inverses.py` 25 hand-written inverse functions into a single `_INVERSE_TABLE` declarative map (modeled on `projection.py:569`). Replace `_register` decorator with table iteration. ~600L → ~120L.
- **T2:** Extract `banodoco_schema.py` validators into `validators/timeline.py`, `validators/pool.py`, `validators/arrangement.py`, `validators/metadata.py`, `validators/registry.py`. Keep all 37 TypedDicts in `banodoco_schema.py`. Re-export public validators from `banodoco_schema.py`.
- **T3:** Extract command handlers from `executor/cli.py` into `executor/cli_handlers.py`. Convert `build_parser()` to table-driven construction. Keep `main()` in `cli.py`.
- **T4:** Extract command handlers from `project/cli.py` into `project/cli_handlers.py`. Convert `build_parser()` to table-driven construction. Keep `main()` in `cli.py`.
- **T5:** Replace `cli_parser.py`'s 829-line `build_parser()` with a declarative `_COMMANDS` table. Preserve monkeypatch indirection through `.cli` facade (documented at L38–55).
- **T6:** Split `pack/__init__.py` into `pack/registry.py`, `pack/definition.py`, `pack/manifest.py`, `pack/walkers.py`, `pack/permissions.py`. Keep `__init__.py` as re-export facade. Update all 15+ import sites to use new canonical paths (or defer to re-exports).
- **T7:** Split `pack/install_local.py` into `pack/install.py`, `pack/uninstall.py`, `pack/update.py`, `pack/rollback.py` with shared `pack/_diff.py` for diff helpers.