# Astrid Environment Variables

Canonical reference for every `ASTRID_*` environment variable.

**Source of truth**: `astrid/core/env_vars.py`.  All constants listed here are
defined in that module following the invariant `constant_name == constant_value`
(the constant identifier equals the env-var string it names).  Use the constant
rather than the bare string in any new code.

Exception: `ASTRID_AUTHOR_TEST_LEGACY` — a backward-compat alias whose value
is the legacy key `ASTRID...TEST` (not its own name).  `get_author_test_env()`
checks the canonical key first, then falls back to the legacy key with a
deprecation warning.  Use `ASTRID_AUTHOR_TEST` for all new code.

---

## Session and home

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_HOME` | `ASTRID_HOME` | User / CI | `session/paths.py` | Overrides the per-user Astrid state directory (default `~/.astrid`). |
| `ASTRID_SESSION_ID` | `ASTRID_SESSION_ID` | `astrid attach` | Gateway, session binding, task harness | Active session UUID.  Propagated into subprocess env. |
| `ASTRID_PROJECTS_ROOT` | `ASTRID_PROJECTS_ROOT` | Tests / CI | `project/paths.py` | Overrides the projects root directory. |
| `ASTRID_GATEWAY_RESOLVED_PROJECT` | `ASTRID_GATEWAY_RESOLVED_PROJECT` | `gateway._dispatch_with_resolved_project` | `executor/cli.py`, `orchestrator/cli.py` | Project slug resolved for the current request; injected as `--project` when omitted by the user. |

## Project run context

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_PROJECT_RUN` | `ASTRID_PROJECT_RUN` | `project/run.py` (`project_run_env`) | Child processes | Set to `1` inside a project-run subprocess to distinguish a harness-driven invocation from a bare CLI call. |

## Task run context

These are propagated into subprocess env by `build_child_subprocess_env`.

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_TASK_RUN_ID` | `ASTRID_TASK_RUN_ID` | Task harness (`task/env.py`) | `task/env.py`, operator view | UUID of the active task run. |
| `ASTRID_TASK_PROJECT` | `ASTRID_TASK_PROJECT` | Task harness | `task/env.py`, `task/hook.py` | Project slug of the active task run. |
| `ASTRID_TASK_STEP_ID` | `ASTRID_TASK_STEP_ID` | Task harness | `task/env.py` | Step identifier within the current task run. |
| `ASTRID_TASK_ITEM_ID` | `ASTRID_TASK_ITEM_ID` | Task harness | `task/env.py` | Optional item-level identifier for repeating steps. |
| `ASTRID_TASK_ITERATION` | `ASTRID_TASK_ITERATION` | Task harness | `task/env.py` | Zero-padded iteration index (e.g. `001`) for repeat steps. |

## Identity and invocation

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_ACTOR` | `ASTRID_ACTOR` | Session/task subsystem | `task/env.py` | Identifies the actor driving the invocation (e.g. `agent:<id>`).  Cleared from the child subprocess env. |
| `ASTRID_AUTHOR_TEST` | `ASTRID_AUTHOR_TEST` | `orchestrate/test_runner.py` | `task/env.py` (`is_author_test_mode`) | Set to `1` in author-test mode: auto-approves attested gates, uses a scratch projects root. |
| `ASTRID_INTERNAL_INVOCATION` | `ASTRID_INTERNAL_INVOCATION` | `executor/runner.py`, `orchestrator/runner.py` | `executor/runner.py`, `task/command_render.py` | Set to `1` by the runner when launching a step subprocess, so the child can skip certain prompts. |
| `ASTRID_STRICT_INSTRUCTION_SUBST` | `ASTRID_STRICT_INSTRUCTION_SUBST` | User / CI | `task/operator_view.py` | Set to `1` to enforce strict substitution of `${ASTRID_…}` placeholders; raises on unknown tokens.  Implied when `ASTRID_AUTHOR_TEST=1`. |

## Pack discovery

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_PACKS_PATH` | `ASTRID_PACKS_PATH` | User / CI | `core/pack_discovery.py` | Colon-separated list of additional pack search directories. |

## Logging

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_LOG_MAX_BYTES` | `ASTRID_LOG_MAX_BYTES` | User / CI | `runtime/log_capture.py` (`RotatingTextLog`) | Soft byte cap for rotating log files.  Defaults to 10 MiB when unset. |

## Feature flags / opt-outs

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_NO_NUDGE` | `ASTRID_NO_NUDGE` | User | `skills/__init__.py` | Set to `1` to suppress the skill-nudge banner. |
| `ASTRID_ALLOW_LEGACY_APPEND_EVENT` | `ASTRID_ALLOW_LEGACY_APPEND_EVENT` | Migration tooling | `task/events.py` | Set to `1` to allow the legacy append-event API that bypasses hash chaining.  Not for production use. |

## External catalog (Banodoco)

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_BANODOCO_CATALOG_URL` | `ASTRID_BANODOCO_CATALOG_URL` | User / CI | `executor/banodoco_catalog.py` | URL of the Banodoco agent-executor catalog.  Required when `ASTRID_BANODOCO_AGENT_EXECUTORS=1`. |

## Backward-compat alias

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_AUTHOR_TEST_LEGACY` | `ASTRID...TEST` (legacy key) | — | `get_author_test_env()` fallback only | Retained so `get_author_test_env()` can fall back to the old env-var name with a deprecation warning.  Use `ASTRID_AUTHOR_TEST` for all new code. |

---

## Allowlisted modules

The following directories contain references to `ASTRID_*` env vars but are
**not required** to import from `env_vars.py`.  Their constants are catalogued
above for documentation purposes only.

| Directory | Reason |
|---|---|
| `astrid/threads/` | Contract-locked; separately versioned subsystem. |
| `astrid/audit/` | Separate concern; defines its own context (`ASTRID_AUDIT_*`). |
| `astrid/packs/` | Executor `run.py` files that do not import astrid core. |

### Additional env vars in allowlisted modules

| Constant | Env var | Module | Effect |
|---|---|---|---|
| `ASTRID_STATE_HOME` | `ASTRID_STATE_HOME` | `skills/state.py` | Overrides the skills state directory (default: `~/.local/share/astrid` or `~/Library/Application Support/astrid`). |
| `ASTRID_AUDIT_DISABLED` | `ASTRID_AUDIT_DISABLED` | `audit/context.py` | Set to `1` to disable audit event recording. |
| `ASTRID_AUDIT_RUN_DIR` | `ASTRID_AUDIT_RUN_DIR` | `audit/context.py` | Directory for the current audit run. |
| `ASTRID_AGENT_VERSION` | `ASTRID_AGENT_VERSION` | `threads/record.py` | Agent version string injected into thread records. |
| `ASTRID_REPO_ROOT` | `ASTRID_REPO_ROOT` | `threads/cli.py` | Absolute path to the repository root for relative-path display. |
