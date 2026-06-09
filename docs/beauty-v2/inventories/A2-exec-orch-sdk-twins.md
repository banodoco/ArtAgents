# Inventory appendix — A2-exec-orch-sdk-twins

_Read-only DeepSeek V4 Pro research against base `2edd0ce`. Verify any functional claim with ast.parse/grep before acting — one claim per audit class has historically been a truncated-read false positive._


### Theme: Executor/Orchestrator/SDK twin duplication

**Scope of the problem:** Across the three parallel hierarchies (executor, orchestrator, SDK discovery), ~56 duplicated or near-identical functions/constants/classes exist, totaling ~1,600 LOC of copy-paste code. The executor and orchestrator packages each implement near-identical runners, CLI gateways, schema validators, and registry classes whose only meaningful difference is the type name (`ExecutorDefinition` vs `OrchestratorDefinition`). The orchestrator package imports PRIVATE symbols (`_has_value`, `_stringify_value`, `_format_invocation_hint`, `_print_invocation_example`) from the executor package, violating encapsulation. The SDK discovery layer then duplicates both `_capability_from_X` and `_resolve_X_capability` for the two types with ~93% identical bodies.

**Complete instance inventory:**

| # | file:line | what | severity |
|---|-----------|------|----------|
| 1 | executor/schema.py:199, orchestrator/schema.py:95 | `to_capability_handle` — 56/56 lines, 93% identical (only type annotations differ) | BLOCKER |
| 2 | executor/schema.py:195, orchestrator/schema.py:91 | `to_json` — 2/2 lines, 100% identical verbatim copy | UGLY |
| 3 | executor/schema.py:190, orchestrator/schema.py:88 | `to_dict` — ~25% identical (executor pops `external_runtime`) | NIT |
| 4 | executor/schema.py:496, orchestrator/schema.py:317 | `_parse_cache` — 10/10 lines, 100% identical | BLOCKER |
| 5 | executor/schema.py:533, orchestrator/schema.py:329 | `_parse_isolation` — 11/11 lines, 100% identical | BLOCKER |
| 6 | executor/schema.py:614, orchestrator/schema.py:412 | `_validate_cache` — 9/9 lines, 56% identical | UGLY |
| 7 | executor/schema.py:670, orchestrator/schema.py:423 | `_validate_isolation` — 4/4 lines, 75% identical | NIT |
| 8 | executor/schema.py:676, orchestrator/schema.py:432 | `_validate_unique_env_passthrough` — 7/7 lines, 86% identical | UGLY |
| 9 | executor/schema.py:753, orchestrator/schema.py:441 | `_validate_command` — partial overlap (executor validates `input_args` too) | NIT |
| 10 | executor/runner.py:60, orchestrator/runner.py:49 | `_PLACEHOLDER_RE` — identical `re.compile` copy | UGLY |
| 11 | executor/runner.py:1045–1046 | `_has_value` — defined here, **imported by orchestrator/runner.py:18** as private cross-package leak | BLOCKER |
| 12 | executor/runner.py:1112–1117 | `_stringify_value` — defined here, **imported by orchestrator/runner.py:18** as private cross-package leak | BLOCKER |
| 13 | executor/runner.py:995, orchestrator/runner.py:747 | `_validate_required_inputs` — 8/8 lines, 62% identical (only error type differs) | BLOCKER |
| 14 | executor/runner.py:985, orchestrator/runner.py:737 | `_expand_placeholders` — 7/7 lines, 86% identical (only error class differs) | BLOCKER |
| 15 | executor/runner.py:945, orchestrator/runner.py:725 | `_output_value` — 8/10 lines, 60% identical | UGLY |
| 16 | executor/runner.py:850, orchestrator/runner.py:705 | `_command_subprocess_env` — structural twin (executor has extra `_external_pack_pythonpath_env`) | UGLY |
| 17 | executor/runner.py:846, orchestrator/runner.py:676 | `_project_subprocess_env` — identical 2-liner | NIT |
| 18 | executor/runner.py:798, orchestrator/runner.py:649 | `_project_status_for_result` — 6/6 lines, 67% identical | NIT |
| 19 | executor/runner.py:778, orchestrator/runner.py:629 | `_project_argv` — structural twin | UGLY |
| 20 | executor/runner.py:893, orchestrator/runner.py:554 | `_placeholder_values` — structural twin (different default placeholders) | UGLY |
| 21 | executor/runner.py:1035, orchestrator/runner.py:791 | `_request_values` — structural twin (orchestrator adds port defaults) | UGLY |
| 22 | executor/runner.py:752, orchestrator/runner.py:580 | `_prepare_project_request` — structural twin | UGLY |
| 23 | executor/runner.py:829, orchestrator/runner.py:680 | `_resolve_project_request` — structural twin | UGLY |
| 24 | executor/runner.py:839, orchestrator/runner.py:693 | `_prepare_dry_run_request` — structural twin | UGLY |
| 25 | executor/runner.py:522, orchestrator/runner.py:336 | `_run_in_process_*_command` — 64+58 LOC structural twin | UGLY |
| 26 | executor/runner.py:588, orchestrator/runner.py:396 | `_in_process_*_error_result` — 24+19 LOC structural twin | UGLY |
| 27 | executor/runner.py:139, orchestrator/runner.py:153 | `ExecutorCapabilityRunner` / `OrchestratorCapabilityRunner` — 93+65 LOC structural twin classes | UGLY |
| 28 | executor/runner.py:93, orchestrator/runner.py:57 | `ExecuteRunRequest` / `OrchestratorRunRequest` — structural twin dataclasses | NIT |
| 29 | executor/runner.py:806, orchestrator/runner.py:657 | `_finalize_project_*` — structural twin | NIT |
| 30 | executor/cli.py:38, orchestrator/cli.py:41 | `_eprint` — 2/2 lines, 100% identical | UGLY |
| 31 | executor/cli.py:687, orchestrator/cli.py:647 | `_gateway_resolved_project` — 7/7 lines, 100% identical | BLOCKER |
| 32 | executor/cli.py:805, orchestrator/cli.py:669 | `_require_qualified_id` — 3/3 lines, 100% identical | BLOCKER |
| 33 | executor/cli.py:418, orchestrator/cli.py:455 | `_aliases_text` — 19/19 lines, 100% identical | BLOCKER |
| 34 | executor/cli.py:861, orchestrator/cli.py:691 | `_print_ports` — 7/7 lines, 100% identical | UGLY |
| 35 | executor/cli.py:348, orchestrator/cli.py:383 | `_banodoco_config_from_args` — 12/12 lines, 92% identical | UGLY |
| 36 | executor/cli.py:533, orchestrator/cli.py:591 | `_definition_pack_id` — 5/5 lines, 80% identical | NIT |
| 37 | executor/cli.py:540, orchestrator/cli.py:598 | `_filter_by_pack` — 4/4 lines, 75% identical | NIT |
| 38 | executor/cli.py:870, orchestrator/cli.py:700 | `_print_outputs` — 7/7 lines, 57% identical | NIT |
| 39 | executor/cli.py:879, orchestrator/cli.py:709 | `_cmd_override` — 24/24 lines, 71% identical | UGLY |
| 40 | executor/cli.py:905, orchestrator/cli.py:735 | `_cmd_dirty` — 23/23 lines, 52% identical | UGLY |
| 41 | executor/cli.py:930, orchestrator/cli.py:760 | `_cmd_update` — 22/22 lines, 73% identical | UGLY |
| 42 | executor/cli.py:954, orchestrator/cli.py:784 | `_*_content_root` — 10/10 lines, 60% identical | NIT |
| 43 | executor/cli.py:362, orchestrator/cli.py:397 | `_cmd_list` — 27/29 lines, 54% identical | UGLY |
| 44 | executor/cli.py:391, orchestrator/cli.py:428 | `_cmd_search` — 25/25 lines, 80% identical | UGLY |
| 45 | executor/cli.py:457, orchestrator/cli.py:493 | `_cmd_inspect` — 74/96 lines, 27% identical (different runtime display) | NIT |
| 46 | sdk/discovery.py:318, sdk/discovery.py:362 | `_capability_from_executor` / `_capability_from_orchestrator` — 41/41 lines, 93% identical | BLOCKER |
| 47 | sdk/discovery.py:457, sdk/discovery.py:482 | `_resolve_executor_capability` / `_resolve_orchestrator_capability` — 22/22 lines, 68% identical | BLOCKER |
| 48 | orchestrator/cli.py:420 | `_format_invocation_hint` — private import from executor/cli.py | BLOCKER |
| 49 | orchestrator/cli.py:569 | `_print_invocation_example` — private import from executor/cli.py | BLOCKER |
| 50 | orchestrator/cli.py:15 | `BanodocoCatalogConfig` — imported from executor/banodoco_catalog instead of shared location | UGLY |
| 51 | executor/schema.py:366, orchestrator/schema.py:266 | `_parse_port` — 13/12 lines, similar but uses `ExecutorPort` vs `Port` | UGLY |
| 52 | executor/schema.py:381, orchestrator/schema.py:280 | `_parse_output` — 16/14 lines, executor adds `extension` | UGLY |
| 53 | executor/schema.py:591, orchestrator/schema.py:400 | `_validate_port` — executor adds type check | NIT |
| 54 | executor/registry.py:41 | `BUILTIN_STEP_ORDER` — executor-only constant with no orchestrator counterpart | NIT |
| 55 | executor/registry.py, orchestrator/registry.py | Registry class structure — `_resolve_entry`, `_iter_entries`, `get`, `list`, `register`, `fork` methods are structural twins across ~200+ LOC each | UGLY |
| 56 | executor/schema.py:461, orchestrator/schema.py:296 | `_parse_command` — 22/19 lines; executor adds `input_args` parsing | NIT |

