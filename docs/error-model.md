# Runtime Error Model

This document records the runtime-correctness error policy that m3 enforces in
the Astrid harness. It is derived from existing good patterns in
`astrid/core/element/cli.py`, `astrid/core/orchestrator/cli.py`,
`astrid/core/task/events.py`, `astrid/core/session/writer.py`, and the task
runtime under `astrid/core/task/`.

## Boundary Rules

- CLI boundaries catch named domain exception tuples, print actionable stderr,
  and return a non-zero exit code instead of emitting tracebacks for expected
  operator errors.
- `astrid/core/element/cli.py` and `astrid/core/orchestrator/cli.py` are the
  reference shape: narrow named catches, `print(..., file=sys.stderr)`, return
  `2`.
- Domain exceptions should carry structured recovery data when callers need it.
  The reference pattern is `EventLogError` plus the typed subclasses
  `StaleTailError`, `StaleEpochError`, and `NotWriterError` in
  `astrid/core/task/events.py`, which keep machine-readable fields on the
  exception object as well as a human-readable message.

## Internal Runtime Rules

- Internal runtime-correctness code recovers narrowly with a documented reason
  or raises. It does not silently swallow exceptions.
- Broad `except Exception` is not acceptable for core runtime control flow
  unless the committed inventory explicitly justifies it.
- Best-effort non-CLI catches are allowed only when failure must not abort the
  primary operation. Those catches must be narrow, or they must log/contextualize
  why the failure is being ignored unless the inventory documents why logging is
  noisy, recursive, or unsafe.
- Audit integrity failures fail closed by default. Any corruption-tolerant or
  verification-skipping path must be explicit, operator-chosen, and documented
  as an opt-out.
- `assert` is not runtime validation. Python strips asserts under `-O`, so
  operator-facing validation and runtime invariants must raise explicit
  exceptions instead.

## Catch Categories

Every non-test catch in the runtime sweep should fit one of these categories and
say so in code review and the inventory:

- User-facing fallback: a compatibility or convenience fallback whose behavior
  is intentionally surfaced to the operator.
- Telemetry-only: best-effort reporting that must not block the primary action.
- Corruption-tolerant recovery: narrow recovery around partially malformed or
  missing state where the fallback behavior is deliberate and bounded.
- Validation accumulation: code that keeps collecting user-visible validation
  errors instead of failing on the first one.

Discovery, provenance, session fallback, and task-helper catches should state
which category they belong to.

## The AstridError Envelope Contract

Since m3, all operator- and agent-facing failures must travel through the
canonical `AstridError` envelope defined in `astrid/contracts/errors.py`.  The
envelope carries structured recoverability data that allows agents and the
assessor to extract valid options and recovery commands without parsing ad-hoc
error text.

### Canonical Fields

Every `AstridError` carries these attributes:

| Field | Type | Purpose |
|---|---|---|
| `cause` | `str` | Human-readable description of what went wrong. |
| `valid_options` | `tuple[str, ...]` | Recovery-safe enumeration of allowed values (empty when not applicable). |
| `recovery_command` | `str` | The next command the operator/agent should run (empty when not applicable). |
| `state_snapshot` | `dict[str, Any]` | Compact JSON-safe state the renderer surfaces verbatim. |
| `degraded` | `bool` | `True` when this envelope wraps an unhandled generic exception; `False` for expected domain errors. |

### Legacy Compatibility Fields

For backward compatibility with existing error-handling code, `AstridError` also
exposes these aliases:

- `message` — mirrors `cause`
- `reason` — mirrors `cause`
- `recovery` — mirrors `recovery_command`
- `code` — optional machine-readable string (set to `None` when absent)
- `source_type` — the original exception class name (set to `None` when absent)

These legacy fields exist so old catch sites that read `.message` or `.reason`
continue to work.  New code MUST use the canonical field names.

### The Rendering Contract

`render_astrid_error()` in `astrid/contracts/errors.py` prints the envelope to
stderr in this order:

1. **Bug flag** (only when `degraded=True`):
   ```
   unstructured - this is a bug.
   ```
2. **Cause**:
   ```
   <cause text>
   ```
3. **Valid options** (only when non-empty):
   ```
   valid options: <comma-separated list>
   ```
4. **Recovery command** (only when non-empty):
   ```
   recovery: <command text>
   ```
5. **State snapshot** (only when non-empty):
   ```
   state snapshot: <compact JSON>
   ```

