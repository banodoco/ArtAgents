# Inventory appendix — A3-circular-facades

_Read-only DeepSeek V4 Pro research against base `2edd0ce`. Verify any functional claim with ast.parse/grep before acting — one claim per audit class has historically been a truncated-read false positive._


---

### Theme: Circular-facade 'fake split' shims
**Scope of the problem:** Six packages across `astrid/core/` were nominally "split" from god files into leaf modules but retain circular dependencies papered over with in-function lazy imports (`# noqa: PLC0415`) and barrel re-exports (`# noqa: E402`). In every case the facade module re-exports names from its leaf children at module level, while the leaf children reach BACK into the facade via in-function imports, creating a bidirectional cycle that only works because Python defers the body-level import until call time. The code comments openly acknowledge this as "monkeypatch seam" preservation. 82 in-function facade-back lazy imports were found across 18 leaf modules, paired with 36 `# noqa: E402` barrel re-export lines across 6 facade modules. Estimated LOC trapped in this pattern: ~1,200 lines of re-exports + ~350 lines of lazy-import boilerplate.

**Complete instance inventory:**

| # | file:line | what | severity |
|---|-----------|------|----------|
| **session/cli.py facade (4 re-export blocks, 14 back-imports)** |
| 1 | session/cli.py:60-67 | Module-level re-export of 7 names from cli_attach | BLOCKER |
| 2 | session/cli.py:73-81 | Module-level re-export of 7 names from cli_sessions | BLOCKER |
| 3 | session/cli.py:85-97 | Module-level re-export of 10 names from cli_status | BLOCKER |
| 4 | session/cli.py:253-256 | Module-level re-export of COMMANDS/build_parser from cli_parser | BLOCKER |
| 5 | session/cli_attach.py:94-103 | In-function `from astrid.core.session.cli import` (8 names) | BLOCKER |
| 6 | session/cli_attach.py:131 | In-function `from astrid.core.session.lifecycle import load_session` | UGLY |
| 7 | session/cli_sessions.py:57-60 | In-function import of NONE_PLACEHOLDER, _list_session_files from cli | BLOCKER |
| 8 | session/cli_sessions.py:88-90 | In-function import of _session_store from cli | BLOCKER |
| 9 | session/cli_sessions.py:172-176 | In-function import of _ensure_identity, _find_reusable_session, _make_bootstrap_session from cli | BLOCKER |
| 10 | session/cli_sessions.py:320-323 | In-function import of _list_session_files, _session_store from cli | BLOCKER |
| 11 | session/cli_status.py:92 | In-function import of _json_mode from cli | BLOCKER |
| 12 | session/cli_status.py:218-222 | In-function import of NONE_PLACEHOLDER + 2 takeover hints from cli | BLOCKER |
| 13 | session/cli_status.py:342-346 | Same as #12, duplicated in _render_bound_status_json | BLOCKER |
| 14 | session/cli_parser.py:22 | In-function import of cmd_attach from .cli | BLOCKER |
| 15 | session/cli_parser.py:58 | In-function import of cmd_sessions_ls from .cli | BLOCKER |
| 16 | session/cli_parser.py:64 | In-function import of cmd_sessions_detach from .cli | BLOCKER |
| 17 | session/cli_parser.py:71 | In-function import of cmd_sessions_takeover from .cli | BLOCKER |
| 18 | session/cli_parser.py:81 | In-function import of cmd_sessions_prune from .cli | BLOCKER |
| 19 | session/cli_parser.py:98 | In-function import of cmd_status from .cli | BLOCKER |
| **task/operator_view.py ↔ operator_render.py (mutual cycle)** |
| 20 | task/operator_view.py:185-208 | Module-level re-export of 22 names from operator_render | BLOCKER |
| 21 | task/operator_render.py:387-391 | In-function import of 3 names from operator_view (to avoid circular dep) | BLOCKER |
| **pack/install.py barrel (4 re-export blocks, 13 back-imports across 3 leaf modules)** |
| 22 | pack/install.py:58-66 | Module-level re-export of 7 trust helpers from install_trust | BLOCKER |
| 23 | pack/install.py:71-79 | Module-level re-export of 8 names from install_local | BLOCKER |
| 24 | pack/install.py:84-93 | Module-level re-export of 8 git helpers from install_git | BLOCKER |
| 25 | pack/install.py:98-107 | Module-level re-export of 8 CLI wrappers from install_cli | BLOCKER |
| 26 | pack/install_local.py:83-90 | In-function import of 7 names from install (install_pack body) | BLOCKER |
| 27 | pack/install_local.py:292-? | In-function import of 3 names from install (uninstall_pack body) | BLOCKER |
| 28 | pack/install_local.py:490 | In-function import of _confirm from install (update_pack body) | BLOCKER |
| 29 | pack/install_local.py:545-? | In-function import of 3 names from install (update_pack second site) | BLOCKER |
| 30 | pack/install_local.py:698 | In-function import of _format_trust_summary from install (rollback_pack) | BLOCKER |
| 31 | pack/install_local.py:712 | In-function import of _update_git_pack from install (update_pack git branch) | BLOCKER |
| 32 | pack/install_local.py:837 | In-function import of _confirm from install (rollback_pack second site) | BLOCKER |
| 33 | pack/install_git.py:336 | In-function import of install_pack from install | BLOCKER |
| 34 | pack/install_git.py:388-392 | In-function import of 3 names from install | BLOCKER |
| 35 | pack/install_cli.py:43 | In-function import of install_pack from install | BLOCKER |
| 36 | pack/install_cli.py:78 | In-function import of update_pack from install | BLOCKER |
| 37 | pack/install_cli.py:93 | In-function import of uninstall_pack from install | BLOCKER |
| 38 | pack/install_cli.py:105 | In-function import of rollback_pack from install | BLOCKER |
| **pack/cli.py facade (4 re-export blocks, 5 back-imports)** |
| 39 | pack/cli.py:30 | Module-level re-export of build_parser, _add_taxonomy_filter_args from cli_parser | UGLY |
| 40 | pack/cli.py:31-56 | Module-level re-export of 22 names from cli_basic | UGLY |
| 41 | pack/cli.py:57-70 | Module-level re-export of 13 names from cli_inspect | UGLY |
| 42 | pack/cli.py:71-77 | Module-level re-export of 6 names from cli_search | UGLY |
| 43 | pack/cli_parser.py:48-60 | In-function import of 10 handler names from .cli | UGLY |
| 44 | pack/cli_inspect.py:588 | In-function import of _print_taxonomy_block from .cli | UGLY |
| 45 | pack/cli_inspect.py:775 | In-function import of 3 names from .cli | UGLY |
| 46 | pack/cli_basic.py:456 | In-function import of _pack_payload from .cli | UGLY |
| 47 | pack/cli_basic.py:470 | In-function import of _pack_payload from .cli (duplicate) | UGLY |
| **gateway/__init__.py facade (68-line re-export block, 2 dead imports)** |
| 48 | gateway/__init__.py:37-39 | Module-level import of dispatch/project/wait as _gateway_* aliases | UGLY |
| 49 | gateway/__init__.py:38 | DEAD: `from . import project as _gateway_project` — never referenced | BLOCKER |
| 50 | gateway/__init__.py:39 | DEAD: `from . import wait as _gateway_wait` — never referenced | BLOCKER |
| 51 | gateway/__init__.py:40-108 | 68-line barrel re-export of 47 names from project/help/wait/dispatch | BLOCKER |
| 52 | gateway/project.py:232 | In-function `from astrid.core.gateway import _dispatch` | BLOCKER |
| 53 | gateway/project.py:238 | Same in-function import, duplicated in try/finally block | BLOCKER |
| 54 | gateway/dispatch.py:85 | In-function import from session/cli.py (build_parser, cmd_attach) | UGLY |
| 55 | gateway/dispatch.py:98-99 | In-function import from session/cli.py (build_parser, cmd_status) | UGLY |
| 56 | gateway/dispatch.py:388-393 | In-function import of 4 session CLI names | UGLY |
| **timeline/cli.py facade (6 re-export blocks, 45 back-imports across 6 leaf modules)** |
| 57 | timeline/cli.py:54 | Module-level re-export of build_parser from cli_parser | BLOCKER |
| 58 | timeline/cli.py:192-201 | Module-level re-export of 9 cmd_* names from cli_crud | BLOCKER |
| 59 | timeline/cli.py:202-205 | Module-level re-export of cmd_cost, cmd_export from cli_output | BLOCKER |
| 60 | timeline/cli.py:206-229 | Module-level re-export of 22 cmd_* names from cli_edits | BLOCKER |
| 61 | timeline/cli.py:230-241 | Module-level re-export of 10 names from cli_events | BLOCKER |
| 62 | timeline/cli.py:242-251 | Module-level re-export of 8 cmd_* names from cli_backends | BLOCKER |
| 63 | timeline/cli_parser.py:56-? | In-function import of ~32 handler names from .cli | BLOCKER |
| 64 | timeline/cli_crud.py:67,88,198,223,257,273,312 | 7 in-function imports of _require_session from .cli | BLOCKER |
| 65 | timeline/cli_output.py:33,162 | 2 in-function imports of _require_session from .cli | BLOCKER |
| 66 | timeline/cli_edits.py:45,129,156,179,204,228,253,277,301,325,354,381,411,437,461,493,516,546,572,600,624,652,663 | 23 in-function imports from .cli | BLOCKER |
| 67 | timeline/cli_events.py:259,323,437,583,651 | 5 in-function imports of _require_session from .cli | BLOCKER |
| 68 | timeline/cli_backends.py:25,112,156,193,346,476,595 | 7 in-function imports of _require_session/_timeline_actor_from_session from .cli | BLOCKER |
| **theme/__init__.py (bottom-of-file circular avoidance)** |
| 69 | theme/__init__.py:89 | `from . import _cli as cli` deferred to bottom to avoid circular import | NIT |
| 70 | theme/_cli.py:8 | Module-level import from `astrid.core.theme` (the __init__ that defers back) | NIT |

