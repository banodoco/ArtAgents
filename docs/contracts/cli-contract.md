# Agent CLI Contract

This document defines the stable public contract between Astrid's CLI and
agentic consumers (both human operators and AI agents).  It covers stream
discipline, output modes, error signaling, and the behavioral guarantees
that agents can rely on when invoking Astrid subcommands.

The gateway owns **exactly eight families** — the five product families
(`projects`, `timelines`, `media`, `tasks`, `runs`) and the three
operational families (`serve`, `doctor`, `backup`) — plus the two
manifest-declared nested mounts (`timelines shots`, `media references`).
One verb = one SDK call. No other top-level command exists; see
[the CLI census](../getting-started.md) and
[CLI journeys](../guides/cli-journeys.md).

## Stream Discipline

Every Astrid CLI invocation observes strict stdout/stderr separation:

| Stream | Content | Purpose |
|---|---|---|
| **stdout** | Command result surface | The human-readable result line, or (in `--json` mode) exactly one JSON document.  Agents read stdout for the command outcome. |
| **stderr** | Diagnostics and structured errors | Error envelopes, `valid options:` / `recovery:` lines, and pure diagnostics.  Agents parse stderr for structured recovery guidance. |

### Default Mode (Human-Readable)

In default mode (no `--json`), stdout carries the command result: for a
mutation, one concise identity line (e.g. the created project slug and id);
for a read, the requested listing or detail in plain text.

Stderr in default mode carries only true diagnostics: typed error envelopes
and recovery guidance.

### JSON Mode (`--json`)

When `--json` is passed, stdout contains **exactly one JSON document** —
one line, one object, terminated by a single `\n`.  No preamble, no prose,
no separator.  This is the sole machine-contract path.  Agents reading JSON
must parse stdout as a single JSON object.

The JSON payload is the frozen five-key envelope:

```json
{
  "ok": true,
  "data": {"id": "…", "slug": "demo"},
  "error": null,
  "receipt": {
    "receipt_id": "…",
    "command_kind": "…",
    "idempotency_key": "…",
    "request_hash": "…",
    "project_id": "…",
    "project_seq": [1, 1],
    "event_ids": ["…"],
    "result": {"…": "…"},
    "created_at": "…"
  },
  "idempotency_key": "…"
}
```

| Key               | Meaning                                                            |
| ----------------- | ------------------------------------------------------------------ |
| `ok`              | `true` on success, `false` on a typed SDK error                    |
| `data`            | the command's result payload (`null` on failure)                   |
| `error`           | a frozen error object (`{code, message, details}`) or `null`       |
| `receipt`         | the committed command receipt on mutations, `null` on reads/failure|
| `idempotency_key` | caller-supplied key, or the key the SDK generated before mutation  |

Stderr in JSON mode may carry `valid options:` / `recovery:` lines and the
structured error envelope. Agents should parse `recovery:` from stderr as
the canonical next command.

### Design Decisions (Settled)

These decisions are locked and must not be re-litigated:

- **SD1**: `--json` is the sole machine-contract path.  It never includes
  preamble or prose — exactly one JSON object on stdout.
- **SD2**: Recovery guidance (`valid options:` / `recovery:`) lives on
  stderr in both modes, so the stdout contract stays parseable.
- **SD3**: Exit-code taxonomy is `0`=success (envelope `ok=true`), `1`=typed
  SDK error (envelope `ok=false`), `2`=usage/parse error (argparse).

## Verb Reference

The gateway families and their verbs:

- **`projects`** — `create`, `list`, `show`, `update`, `select`.  `select`
  persists a non-authoritative default-project preference (file-side only; no
  receipt, no DB mutation).
- **`timelines`** — `create`, `list`, `show`, `save`, `archive`, `history`,
  `diff`.  `save` is a whole-document compare-and-swap; a stale
  `--expected-version` is the typed `stale_version` and changes nothing.
- **`media`** — `import`, `list`, `show`, `verify`, `relocate`, `relate`.
  `verify`/`relocate` require `--realm`; `relate` has the frozen five-kind
  `--kind` (`derived_from`, `variant_of`, `uses_as_input`, `mask_for`,
  `audio_for`).
- **`tasks`** — `create`, `list`, `show`, `cancel`, `retry`, `events`.
  `create` admits one immutable task (`--capability` + JSON `--spec`).
- **`runs`** — `list`, `show`, `cancel`, `retry-failed`, `events`.
  `retry-failed` is the batch-retry surface (all-failed-children by default,
  explicit repeatable `--task` subset otherwise).
- **`serve`** — start the HTTP editor bridge (`--host`, `--port`,
  `--projects-root`, `--editor-path`, `--no-open-editor`).
- **`doctor`** — read-only health check (`schema_versions`, media paths,
  SQLite quick-check, FK status).  `--projects-root` selects the root.
- **`backup`** — `create` (staged, validated, `--out`) and `restore`
  (journaled, idempotent).

Nested mounts (manifest-declared, never top-level):

- **`media references`** — `create`, `update`, `archive`, `associate`,
  `link`, `set-primary`, `list`, `show`.
- **`timelines shots`** — `list`, `create`, `add`, `remove`, `reorder`.

There is no `next` / `status` / `attach` / `start` / `ack` surface: the
legacy task-mode CLI was retired with the filesystem task-run store.  Pack
capabilities are not gateway commands either — they run through the SDK
(`astrid.sdk.invoke`, `astrid.sdk.client.AstridClient`).

## Error Contract

All recoverable CLI failures travel through the `AstridError` envelope defined
in `astrid/core/contracts/errors.py`.  See [docs/error-model.md](error-model.md) for
the full taxonomy, envelope fields, rendering contract, and authoring rules.

Key points for agents:

- **Exit code 1** means a typed SDK error (`ok=false` in JSON mode).  Parse
  the `error` envelope for the `code`; retry only when the error contract
  says the operation is retryable.
- **Exit code 2** means a usage/parse error.  `valid options:` lists the
  accepted values and `recovery:` suggests the correct invocation.
- **Parser errors** (`AstridArgumentError`) are converted to `AstridError`
  envelopes with `valid_options` listing the accepted values and a
  `recovery_command` suggesting the correct invocation.

## Cross-References

- [Error Model](error-model.md) — canonical exit-code taxonomy, error envelope contract, recovery-command expectations.
- [Run Ledger Contract](run-ledger-contract.md) — event log append semantics and hash-chain integrity.
- [Platform Contract](platform-contract.md) — cross-backend primitives and gateway-level guarantees.
- [Discovery for Agents](../guides/discovery-for-agents.md) — how agents discover available capabilities through the SDK.
- [Output Result Contract](output-result-contract.md) — how executor outputs are surfaced.