**Root cause:** The executor and orchestrator packages were split out of monolithic god files during a cleanup epic, but the split followed a literal file-copy-then-rename pattern rather than extracting shared abstractions. Both packages implement the *same* capability lifecycle (manifest→definition→handle, validate, run, CLI) for different `Definition` types. No shared base class, mixin, or `_capability_common.py` module was created because the split prioritized topological separation over DRY. The orchestrator then reached back into executor internals (`_has_value`, `_stringify_value`, `_format_invocation_hint`) when it needed those helpers, creating a circular-adjacent import dependency.

**Cross-impact:**
- **Theme-2 (monkeypatch seams):** Fixing executor twins directly touches the `ExecutorCapabilityRunner`/`OrchestratorCapabilityRunner` class hierarchy that theme-2's monkeypatch seams bolt onto. Any base-class extraction of these runners must preserve the `CapabilityRunner[Request, Result, Definition]` generic interface that the patch fixtures depend on.
- **astrid/core/contracts/capability_runner.py:** The shared `CapabilityRunner` ABC already exists but only defines the skeleton — the executor/orchestrator subclasses duplicate the *implementation* of each method. Extracting shared implementation into this base class would be the natural fix but requires careful generic typing.
- **astrid/core/contracts/schema.py:** Already holds shared types (`Port`, `Output`, `CapabilityHandle`, `CachePolicy`, etc.) and is the right home for `to_capability_handle` — both executor and orchestrator versions produce *identical* `CapabilityHandle` output from different definition types, so a single protocol-based adapter function could replace both.
- **pack resolution system:** The registry `fork()`, `_attach_pack_metadata`, and `_rewrite_*_manifest_fork` methods in both registry files are structural twins; any shared registry base class must be compatible with the pack discovery/override/alias resolver pipeline.
- **SDK `discovery.py`:** Fixing the `_capability_from_executor/orchestrator` twins directly affects `_resolve_capability_kindless` (line 557) which calls both. A single `_capability_from_definition` with a `capability_type` parameter would collapse both.
- **CLI parser sharing:** The `build_parser()` functions (executor:67, orchestrator:72) share ~80% structure but differ in subcommands (executor has `install`, `validate --check-binaries`; orchestrator has passthrough `--`). Any CLI-sharing approach must handle these divergent subcommands.

