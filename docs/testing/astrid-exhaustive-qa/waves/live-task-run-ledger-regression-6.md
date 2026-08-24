# Live task/run ledger regression — wave 6

Date: 2026-08-24  
Surface: public Astrid CLI and documented public Python SDK only  
Isolation: fresh `ASTRID_PROJECTS_ROOT=/tmp/astrid-ledger-regression-6.zs2rwe/projects`  
Verdict: **PASS — no P0, P1, or F2 root cause confirmed**

## Scope and method

This was a live agent-UX replay, not a programmatic test-suite run. I created a
fresh project and canonical timeline, invoked the real built-in renderer, and
then operated the resulting kernel records through `runs`, `tasks`, and the
documented `AstridClient` facade. Product interaction used only public
CLI/SDK surfaces. I did not inspect implementation source or tests before or
during the replay, and no product code was changed.

The canonical timeline was version 1 with one structured `clipType: "text"`
clip and an authoritative 320x180@30 canvas/output:

```bash
ASTRID_PROJECTS_ROOT=/tmp/astrid-ledger-regression-6.zs2rwe/projects \
  python3 -m astrid projects create ledger-lab --name "Ledger Lab" --json

ASTRID_PROJECTS_ROOT=/tmp/astrid-ledger-regression-6.zs2rwe/projects \
  python3 -m astrid timelines create main --project ledger-lab \
  --name "Main Timeline" --default \
  --config '{"tracks":[{"id":"cards","kind":"visual","label":"Cards"}],"clips":[{"id":"title","at":0,"track":"cards","clipType":"text","hold":1,"text":{"content":"LEDGER","fontSize":48,"color":"#ffffff","align":"center"}}],"theme_overrides":{"visual":{"canvas":{"width":320,"height":180,"fps":30}}},"output":{"resolution":"320x180","fps":30,"file":"ledger.mp4"}}' \
  --registry '{}' --json
```

## Successful managed render

I used the documented project-managed SDK route:

```python
r = astrid.invoke(
    "rendering.render",
    kind="executor",
    project="ledger-lab",
    inputs={"timeline_ref": "main", "expected_version": 1},
)
```

It returned one coherent durable identity:

```text
run     b767b291da39e5a3717b853002
task    19ba84ad426ddc97fa866660ec
attempt 01m0sr9pchv613je4endxjz5kj
ok      true
```

The corrected staging contract held on the normal returned success and on a
later exact replay:

```text
InvocationResult.run_root                       null
"run_root" in InvocationResult.raw_result       false
.astrid/media/.staging recursive entries        0
```

The result contained two durable managed-CAS artifacts. Both files existed
after completion and after all later lifecycle operations, and independently
computed SHA-256 values matched the advertised hashes:

| Artifact | Advertised and actual SHA-256 |
|---|---|
| `hype.mp4` | `cd46080c312bf57b608606f05450836856f14f25ace62d5893e2d4cc5f001092` |
| `hype.mp4.provenance.json` | `2320c08c0cafc6015e5503f85654f369be07553de6ff42bf3f2e1415bf57efb0` |

The returned files were under resolved
`projects/.astrid/media/sha256/<2>/<2>/<digest>` locators. `ffprobe` confirmed
the primary artifact is H.264 at 320x180 and 30 fps.

`runs show --evidence`, `tasks show`, `runs events`, and `tasks events` all
agreed on success. The task stream was exactly:

```text
core.task.created
core.task.claimed       attempt 01m0sr9pchv613je4endxjz5kj
core.task.started       attempt 01m0sr9pchv613je4endxjz5kj
core.task.completed     attempt 01m0sr9pchv613je4endxjz5kj
```

The task had `winning_attempt_id=01m0sr9pchv613je4endxjz5kj`; run progress
was one succeeded child and zero failed/cancelled children. The run read's
ordered `child_outputs` matched the SDK artifact hashes and media IDs.

## Deterministic post-admission failure and exact replay

To force a real handler failure after admission, I submitted a syntactically
valid managed render with an unknown qualified renderer selector:

```python
r = astrid.sdk.invoke_result(
    "rendering.render",
    kind="executor",
    project="ledger-lab",
    inputs={
        "timeline_ref": "main",
        "expected_version": 1,
        "backend": "rendering.definitely_missing",
        "output_name": "doomed.mp4",
    },
)
```

This was demonstrably post-admission: it returned non-null kernel identities
and the task stream included claim/start/fail.

```text
run     6b69ff8ccec5b83abecf696ec9
task    546c455070fc4561377e723a5b
attempt 01m0srb2hfbm0fmx7460zzwjc6
ok      false
type    RendererUnsupportedError
reason  handler_failed
message unknown renderer id 'rendering.definitely_missing'
```

The first exact replay of the identical SDK request returned the same run,
task, attempt, and error mapping. It did not add task events, did not create
outputs, and left staging empty. This proves the persisted error is returned
on replay rather than collapsed to a generic failure or silently retried.

`runs show --evidence` reported a failed run, an empty output set, and one
latest failure carrying the same attempt ID and actionable error. The
`evidence` list itself was empty, as expected for this renderer-selector
failure; the structured failure is available in the sibling `failures`
field and in `tasks events`.

## Deliberate retry

I explicitly retried the failed child through the public operator verb:

