# Task dependency UX repair

Date: 2026-08-23  
Wave: `waves/live-task-dependency-1.md`  
Surface: live `python3 -m astrid` CLI, isolated project root

## Outcome

The task-dependency journey now gives an agent enough information to form and
recover a dependency chain without inspecting source or guessing the graph
schema:

- `tasks create --help` documents the object shape and a copyable example:
  `[{'task_id':'<task-id>','kind':'hard','ordinal':0}]`. It also explains
  that `kind` defaults to `hard`, hard edges block until `succeeded`, and soft
  edges never block.
- Malformed dependency input returns `validation_error` with `field`,
  `expected`, `received_type`/`received`, an example, and a recovery hint.
  Bare task-id strings are therefore rejected with a useful explanation
  instead of `details: {}`.
- `tasks show` and `tasks list` expose `hard_prerequisites`, including each
  prerequisite id, edge kind/ordinal, and current status, plus a derived
  `blocked_reason`. A queued/blocked prerequisite is described as waiting;
  a failed/cancelled prerequisite is described as `unsatisfiable`.
- Retrying a blocked dependent is rejected as a non-mutating
  `validation_error` with `reason: dependency_unsatisfied` and explicit
  recovery. Waiting tasks should wait for every hard prerequisite; a chain
  with a failed/cancelled prerequisite should be cancelled and recreated.

The existing contract does not require cascading cancellation, so cancellation
remains local. A dependent stays `blocked`, but its read-time projection now
truthfully identifies that it can never satisfy its immutable hard edge under
the current chain.

## Exact isolated live journey

The journey was run sequentially with only the public CLI against a fresh
`ASTRID_PROJECTS_ROOT`:

1. Create `queue-lab`.
2. Submit `dependencies=["not-an-object"]`: the CLI returned an actionable
   structured validation envelope naming `dependencies[0]` and the expected
   dependency object.
3. Create a queued `source-check` task.
4. Create `render-after-check` with
   `dependencies=[{"task_id":"<source-id>"}]`: it was admitted as
   `blocked`.
5. `tasks show`/`tasks list` reported the prerequisite as `queued` and the
   reason as waiting for that hard prerequisite.
6. Cancel `source-check`.
7. Fresh `show`/`list` reads reported the dependent's prerequisite as
   `cancelled` and `blocked_reason` as `unsatisfiable`, with the replacement
   chain recovery.
8. `tasks retry <dependent>` returned the specific dependency recovery and
   made no mutation. `tasks events <dependent>` still showed only its original
   creation event; no unsupported cascade or synthetic transition was added.

## Verification

- `python3 -m compileall -q astrid/core/repositories/tasks.py astrid/sdk/exceptions.py astrid/core/cli/domain_tasks.py`
- `pytest -q tests/v10/test_task_admission.py tests/sdk/test_tasks.py` — **60 passed**

No broad test suite was run.