**Proposed fix approach:** Three-tier collapse:

1. **Shared constants/helpers → `astrid/core/contracts/_capability_common.py`:** Move `_PLACEHOLDER_RE`, `_has_value`, `_stringify_value`, `_eprint`, `_gateway_resolved_project`, `_require_qualified_id`, `_aliases_text`, `_definition_pack_id`, `_filter_by_pack`, `_require_pack_match`, `_print_ports`, `_print_outputs`, `_banodoco_config_from_args`, `_definition_content_root`, `_parse_input_values` to a single shared module. Both packages import from it.

2. **Schema collapse → protocol/overload on `to_capability_handle`:** Since `ExecutorDefinition` and `OrchestratorDefinition` both produce the same `CapabilityHandle` via identical logic (extract `id.split(".")`, read `metadata`, construct `Provenance`/`SafetyDeclaration`), define a `HasCapabilityFields` protocol (requiring `.id`, `.name`, `.kind`, `.version`, `.description`, `.short_description`, `.keywords`, `.inputs`, `.outputs`, `.isolation`, `.metadata`) and make `to_capability_handle` a single generic function. Move `_parse_cache`, `_parse_isolation`, `_validate_cache`, `_validate_isolation`, `_validate_unique_env_passthrough` to the shared contracts layer.

