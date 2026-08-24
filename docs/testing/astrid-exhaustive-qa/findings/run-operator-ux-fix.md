# Run/operator UX fix

Date: 2026-08-23 (Europe/Berlin)  
Source wave: `waves/live-run-operator-1.md`  
Scope: live kernel/SDK-shaped operator actions over a disposable root, followed by narrow regression tests.

## Outcome

The operator lifecycle is now recoverable and truthful:

- `tasks cancel` and `runs cancel` accept a running child without exposing
  executor-internal attempt/lease fences. The single writer atomically wins
  either cancellation or completion. If cancellation wins while the handler
  is outside SQLite, the task and attempt become terminal `cancelled`, the
  handler may finish its current work, and its later completion is fenced so
  no media or task output is published.
- `tasks retry` / `runs retry-failed` permit exactly one deliberate retry for a
  failed invocation child that consumed its default `max_attempts=1`. The
  existing task and run IDs are preserved; the task budget is extended to two
  attempts only for that retry. A retry receipt is idempotent, and a second
  failed attempt is budget-exhausted rather than entering an automatic loop.
- `runs.close` remains an SDK coordinator transition for zero-child/legacy
  lifecycle repair. It is explicitly not an operator CLI action; operator
  recovery is `runs cancel` or `runs retry-failed`. Terminal relabel protection
  remains unchanged.
- Task read-only commands accept the natural `--project` scope and reject a
  foreign task with typed validation. `runs show` now exposes compact failed
  attempt evidence (`task_id`, `attempt_id`, parsed error) alongside ordered
  progress, removing the unnecessary manual hop to task events for the common
  failure diagnosis.

## Live reproduction and proof

The initial black-box report reproduced the old behavior: both cancellation
surfaces rejected a genuinely running `editorial.human_review` invocation,
and both retry verbs returned `terminal_state` after a default one-attempt
failure. The fix was then exercised against a fresh disposable SQLite root
(`/tmp/astrid-runop-proof-*`), using a real `ExecutionService` worker thread
and public-shaped repository services:

1. Admit a run with one child, claim/start it, and run a handler that blocks
   outside SQLite before writing `late.txt`.
2. While the handler is live, issue the operator cancellation without
   attempt/lease/version arguments.
3. Release the handler; it writes the file and returns a valid manifest.
4. The completion fence returns `losing`; no media row is created.

Observed proof output:

```text
CANCEL cancelled the running handler may finish its current work, but its completion is fenced and no post-cancel artifact will be published prepared losing
MEDIA_COUNT 0
```

The same disposable root then admitted a one-child invocation-shaped run,
forced its attempt to fail with `{"reason":"missing external file"}`, and
called group retry twice with the same key:

```text
RETRY <same-run-id> <same-task-id> failed (<same-task-id>,) (<same-task-id>,) running
```

The first call created attempt 2 and reopened the failed run to `running`; the
second call replayed the same receipt and task identity without creating a
third attempt. A second failed attempt is covered by the existing exhausted
budget fence. Cancellation and terminal-state transitions remain writer-order
wins; a completion that wins first still makes later cancellation return the
typed terminal outcome.

Additional disposable-root checks produced:

```text
IDEMPOTENCY True True TaskTransitionError RELABEL RunTerminalError
```

That is: duplicate cancel replayed the same task/event head, a fresh-key
cancel on the terminal task was rejected, and attempts to relabel a closed run
were rejected without mutation.

The public CLI read-scope replay also passed:

```text
CLI_SCOPE True <task-id>
CLI_EVENTS_SCOPE True 1
```

## Narrow verification

```text
python3 -m compileall -q \
  astrid/core/repositories/tasks.py \
  astrid/core/repositories/runs.py \
  astrid/core/task_executor/service.py \
  astrid/sdk/invocation.py \
  astrid/sdk/tasks.py astrid/sdk/runs.py \
  astrid/core/cli/domain_tasks.py

pytest -q tests/v10/test_task_executor.py -k 'cancel' \
  tests/v10/test_run_close.py -k 'terminal' \
  tests/v10/test_domain_cli_surface.py -k 'task' --maxfail=1
29 passed, 50 deselected
```

