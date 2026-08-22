# Async Completion — retired

> **Retired.** This guide documented the Sprint 3 task-mode runtime
> (`astrid plan`, `astrid next`, `astrid ack`, the `local`/`manual`
> adapters, and the `runs/<run-id>/inbox/` completion pipeline). The
> task-mode runtime was removed with the v10 cutover: the filesystem
> task-run store, plan/step adapters, and session-gated verbs are gone.

The current surface is the eight-family CLI (projects, timelines, media,
tasks, runs, serve, doctor, backup) plus the SDK. Kernel tasks admitted via
`python3 -m astrid tasks create` are admitted and tracked in the kernel
`runs`/`tasks`/`events` tables only. Executing an admitted task requires a
task-mode adapter driver (`astrid.core.task_executor`); today only the test
suites wire such drivers — there is no shipped command that executes an
admitted task. Direct-mode invocation (`astrid.sdk.invoke`) runs a
capability immediately and records the filesystem `run.json` ledger instead.
See [CLI journeys](cli-journeys.md) and
[docs/reference/sdk.md](../reference/sdk.md) for the supported flows.
