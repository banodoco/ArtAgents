# Async Completion — retired

> **Retired.** This guide documented the Sprint 3 task-mode runtime
> (`astrid plan`, `astrid next`, `astrid ack`, the `local`/`manual`
> adapters, and the `runs/<run-id>/inbox/` completion pipeline). The
> task-mode runtime was removed with the v10 cutover: the filesystem
> task-run store, plan/step adapters, and session-gated verbs are gone.

The current surface is the eight-family CLI (projects, timelines, media,
tasks, runs, serve, doctor, backup) plus the SDK. Kernel tasks admitted via
`python3 -m astrid tasks create` are executed by pack-owned task-mode
adapters through `astrid.core.task_executor` (fenced attempts, staging
transactions, universal result manifests) — there is no interactive
`next`/`ack` loop. See [CLI journeys](cli-journeys.md) and
[docs/reference/sdk.md](../reference/sdk.md) for the supported flows.