The broader pre-existing SDK public-surface selection still has unrelated
failures from concurrent generation-preflight and `_kernel_invoke` signature
changes; those are outside this run/operator loop and are not used as
evidence for this fix.

## Second-order replay finding and fix

The independent replay wave found a deeper failure in the first version of
this fix: `tasks retry` admitted attempt 2 and returned `running`, but no
executor was dispatched. The task remained running with the old `finished_at`
on its parent run, so `runs retry-failed` then saw a terminal run and could not
recover it. This was reproduced before changing the implementation and was
treated as a separate end-to-end defect rather than as a successful retry.

The retry path now shares `dispatch_retried_task` between both public retry
surfaces. A fresh retry receipt admits exactly one fenced attempt, relocates
declared outputs into the attempt's private staging directory (including
project-scoped invocations), executes the immutable capability/spec through
the real handler, and completes through the normal media fence. The
one-attempt invocation exception reopens a failed parent projection before
dispatch (`status=running`, `finished_at=NULL`, derived failed count zero).
Exact receipt replays remain read-only and create no additional attempt or
event; `runs show` is the authoritative current read after dispatch.

### Fresh public `tasks retry` proof

On disposable root `/tmp/astrid-task-retry-proof-*`, a real public
`media.clip_extract` invocation first failed because its immutable
`replay/prereq.mp4` path was absent. After creating a valid MP4 at that exact
path, public `tasks retry` executed attempt 2 and published two managed media
records (manifest and video):

```text
TASK_RETRY True succeeded 2
TASK_REPLAY True True 1
FINAL succeeded succeeded 1 2026-08-23T18:15:00.069032Z 2
MEDIA [('data', 443), ('video', 261)]
```

The task and run IDs were unchanged. The replay used the same attempt/event
receipt (`True True 1`) and did not create a third attempt.

### Fresh public `runs retry-failed` proof

On disposable root `/tmp/astrid-run-retry-proof4-*`, the same missing-input
journey was exercised through public `runs retry-failed`. After correcting the
external prerequisite, the retry dispatched the actual clip executor and the
managed media store contained the resulting non-empty clip. The terminal read
was consistent across task, derived progress, run result, and `finished_at`:

```text
INITIAL run=990515f2aceb7163152a9fed96 task=3001d0dd95421372797e79fe74
RETRY True None {
  ... "status": "succeeded", "result": {
    "status": "succeeded", "succeeded": 1, "failed": 0,
    "cancelled": 0, "total_children": 1
  }, "retried_task_ids": ["3001d0dd95421372797e79fe74"], ...
}
FINAL_STATUS succeeded {"status": "succeeded", "succeeded": 1,
"failed": 0, "cancelled": 0, "total_children": 1} \
2026-08-23T18:13:09.219111Z ...
ARTIFACT managed_local video/mp4 261 bytes
```

The exact-key replay returned the same immutable retry receipt and now also
refreshes its response data to the current post-dispatch terminal read,
without dispatching a second attempt.

The implementation also fixed a read-only row-factory bug in the run service
that otherwise surfaced as the opaque `dictionary update sequence` internal
error during group retry. Narrow regression coverage now pins the parent
projection reopening:

```text
pytest -q tests/v10/test_task_executor.py \
  -k 'one_shot_invocation_retry_reopens_parent_projection or cancel' \
  --maxfail=1
1 passed, 29 deselected

pytest -q tests/sdk/test_runs.py -k 'retry_failed' --maxfail=1
3 passed, 13 deselected
```

The live proofs were performed before these narrow tests, as required. No
user project was touched; all roots and media were disposable.

## Replay-3 response-envelope correction

The next live replay exposed a response-only defect: the synchronous handler
finished, but the initial `tasks retry`/`runs retry-failed` envelope still
contained the repository's admission snapshot (`running`/`claimed`, and in
some cases the prior `finished_at`). A follow-up show was required even
though execution was already complete.

