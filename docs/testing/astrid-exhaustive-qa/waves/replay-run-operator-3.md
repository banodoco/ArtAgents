# Replay run operator 3 — live UX recovery replay

Date: 2026-08-23 (Europe/Berlin)  
Checkout: `/Users/peteromalley/Documents/reigh-workspace/Astrid`  
Surface: public CLI, public `astrid.sdk`, and public `AstridClient`; no source,
tests, git history, or prior QA reports were used.  
Disposable root: `/tmp/astrid-replay3-run.BK9VK0` (`ASTRID_PROJECTS_ROOT`).

## Verdict

**PASS for the requested operator recovery paths, with one UX caveat.** A real
local subprocess was cancelled cooperatively and stayed terminal; missing media
input was diagnosed, repaired at the same path, and recovered through both
single-task retry and batch run retry. IDs were preserved and each recovery
created exactly attempt 2. Final `runs show --evidence`, `tasks show`, and event
streams agree: both repaired runs and tasks are `succeeded`, with managed media
artifacts. Same-key replay returned the original receipt and did not create
attempt 3.

The retry command envelope is a pre-finalization snapshot: its `data.task` (and
the batch `data.run`) can still say `running` and retain the previous
`finished_at` while the synchronous executor is finishing. A follow-up show is
needed for the terminal truth. The durable event stream and subsequent reads
were truthful and final. An in-flight read during a separate probe was blocked
by the retry process's canonical-store ownership, so I do not claim direct
mid-attempt proof of the cleared `finished_at`; final state and the retried /
started / completed event sequence are correct.

## Setup and public discovery

```sh
ROOT=$(mktemp -d /tmp/astrid-replay3-run.XXXXXX)
export ASTRID_PROJECTS_ROOT="$ROOT"
python3 -m astrid doctor --json
python3 -m astrid projects create replay3 --name 'Replay 3' --json
python3 -m astrid --help
python3 -m astrid tasks --help
python3 -m astrid runs --help
```

The first doctor was correctly red on a brand-new root; project creation
initialized the kernel. Public SDK discovery showed `blender.render` and
`media.clip_extract` as real executor capabilities. No separate public
blocking/sleep executor was discoverable.

## 1. Running local executor: cancel, repeat, wait, terminal fence

To make a real local executor block, I used a disposable executable supplied as
the public `blender.render` `inputs.blender` path. It slept for 120 seconds;
the SDK invocation was launched in a background process:

```sh
python3 - <<'PY' > "$ROOT/replay3/scratch/blender.invoke.log" 2>&1 &
import astrid.sdk as sdk
print(sdk.invoke(
    'blender.render', kind='executor', include_installed=False,
    inputs={'execution':'local', 'blender':'.../replay3-blocking-blender.sh',
            'frames':1, 'engine':'eevee', 'resolution':'16x16'},
    project='replay3'))
PY
python3 -m astrid runs list --project replay3 --json
python3 -m astrid tasks list --project replay3 --json
python3 -m astrid runs cancel --project replay3 \
  --idempotency-key replay3-cancel-run-1 --json 80d262df150fc0a355b9416cbf
python3 -m astrid runs cancel --project replay3 \
  --idempotency-key replay3-cancel-run-1 --json 80d262df150fc0a355b9416cbf
python3 -m astrid tasks cancel --project replay3 \
  --idempotency-key replay3-cancel-task-terminal --json 23bf620db2ebdaba8c39642e91
sleep 3
python3 -m astrid runs show --project replay3 --json 80d262df150fc0a355b9416cbf
python3 -m astrid tasks show --project replay3 --json 23bf620db2ebdaba8c39642e91
python3 -m astrid runs events --project replay3 --json 80d262df150fc0a355b9416cbf
python3 -m astrid tasks events --project replay3 --json 23bf620db2ebdaba8c39642e91
find "$ROOT/replay3/runs" -maxdepth 4 -type f -print
```

Rediscovered IDs: run `80d262df150fc0a355b9416cbf`, task
`23bf620db2ebdaba8c39642e91`. First run cancel returned `cancelled_task_ids`
and `cooperative_task_ids` containing the task, run progress
`cancelled:1/failed:0/succeeded:0`, and one receipt. Repeating the exact key
returned the identical `cancel_request_id`, receipt ID, event IDs, and result.
The task-level new-key cancel correctly returned `terminal_state`. After the
wait, both reads remained `cancelled`, with the same `finished_at` and no
winning attempt. Event kinds were exactly `created`, `claimed`, `started`,
`cancelled`; no completion event occurred. The run projection tree was empty
(no artifact files), and `ps` showed no executor process remaining.

## 2. Missing media input → `tasks retry` → success

Initial invocation used the absent path
`$ROOT/replay3/scratch/retry-source.mp4`:

