# Live agent UX wave: task dependencies and cancellation

Date: 2026-08-23  
Project root: `/tmp/astrid-live-task-dependency-ic08FF` (fresh, isolated)  
Project: `queue-lab` (`a1d29c35-c875-5814-a0cf-65ac72b5e51f`)

This was a live CLI journey, using only the public `python3 -m astrid` gateway
and its user-visible reads. No executor-owned transitions were driven, and no
tests or source implementation were inspected.

## Journey and command evidence

### 1. Discovery

Started with:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-task-dependency-ic08FF python3 -m astrid --help
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-task-dependency-ic08FF python3 -m astrid tasks --help
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-task-dependency-ic08FF python3 -m astrid tasks create --help
```

The census was clear about the eight families. The tasks family exposed only
`create`, `list`, `show`, `cancel`, `retry`, and `events`; there was no
`status` or `name` verb/option. `tasks create --help` described
dependencies only as “Optional hard dependencies as a JSON array,” without an
example or schema.

I created the project and read it back with `projects show --json`; the project
plan was an empty, newly-created skeleton.

### 2. Naming and dependency syntax discovery

The natural first attempt to name the task was:

```text
... tasks create --project queue-lab --capability rendering.timeline_visualize \
  --spec '{"probe":"noop"}' --name source-check --json
```

It failed at argument parsing (exit 2): `unrecognized arguments: --name
source-check`. There is no first-class task name field. To keep the requested
labels visible, I put `task_name` in each immutable spec and used the requested
label as the idempotency key.

The first task was admitted with:

```text
... tasks create --project queue-lab --capability rendering.timeline_visualize \
  --spec '{"task_name":"source-check","probe":"noop"}' \
  --idempotency-key source-check --json
```

Result: task `a33e6ffc-8c42-5db0-a543-948940aebc82`, status `queued`,
capability `rendering.timeline_visualize`, no dependencies.

The first intuitive dependency form was:

```text
--dependencies '["a33e6ffc-8c42-5db0-a543-948940aebc82"]'
```

It failed (exit 1) with:

```json
{"code":"validation_error","details":{},"message":"the request failed validation"}
```

There was no indication of the expected object shape. Trying the plausible
object form succeeded:

```text
--dependencies '[{"task_id":"a33e6ffc-8c42-5db0-a543-948940aebc82"}]'
```

The second task was admitted using the same real capability and a harmless
spec (`{"task_name":"render-after-check","probe":"noop-render"}`). It
received ID `79116019-2ced-57ca-ab25-876a31f03885` and immediately returned
status `blocked`. The read model normalized the dependency to:

```json
{
  "task_id": "79116019-2ced-57ca-ab25-876a31f03885",
  "depends_on_task_id": "a33e6ffc-8c42-5db0-a543-948940aebc82",
  "kind": "hard",
  "ordinal": 0
}
```

### 3. Verifying the block

Fresh sequential reads were successful:

```text
... tasks show 79116019-2ced-57ca-ab25-876a31f03885 --json
... tasks list --project queue-lab --json
... tasks events 79116019-2ced-57ca-ab25-876a31f03885 --json
```

`show` and `list` confirmed task 1 was `queued` and task 2 was `blocked`.
`show` included the dependency edge, but neither `show` nor `list` supplied a
human-readable reason such as “waiting for source-check (queued).” The second
task's only event was `core.task.created`, whose data contained
`status: blocked` and the dependency edge, but no blocked-reason or
dependency-status field. An agent has to inspect the other task separately and
infer the cause.

I also tried the intuitive status/legacy surfaces:

```text
... tasks status queue-lab --json
```

This returned exit 2 and listed the valid task verbs. The retired top-level
surface:

```text
... next --help
```

returned exit 2, `unknown command 'next'`, listed valid families, and suggested
`astrid --help`. That recovery was materially better than the dependency
validation error.

### 4. Cancel upstream, then determine recovery

I cancelled the queued prerequisite through the public lifecycle command:

```text
... tasks cancel a33e6ffc-8c42-5db0-a543-948940aebc82 \
  --project queue-lab --json
```

The result was successful: task 1 became `cancelled`, with a cancel request ID,
`finished_at`, and a `core.task.cancelled` event. A fresh `tasks show/list`
confirmed task 2 remained `blocked`; it did not become cancelled or failed,
and its `updated_at`/event head stayed at creation. There was no propagated
event explaining that its hard prerequisite had been cancelled.

I tested the apparent recovery action:

```text
... tasks retry 79116019-2ced-57ca-ab25-876a31f03885 \
  --project queue-lab --idempotency-key retry-render-after-check --json