The services now perform an authoritative read after synchronous dispatch and
also on exact-key replay. `tasks retry` refreshes both the task and latest
attempt DTO; `runs retry-failed` refreshes current run counts, status, nested
result, `finished_at`, and progress. The command receipt remains the same
immutable receipt, and replay performs no dispatch or attempt creation, but
its response data is now the same current terminal result as the original
successful response.

Fresh disposable-root proof:

```text
TASK_RESPONSE succeeded succeeded 2026-08-23T18:28:47.299401Z
TASK_SHOW_MATCH True True succeeded
RUN_RESPONSE succeeded 2026-08-23T18:28:51.183975Z succeeded
RUN_SHOW_MATCH True True True
ATTEMPTS 2 ["<same-task-id>"]
```

Here `TASK_SHOW_MATCH` proves the first task-retry response already matched
the immediate authoritative show; the second `True` proves same-key replay
returned identical final data. `RUN_SHOW_MATCH` proves the same for the batch
run, including `finished_at`, and its final `True` proves replay equality.
Both paths remained at attempt 2; no attempt 3 or extra dispatch occurred.

Focused regressions cover both public service response envelopes:

```text
pytest -q tests/sdk/test_tasks.py \
  -k 'retry_response_refreshes or retry_restarts' --maxfail=1
2 passed, 19 deselected

pytest -q tests/sdk/test_runs.py \
  -k 'retry_failed_response_refreshes or retry_failed_restarts' --maxfail=1
2 passed, 15 deselected
```

## Replay-4 receipt/result correction

Replay 4 found one remaining inconsistency specific to `tasks retry`: the
current `data.task` and `data.attempt` were final, but the public receipt still
contained the pre-dispatch claimed/running result and the task response had no
parent `run`, `progress`, or `result` fields. It also observed event-head
metadata changing between an original response and replay.

The receipt architecture is still identity-immutable: receipt id, request
hash, event ids, and project sequence are never changed, and no second receipt
or event is emitted. Because these retries execute synchronously, the receipt
`result_json` is now finalized in place after the fenced handler completes.
This changes only the committed result payload from admission snapshot to the
authoritative terminal response, so exact-key repository replay remains
idempotent while its result is no longer contradictory. A task response now
always includes nullable `run`, `progress`, and `result`; invocation-created
tasks populate them from the current parent run, while standalone tasks return
`null` for all three.

Fresh live proof on `/tmp/astrid-replay5-receipt-*`:

```text
FIRST succeeded succeeded succeeded succeeded succeeded
RECEIPT succeeded succeeded succeeded succeeded 2026-08-23T18:45:55.567084Z
REPLAY_STABLE True True True
SHOW_MATCH True True True
```

The first line covers task, attempt, parent run, parent progress, and parent
result. The receipt itself is terminal too; replay retained the same receipt
identity, returned byte-stable logical result (including unchanged
`event_head_seq`), and produced no attempt 3. Public task/run shows matched
the response immediately.

## Files changed for this loop

- `astrid/core/repositories/tasks.py` — cooperative running cancellation,
  one-shot invocation retry eligibility/budget extension, receipt evidence.
- `astrid/core/repositories/runs.py` — running-child group cancellation,
  failed-run one-shot retry, cooperative child reporting.
- `astrid/core/task_executor/service.py` — cancellation-aware failure routing.
- `astrid/core/receipts/service.py` — in-place synchronous result finalization
  preserving receipt identity.
- `astrid/application.py` — parent run service wired into task retry reads.
- `astrid/sdk/invocation.py` — losing/cancelled completion truth and staging
  cleanup without publication.
- `astrid/sdk/tasks.py`, `astrid/core/cli/domain_tasks.py` — read-only
  project scope consistency and authoritative retry task/attempt responses.
- `astrid/sdk/runs.py` — run-level failed-attempt evidence and authoritative
  retry run/progress responses.
- `tests/sdk/test_tasks.py`, `tests/sdk/test_runs.py`,
  `tests/v10/test_task_executor.py` — narrow retry/cancellation regressions.
- `astrid/packs/_core/skill/SKILL.md` — coordinator-only close guidance.

No user project was touched; the proof root and its generated files were
disposable.