The exit code is `1` for degraded errors and `2` for all other `AstridError`
instances.  This distinction lets dry-run harnesses and agentic auditors
distinguish expected recoverable failures from unexpected bugs.

### The catch-all in pipeline.main()

`pipeline.main()` wraps the entire CLI dispatch in two catch blocks:

```python
try:
    return _main_impl(raw)
except AstridError as exc:
    return render_astrid_error(exc)
except Exception as exc:
    bug = wrap_degraded_error(
        exc,
        state_snapshot={"argv": raw, "entrypoint": "astrid.pipeline.main"},
    )
    return render_astrid_error(bug)
```

- **`AstridError`** — rendered directly.  The cause, valid options, recovery
  command, and state snapshot reach stderr intact.  No Python traceback appears.
- **Any other `Exception`** — wrapped by `wrap_degraded_error()` into a degraded
  `AstridError` envelope with `degraded=True`.  The original exception type and
  message are preserved as `cause`, and the stderr output begins with the
  `unstructured - this is a bug.` flag.

This means every single CLI invocation that raises will produce structured
stderr.  Bare Python tracebacks should never reach the operator.

### Authoring Rules

When you are writing or migrating a CLI parser, a kernel helper, or a pack
entrypoint, follow these rules:

1. **Raise `AstridError` for known recoverable failures.**  Populate
   `valid_options` when the failure is an invalid enum/choice so agents see the
   allowed values.  Populate `recovery_command` with the exact next command the
   caller should run.

2. **Do not catch `AstridError` at internal boundaries** unless you are adding
   context to the envelope.  If you re-wrap, use `coerce_astrid_error()` to
   merge state snapshots and preserve the original `valid_options` and
   `recovery_command`.

3. **Internal validation helpers may still raise `ValueError` or domain-specific
   exceptions** as long as the public CLI boundary (or pack entrypoint) catches
   them and converts them to `AstridError` before the call unwinds past
   `pipeline.main()`.

4. **Use `AstridError` subclasses for typed domain errors.**  The pattern
   established by `TaskRunGateError`, `SessionBindingError`,
   `TimelineEditError`, `ProjectError`, `ProjectValidationError`, and
   `ExecAstridError` is: inherit from `AstridError`, set `cause` in `__init__`,
   and preserve any legacy attributes the existing call sites expect.

5. **Use `wrap_degraded_error()` only at the outermost catch-all.**  Do not call
   it inside pack entrypoints or kernel helpers — let those raise proper
   `AstridError` instances so the degraded flag is reserved for genuinely
   unexpected Python exceptions.

6. **Non-exception result objects** (such as `ExecError` dataclasses) satisfy
   the `AstridErrorEnvelope` protocol via properties.  Use `error_from_result()`
   to convert an `ExecError`-bearing result into an `AstridError` for rendering.
   Do not raise result dataclasses as exceptions — use `ExecAstridError` for
   raised execution failures.

### Structured Stderr for Agents

The assessor in `tests/agentic/assessor.py` filters stderr through
`_head_tail_filter_stderr()`, which preserves lines containing these markers:

- `valid options:` — the allowed-values enumeration
- `recovery:` — the recovery command
- `state snapshot:` — compact JSON state
- `unstructured` — the degraded bug flag
- `error`, `rejected`, `exit `, `invalid`, `cannot`, `failed` — cause-keyword
  patterns matched case-insensitively

Agents reading Astrid stderr can therefore:

- Parse `valid options:` to discover what values are accepted.
- Parse `recovery:` to learn the exact next command.
- Detect `unstructured - this is a bug.` to distinguish expected failures from
  bugs.

No source grep or ad-hoc text parsing is needed.

## Task Runtime Guidance

- Task-run event transport is session-free and append-focused. Production task
  mutations flow through `WriterContext.append()`; raw append helpers in
  `astrid/core/task/events.py` are transport primitives or legacy
  test/migration seams, not a second production write API.
- Lifecycle and gate helpers may use best-effort cleanup or advisory audit paths
  only when the main operator-visible event has already been written or the
  failure is explicitly non-blocking.
- If a helper chooses not to raise, its reason should be obvious from the code
  and recorded in the m3 inventory.

## Sweep Coverage

The m3 inventory and follow-on fixes should apply this policy across:

- CLI boundaries
- audit verification and report generation
- discovery and registry loading
- provenance and lineage compatibility readers
- session binding and writer-auth fallbacks
- best-effort task helpers and cleanup paths
- validation-accumulation code paths
