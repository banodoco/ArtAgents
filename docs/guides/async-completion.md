# Async Completion — retired

> **Retired.** This guide documented the Sprint 3 task-mode runtime
> (`astrid plan`, `astrid next`, `astrid ack`, the `local`/`manual`
> adapters, and the `runs/<run-id>/inbox/` completion pipeline). The
> task-mode runtime was removed with the v10 cutover: the filesystem
> task-run store, plan/step adapters, and session-gated verbs are gone.

Async completion is now a property of the single execution ledger, not a
separate inbox pipeline. Every capability invocation is admitted into the
kernel as a run + task and executes through the kernel lifecycle —
admit → claim → start → execute → complete|fail — with events, receipts,
attempts, and leases recording each transition. Callers poll the kernel,
not files: `python3 -m astrid tasks show <task_id> --project <slug> --json`
or `python3 -m astrid runs show <run_id> --project <slug> --json`. The
filesystem `run.json` under the project is a write-once finalize-time
projection of that kernel state, stamped `"authority": "kernel"` — see
[the run ledger contract](../contracts/run-ledger-contract.md). See
[CLI journeys](cli-journeys.md) and
[docs/reference/sdk.md](../reference/sdk.md) for the supported flows.
