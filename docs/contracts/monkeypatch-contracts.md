# Monkeypatch Contract Surface — Audit & Refactor Guardrails

> **Generated:** 2026-06-09 — read-only audit of `tests/`  
> **Purpose:** Pin every `astrid.core.*` / `astrid.sdk.*` symbol that tests mock, so future
> refactors keep those dotted paths resolving.

## Rules for Refactorers

1. **Any refactor that moves these symbols MUST keep the dotted path resolving.**  
   If you rename a module, re-export the old name from the new location (facade pattern).
2. `mock.patch("dotted.string")` patching requires the *import-time* resolution path, so
   even private re-exports (`from ._impl import X as X`) must be preserved.
3. `monkeypatch.setattr(module_obj, "attr")` pins the attribute *name* on the imported
   module object. The dotted import path of that module object (shown in the "resolves via"
   column) must remain importable.
4. `mock.patch.object(module_obj, "attr")` is the same contract as `setattr` — the module
   object must exist at that import path and must carry that attribute.

---

## 1. session/cli

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.session.paths.astrid_home` | `tests/session/test_session_lifecycle.py` : 46, 67 | `astrid_home` | `monkeypatch.setattr("...", ...)` |
| `astrid.core.session.binding.resolve_current_session` | `tests/agentic/test_agent_probe_regression.py` : 308 | `resolve_current_session` | `monkeypatch.setattr(_binding_mod, ...)` resolves via `from astrid.core.session import binding` |
| `astrid.core.session.binding.resolve_current_session_with_fs_fallback` | `tests/test_pipeline_dispatch_aliases.py` : 31, 54, 87, 121, 139, 154, 172 | `resolve_current_session_with_fs_fallback` | `mock.patch("astrid.core.session.binding.resolve_current_session_with_fs_fallback")` |
| `astrid.core.session.cli` (*module object*) | `tests/session/test_session_cli.py` : 102, 134, 149, 164, 178, 199, 214, 236, 251, 267, 282 | `cmd_attach`, `cmd_sessions_ls`, `cmd_sessions_detach`, `cmd_sessions_takeover`, `cmd_status`, `_list_session_files`, `cmd_sessions_prune` | `monkeypatch.setattr(session_cli, ...)` resolves via `from astrid.core.session import cli` |
| `astrid.core.session.cli` (*module object*) | `tests/session/test_cli_gate.py` : 436 | `cmd_sessions_takeover` | `monkeypatch.setattr(session_cli, ...)` resolves via `from astrid.core.session import cli` |
| `astrid.core.session.cli.attach_session` | `tests/session/test_session_attach_detach.py` : 237, 265 | `attach_session` | `monkeypatch.setattr(cli, ...)` resolves via `from astrid.core.session import cli` |
| `astrid.core.session.cli.SessionStore.iter_sessions` | `tests/session/test_session_attach_detach.py` : 371 | `SessionStore.iter_sessions` | `monkeypatch.setattr(cli.SessionStore, ...)` |
| `astrid.core.session.cli.SessionStore.delete` | `tests/session/test_session_attach_detach.py` : 408 | `SessionStore.delete` | `monkeypatch.setattr(cli.SessionStore, ...)` |
| `astrid.core.session.lifecycle.SessionStore.save` | `tests/session/test_session_lifecycle.py` : 409 | `SessionStore.save` | `monkeypatch.setattr(lifecycle.SessionStore, ...)` |

## 2. pack (read-only)

The retired `pack/install` mutation surface has no supported monkeypatch
contracts. The remaining pack contract below covers only resolver behavior.

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.pack.resolver.resolve_callable_from_metadata` | `tests/test_pipeline_dispatch_aliases.py` : 92 | `resolve_callable_from_metadata` | `mock.patch("astrid.core.pack.resolver.resolve_callable_from_metadata")` |

## 3. pack/cli

*No `astrid.core.pack.cli` monkeypatches were found in `tests/`. The pack CLI surface
(`astrid.core.pack.cli`) is tested indirectly through gateway dispatch tests.*