```sh
python3 - <<'PY'
import astrid.sdk as sdk
print(sdk.invoke('media.clip_extract', kind='executor',
  include_installed=False,
  inputs={'input':'.../retry-source.mp4','start':0,'dur':1}, project='replay3'))
PY
python3 -m astrid runs show --project replay3 --evidence --json \
  a5a6be6a222ba2999bbc85af9b
python3 -m astrid tasks show --project replay3 --json \
  834308b9597f202bc296f700c5
python3 -m astrid tasks events --project replay3 --json \
  834308b9597f202bc296f700c5
```

The executor reported `input file not found` with recovery guidance. Run
`a5a6be6a222ba2999bbc85af9b` and task `834308b9597f202bc296f700c5` were
`failed`; `runs show --evidence` exposed one failure with attempt
`01m0qxn7xgm7w2g90wqc2yx585` and an empty evidence list.

I created a valid 2-second MP4 at the exact same path with ffmpeg, imported it
through the public media command, then retried:

```sh
ffmpeg -hide_banner -loglevel error -y -f lavfi \
  -i color=c=blue:s=64x64:d=2 -f lavfi -i sine=frequency=440:duration=2 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest \
  "$ROOT/replay3/scratch/retry-source.mp4"
python3 -m astrid media import "$ROOT/replay3/scratch/retry-source.mp4" \
  --project replay3 --json
python3 -m astrid tasks retry --project replay3 \
  --idempotency-key replay3-task-retry-1 --json \
  834308b9597f202bc296f700c5
python3 -m astrid tasks retry --project replay3 \
  --idempotency-key replay3-task-retry-1 --json \
  834308b9597f202bc296f700c5
```

The retry preserved the same run/task IDs and emitted exactly attempt 2,
`01m0qxnv1ggdqa730bbygv4h0m`, with `max_attempts:2`. Final reads reported:

```text
run  a5a6be6a222ba2999bbc85af9b  succeeded  finished_at=2026-08-23T18:21:12.515171Z
task 834308b9597f202bc296f700c5 succeeded  finished_at=2026-08-23T18:21:12.515171Z
winning_attempt_id=01m0qxnv1ggdqa730bbygv4h0m
events=created, claimed, started, failed, retried, started, completed
```

The completion event published two managed artifacts: primary video
`01m0qxnvy7hn1z2yjt5y15z0ba` (`managed_local`, 9,934 bytes,
`out/clip.mp4`) and manifest data `01m0qxnvy3scxjmwdq9gnv6a0h` (456 bytes,
`out/manifest.json`). `media show` verified both locators and hashes. The
same-key retry returned the original receipt/event IDs and final inspection
still showed attempt 2 only—no attempt 3.

## 3. Separate `runs retry-failed` replay

I repeated the missing-input setup with
`$ROOT/replay3/scratch/runretry-source.mp4`, then created a valid red MP4 at
that same path and ran:

```sh
python3 -m astrid runs show --project replay3 --evidence --json \
  9a7a73f283dc20e2441686d8e1
python3 -m astrid runs retry-failed --project replay3 \
  --idempotency-key replay3-run-retry-failed-1 --json \
  9a7a73f283dc20e2441686d8e1
python3 -m astrid runs retry-failed --project replay3 \
  --idempotency-key replay3-run-retry-failed-1 --json \
  9a7a73f283dc20e2441686d8e1
```

Final run `9a7a73f283dc20e2441686d8e1` and task
`3a454139f5728762378e5c4f51` were both `succeeded`, with exactly attempt 2
(`01m0qxq660sbejdm0b628wsxxd`) and the same event pattern as above. The
completion event published managed video
`01m0qxq764nsjj2z7x5fcd2ktt` (261 bytes, `out/clip.mp4`) plus manifest
`01m0qxq761b12k4m6mqx9sva0r` (458 bytes). Same-key batch replay returned the
original receipt and did not create attempt 3.

## Operator guidance / wrong turns

- `python3 -m astrid runs close --help` is intentionally rejected; the
  operator CLI has only `list/show/cancel/retry-failed/events`.
- Public SDK inspection showed `client.runs.close(project_id, run_id, ...)`
  and its documentation says it is coordinator-only for zero-child or
  already-all-terminal runs. Calling it on the cancelled terminal run returned
  `terminal_state` without a receipt. Operators should use `runs cancel` or
  `runs retry-failed`; coordinators own `close`.
- A first attempt to block `media.clip_extract` with a FIFO failed immediately
  because executor input staging treated the FIFO as missing. This was a
  disposable wrong turn; the real `blender.render` subprocess fixture provided
  the requested live cancellation coverage.
- Polling a task while a background retry owned the canonical store returned
  the documented retryable `unavailable/store_owned` error. The retry then
  finalized; final show/events were used as the authoritative evidence.

All disposable executor fixture scripts were removed from the checkout. No
product code or tests were modified.
