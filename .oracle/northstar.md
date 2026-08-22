# North Star — Astrid unified execution

## The desirable end state

Astrid v10 as **ONE store and ONE execution path**: every durable fact lives in the
SQLite kernel (projects, timelines, shots, references, tasks, runs, media, evidence,
receipts, events); every capability invocation — executor or orchestrator — runs as a
kernel run+task (admit → claim → start → execute → complete|fail) with hash-chained
events, receipts, attempts/leases, and managed outputs. `sdk.invoke` is the thin
admission wrapper. The filesystem `run.json` is at most a derived projection of the
kernel run — never an independent authority. Docs describe exactly what ships; the
suite and empirical process runs prove it.

## Enduring qualities and invariants to preserve

- **Single authority**: the kernel writer + UnitOfWork + receipts + events is the only
  state. No second store, no silent divergence path, no eventlog-only escape for an
  existing kernel timeline.
- **Every run is observable**: leases, attempts, retries, expiry, and the full event
  chain make any execution auditable, resumable, and replayable.
- **Honest docs**: no overclaims (e.g. "admitted tasks run" only when a driver ships);
  documented limitations are real limitations.
- **Elegance**: KISS / YAGNI. One generic adapter beats 50 bespoke ones; relax the
  completion contract minimally; cut scope that isn't pulling its weight.
- **Verified empirically**: every claim backed by a runnable process, test, or probe —
  not narrative.

## Anti-patterns to avoid

- A second ledger that must be kept "consistent by convention."
- Kernel/eventlog divergence (orphaned receipts, silent downgrades).
- Ghost verbs or docs that claim behavior that does not exist.
- Per-executor adapters where one generic path would do.
- Scope creep disguised as architecture (serve/GPU supervision beyond what execution needs).

## What aligned progress looks like

Each batch leaves the kernel as the single execution authority: more invocation paths
admitted as kernel tasks, fewer places that write run.json, docs and tests converging
on one ledger, and every gate (suite, process runs, oracle review) passing before the
next batch starts.
