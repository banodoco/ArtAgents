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

- **`astrid next`** — universal port-of-call; always prints exactly one legal action on stdout.  Supports `--quiet`, `--json`, and `--skip`.  JSON states: `unbound`, `no_active_run`, `reader`, `active`, `exhausted`, `blocked`.
- **`astrid status`** — human-readable or JSON status block (session or task-scoped via `--project <slug>`).
- **`astrid start`** — creates a new task run; JSON payload includes `orchestrator_id`, `timeline_slug`, `plan_hash`, `next_command`.
- **`astrid abort`** — clears the active run and releases the writer lease; idempotent.
- **`astrid ack`** — approves, retries, or iterates the current step.  `--decision abort` forwards to `cmd_abort`.
- **`astrid skip`** — skips an optional step; JSON payload includes `step_path`, `kind`, `actor_kind`, `actor_id`, `next_command`.
- **`astrid attach`** — binds a session to a project.  `--json` is non-prompting: missing timeline raises `AstridError` with `valid_options` + `recovery_command`.
- **`astrid sessions status`** — JSON payload includes `session_id`, `agent_id`, `project`, `run_id`, `role`, `state`, `run_status`, `recent_events`.

## Error Contract

All recoverable CLI failures travel through the `AstridError` envelope defined
in `astrid/core/contracts/errors.py`.  See [docs/error-model.md](error-model.md) for
the full taxonomy, envelope fields, rendering contract, and authoring rules.

Key points for agents:

- **Exit code 2** means the failure is recoverable.  Parse `recovery:` from
  stderr and execute it as the next command.
- **Exit code 1** means a degraded/internal bug.  The operator sees
  `unstructured - this is a bug.` on stderr.  Report the failure; do not retry.
- **Parser errors** (`AstridArgumentError`) are converted to `AstridError`
  envelopes with `valid_options` listing the accepted values and a
  `recovery_command` suggesting the correct invocation.

## Cross-References

- [Error Model](error-model.md) — canonical exit-code taxonomy, error envelope contract, recovery-command expectations.
- [Run Ledger Contract](run-ledger-contract.md) — event log append semantics and hash-chain integrity.
- [Platform Contract](platform-contract.md) — cross-backend primitives and gateway-level guarantees.
- [Discovery for Agents](../guides/discovery-for-agents.md) — how agents discover available projects, timelines, orchestrators, and elements.
- [Output Result Contract](output-result-contract.md) — how element and executor outputs are surfaced.