```

It failed (exit 1) with `code: terminal_state`, message “the record is in a
terminal state,” even though the task's visible status was `blocked`. Retrying
the cancelled prerequisite produced the same `terminal_state` error. There is
no public command to replace a dependency or revive a cancelled task.

I then cancelled the orphaned dependent:

```text
... tasks cancel 79116019-2ced-57ca-ab25-876a31f03885 \
  --project queue-lab --json
```

That succeeded. Final fresh `tasks list --project queue-lab --json` state:

```text
a33e6ffc-8c42-5db0-a543-948940aebc82  cancelled  rendering.timeline_visualize
79116019-2ced-57ca-ab25-876a31f03885 cancelled  rendering.timeline_visualize
```

Final event reads showed task 1's create + cancel events and task 2's create +
cancel events. There was no dependency-resolution/cascade event. The sensible
recovery for this exact story is cancellation/cleanup of the dependent, then a
new task chain if the work is still wanted; `retry` is not an available recovery
for either a blocked dependent or a cancelled prerequisite.

### 5. Read contention observation

An intentionally parallel batch of read-only `show`, `list`, and `events`
commands produced the user-visible error three times:

```text
unstructured - this is a bug.
the database is already owned by another process
recovery: retry the command; if it repeats, report this bug
```

Each sequential retry succeeded, so this did not corrupt the journey. It is
still relevant to agent UX: multi-agent or parallel read workflows can turn a
safe observation into a scary “bug” response, with no structured error envelope.

## Severity-ranked UX critique

### P1 — A cancelled hard prerequisite strands dependents silently

After cancelling the prerequisite, the dependent stayed `blocked` forever with
no state transition, reason, or actionable relationship shown. A user cannot
tell from the dependent alone whether it is waiting, permanently impossible,
or merely delayed. The system also does not cascade cancellation or mark the
dependent as unsatisfiable. This is the largest correctness/operability issue:
it creates orphan work that looks live but can never run.

### P1 — Dependency input contract is undiscoverable

Help says only “JSON array.” A natural array of task IDs was rejected with a
generic validation error (`details: {}`). The accepted contract,
`[{"task_id":"..."}]`, was found by guessing. For an agent, this is a hard
admission blocker and an unnecessary trial-and-error loop.

### P1 — Blocked state has no explanation or dependency status

`show`, `list`, and `events` expose the edge and `blocked` status but omit the
reason and current prerequisite state. The agent must perform multiple reads and
manually join IDs. The event stream should make the causal state explicit.

### P2 — Retry semantics contradict the visible state

`tasks retry` on a visible `blocked` task returns `terminal_state`. That makes
“blocked” appear nonterminal to the user while the retry API treats it as
terminal, with no details or recovery guidance. A blocked task needs either a
supported unblock/retry path or a specific error explaining that its hard
dependency was cancelled and a replacement chain is required.

### P2 — Task labels are not first-class

The requested names `source-check` and `render-after-check` could not be passed
as task names. They had to be duplicated in the spec and idempotency keys, while
normal list output shows only opaque IDs and capabilities. This is especially
awkward when reasoning about a dependency graph. Add a display name/label to
admission and list/show output, or explicitly document the supported naming
pattern.

### P2 — Parallel read contention is surfaced as an unstructured bug

Concurrent read-only commands hit a database-owner error and emitted a
non-JSON diagnostic despite `--json`. Sequential retry worked. The gateway
should serialize/coordinate safe reads or return a structured retryable error
with a bounded backoff hint; multi-agent usage makes this more than a cosmetic
issue.

### P3 — Retired-command recovery is good but current-task discovery is thin

`next` clearly suggested `astrid --help`, and `tasks status` listed valid task
verbs. Those errors were usable. The task help would still benefit from a
one-screen lifecycle example showing create → show/list/events → cancel/retry,
plus a dependency example.

## What Astrid should have told the agent

At dependency admission:

> `--dependencies` takes objects, not bare IDs:
> `[{"task_id":"<task-id>"}]`. This creates a hard dependency. The new task
> will be `blocked` until the prerequisite succeeds.

On `show`/ `list`:

> `render-after-check` is blocked because hard dependency `source-check`
> (`a33e6ffc-...`) is currently `queued`.

After upstream cancellation:

> This hard dependency was cancelled, so the dependent is unsatisfiable and
> will not run. Retry is unavailable for cancelled/blocked tasks. Cancel this
> dependent and create a replacement prerequisite + dependent chain if the work
> is still wanted.

The product should implement that guidance as structured fields and events,
not only prose: `display_name`, `blocked_reason`, dependency snapshots/statuses,
and a dependency-invalidated event. If the intended policy is cascading
cancellation, apply it and show the cascade; if not, mark the dependent
`blocked_unsatisfiable` (or equivalent) instead of leaving an indefinitely
ambiguous `blocked` row.

