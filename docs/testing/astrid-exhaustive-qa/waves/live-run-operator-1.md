# Live run/operator journey 1

Date: 2026-08-23 (Europe/Berlin)  
Scope: fresh black-box CLI + public SDK journey, no source/test/prior-QA inspection, no paid/cloud generation.  
Disposable root: `/tmp/astrid-live-operator-ujoZL4` (removed after the run).

## Verdict

**CONDITIONAL FAIL for an operator lifecycle.** Admission, discovery, read
surfaces, event evidence, deterministic failure diagnosis, corrected re-run,
and CLI/SDK read consistency worked. A queued standalone task can be safely
cancelled with no artifact publication. However, a genuinely running executor
cannot be cancelled through either public cancellation surface, failed
executor runs cannot be retried with the documented retry operations when the
default `max_attempts=1` is exhausted, and the documented SDK `runs.close`
transition has no reachable legal state in this clean public flow. Terminal
truth is protected: close attempts never relabeled terminal runs.

## Journey and evidence

### Clean start and discovery

Commands used:

```text
python3 -m astrid --help
python3 -m astrid runs --help
python3 -m astrid tasks --help
python3 -m astrid doctor --json
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-operator-ujoZL4 \
  python3 -m astrid projects create operator-live --name 'Operator Live Disposable' --json
```

The census exposed the five product families plus operational families. The
first doctor check correctly reported a brand-new root as missing its managed
database; `projects create` initialized it. Public SDK discovery then found 66
executors and 12 orchestrators. The local, network-free documented
`editorial.script_pipeline` executor supports `fake=true`, so it was used for
the successful baseline and deterministic failure. `editorial.human_review`
was used as the sufficiently-long local live boundary (`timeout=60`,
`no_open=true`).

### Successful baseline (fresh run admitted by SDK)

```python
astrid.invoke(
    "editorial.script_pipeline", kind="executor",
    include_installed=False, project="operator-live",
    inputs={"preset":"seinfeld", "fake":True,
            "candidates":2, "rough_attempts":3, "select_best":True},
)
```

Run `39f11bd7413a159e3803be09d8`; child task
`8d966c0e0402304d94c1a94336`; both ended `succeeded`. `runs list`, `runs
show --evidence`, `runs events`, `tasks list`, `tasks show`, and `tasks events`
were all usable. Run events exposed `core.run.created`; the child task event
stream exposed the full `created → claimed → started → completed` lifecycle
with 13 output media records. The task event hash chain was returned by the
public CLI.

### Rediscovery and cancellation boundary

With no remembered ID, `tasks list --project operator-live` rediscovered a
standalone queued task admitted through the public CLI:

```text
tasks create --project operator-live \
  --capability editorial.script_pipeline \
  --spec '{"preset":"seinfeld","fake":true,"candidates":100,"rough_attempts":100}' \
  --available-at 2099-01-01T00:00:00Z --max-attempts 2 --json
```

Task `73320a21-deec-5c88-b725-8d5c8b9a7fb2` was rediscovered as `queued`, with
`run_id=null`, `input_manifest=[]`, and no attempt. `tasks show` and `tasks
events` showed the admission event. This is the closest cancellable public
boundary because the CLI has no executor worker/attach operation for an
admitted standalone task.

```text
tasks cancel --project operator-live 73320a21-deec-5c88-b725-8d5c8b9a7fb2 \
  --idempotency-key cancel-live-1 --json
```

