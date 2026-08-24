# Replay retry envelope 4

Date: 2026-08-23 (Europe/Berlin)

## Scope

Fresh black-box LIVE UX replay using only the public SDK and CLI. No source,
tests, git state, or prior QA material was used. The disposable test root was
`/tmp/astrid-replay-envelope4.1ij6Mj` and was removed after the checks.

Project: `demo`

## Reproduction

Two `sdk.invoke("media.clip_extract", kind="executor", ...)` calls used
different absent local input paths and both deterministically failed:

| case | run | task | absent input |
|---|---|---|---|
| task retry | `df051c01f7ba17f8332035606e` | `e30be9b0978129294b6a14b3bf` | `fixtures/source-a.mp4` |
| run retry | `024cef8156dba414a3f3276620` | `cbde4594cb743f3b4e21fa73cc` | `fixtures/source-b.mp4` |

Valid 2-second MP4 files were then created at exactly those paths. Recovery
was performed with:

```text
python3 -m astrid tasks retry e30be9b0978129294b6a14b3bf --project demo \
  --idempotency-key replay-envelope4-task-retry --json
python3 -m astrid runs retry-failed 024cef8156dba414a3f3276620 --project demo \
  --idempotency-key replay-envelope4-run-retry --json
```

## Mutation-response truth (before any follow-up read)

### `tasks retry`

The command's own `data` was terminal and internally consistent:

- `data.attempt.attempt_no`: `2`
- `data.attempt.status`: `succeeded`
- `data.attempt.finished_at`: `2026-08-23T18:38:38.935574Z`
- `data.task.id`: `e30be9b0978129294b6a14b3bf`
- `data.task.run_id`: `df051c01f7ba17f8332035606e`
- `data.task.status`: `succeeded`
- `data.task.finished_at`: `2026-08-23T18:38:38.935574Z`
- prior attempt failure was at `2026-08-23T18:38:00.054767Z`, so the final
  timestamp is fresh rather than attempt-1 stale.

However, the strict response contract is not met. `data` contains no `run`,
`progress`, or `result`. More importantly, `receipt.result` is the admission
snapshot, not the command's final state: it contains attempt 2 as `claimed`
with `finished_at: null` and the task as `running` with the attempt-1
`finished_at`.

### `runs retry-failed`

This command's own `data` was terminal and complete:

- `data.run.id`: `024cef8156dba414a3f3276620`
- `data.run.status`: `succeeded`
- `data.run.finished_at`: `2026-08-23T18:38:50.842888Z`
- `data.run.result`: `{status: succeeded, succeeded: 1, failed: 0, cancelled: 0, total_children: 1}`
- `data.progress.status`: `succeeded`, `succeeded: 1`, `failed: 0`,
  `cancelled: 0`, `total_children: 1`
- `data.progress.ordered[0].task_id`: `cbde4594cb743f3b4e21fa73cc`
- `data.retried_task_ids`: `["cbde4594cb743f3b4e21fa73cc"]`

The final timestamp is fresh; attempt 1 failed at
`2026-08-23T18:38:23.847050Z`. This response does not itself expose the
attempt-2 record, but its ordered task id and subsequent public events verify
the child attempt.

## Follow-up verification

Public `tasks events` for each task contained exactly seven lifecycle events:

```text
claimed(1), started(1), failed(1), retried(2), started(2), completed(2)
```

There was no attempt 3 after either idempotent replay. Public `runs show
--evidence --json` returned `status: succeeded`, terminal `finished_at`, and
matching progress/result for both run ids.

The primary clip output was materialized as managed media and verified:

- media id: `01m0qynstt8h74f72326rh9x7d`
- kind/mime: `video` / `video/mp4`
- bytes: `261` (non-empty)
- content hash: `a555701da6bea5183cac40ea6f1b45d6fe182db4efc0cfca10ebab60fcdce498`
- location realm: `managed_local`
- locator: `.astrid/media/sha256/a5/55/a555701da6bea5183cac40ea6f1b45d6fe182db4efc0cfca10ebab60fcdce498`
- `media show` and `media verify --realm managed_local` both succeeded.

## Idempotency replay

Repeating each exact retry command with the same idempotency key did not
dispatch work and did not create attempt 3. Both receipts were stable:

- task retry receipt: `54113fe4cf434055938966b7d7da4ac6`
- run retry receipt: `224b7397ec3a4974914369f500a57434`

The run replay returned the same terminal response and receipt. The task
replay returned the same receipt and terminal ids/status/attempt 2; its
`task.event_head_seq` reflected later project events (`22` versus `16` in the
first response), so the raw envelope was not byte-identical metadata-wise.

## Verdict

**FAIL for the strict retry-response envelope requirement; PASS for recovery,
fresh terminal state, exactly-two-attempt lifecycle, managed artifact
materialization/verification, and no-op idempotency.** The blocking defect is
specific to `tasks retry`: its own JSON `data` omits terminal run/progress/result
and its receipt result remains the pre-execution claimed/running snapshot.
