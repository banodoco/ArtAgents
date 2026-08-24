# North Star — one authoritative Astrid product

## The desirable end state

Astrid v10 as **ONE store and ONE execution path**: every durable fact lives in the
SQLite kernel (projects, timelines, shots, references, tasks, runs, media, evidence,
receipts, events); every capability invocation — executor or orchestrator — runs as
a kernel run+task (admit → claim → start → execute → complete|fail) with hash-chained
events, receipts, attempts/leases, and managed outputs. `sdk.invoke` is the thin
admission wrapper. The filesystem `run.json` is at most a derived projection of the
kernel run, never an independent authority. Phase B's catalog, bindings, bridge,
orchestrators, setup, and conformance surfaces are implementations of this same
authority rather than a second execution model.

## Enduring qualities and invariants

- **Single authority:** the kernel writer + UnitOfWork + receipts + events is the
  only structured state; media bytes are managed content. No second store, silent
  divergence path, or eventlog-only escape for an existing kernel timeline.
- **Every run is observable:** leases, attempts, retries, expiry, and the full event
  chain make execution auditable, resumable, and replayable.
- **Correctness by primitives:** receipts, fences, CAS, digest checks, atomic
  transactions, and named tests enforce the dangerous boundaries.
- **Growth by declaration:** capabilities and workflow bindings are declarative
  registry data over generic seams; no runtime plugin-loading or unnecessary schema
  churn.
- **Invisible failure by default:** crashes leave orphans or replays, never partial
  authority, false success, silent executor swaps, or cloud fallback.
- **Honest latency and docs:** transport does not determine correctness, and docs,
  probes, and availability messages describe exactly what is runnable.
- **Verified empirically:** every claim is backed by a runnable process, test, or
  probe, not narrative alone. GPU-only limits are named as blocked.

## Anti-patterns to avoid

- A second ledger or placement authority kept consistent by convention.
- Kernel/eventlog divergence, orphaned receipts, or silent downgrades.
- Ghost verbs or docs that claim behavior that does not exist.
- Per-executor adapters where one generic path suffices.
- Plugin-law ceremony, cloud fallbacks, and speculative multi-user/GPU
  supervision machinery.

## Aligned progress

Each batch leaves the kernel as the single execution authority: more invocation
paths admitted as kernel tasks, more capabilities declared and truthfully advertised,
fewer places that write `run.json`, and every suite/process/oracle gate passing before
the next batch or integration seam.