Cancellation returned `ok=true`, status `cancelled`, a receipt, and one
`core.task.cancelled` event (`reason=queued`). Repeating the exact command and
key returned the same committed receipt/result (idempotent). Repeating with a
new key returned typed `terminal_state`; no second event was appended. The
cancelled task stayed `run_id=null`, `winning_attempt_id=null`,
`input_manifest=[]`. Media list immediately after cancellation remained at 13
records (the baseline run's outputs); the final list reached 16 only after the
later corrected successful run. No record was attributable to the cancelled
task and no cancelled-task output was published.

For a real running boundary, a local human-review executor was started in a
separate terminal with `timeout=60`. `runs list` rediscovered
`4343b2b91c4e8a8c33eb1bf1b3` as `running`, and `runs show` exposed child
`0b8811f486072d87e85ff720ab` as `running`. While active:

* `runs cancel --project operator-live 4343b2b91c4e8a8c33eb1bf1b3` returned
  `validation_error`.
* `tasks cancel --project operator-live 0b8811f486072d87e85ff720ab` also
  returned `validation_error`.
* SDK `client.runs.close("operator-live", run_id)` returned
  `validation_error` while the child was active.

The executor eventually timed out without `/submit`; the final public state
was `failed`, with task event evidence
`core.task.failed` and error `human_review: timeout after 60s without /submit`.
No output artifact was published for this failed live run. This demonstrates a
real running status and progress/event observation, but not worker cancellation
because the public product rejected both cancellation requests.

### Deterministic failure, recovery, and identity reconciliation

Failure invocation (local fake mode, no network):

```python
astrid.invoke(
    "editorial.script_pipeline", kind="executor",
    include_installed=False, project="operator-live",
    inputs={"preset":"no-such-preset", "fake":True,
            "candidates":2, "rough_attempts":3},
)
```

The SDK returned `ok=false` but a committed run ID. Run
`45995099fa0d2db654d36e8718` and task `5990fec21906ed8ec322507380` were
rediscoverable. `runs show` gave `failed` progress; `tasks events` gave the
actionable cause: `FileNotFoundError` for the missing preset. The sequence was
`created → claimed → started → failed`, with no outputs.

For a separate deterministic recoverable-input test, invoking
`iteration.experiment_review` with a missing public `review` path created run
`9fe69642b97e7a2bce27e7dafd` / task `d40d4d663b1bffce211641e51e`, failed with
the public stderr guidance to provide a valid `review.json`, and published no
output. After creating a valid review file, both documented retry operations
were attempted:

```text
runs retry-failed --project operator-live 9fe69642b97e7a2bce27e7dafd --json
tasks retry --project operator-live d40d4d663b1bffce211641e51e --json
```

Both returned typed `terminal_state` because the invocation-created task had
already consumed its default single attempt. Re-invoking the corrected input
under a changed path (the original failed invocation is idempotent and returns
the same failed run) produced new run `64f463c36b65b1f6a573315dde` and task
`a5c408f717d44c88478cf49394`, both `succeeded`, with
`core.task.completed` and three review artifacts. Thus the operator can
recover by creating a new identity, but cannot use the documented retry verb
to mutate/fix the original invocation.

### `runs close` and terminal truth

The CLI help has no `runs close` verb; attempting it exited 2 with argparse's
invalid-choice error. The public SDK method is present:

```python
client.runs.close(project, run_id, outcome=None)
```

Observed behavior:

* active run `4343b2b91c4e8a8c33eb1bf1b3` → `validation_error` (active child);
* terminal succeeded run `64f463c36b65b1f6a573315dde` → `terminal_state`;
* the same terminal run with outcomes `failed`, `cancelled`, and `succeeded`
  → `terminal_state` each time.

No public command creates a zero-child run or leaves an all-terminal run in a
resolvable `running` state, so the documented legal `runs.close` case was not
reachable without source/store tricks. The negative checks do prove terminal
truth cannot be relabeled.

## Severity-ranked findings

### P1 — Running executor cancellation is not an operator action

Both public cancellation surfaces rejected a rediscovered `running` executor
and left it running until its timeout. Only a queued standalone task can be
cancelled, and that task has no run/executor attachment. Provide a worker-safe
cancellation fence or an explicit documented distinction that cancellation is
admission-only.

### P1 — Documented retry cannot recover a failed executor invocation

SDK executor invocations expose no `max_attempts`/retry policy option and
default to one attempt. `runs retry-failed` and `tasks retry` both returned
`terminal_state` on failed invocation-created tasks, even after the missing
input was corrected. A corrected re-invocation works but creates a new run and
task, leaving the operator to reconcile identities manually.

### P1 — Legal `runs.close` state is unreachable from the public flow

SDK close rejects active children and rejects every terminal run. The CLI does
not expose close at all. Terminal protection is correct, but the documented
legal close transition needs a reachable public setup or its documentation
needs to be narrowed.

### P2 — Manual ID hop and CLI-help friction

The normal path required `runs list → runs show → progress.ordered[].task_id →
tasks show/events`. `tasks show` and `tasks events` do not accept `--project`
(two initial attempts used that otherwise natural flag and exited 2), while
mutations do require it. The distinction is discoverable from subcommand help
but costs wrong-verb/argument attempts for a returning operator.

### P2 — Failure evidence is task-centric

`runs show --evidence` returned an empty evidence array for failed executor
runs; the actionable exception appeared in `tasks events`. Run progress exposes
the child ID, so the information is recoverable, but a returning operator must
perform the extra hop.

## Consistency and effort measurements

* CLI and SDK agreed on final statuses and run→task mappings for succeeded,
  failed, cancelled, and timed-out jobs.
* Event ordering was consistent: run stream had `core.run.created`; task stream
  had the lifecycle transitions and error payloads.
* Deliberate wrong/failed attempts: two `--project` misuse calls for
  read-only task subcommands, one CLI `runs close` invalid verb, two rejected
  live cancellation calls, two rejected retry calls, and four SDK close calls
  against a terminal run (one per outcome shape).
* Manual identifier hops: baseline run→task, failed run→task, corrected
  run→task, and live run→task (four explicit hops); each was obtained from
  public `runs show` progress rather than remembered IDs.
* Actionable recovery was good for diagnostics and new corrected invocation;
  retry-in-place was unavailable.
* Idempotency was good for repeated cancellation with the same key; a fresh
  key on the terminal record correctly returned `terminal_state`.

## Cleanup

Only the disposable root `/tmp/astrid-live-operator-ujoZL4` and its local test
files/processes were cleaned. No product code was modified.