## 4. timeline/cli

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.timeline.save_timeline` | `tests/test_publish.py` : 440 | `save_timeline` | `mock.patch("astrid.core.timeline.save_timeline")` |

The retired local timeline CLI, edit helpers, event-log backend, projection
writer, branch, erasure, recovery, and undo modules have no compatibility
monkeypatch contract. Supported timeline mutations are versioned generated-
client calls and are tested at the SDK/runtime boundary.

## 5. task/operator/view ↔ operator/render

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.task.operator.view.render_step_instructions` | `tests/agentic/test_agent_probe_regression.py` : 294 | `render_step_instructions` | `monkeypatch.setattr(_operator_view_mod, ...)` resolves via `from astrid.core.task.operator import view` |

## 6. gateway/__init__

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.gateway._dispatch` | `tests/test_pipeline_error_rendering.py` : 162, 187 | `_dispatch` | `mock.patch("astrid.core.gateway._dispatch")` |

## 7. executor/cli

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.executor.cli.main` | `tests/test_pipeline_caching.py` : 281, 290 | `main` | `mock.patch("astrid.core.executor.cli.main")` |
| `astrid.core.executor.cli.main` | `tests/test_canonical_cli.py` : 157, 224 | `main` | `mock.patch.object(executors_cli, ...)` resolves via `from astrid.core.executor import cli` |
| `astrid.core.executor.cli.load_default_registry` | `tests/test_task_kernel_dispatch.py` : 36 | `load_default_registry` | `monkeypatch.setattr(executor_cli, ...)` resolves via `from astrid.core.executor import cli` |

## 8. orchestrator/cli

| Dotted path / attribute | Test file : line | Symbol pinned | How patched |
|---|---|---|---|
| `astrid.core.orchestrator.cli.main` | `tests/test_canonical_cli.py` : 154, 221 | `main` | `mock.patch.object(orchestrators_cli, ...)` resolves via `from astrid.core.orchestrator import cli` |
| `astrid.core.orchestrate.cli.main` | `tests/test_pipeline_dispatch_aliases.py` : 157, 175 | `main` | `mock.patch("astrid.core.orchestrate.cli.main")` |

> **Note:** `astrid.core.orchestrate.cli` is a **distinct** module from
> `astrid.core.orchestrator.cli`. Both paths must resolve. The `orchestrate` path is the
> deprecated alias gateway; `orchestrator` is the canonical name.

## 9. sdk/discovery

All patched via `monkeypatch.setattr(sdk, ...)` where `sdk = importlib.import_module("astrid.sdk")`
in `tests/test_sdk_public_surface.py`.

| Attribute on `astrid.sdk` | Lines | Test file |
|---|---|---|
| `_load_executor_registry` | 333 | `tests/test_sdk_public_surface.py` |
| `_load_orchestrator_registry` | 334 | `tests/test_sdk_public_surface.py` |
| `_load_element_registry` | 335 | `tests/test_sdk_public_surface.py` |
| `_discover_pack_inventory` | 336 | `tests/test_sdk_public_surface.py` |
| `_load_registries` | 1201 | `tests/test_sdk_public_surface.py` |
| `get_capability` | 1202 | `tests/test_sdk_public_surface.py` |
| `run_executor` | 337, 348, 353, 358, 558, 764, 836, 870, 905, 996, 1028, 1203, 1238, 1260, 1295 | `tests/test_sdk_public_surface.py` |
| `run_orchestrator` | 932, 1548 | `tests/test_sdk_public_surface.py` |
| `invoke` | 1598, 1645, 1671, 1812, 1878, 1909, 1940, 1993, 2047, 2087, 2147, 2169, 2206, 2246, 2283, 2324, 2364, 2387, 2407, 2449, 2527, 2635, 2657, 2681, 2703, 2728, 2771, 2814, 2837 | `tests/test_sdk_public_surface.py` |
| `_infer_image_mode` | 2486 | `tests/test_sdk_public_surface.py` |

## 10. Registry discover_packs (cross-cutting)

These `discover_packs` symbols are the most heavily mocked surface across the codebase.
Each dotted path must continue to resolve.

