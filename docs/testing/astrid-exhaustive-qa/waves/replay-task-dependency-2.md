# Replay: task dependency UX (fresh live run)

## Verdict

PASS. The dependency workflow is discoverable from the public CLI, exposes a
clear live blocked state and then a clear unsatisfiable state, gives truthful
retry guidance, and makes the non-cascade cancellation policy observable.

## Live setup

- Used a fresh `ASTRID_PROJECTS_ROOT` created with `mktemp`:
  `/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/tmp.9eODJyIpWJ`.
- Started at the public surface with `python3 -m astrid --help` and
  `python3 -m astrid tasks --help`.
- Created project `queue-lab` (`beca965c-6698-5892-af17-a202738f1bf4`).
- No source inspection, test runner, SDK calls, or programmatic test harness
  was used; all observations below came from live CLI commands.

## Discoverability

`python3 -m astrid tasks create --help` documents:

```text
--dependencies DEPENDENCIES
  Optional dependency objects as a JSON array; example
  '[{"task_id":"<task-id>","kind":"hard","ordinal":0}]'.
  kind defaults to hard; hard deps block until succeeded, soft deps never block.
```

This makes the schema, default kind, and blocking semantics discoverable
without guessing.

## Workflow evidence

1. Created standalone source-check task `01bf07eb-0f28-57a3-92d2-40e0cd46d550`
   with real capability `rendering.timeline_visualize` and harmless spec
   `{"timeline_source":"source-check.json"}`. Admission succeeded with
   status `queued`.
2. Created dependent render task `4c7c86d9-0a51-53e2-96f6-3d49758749d4`
   with spec `{"timeline_source":"render-after-check.json"}` and
   dependency `[{'task_id': source-check, 'kind':'hard', 'ordinal':0}]`.
   Admission succeeded and immediately returned status `blocked`.
3. Fresh `tasks show` and `tasks list` exposed both:

   - `blocked_reason`: `blocked: waiting for hard prerequisite
     01bf07eb-... (queued)`
   - `hard_prerequisites`: the prerequisite id, kind `hard`, ordinal `0`, and
     status `queued`.

   The dependent's `tasks events` stream also recorded the dependency in the
   immutable `core.task.created` event.
4. Cancelled the prerequisite using the project-scoped cancel command. It
   became terminal `cancelled` with a `core.task.cancelled` event.
5. The dependent was not cascade-cancelled. A fresh `tasks show` changed its
   reason to:

   ```text
   unsatisfiable: hard prerequisite 01bf07eb-... (cancelled) cannot satisfy
   this task; cancel this dependent and create a replacement prerequisite chain
   ```

   It remained explicitly `blocked`, with `hard_prerequisites` showing the
   prerequisite as `cancelled`. `tasks list` exposed the same prerequisite
   status and dependent state.
6. Retrying the dependent failed truthfully with typed `validation_error`,
   `reason: dependency_unsatisfied`, and recovery text explaining that retry
   is unavailable; wait for every hard prerequisite to succeed, or cancel this
   dependent and create a replacement chain if a prerequisite is cancelled or
   failed. Retrying the cancelled prerequisite correctly returned
   `terminal_state`.
7. Cancelled the unsatisfiable dependent explicitly. Final `tasks list` showed
   both tasks as `cancelled`. The dependent event stream contained the original
   `core.task.created` event followed by `core.task.cancelled` with reason
   `blocked`; the prerequisite stream contained `core.task.created` followed
   by `core.task.cancelled` with reason `queued`.

## UX assessment

- Dependency schema: discoverable and actionable in help.
- Waiting state: clear, with prerequisite id, kind, and current status.
- Cancellation behavior: non-cascade policy is understandable because the
  dependent remains visible, becomes explicitly unsatisfiable, and directs the
  operator to cancel it and create a replacement chain.
- Retry behavior: correctly refuses a fundamentally unsatisfiable dependency
  rather than pretending retry can recover it.
- Recovery: explicit cancellation of the dependent is the correct recovery for
  this run; a fresh prerequisite chain is required for continued work.

