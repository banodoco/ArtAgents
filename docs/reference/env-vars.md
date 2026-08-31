# Astrid Environment Variables

Stage1 runtime connection and the remaining Astrid process variables.

## Stage1 runtime connection

The live CLI and SDK connect to the Banodoco workspace runtime. The runtime
owns durable projects, media, receipts, events, and execution state; Astrid
does not select a project root or open a local database/CAS.

| Variable | Who sets | Effect |
|---|---|---|
| `BANODOCO_RUNTIME_ENDPOINT` | Runtime launcher / operator | Runtime HTTP endpoint. Overrides discovery when set. |
| `BANODOCO_RUNTIME_DISCOVERY` | Runtime launcher / operator | Path to the runtime discovery JSON used when no endpoint is set. |
| `BANODOCO_RUNTIME_CREDENTIAL` | Runtime launcher / operator | Path to the credential/token file used by the generated workspace client. |
| `BANODOCO_RUNTIME_CHECKOUT` | Astrid launcher / operator | Editable neutral runtime checkout used for automatic first launch. |
| `BANODOCO_LOCAL_RUNTIME_CHECKOUT` | Runtime launcher / operator | Compatibility alias for the editable neutral runtime checkout. |
| `BANODOCO_LOCAL_SOURCE_MANIFEST` | Astrid launcher / operator | Existing Astrid source-profile manifest passed to neutral bootstrap. |
| `BANODOCO_ASTRID_SOURCE_CHECKOUT` | Astrid launcher / operator | Astrid editable source checkout when the package is not running from an editable checkout. |
| `BANODOCO_ASTRID_AUTO_BOOTSTRAP` | User / CI | Set to `0` to make `AstridClient.open()` fail closed without launching the neutral runtime. |

These are runtime composition variables, not project-store overrides. Product
commands use the configured checkout/manifest to invoke
`banodoco-local up --profile astrid` automatically; the explicit command
remains available for operator lifecycle work.

The `ASTRID_*` registry below remains useful for pack subprocesses, tests, and
authoring tools. Variables marked **historical/internal** are not live workspace
authority and must not be used to configure product state.

**Source of truth**: `astrid/core/env_vars.py`.  All constants listed here are
defined in that module following the invariant `constant_name == constant_value`
(the constant identifier equals the env-var string it names).  Use the constant
rather than the bare string in any new code.

Exceptions to the name==value invariant:

- `ASTRID_AUTHOR_TEST` — the constant's value is the env-var string
  `ASTRID...TEST` (with three dots), not its own identifier.
- `ASTRID_AUTHOR_TEST_LEGACY` — backward-compat alias whose value is the
  legacy key `ASTRID...TEST` (not its own name).

`get_author_test_env()` checks the canonical key (`ASTRID...TEST`) first, then
falls back to the legacy key with a deprecation warning.  Use
`ASTRID_AUTHOR_TEST` for all new code.

---

## Session and home

Astrid Stage1 has no session-binding or home-directory state authority. Do not
set session identifiers or project-root overrides to configure a product
command; project and actor context come from the runtime request.