**Root cause:** During the M4 "giant-file decomposition" epic, command handlers and helpers were physically moved into leaf modules (cli_attach, cli_status, operator_render, install_local, cli_parser, etc.), but tests and runtime code continued to reference the original facade namespace (`astrid.core.session.cli.cmd_attach`, `astrid.core.task.operator_view.render_step_instructions`, `astrid.core.pack.install.install_pack`). Rather than updating callers or introducing a shared `_helpers.py` module for the genuinely-shared utilities, the split preserved the facade as a re-export barrel and had leaf modules lazily reach back into it. The comments explicitly state this is intentional: "late import to preserve monkeypatch seams." The shared functions (`_ensure_identity`, `_json_mode`, `NONE_PLACEHOLDER`, `_require_session`, `_format_trust_summary`, `_path_tuple_from_event`) reside in the facade simply because that's where they've always lived — nobody stopped to ask where they *should* live.

**Cross-impact:**
- **Theme 1 (duplicated/leaky helpers):** The `_require_session` helper duplicated 45× across timeline leaf modules via lazy imports from cli.py is a close cousin — if theme-1 fixes move `_require_session` to a shared `_session_gate.py`, every one of these 45 lazy imports must be updated simultaneously.
- **Theme 3 (test monkeypatch contracts):** All 82 lazy imports cite "monkeypatch seam" as justification. Fixing this theme requires updating ~200+ test files that `mock.patch("astrid.core.session.cli.cmd_attach")` or `mock.patch("astrid.core.pack.install._confirm")` — the test surface is contract-locked to the facade module path.
- **Theme 5 (dead code / unused imports):** The `_gateway_project` and `_gateway_wait` dead imports (instances #49-50) overlap directly. The 68-line gateway barrel re-export block likely contains additional unused re-exports.
- **gateway/dispatch.py:** Its 4 late imports from `session/cli.py` are not technically circular (dispatch doesn't re-export into session) but are architecturally identical — the dispatch module should not know about session CLI internals.
- **install_git.py ↔ install_trust.py:** These leaf modules both import from `install.py` barrel, which re-exports from both — forming a transitive circularity through the barrel.

**Proposed fix approach:** For each facade-and-leaves cluster, extract the genuinely-shared helpers into a `_shared.py` or `_helpers.py` module that is imported at module level by BOTH the facade and all leaf modules. The facade retains only thin re-exports for backward compatibility (deprecated with a warnings period). Example for session: create `session/_shared.py` containing `_ensure_identity`, `_json_mode`, `NONE_PLACEHOLDER`, `_list_session_files`, `_session_store`, `_find_reusable_session`, `_make_bootstrap_session`, `_is_target_warm`, `TAKEOVER_HINT_READER`, `TAKEOVER_HINT_ORPHAN`. `cli.py`, `cli_attach.py`, `cli_sessions.py`, `cli_status.py` all import from `_shared.py` at module level. The facade `cli.py` continues to re-export for backward compat but the cycle is broken.

**Sequencing & risk:**
1. **Highest risk:** `session/cli.py` and `pack/install.py` — these have the most test monkeypatch contracts. Must add deprecation shims; cannot remove names from the facade namespace.
2. **Independent:** `task/operator_view.py ↔ operator_render.py` (only 1 cross-link, small blast radius), `theme/__init__.py` (2 lines, NIT severity), `gateway/__init__.py` dead imports (safe to remove).
3. **Must sequence after test audit:** All clusters require a test grep pass to identify every `mock.patch("astrid.core.<pkg>.<facade>.<name>")` reference before making changes.
4. **Safe first step:** Remove the 2 dead `_gateway_project`/`_gateway_wait` imports — zero risk, verifiable with `ast.parse`.

**Suggested tickets (one-agent-each, sequential):**

**T1 — Gateway dead imports removal:** Remove `_gateway_project` (line 38) and `_gateway_wait` (line 39) from `gateway/__init__.py`. Verify with `python3 -c "import ast; ast.parse(open('astrid/core/gateway/__init__.py').read())"` and full test suite. Risk: zero.

**T2 — Task operator_view/operator_render cycle break:** Move `_path_tuple_from_event`, `_inline_failure_tail`, `_format_inline_failure_tail` from `operator_view.py` into `operator_render.py` (they are only used there, imported lazily at line 387). Remove the lazy import. Verify 22-name re-export block still works. Risk: low (3 moved functions, 1 call site).

**T3 — Session _shared.py extraction:** Create `session/_shared.py`. Move `_ensure_identity`, `_json_mode`, `NONE_PLACEHOLDER`, `_list_session_files`, `_session_store`, `_find_reusable_session`, `_make_bootstrap_session`, `_is_target_warm`, `TAKEOVER_HINT_READER`, `TAKEOVER_HINT_ORPHAN`, `_emit_notice` from `cli.py` into it. Update all 4 leaf modules + cli.py to import from `_shared.py` at module level. Add backward-compat re-exports in `cli.py`. Risk: HIGH (14 lazy-import sites + ~50+ test monkeypatch references). Must be done with grep audit first.

**T4 — Timeline _shared.py extraction:** Create `timeline/_shared.py`. Move `_require_session`, `_timeline_actor_from_session`, `_SESSION_GATE_HINT` from `cli.py` into it. Update all 6 leaf modules (45 lazy-import sites) to import from `_shared.py`. Risk: HIGHEST (45 sites, largest blast radius). Sequence after T3 to apply lessons learned.

**T5 — Pack install barrel collapse:** Merge `install_trust.py` back into `install.py` (trust helpers are small and always imported together). Move genuinely-reusable helpers (`_confirm`, `_format_trust_summary`) into a lightweight `install/_helpers.py`. Update `install_local.py` (7 sites), `install_git.py` (2 sites), `install_cli.py` (4 sites) to import directly from `_helpers.py` or their actual source module rather than through the `install.py` barrel. Risk: HIGH (13 lazy-import sites + test monkeypatch contracts).

**T6 — Pack cli.py facade cleanup:** Move `_pack_payload`, `_pack_taxonomy`, `_print_taxonomy_block` into `cli_basic.py` or a new `cli/_shared.py`. Update `cli_inspect.py` (2 sites) and `cli_basic.py` (2 sites) to stop importing from `.cli`. Risk: MEDIUM (5 sites, narrower test surface).

**T7 — Gateway dispatch decoupling:** Audit the 4 late imports in `gateway/dispatch.py` from `session/cli.py`. Either promote to module-level (if no actual cycle exists) or route through a protocol/interface. Risk: LOW (no cycle, just bad layering).