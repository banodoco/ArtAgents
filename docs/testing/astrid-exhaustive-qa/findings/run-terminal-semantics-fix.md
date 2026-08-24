# Run terminal semantics fix

## Verdict

The confirmed live-agent F0 is fixed. A synchronous SDK invocation now leaves
its run terminal when the only child fails terminally; the run status and
derived progress agree; the documented default `client.runs.close(project,
run_id)` cannot relabel that work as succeeded; and the failed invocation's
per-attempt media staging directory is removed.

## Intended invariant

The kernel task rows are the source of truth. `derive_run_progress_counts`
must produce the same terminal outcome at read time and at every persisted run
projection/finalization boundary:

* while any child is queued, blocked, or running, the run is `running`;
* once all children are terminal, any failed child makes the run `failed`;
* otherwise any cancelled child makes it `cancelled`;
* otherwise all children succeeded and the run is `succeeded`;
* a zero-child run is the one deliberate exception: it derives `running` and
  needs an explicit close transition, whose omitted outcome defaults to
  `succeeded` for compatibility.

`run.json` remains a derived, write-once projection and is not consulted for
status. A successful or failed synchronous `sdk.invoke` therefore needs to
return after the kernel task transition has also recomputed its parent run;
`runs.close` is a recovery/lifecycle operation, not a status override.

## Root causes found

1. `TaskRepository.complete` recomputed the parent run, but terminal
   `TaskRepository.fail` did not. A handler failure could leave the child
   `failed` while the run row remained `running` even though the read-time
   progress already said `failed`.
2. The SDK run service exposed `outcome="succeeded"` as the close default.
   A fresh agent following the public close path could therefore write
   `runs.status=succeeded` while the child-derived counts still contained
   `failed: 1, succeeded: 0`.
3. `ExecutionService.execute` intentionally retained its assigned
   `.astrid/media/.staging/<txn>` directory after a synchronous handler or
   manifest failure. The startup GC is correct for crash leftovers, but this
   normal failure path created avoidable doctor warnings.

## Changes

* Terminal `TaskRepository.fail` and terminal lease expiry now call the same
  `_update_run_projection_on_child_terminal` helper used by completion. This
  keeps parent status, `finished_at`, and persisted progress aligned with the
  shared derivation rule.
* `RunsService.close` and `RunRepository.close` now accept an omitted outcome.
  After verifying that no non-terminal child remains, the repository derives
  the outcome from child rows. Zero-child close still resolves to
  `succeeded`; failed/cancelled terminal children resolve to their honest
  result. An explicitly contradictory outcome is rejected before mutation,
  including the legacy case where a run row is still `running` despite an
  already-terminal failed child.
* After failure has been durably routed through `TaskRepository.fail`, the
  execution service removes only the exact kernel-generated attempt staging
  directory. Symlinks are refused and filesystem removal errors are left to
  the existing startup GC rather than masking the recorded failure.

### Compatibility decision

The old explicit `outcome="succeeded"` argument remains accepted for
zero-child runs and for already-successful child sets. The public omitted
default is now derived, which changes only the unsafe ambiguous case. An
explicit outcome that contradicts terminal child rows now returns a typed
validation error instead of silently rewriting the run. Existing explicit
`failed` and `cancelled` zero-child close behavior is preserved.

## Live isolated verification

Using a fresh root `/private/tmp/astrid-terminal-fix-x8ajmC`, I created the
`live-failure` project and invoked the public SDK entrypoint:

```python
astrid.invoke(
    "generation.generate_image",
    kind="executor",
    include_installed=False,
    project="live-failure",
    inputs={
        "mode": "t2i",
        "model": "not-a-real-model",
        "execution": "codex",
        "prompt": "a test image",
    },
)
```

The invocation returned `ok=false`, run
`cd4315fb02ca03dd2911ee465e`, and task
`ae98242c438a7d208c72a64d86`. The actionable unknown-model executor error was
recorded. A fresh `AstridClient` then reported:

```text
runs.list: status=failed, result.failed=1, result.succeeded=0,
           result.total_children=1, finished_at=<set>
runs.show: progress.status=failed, failed=1
runs.close(project, run_id): ok=false, error.code=terminal_state
```

The exact staging root had no transaction directories (`STAGING []`), and
`python3 -m astrid doctor --json` returned `ok: true` with `media_paths: ok`
and no orphan-staging warning.

## Regression verification

```text
98 passed in 15.26s
```

The focused set covers repository close semantics, task lifecycle/expiry,
execution failure routing and cleanup, parent-run projection, and typed run
service reads. The new narrow guards specifically cover terminal handler
failure, default close derivation against a stale failed child, explicit
contradictory close rejection, and failed staging cleanup.
