# Agent CLI Contract

This document defines the stable public contract between Astrid's CLI and
agentic consumers (both human operators and AI agents).  It covers stream
discipline, output modes, error signaling, and the behavioral guarantees
that agents can rely on when invoking Astrid subcommands.

## Stream Discipline

Every Astrid CLI invocation observes strict stdout/stderr separation:

| Stream | Content | Purpose |
|---|---|---|
| **stdout** | Agent-facing instruction surface | Preamble, status text, actionable prose, and (in `--json` mode) exactly one JSON document.  Agents read stdout for next-step instructions. |
| **stderr** | Diagnostics and structured errors | Error envelopes, `valid options:` / `recovery:` lines, timeline/default notices in JSON mode, and pure diagnostics (produces-check failures, cursor-rewind errors).  Agents parse stderr for structured recovery guidance. |

### Default Mode (Human-Readable)

In default mode (no `--json`), stdout carries agent-facing prose:

- `astrid next`: prints the prohibition preamble, a blank separator line, and
  exactly one actionable instruction block.  Example output:
  ```
  ASTRID TASK RUN — PROHIBITIONS
  - You are inside a frozen plan...
  ...
  - Use `astrid abort --project <slug>` ...

  Step: step_a
  Run: astrid element run step_a -- ...
  ```
- `astrid status --project <slug>`: prints run-id, plan-hash, progress,
  current step, owner, inbox pending count, and recent events.
- `astrid attach <project>`: prints `session created`, the `export
  ASTRID_SESSION_ID=...` line, and timeline/run/role metadata.
- `astrid attach <project>` (reader takeover): prints a takeover hint
  block on stdout — this is an actionable recovery instruction, not a
  diagnostic (see SD2 below).

Stderr in default mode carries only true diagnostics: produces-check
failures, cursor-rewind errors, auto-resolve notices, and structured
error envelopes from `AstridError` (exit code 2).

### JSON Mode (`--json`)

When `--json` is passed, stdout contains **exactly one JSON document** —
one line, one object, terminated by a single `\n`.  No preamble, no prose,
no separator.  This is the sole machine-contract path.  Agents reading JSON
must parse stdout as a single JSON object.

The JSON payload carries shared lifecycle fields first:

```json
{"project": "my-project", "run_id": "01J...", "schema_version": 1, "state": "started", ...}
```

Key fields common to all lifecycle JSON payloads:

| Field | Type | Description |
|---|---|---|
| `schema_version` | `int` | Always `1`.  Version of the JSON payload schema. |
| `project` | `string` or `null` | Project slug, or `null` when not applicable (e.g., unbound session). |
| `run_id` | `string` or `null` | Active run ULID, or `null` when no run is active. |
| `state` | `string` | Machine-readable state: `started`, `aborted`, `no_active_run`, `acknowledged`, `retry_queued`, `iteration_failed`, `skipped`, `attached`, `session_bound`, `lease_error`, `reader`, `unbound`, etc. |

Verb-specific fields follow the shared fields; see the verb reference below.