```bash
python3 -m astrid runs retry-failed \
  6b69ff8ccec5b83abecf696ec9 \
  --project ledger-lab \
  --task 546c455070fc4561377e723a5b \
  --idempotency-key deliberate-retry-1 --json
```

The retry extended the exhausted single-attempt budget from 1 to 2, minted a
new fenced attempt, ran it, and persisted the deterministic failure:

```text
attempt 1  01m0srb2hfbm0fmx7460zzwjc6  failed
attempt 2  01m0srbtz3nsrknfsf5q2915a4  failed
max_attempts after explicit retry            2
```

The final seven-event task history was:

```text
created, claimed(1), started(1), failed(1),
retried(2), started(2), failed(2)
```

There was no synthetic second `claimed` event: `core.task.retried` itself
created the claimed attempt and carried its fresh lease/version data. The run
stream retained `core.run.created` followed by `core.run.retried`.

After the retry, all current-state surfaces selected attempt 2:

- `runs show --evidence` exposed only attempt 2 in the current `failures`
  summary;
- `tasks events` retained both attempts and both identical errors;
- exact SDK replay of the original doomed request returned attempt 2 and its
  error;
- `tasks show` remained failed with no winning attempt;
- `runs show` remained failed with one failed child.

Thus historical errors were preserved, the current error was not stale, and
the retry did not fork the run/task identity. Repeating the retry command with
the exact same idempotency key replayed its receipt and did **not** create an
attempt 3; the event count remained seven.

One potentially confusing but internally valid envelope detail: after the
synchronous retry finished failing, top-level `data` showed the final failed
projection while `receipt.result` retained the running projection committed
by the retry transaction before execution. The stable receipt and current
read model are serving different moments in the lifecycle. This is worth
explaining in operator docs, but it is not ledger divergence.

## Cancel and close boundaries

### Legal queued-task cancellation

I created one standalone queued task through `tasks create`, then cancelled it
before any claim:

```text
task 03d72408-642c-57aa-a1a0-08e5e7a5a3c8
queued -> cancelled
attempt null
execution_guidance null
```

The task stream contained exactly `core.task.created` and
`core.task.cancelled`; the cancel event recorded `reason=queued`, a durable
cancel request ID/timestamp, and no invented attempt. CLI exit status was 0.

### Illegal terminal operations

The following safe negative probes all exited 1 with a typed
`terminal_state` error and did not mutate the ledger:

```text
tasks cancel <succeeded-task>
tasks retry  <succeeded-task>
runs cancel  <succeeded-run>
AstridClient.runs.close(<succeeded-run>)
```

The shared response was `code=terminal_state`, message `the record is in a
terminal state`. This correctly protects terminal truth. The CLI help already
describes task cancellation as nonterminal-only. The public core skill also
states that `runs.close` is a coordinator-only transition for a zero-child or
legacy all-terminal lifecycle; normal public invocation always creates a
child, and no `runs create` CLI exists. Therefore no legal close state was
reachable in this black-box operator scenario, and I did not manufacture one
through private repository/store access.

## Final convergence and integrity

Final public reads agreed exactly:

| Record | SDK/CLI status |
|---|---|
| successful render run | `succeeded` |
| successful render task | `succeeded` |
| doomed/retried render run | `failed` |
| doomed/retried render task | `failed` |
| standalone cancelled task | `cancelled` |

The final successful exact replay still returned the original run/task/attempt
and the exact same two CAS artifacts. Both hashes still matched. Staging was
empty after success, failure, exact replay, retry, cancellation, and final
replay.

`astrid doctor --json` ended `ok=true`, `state=ready` with SQLite quick-check,
foreign-key integrity, schema-version, data-path, and managed-media checks all
`ok`.

## Agent friction and severity

- **P2 documentation clarity:** `runs retry-failed --json` returns final
  post-execution state in top-level `data`, while the immutable mutation
  receipt naturally retains the intermediate running state. This is correct,
  but an agent can initially read it as disagreement unless the receipt's
  point-in-time semantics are explicit.
- **P2 recovery specificity:** illegal terminal cancel/retry/close errors are
  typed and safe, but use the same terse `terminal_state` message with empty
  details. The relevant CLI help/core skill supplies the missing rule; adding
  a command-specific recovery sentence would reduce one documentation hop.
- **P3 DTO discoverability:** `InvocationResult.run_id` is a direct public
  convenience attribute, while task/attempt identities are most reliably
  consumed from serialized `kernel_task_id` / `kernel_attempt_id`. An agent
  guessing `result.task_id` gets `AttributeError`. The documented serialized
  envelope remains complete.

None of these produced state divergence, lost errors, duplicate attempts,
staging leakage, invalid CAS locators, or unsafe terminal mutation. They do not
meet this wave's P0/P1/F2 fix threshold, so no finding/fix document or product
change was created.

After recording the evidence and completing the final integrity check, I
removed the disposable `/tmp/astrid-ledger-regression-6.zs2rwe` tree. No
workspace product or fixture data was removed.

## Final verdict

**PASS.** The recent invocation/error/staging changes hold across success,
post-admission failure, exact replay, explicit retry, legal queued
cancellation, illegal terminal operations, SDK/CLI reads, event history, CAS
publication, and final database/media integrity. The kernel ledger remained
the single status authority and no stale-error, duplicate-attempt, or staging
regression was observed.