| Dotted path | Test files | Mode |
|---|---|---|
| `astrid.core.executor.registry.discover_packs` | `tests/test_capability_alias_resolver.py` (18 sites), `tests/packs/test_pack_discovery.py` (8 sites), `tests/packs/test_pack_discovery_metadata.py` (1 site) | `mock.patch("...")` |
| `astrid.core.orchestrator.registry.discover_packs` | `tests/test_capability_alias_resolver.py` (8 sites), `tests/packs/test_pack_discovery.py` (5 sites), `tests/packs/test_pack_discovery_metadata.py` (1 site) | `mock.patch("...")` |
| `astrid.core.element.registry.discover_packs` | `tests/packs/test_pack_discovery.py` (5 sites), `tests/core/test_element_kind_registry.py` : 762 | `mock.patch("...")` |

## 11. Other `astrid.core.*` dotted-string patches

| Dotted path | Test file : line | Symbol pinned |
|---|---|---|
| `astrid.core.executor.registry.load_default_registry` | `tests/test_pipeline_dispatch_aliases.py` : 90 | `load_default_registry` |
| `astrid.core.orchestrator.registry.load_default_registry` | `tests/core/test_executor_runner_errors.py` : 606 | `load_default_registry` |
| `astrid.core.element.install.subprocess.run` | `tests/core/test_elements_install.py` : 68, 80 | `subprocess.run` (on `element.install.subprocess`) |
| `astrid.core.task.lifecycle.cmd_runs_ls` | `tests/test_pipeline_dispatch_aliases.py` : 124, 142 | `cmd_runs_ls` |

## 12. Other `astrid.core.*` module-object patches

These use `monkeypatch.setattr(module_obj, "attr")` or `mock.patch.object(module_obj, "attr")`,
pinning the attribute name on an imported module. The import path of the module object is the contract.

| Module import path | Attribute pinned | Test file : line |
|---|---|---|
| `from astrid.core.task import lifecycle` | `_dispatch_from_tail` | `tests/agentic/test_agent_probe_regression.py` : 266; `tests/test_cmd_next_tail_dispatch.py` : 264 |
| `from astrid.core.task import lifecycle` | `render_step_instructions` | `tests/agentic/test_agent_probe_regression.py` : 293 |
| `from astrid.core.task import lifecycle` | `cmd_start` | `tests/test_canonical_cli.py` : 174 |
| `from astrid.core.task import lifecycle` | `cmd_ack` (et al, via `attr` loop) | `tests/test_canonical_cli.py` : 205 |
| `from astrid.core.task import gate` | `gate_command` | `tests/test_canonical_cli.py` : 175, 206 |
| `from astrid.core.task import gate` | `_run_inline_checks` | `tests/agentic/test_agent_probe_regression.py` : 283, 354; `tests/test_for_each_autoclose.py` : 70 |
| `from astrid.core.task.gate import repeat` | `load_plan` | `tests/test_for_each_autoclose.py` : 153 |
| `from astrid.core.executor import runner` | `import_module` | `tests/core/test_executor_runner_errors.py` : 607 |
| `from astrid.core.executor import runner` | `subprocess.run` | `tests/core/test_executor_runner_errors.py` : 728, 834 |
| `from astrid.core.executor import runner` | `prepare_project_run` | `tests/test_task_env_contract.py` : 129 |
| `from astrid.core.orchestrator import runner` | `subprocess.run` | `tests/core/test_orchestrator_runner_errors.py` : 237, 289 |
| `from astrid.core.orchestrator import runner` | `_test_python_target` | `tests/core/test_orchestrator_runner_errors.py` : 345, 487, 503, 519, 800 |
| `from astrid.core.orchestrator import runner` | `prepare_project_run` | `tests/test_task_env_contract.py` : 130 |
| `from astrid.core.element import cli` | `main` | `tests/test_pipeline_dispatch_aliases.py` : 34 |
| `from astrid.core import doctor` | `main` | `tests/test_pipeline_dispatch_aliases.py` : 57 |
| `from astrid.core.gateway import setup` | `main` | `tests/test_pipeline_dispatch_aliases.py` : 67 |
| `from astrid.core import gateway` | tests reference `gateway.main` but don't monkeypatch it | — |
| `astrid.core.task.lifecycle.SessionStore` | `save` (spy) | `tests/session/test_session_lifecycle.py` : 409 |