3. **Runner merge → extract base implementation of `CapabilityRunner`:** Move the common parts of `build_command`, `prepare_project`, `resolve_project_request`, `finalize_project`, `_expand_placeholders`, `_validate_required_inputs`, `_project_argv`, `_placeholder_values` (with a template-method pattern for type-specific differences) into `CapabilityRunner` or a `BaseCapabilityRunner` mixin.

4. **SDK collapse → single `_capability_from_definition`** parameterized by `capability_type: str`.

5. **CLI collapse → table-driven subcommand dispatch:** Factor `_cmd_list`, `_cmd_search`, `_cmd_override`, `_cmd_dirty`, `_cmd_update` into shared implementations parameterized by a `component_type: Literal["executor", "orchestrator"]` string. Keep `_cmd_inspect` and `_cmd_run` separate due to genuinely different output schemas.

**Sequencing & risk:**

- **Phase 1 (low risk, no type changes):** Extract leaf helpers (`_PLACEHOLDER_RE`, `_has_value`, `_stringify_value`, `_eprint`, `_gateway_resolved_project`, `_require_qualified_id`, `_aliases_text`, `_print_ports`, `_banodoco_config_from_args`) into `_capability_common.py`. These are pure functions with no type coupling. Modify imports in both packages. This removes ~200 LOC of duplication and the private-import leaks.
- **Phase 2 (medium risk, type-annotation changes):** Collapse `_parse_cache`, `_parse_isolation`, `_validate_cache`, `_validate_isolation`, `_validate_unique_env_passthrough` into the shared contracts layer. These use only shared types (`CachePolicy`, `IsolationMetadata`).
- **Phase 3 (medium risk, generic type needed):** Collapse `to_capability_handle` into a single protocol-based function. Both definitions share the fields it reads. Requires adding the protocol to `contracts/schema.py`.
- **Phase 4 (higher risk, behavior change):** Extract shared runner implementation. This is the most import-coupled and test-coupled code. The `_placeholder_values`, `_expand_placeholders`, `_validate_required_inputs` functions are the safest to start with. The `CapabilityRunner` subclass merge requires preserving the exact method dispatch order that the monkeypatch seams (theme-2) depend on.
- **Phase 5 (medium risk):** Collapse SDK `_capability_from_executor/orchestrator` and `_resolve_*` into parameterized versions.
- **Phase 6 (higher risk):** Table-drive the CLI `_cmd_*` functions. These are widely tested via integration tests; must preserve exact arg parsing behavior and exit codes.

**Suggested tickets (one-agent-each, sequential):**

**T1:** Create `astrid/core/contracts/_capability_common.py` with `_PLACEHOLDER_RE`, `_has_value`, `_stringify_value`, `_eprint`, `_gateway_resolved_project`, `_require_qualified_id`, `_aliases_text`, `_print_ports`, `_banodoco_config_from_args`. Update imports in executor/runner.py, executor/cli.py, orchestrator/runner.py, orchestrator/cli.py. Remove the private cross-imports (`orchestrator/runner.py:18`, `orchestrator/cli.py:420,569`).

**T2:** Move `_parse_cache`, `_parse_isolation`, `_validate_cache`, `_validate_isolation`, `_validate_unique_env_passthrough`, `_definition_pack_id`, `_filter_by_pack`, `_require_pack_match`, `_definition_content_root` to `_capability_common.py`. Both schema.py and cli.py files import from shared location.

**T3:** Collapse `to_capability_handle` to a single protocol-based function in `contracts/schema.py`. Add `HasCapabilityFields` protocol. Both `executor/schema.py` and `orchestrator/schema.py` re-export it.

**T4:** Collapse `_capability_from_executor`/`_capability_from_orchestrator` and `_resolve_executor_capability`/`_resolve_orchestrator_capability` in `sdk/discovery.py` into single parameterized functions.

**T5:** Extract `_expand_placeholders`, `_validate_required_inputs`, `_output_value` (with template method) into `CapabilityRunner` or a shared mixin. Both runner files delegate to the shared implementation.

**T6:** Table-drive the CLI `_cmd_override`, `_cmd_dirty`, `_cmd_update`, `_cmd_list`, `_cmd_search` into shared implementations parameterized by component type string.