Stderr in JSON mode may carry `valid options:` / `recovery:` lines,
timeline/default notices, and the structured `AstridError` envelope.
Agents should parse `recovery:` from stderr as the canonical next command
(see [Recovery-Command Expectations](error-model.md#recovery-command-expectations)).

### Design Decisions (Settled)

These decisions are locked and must not be re-litigated:

- **SD1**: The `next` prohibition preamble stays on **stdout** in default
  mode.  `--quiet` suppresses only the preamble and separator line, leaving
  actionable prose intact.  `--json` is the sole machine-contract path and
  never includes the preamble.  Moving the preamble to stderr would break
  agents that read stdout as the instruction surface.

- **SD2**: Default-mode session takeover hints (e.g., "attached as reader —
  another session holds the writer lease") remain on **stdout** as actionable
  recovery content, not pure diagnostics.  These hints are instructions for
  session resolution, not error diagnostics.  JSON mode provides the
  machine-readable alternative.

- **SD3**: Exit-code taxonomy is `0`=success, `1`=degraded/internal bug,
  `2`=expected recoverable user/environment issue.  See
  [Canonical Exit-Code Taxonomy](error-model.md#canonical-exit-code-taxonomy).

## Verb Reference

### `astrid next`

The universal port-of-call.  Always prints exactly one legal action on stdout,
regardless of session/run state.

| Flag | Behavior |
|---|---|
| *(default)* | Prints prohibition preamble, separator, and one actionable prose block on stdout. |
| `--quiet` | Suppresses the preamble and separator; keeps actionable prose. |
| `--json` | Emits exactly one JSON document on stdout.  No preamble, no prose. |
| `--quiet --json` | Same as `--json` (preamble is never in JSON mode). |
| `--skip` | Skips optional steps.  In JSON mode, emits one JSON payload for each skipped step plus a final payload for the next non-optional step or exhaustion.  No prose on stdout in JSON mode. |

JSON states: `unbound`, `no_active_run`, `reader`, `active`, `exhausted`,
`blocked` (tail-dispatch).  Each payload includes `action`, `command`,
`step`, `blocked`, and `reason` fields.

### `astrid status`

| Flag | Behavior |
|---|---|
| `--project <slug>` (default) | Human-readable status block on stdout; diagnostics on stderr. |
| `--project <slug> --json` | JSON status object on stdout.  Includes `progress_completed`, `progress_total`, `current_step`, `current_step_kind`, `current_step_version`, `current_step_iteration`, `current_step_item_id`, `inbox_pending`, `owner_assignee`, `owner_claimed`. |
| *(no `--project`)* (default) | Routes to session status; prints session breadcrumb on stdout. |
| *(no `--project`)* `--json` | Routes to session status; JSON payload on stdout with `state=no_session_bound`. |

Gateway routing: `astrid status --json` without `--project` delegates to
session status JSON; `astrid status --project <slug> --json` delegates to task
status JSON.  The `--json` flag is preserved through the gateway dispatch.

### `astrid start`

Creates a new task run.  JSON payload includes `orchestrator_id`,
`timeline_slug`, `plan_hash`, and `next_command` (`astrid next --project
<slug>`).

### `astrid abort`

Clears the active run and releases the writer lease.  Idempotent:
calling abort with no active run returns `state=no_active_run`.

### `astrid ack`

Approves, retries, or iterates the current step.  States:
`acknowledged`, `retry_queued`, `iteration_failed`.  The `--decision abort`
shortcut forwards `--json` to `cmd_abort`.  Recoverable validation failures
(identity gate, stale epoch, etc.) produce error envelopes on stderr with
exit code 2.

### `astrid skip`

Skips an optional step.  JSON payload includes `step_path`,
`kind` (`step_skipped`/`item_skipped`), `actor_kind`, `actor_id`,
`step_version`, `next_command`, and `reason` (when `--reason` is given).

### `astrid attach`

Binds a session to a project.

| Flag | Behavior |
|---|---|
| *(default)* | Interactive: prompts for timeline selection when no default exists. |
| `--json` | **Non-prompting.**  If no default timeline is configured, raises an `AstridError` with `valid_options` and `recovery_command` instead of blocking on stdin. |
| `--json --timeline <slug>` | Non-prompting; uses the explicit timeline. |

JSON success payload includes `session_id`, `agent_id`, `timeline`, `role`,
`attach_kind` (`created`/`reused`/`resumed`), and `export_line`
(`export ASTRID_SESSION_ID=...`).

The non-prompting policy ensures that agents invoking `astrid attach --json`
never hang waiting for stdin input.  All missing-selection failures produce
structured `AstridError` envelopes with `valid_options` and `recovery_command`
on stderr and exit code 2.

### `astrid sessions status`

JSON payload includes `session_id`, `agent_id`, `project`, `run_id`,
`timeline`, `role`, `state` (one of `session_bound`, `lease_error`,
`writer`, `reader`), `run_status`, and `recent_events`.

## Error Contract

All recoverable CLI failures travel through the `AstridError` envelope defined
in `astrid/contracts/errors.py`.  See [docs/error-model.md](error-model.md) for
the full taxonomy, envelope fields, rendering contract, and authoring rules.

Key points for agents:

- **Exit code 2** means the failure is recoverable.  Parse `recovery:` from
  stderr and execute it as the next command.
- **Exit code 1** means a degraded/internal bug.  The operator sees
  `unstructured - this is a bug.` on stderr.  Report the failure; do not retry.
- **Parser errors** (`AstridArgumentError`) are converted to `AstridError`
  envelopes with `valid_options` listing the accepted values and a
  `recovery_command` suggesting the correct invocation.

## Implementation Modules

The contract is implemented across these modules:

| Module | Responsibility |
|---|---|
| `astrid/core/task/cli_contract.py` | Shared JSON emitter (`emit_lifecycle_json`, `emit_json_object`), payload shaping (`shape_lifecycle_payload`), and parser-error adaptation (`astrid_argument_error_to_error`, `exit_with_argument_error`). |
| `astrid/core/task/operator_view.py` | `cmd_next` (preamble, `--quiet`, `--json`, universal port-of-call) and `cmd_status` (task status with JSON and diagnostics-to-stderr). |
| `astrid/core/task/plan_builder.py` | `cmd_start` (run creation with JSON output). |
| `astrid/core/task/run_store.py` | `cmd_abort` (run clearing with JSON output). |
| `astrid/core/task/lifecycle_ack.py` | `cmd_ack` (approve/retry/iterate with JSON and abort delegation). |
| `astrid/core/task/lifecycle_skip.py` | `cmd_skip` (optional-step skip with JSON). |
| `astrid/core/session/cli.py` | `cmd_attach` (non-prompting JSON policy, structured errors) and `cmd_status` (session status JSON). |
| `astrid/gateway.py` | Status routing (`--json` preservation, session vs. task dispatch). |
| `astrid/contracts/errors.py` | `AstridError` envelope, `render_astrid_error`, and `wrap_degraded_error`. |

## Cross-References

- [Error Model](error-model.md) — canonical exit-code taxonomy, error envelope contract, recovery-command expectations.
- [Run Ledger Contract](run-ledger-contract.md) — event log append semantics and hash-chain integrity.
- [Platform Contract](platform-contract.md) — cross-backend primitives and gateway-level guarantees.
- [Discovery for Agents](discovery-for-agents.md) — how agents discover available projects, timelines, orchestrators, and elements.
- [Output Result Contract](output-result-contract.md) — how element and executor outputs are surfaced.
