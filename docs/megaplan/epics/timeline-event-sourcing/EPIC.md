# Epic — Timeline event sourcing with dual backends

## Headline

This epic makes Astrid timelines event-sourced through a dual-backend design: both first-class, sync deferred. The shared primitive is one canonical event envelope plus an `EventLogBackend` protocol. `LocalFsBackend` writes append-only `assembly.jsonl`; `SupabaseBackend` writes the same shape to `public.timeline_events`.

Local Astrid users must be able to work without Supabase. Reigh-app users must be able to work without local files. Continuous sync remains out of scope, but m9 adds explicit one-shot push/pull verbs so the dual-backend story has an operational bridge.

The current Astrid timeline is mostly a blob (`assembly.json` written wholesale by packs) wrapped in a slug-lifecycle CLI. There is no durable audit trail, shared concurrency contract, or local interactive composition surface. Reigh-app already has useful blob infrastructure: `public.timelines.config jsonb`, `config_version integer`, `update_timeline_versioned(...)` for optimistic writes, `public.timeline_checkpoints`, debounced `saveTimeline` persistence, realtime invalidation, and vendored `@banodoco/timeline-ops`. It has in-memory undo but no durable event log.

After this lands:

- Every mutation emits a typed event with actor attribution.
- The same event shape works against LocalFs and Supabase.
- `assembly.json` / `timelines.config` become derived projections.
- CLI and Python APIs expose timeline edits through the backend protocol.
- Reigh-app saves emit events first, then update derived blob/checkpoint surfaces.
- Existing timelines import through `timeline.imported`.

Identity is locked now: timeline/entity identifiers use UUIDs to match reigh-app, while `event_id` and transaction ids use ULIDs for sortable append identity.

## Why This Matters

1. **Local and web both stay real.** A local Astrid project should not need Supabase. A Supabase project should not need mounted local files.
2. **Audit + collaboration.** Today it is hard to answer "who changed this timeline?" or "what edit just happened?" Events make the edit history inspectable and gradable.
3. **Bypass defense.** Sprint A made canonical bypass structurally difficult at the pack invocation layer. Timeline mutation still has direct blob-write escape hatches; event APIs close that gap incrementally.
4. **Use what reigh-app already has.** CAS saves, checkpoints, realtime invalidation, and shared timeline ops remain useful as derived surfaces.
5. **Dual-backend operations are real.** m9 adds `push --to supabase` and `pull --from supabase`, so LocalFs and Supabase are separate first-class homes with explicit movement paths rather than a vague future promise.
6. **Time travel.** Replay, preview, undo, branch, diff, and audit all fall out of an append-only log plus a deterministic projection.

## Milestone Summary

| # | Milestone | Profile | Robustness | Depth | Why this tier |
|---|---|---|---|---|---|
| 1 | Event envelope + backend protocol foundation | `apex` | `thorough` | `high` | Schema, protocol, identity, actor, canonical JSON, and hash-chain decisions are kernel invariants for every later milestone. |
| 2 | Clip primitives | `partnered` | `full` | `medium` | Mechanical once m1 is locked, but cross-cutting across CLI, Python API, backend protocol, and packs. |
| 3 | Transition / effect / theme / track / audio / pool primitives | `partnered` | `full` | `medium` | Broad mutation surface across many domains, all extending the canonical schema package. |
| 3.5 | Pack and worker migration | `partnered` | `full` | `medium` | Closes direct blob write bypasses in packs and workers before projection becomes authoritative. |
| 4 | Backend-agnostic replay + projection layer | `partnered` | `full` | `high` | Projection is pure and backend-agnostic, with golden fixtures consumed by m6/m8. |
| 5 | Concurrency + locking | `premium` | `thorough` | `high` | CAS semantics become a cross-backend contract at the protocol boundary. Premium > apex per the default-lower rule, and m6 owns the real Supabase RPC implementation. |
| 6 | SupabaseBackend + reigh-app event migration | `apex` | `thorough` | `high` | The only milestone integrating database RPC, server-side hashing/projection, two backends, and the canonical reigh-app write path. |
| 7 | Observability | `directed` | `light` | `low` | Read-only CLI/docs over already-emitted events, transparently selecting a backend. |
| 8 | Migration + comprehensive test coverage | `partnered` | `full` | `medium` | Covers local and Supabase migration paths plus shared golden fixtures, agentic scenarios, and collision tests. |
| 9 | Recovery + cross-backend operations | `partnered` | `full` | `medium` | Adds one-shot push/pull, recover, branch, undo, mass-undo, and GDPR erasure on top of m8's test spine. |

## Open Questions To Resolve During The Epic

- **Snapshot anchor cadence** (m4/m6). Projection anchors are backend-specific storage details: LocalFs may use a sibling checkpoint file or `timeline.snapshot` event, while Supabase should reuse `timeline_checkpoints`.
- **Performance budget** (m4). Pick explicit projection rebuild targets, such as 100ms at 1k events and 500ms at 10k.
- **Asset URL stability** (m1/m6). Decide whether event payloads carry stable asset refs or immutable URLs before hash-chained asset-bearing events become common.
- **Operational failure log schema** (m1/m4). Decide whether the ops log shape belongs in m4 or a separate planner slice.
- **Erasure policy details** (m9). Define which metadata fields can remain under GDPR/right-to-erasure constraints.

## What's Out Of Scope

- Continuous local-to-Supabase sync/reconcile.
- Event-level RBAC.
- Compaction of very long event histories.
- Real-time streaming to local consumers such as Remotion incremental previews.
- Cross-project timeline composition.

## Working-tree Constraint (applies to every milestone)

The user keeps substantial uncommitted state in the source repo. Each milestone runs in its own `.megaplan-worktrees/` worktree with `--carry-dirty` (default). Milestones MUST NOT stash, reset, checkout, or otherwise discard uncommitted state. Each commits its changes to its own milestone branch; merges happen via the chain's PR flow (or manual).

m6 additionally requires the canonical `reigh-app/` checkout to be on `main` before it starts. The canonical clone is `reigh-app/`, not `reigh-app-cloud-chain/`, and m6 must not proceed from the vibecomfy branch.