## Renderer and subprocess context

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_REMOTION_PROJECT_DIR` | `ASTRID_REMOTION_PROJECT_DIR` | Release operator | Remotion renderer | Absolute server-owned Remotion project with `node_modules`; never accepted from task input. |
| `ASTRID_NODE_EXECUTABLE` | `ASTRID_NODE_EXECUTABLE` | Release operator | Remotion renderer | Absolute server-owned executable Node path. Readiness performs a bounded `--version` probe; never resolved from `PATH` or accepted from task input. |
| `ASTRID_TIMELINE_SCHEMA_PYTHONPATH` | `ASTRID_TIMELINE_SCHEMA_PYTHONPATH` | Release operator | Remotion renderer | Absolute server-owned install root containing `banodoco_timeline_schema`; validated by module origin before Remotion-only admission. |
| `ASTRID_GATEWAY_RESOLVED_PROJECT` | `ASTRID_GATEWAY_RESOLVED_PROJECT` | Internal subprocess | Pack CLI shims | Ephemeral project hint for a runtime-admitted subprocess; it is not persisted state. |

## Project run context

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_PROJECT_RUN` | `ASTRID_PROJECT_RUN` | `project/runtime.py` (`project_run_env`) | Child processes | Set to `1` inside a runtime-bound subprocess to distinguish a harness-driven invocation from a bare CLI call. |

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
| `ASTRID_AUTHOR_TEST` | `ASTRID...TEST` | `orchestrate/test_runner.py` | `task/env.py` (`is_author_test_mode`) | Set to `1` in author-test mode: auto-approves attested gates, uses a scratch projects root. |
| `ASTRID_INTERNAL_INVOCATION` | `ASTRID_INTERNAL_INVOCATION` | `executor/runner.py`, `orchestrator/runner.py` | `executor/runner.py`, `task/command_render.py` | Set to `1` by the runner when launching a step subprocess, so the child can skip certain prompts. |
| `ASTRID_STRICT_INSTRUCTION_SUBST` | `ASTRID_STRICT_INSTRUCTION_SUBST` | User / CI | `task/operator/view.py` | Set to `1` to enforce strict substitution of `${ASTRID_…}` placeholders; raises on unknown tokens.  Implied when `ASTRID_AUTHOR_TEST` is set. |

## Pack discovery

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_PACKS_PATH` | `ASTRID_PACKS_PATH` | Authoring/tests | `core/pack/discovery.py` | Optional authoring/test discovery path. Stage1 live capability registration is checkout/runtime-owned; this does not install or update a live pack. |

## Logging

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_LOG_MAX_BYTES` | `ASTRID_LOG_MAX_BYTES` | User / CI | `runtime/log_capture.py` (`RotatingTextLog`) | Soft byte cap for rotating log files.  Defaults to 10 MiB when unset. |

## Feature flags / opt-outs

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_NO_NUDGE` | `ASTRID_NO_NUDGE` | User | `skills/__init__.py` | Set to `1` to suppress the skill-nudge banner. |

## External catalog (Banodoco)

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_BANODOCO_CATALOG_URL` | `ASTRID_BANODOCO_CATALOG_URL` | User / CI | `executor/banodoco_catalog.py` | URL of the Banodoco agent-executor catalog.  Required when `ASTRID_BANODOCO_AGENT_EXECUTORS=1`. |

## Backward-compat alias

| Constant | Env var | Who sets | Who reads | Effect |
|---|---|---|---|---|
| `ASTRID_AUTHOR_TEST_LEGACY` | `ASTRID...TEST` (legacy key) | — | `get_author_test_env()` fallback only | Retained so `get_author_test_env()` can fall back to the old env-var name with a deprecation warning.  Use `ASTRID_AUTHOR_TEST` for all new code. |

---

## Internal/authoring-only variables

The following directories contain references to `ASTRID_*` env vars but are
**not required** to import from `env_vars.py`. Their constants are catalogued
for historical or authoring purposes only; none is a live workspace authority.

| Directory | Reason |
|---|---|
| `astrid/core/audit/` | Separate concern; defines its own context (`ASTRID_AUDIT_*`). |
| `astrid/packs/` | Executor `run.py` files that do not import astrid core. |

### Additional env vars in allowlisted modules

| Constant | Env var | Module | Effect |
|---|---|---|---|
| `ASTRID_STATE_HOME` | `ASTRID_STATE_HOME` | `skills/state.py` | Overrides the skills state directory (default: `~/.local/share/astrid` or `~/Library/Application Support/astrid`). |
| `ASTRID_AUDIT_DISABLED` | `ASTRID_AUDIT_DISABLED` | `audit/context.py` | Set to `1` to disable audit event recording. |
| `ASTRID_AUDIT_RUN_DIR` | `ASTRID_AUDIT_RUN_DIR` | `audit/context.py` | Directory for the current audit run. |
