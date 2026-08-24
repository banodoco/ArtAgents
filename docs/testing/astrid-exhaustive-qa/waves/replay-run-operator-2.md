# Replay: run/operator 2

Date: 2026-08-23 (Europe/Berlin)  
Verdict: **FAIL — P1 retry execution is not reachable through the documented public surfaces.**

This was a fresh black-box replay in an isolated root, with no remembered IDs,
no cloud/paid calls, and no product-code changes. I used only the public
Astrid skill, CLI help, public SDK discovery/schema, CLI, and SDK. The temporary
root was `/tmp/astrid-replay-run-operator-2.rk66aq`.

## Commands and evidence

Bootstrap and discovery:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-replay-run-operator-2.rk66aq python3 -m astrid --help
ASTRID_PROJECTS_ROOT=/tmp/astrid-replay-run-operator-2.rk66aq python3 -m astrid doctor --json
ASTRID_PROJECTS_ROOT=/tmp/astrid-replay-run-operator-2.rk66aq python3 -m astrid projects create replay2 --name 'Replay Run Operator 2' --json
python3 - <<'PY'  # SDK, with ASTRID_PROJECTS_ROOT set
import astrid.sdk as sdk
print([c.id for c in sdk.discover(include_installed=False).executors])
PY
```

The empty-root doctor correctly returned `ok:false` because the database did
not yet exist; `projects create` initialized it. Public SDK schema inspection
identified `editorial.human_review` as a local, network-free, blocking human
gate with `timeout`, `no_open`, HTML, and JSON inputs.

### 1. Live local executor, cancellation, and terminal fence

I invoked the human gate in a background Python process:

```text
sdk.invoke('editorial.human_review', kind='executor', include_installed=False,
  project='replay2', inputs={'html':'.../review.html', 'data':'.../data.json',
  'no_open':True, 'timeout':60})
```

The process announced a localhost URL and the public reads rediscovered:

```text
run_id  = 91a3169fcf8e31ae7107f7cabd
task_id = 37e658e92531041335358e030e
capability = editorial.human_review
status = running
```

Public `tasks show/events` and `runs show --evidence/events` showed the
queued → claimed → started stream, with the run progress ordered child in
`running`.

Cancellation used the run surface and an explicit key, then repeated the
exact same request:

```text
python3 -m astrid runs cancel 91a3169fcf8e31ae7107f7cabd --project replay2 \
  --idempotency-key replay2-human-cancel --json
```

Both calls exited 0 and returned the same `cancel_request_id`:
`01m0qw1y79a7zd85p48wser5ck`, the same receipt/event IDs, and
`cancelled_task_ids:[37e658e92531041335358e030e]`.

After cancellation, `runs show` derived `status:cancelled`,
`progress.cancelled:1`, and `tasks show` reported `status:cancelled` with
`cancel_requested_at` and `finished_at` equal to the cancellation time.
Events included `core.task.cancelled` and `core.run.cancelled`; no success or
failure event followed. I waited beyond the handler's declared 60-second
normal timeout and re-read the state. The process was gone and the project
contained only `plan.md` and `project.json` — no `runs/<id>` projection or
human-review output. This proves terminal `cancelled` won and no post-cancel
artifact was emitted.

### 2. Deterministic failed run, evidence diagnosis, correction, retry

I invoked public `media.clip_extract` with a deliberately absent local input:

```text
sdk.invoke('media.clip_extract', kind='executor', include_installed=False,
  project='replay2', inputs={'input':'.../prereq.mp4','start':0,'dur':1})
```

The run failed deterministically:

```text
run_id  = 970490ad84d292b621c1a48014
task_id = 0a0476f943975f28326c33dbed
attempt = 01m0qw3a184jex831xgqmrvh60 (attempt_no 1)
```

`runs show 970490ad84d292b621c1a48014 --project replay2 --json --evidence`
returned a structured failure with `reason:handler_failed`, the executor
return code 2, and the actionable stderr guidance `input file not found` /
`check the input file path, start time, and duration`. Task events ended with
`core.task.failed`, `outcome:failed`, and `reason:executor_failed`; no run
artifact was present.

I corrected the external prerequisite by generating a two-second local MP4
with ffmpeg, then used the documented retry:

```text
python3 -m astrid tasks retry 0a0476f943975f28326c33dbed --project replay2 \
  --idempotency-key replay2-task-retry --json
```

The retry response preserved the same task and run IDs and admitted exactly
one new attempt, `01m0qw42sy0r942jm9wv8m0m9b` (`attempt_no:2`), with one
`core.task.retried` event and `max_attempts:2`. Repeating the exact command
with the same key returned the same attempt ID and receipt/event ID; it did
not create another admission or attempt.

### 3. Retry execution failure / contradictory read model

After the retry command, no public executor process was running. Repeated
read-only polling showed:

```text
tasks list: task 0a0476f943975f28326c33dbed status=running
tasks show: status=running, attempt_no=2, finished_at=old attempt-1 time
runs show --evidence: progress child=running, progress.status=running,
  top-level run.status=failed, result.status=failed,
  top-level finished_at=old attempt-1 time
runs list: run status=failed
```

No `core.task.started`/`core.task.succeeded` event for attempt 2 appeared and
no `clip.mp4` or run projection was produced. The run-level
`runs retry-failed` then rejected with a generic `validation_error` because
the derived child was running; `runs cancel` rejected with `terminal_state`
because the top-level run was already terminal. Thus the corrected
prerequisite could not be driven to success through the documented public
retry/dispatch surfaces, and the run/task read models disagree.

## Read-only scope, terminal protection, and close guidance

`tasks show <id> --project replay2 --json` and
`tasks events <id> --project replay2 --json` both accepted the explicit
project scope and returned project-scoped records. The same-key second run
cancel was a successful idempotent no-op with the original receipt.

SDK terminal-transition probes returned typed `terminal_state` errors for
both cancelling the already-cancelled run and cancelling its already-cancelled
task. `client.runs.close('replay2', <cancelled-run-id>)` likewise returned a
typed `terminal_state` error. The public `runs --help` exposes no `close`
operator verb, while the public skill explicitly documents `runs.close` as a
coordinator-only transition for zero-child/all-terminal lifecycle ownership.

## Wrong turns and friction

* Empty-root `doctor --json` exits nonzero before initialization; the error is
  understandable and points to `projects create`, but scripts need to tolerate
  the expected first-run failure.
* The CLI/SDK surfaces make cancellation clear and idempotent, but retry output
  says “running/claimed” without exposing how a user starts the executor that
  should consume that attempt.
* `runs show --evidence` is useful for the original failure, but after retry it
  presents mutually inconsistent top-level and derived statuses and the run's
  old `finished_at`.
* The retry operation is admission-idempotent, but the same-key success masks
  that the retried attempt is never executed; a user can believe recovery is
  underway while no worker exists.

## Verdict

Cancellation and terminal fencing pass: live local work is discoverable,
cooperatively cancelled, repeat-cancel idempotent, and leaves no post-cancel
artifact. Read-only project scoping, evidence diagnosis, terminal rejection,
and coordinator-only `close` guidance are present. The end-to-end recovery
journey fails: after correcting the prerequisite, documented retry preserves
identity and avoids duplicates but does not execute the retried attempt, and
the read model becomes internally contradictory. This is a P1 operator UX
blocker for “diagnose → correct → retry → succeed.”
