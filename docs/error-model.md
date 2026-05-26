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
