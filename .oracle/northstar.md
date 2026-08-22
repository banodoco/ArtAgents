# North Star — Reigh on Astrid

## End state
Reigh is a local single-user creative product running entirely on one Astrid SQLite file plus a SHA-256 managed media tree, reached only through the `astrid serve` loopback bridge. One editor; shots are a view mode of the same timeline document. Tasks are kernel rows with fenced attempts; completion is atomic across bytes, media, generations, and placement. Generation and render run on the local machine. There is no cloud dependency anywhere in the supported path.

## Enduring principles
- **One authority.** The SQLite file is the only structured truth; the media tree is the only byte truth. Nothing mirrors, syncs, or reconciles.
- **Correctness by primitives.** Receipts, fences, leases, CAS, atomic transactions — few primitives, strongly enforced, each with a named test.
- **Invisible failure is the default failure state.** Crashes leave orphans or replays, never partial authority or false success.
- **Growth by declaration.** New tasks are declarative definitions over a generic executor seam; no runtime code plugins, no schema churn.
- **Honest latency.** Polling with promised budgets; correctness never depends on transport.

## Anti-patterns (avoid)
- A second placement authority or any mirrored state needing reconciliation.
- Cloud fallbacks or silent executor swaps after claim.
- Event/registry ceremony that serves no current consumer ("plugin-law cosplay").
- Rebuilding multi-user/cloud machinery "just in case."
- Abstractions that cannot name the option they preserve.

## Aligned progress looks like
Each batch lands a small, fully-tested increment where every mutation goes through the writer queue, every effect is idempotent-or-fenced, and the docs of record (constitution + build spec) stay consistent with the code.
