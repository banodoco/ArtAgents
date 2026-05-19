# Milestone 6 — SupabaseBackend + reigh-app event migration

## Outcome

Implement `SupabaseBackend` for real and migrate the canonical `reigh-app/` write paths to emit timeline events first. The authority model is already locked: LocalFs and Supabase are separate first-class backends behind the same `EventLogBackend` protocol. Local/Supabase sync is not in m6.

This milestone has two explicit phases inside one chain slot. Phase 6a proves the database/RPC/backend/projection parity in isolation. Phase 6b migrates reigh-app write paths and realtime/user-facing history. The canonical app clone is `reigh-app/`, not `reigh-app-cloud-chain/`; the parallel clone is excluded unless it converges before m6 starts. m6 must land on `main`, not the vibecomfy branch.

## Phase 6a — Supabase backend + RPC + projection parity

### Scope (IN)

1. **Database table.** Add `public.timeline_events` with the m1/m5 envelope:
   - `id ulid primary key`
   - `timeline_id uuid not null references public.timelines(id)`
   - `version integer not null`
   - `prev_hash text`
   - `hash text not null`
   - `kind text not null`
   - `payload jsonb not null`
   - `actor jsonb not null`
   - `expected_version integer`
   - `schema_version integer not null default 1`
   - `created_at timestamptz not null default now()`
   - `txn_id ulid null`
   Add `UNIQUE(timeline_id, version)` for CAS/hash-chain integrity, plus indexes for `(timeline_id, created_at)` and event lookup.
2. **Append RPC.** Implement `append_timeline_event(...)` as the only client write entrypoint. It is `SECURITY DEFINER`, runs in one transaction, locks the timeline head/row, validates `expected_version`, rate-limits the actor/timeline, computes `prev_hash`, `version`, and `hash` server-side, inserts the event, synchronously projects derived config/checkpoint surfaces, and returns the inserted event plus the post-projection head version.
3. **Grants and immutability.** Deny direct `INSERT INTO public.timeline_events` for all roles except `service_role`; clients append only through the RPC. Consider UPDATE/DELETE prevention triggers in the m1 open question, but m6 must at least avoid exposing direct insert grants.
4. **Canonical JSON parity.** Server-side hashing must byte-match the Python canonical serializer from m1. Use a stored procedure in PL/pgSQL or a small extension to produce the exact canonical JSON form. Cross-backend round-trip tests consume m4's golden fixtures unchanged.
5. **Projection compatibility.** Keep `public.timelines.config`, `config_version`, `asset_registry`, and `public.timeline_checkpoints` as derived surfaces. Projection is synchronous in the RPC so callers never observe a committed Supabase event without its derived config update.
6. **Idempotency contract.** The RPC accepts client-supplied `event_id` (ULID) as an idempotency key. Re-appending the same `event_id` returns the existing row instead of erroring. Client retry semantics:
   - **committed:** retry returns the existing row/head.
   - **not committed:** retry appends normally if `expected_version` still matches.
   - **unknown timeout:** retry with the same `event_id`; the RPC resolves whether it already committed.
7. **Server-side actor validation.** The RPC enforces `actor.type = "human"` by overriding or rejecting mismatched `actor.id` to `auth.uid()`. `service_role` invocations for agent/system paths may carry the supplied actor, but the service-role override is logged for audit.
8. **Rate limit.** Add per-actor + per-timeline burst caps, defaulting to 50 events/minute/actor and configurable. Return a typed `rate_limited` error so agent runaway cannot silently flood a log.
9. **`SupabaseBackend`.** Replace the m1 stub in Python. Implement append/read/head/verify against the RPC/table while keeping local-only projects free of Supabase requirements.
10. **Targeted import primitive.** Existing Supabase timelines with `config` but no events can emit idempotent `timeline.imported` with `source: "supabase_config"`; m8 owns the bulk sweep.

### Stop Point

Phase 6a stops when the Supabase table, RPC, projection parity, idempotent retry behavior, actor validation, rate limiting, and Python `SupabaseBackend` pass isolated tests. No reigh-app code is touched before this stop point is met.

## Phase 6b — Reigh-app write-path migration

### Scope (IN)

1. **Canonical app checkout.** Edit `reigh-app/` only. Do not migrate `reigh-app-cloud-chain/` unless it has converged into the canonical app before m6 starts.
2. **Write chain migration.** `useTimelineCommands` calls `useTimelineCommit`, which emits semantic events through `append_timeline_event`. `useTimelinePersistence` changes debounce semantics: each debounce window flushes a batch event with a shared `txn_id`, not one event per operation or a raw blob save.
3. **Agent writes.** `ai-timeline-agent/tools/timeline.ts` emits events through `append_timeline_event`, using `agent` actors per the m1 schema.
4. **Legacy blob RPC.** `update_timeline_versioned` is retired for new writes but kept readable/available for legacy compatibility during migration. It must not remain an independent canonical write path.
5. **Realtime.** `useTimelineRealtime` subscribes to `timeline_events` inserts, not only `timelines` row updates. The UI can surface actor attribution badges and toasts in real time.
6. **Web history parity.** Add a UI surface that calls `read_events` and renders the same actor/kind/version info as the CLI `history` view.
7. **Actor attribution UI.** Add affordances to the m6 planner's concrete component list: `useTimelineCommit`, clip-rendering components, and the agent-tool-call view are the minimum investigation points.
8. **Other reigh-app paths.** Migrate or guard additional save/import/poll/realtime paths listed in Touchpoints so none can bypass the event RPC.

## Anti-scope

- Do not build local-to-Supabase sync/reconcile; m9 owns push/pull.
- Do not require local Astrid projects to configure Supabase.
- Do not remove `public.timelines.config` or break existing readers in the same sprint.
- Do not replace reigh-app's entire editor state model. In-memory undo can remain; durable history comes from events.
- Do not implement CRDT merge or offline two-sided reconciliation.
- Do not run bulk migration sweeps of all existing Supabase timelines; m8 owns the sweep.
- Do not migrate `reigh-app-cloud-chain/` as a side quest.

## Locked Decisions

- `SupabaseBackend` writes the same event envelope as `LocalFsBackend`.
- Supabase computes hash-chain fields server-side under lock. Clients do not choose `prev_hash`, `hash`, or `version`.
- `public.timeline_events` is canonical for Supabase-backed timelines after migration.
- `public.timelines.config` and `public.timeline_checkpoints` are derived/projection surfaces.
- Reigh-app's optimistic concurrency vocabulary is preserved through `expected_version`.
- Realtime includes `timeline_events` inserts so actor attribution can be shown in the web UI.
- Semantic-batched events are required. Debounced UI persistence emits committed operations with `txn_id`, not raw gesture frames.

## Open Questions

- Exact database implementation of ULID. Does the Supabase stack already provide a ULID type/function, or should `id`/`txn_id` be text with validation?
- Should `append_timeline_event(...)` accept one event at a time plus `txn_id`, or a true batch payload that commits multiple events atomically?
- Is projection best implemented in SQL, an Edge Function, or TypeScript server code near the existing data provider while still matching m4's fixtures?
- How should existing `config_version` map to event `version` during the migration window?
- Should `timeline_checkpoints` rows be written by explicit `timeline.snapshot` events, automatic cadence, or both?
- Asset URL stability and orphan-asset semantics under hash-chained events. `astrid/core/reigh/data_provider.py:177` uses epoch-ms paths that are non-deterministic on retry. Candidate resolutions:
  - Event payload carries `asset_ref: {registry_id, content_sha256}` and projection resolves URL from the asset registry.
  - Event payload carries the URL directly, but the registry promises URL immutability as a hard contract.
- Confirm all reigh-app touchpoints still exist before editing; if a file moved, update the plan with the discovered path.

## Constraints

- The Supabase RPC must be transactional. A caller must not observe an inserted canonical event without the corresponding derived config update.
- Hashes must be deterministic and compatible with m1 canonicalization rules.
- CAS/stale, rate-limit, RLS, and projection failures must be typed and mappable to web UI handling.
- RLS/security must not let clients forge actor identity or overwrite hash-chain fields.
- Local-only tests must still pass without Supabase credentials.
- The web app must keep using UUID `timeline_id`; do not introduce ULID timeline ids on the Supabase side.
- `service_role` bypasses must be explicitly logged for audit.

## Done Criteria

1. Supabase migration creates `public.timeline_events` with `UNIQUE(timeline_id, version)` and required indexes/constraints.
2. `append_timeline_event(...)` is `SECURITY DEFINER`, direct inserts are denied except to `service_role`, and the RPC appends under lock, enforces `expected_version`, computes server-side hash fields, rate-limits, validates actor identity, updates derived config/checkpoint surfaces, and returns the inserted event/head.
3. Idempotent retry by `event_id` is tested for committed, not-committed, and unknown-timeout client flows.
4. `SupabaseBackend` implements `EventLogBackend` for append/read/head/verify against Supabase.
5. Cross-backend round-trip tests consume m4's golden fixtures unchanged.
6. Reigh-app's `saveTimeline` path no longer treats `update_timeline_versioned(...)` blob writes as canonical. It emits events first through the new RPC/projection flow.
7. `useTimelineRealtime` broadcasts `timeline_events` inserts, so reigh-app UI can surface actor attribution badges and toasts in real time.
8. Web users get parity with CLI for `history`: a UI surface calls `read_events` and renders actor/kind/version info.
9. `ai-timeline-agent/tools/timeline.ts` emits events through `append_timeline_event`.
10. Supabase import primitive emits `timeline.imported` for an existing config and is idempotent.
11. LocalFs backend behavior from m1-m5 is unchanged.

## Touchpoints

**Astrid files:**

- `astrid/core/timeline/eventlog/supabase.py` — replace stub with real backend.
- `astrid/core/timeline/eventlog/protocol.py` — adjust only if m6 exposes a missing method.
- `astrid/core/timeline/eventlog/types.py` — Supabase serialization/error mapping.
- `astrid/core/timeline/events/schema/` — canonical source for generated/conforming TS event schemas.
- `astrid/core/timeline/projection.py` — shared projection contract reference for derived config.
- Existing timeline eventlog tests plus new Supabase integration tests.

**Supabase/database objects:**

- `supabase/migrations/20260325090000_create_video_editor_tables.sql`
- `supabase/migrations/20260326100000_add_timeline_config_version.sql`
- `supabase/migrations/20260413100000_add_atomic_timeline_save.sql`
- `supabase/migrations/20260326100500_create_timeline_checkpoints.sql`
- `public.timeline_events`
- `public.timeline_event_failures`
- `append_timeline_event(...)`
- existing `public.timelines`
- existing `public.timeline_checkpoints`
- existing `update_timeline_versioned(timeline_id, expected_version, config, asset_registry)` compatibility path

**Reigh-app touchpoints in canonical `reigh-app/`:**

- `reigh-app/src/tools/video-editor/hooks/useTimelineCommands.ts`
- `reigh-app/src/tools/video-editor/hooks/useTimelineCommit.ts`
- `reigh-app/src/tools/video-editor/hooks/useTimelinePersistence.ts`
- `reigh-app/src/tools/video-editor/hooks/useTimelineRealtime.ts`
- `reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts`
- `reigh-app/src/tools/video-editor/hooks/usePollSync.ts`
- `reigh-app/src/tools/video-editor/hooks/useTimeline.ts`
- `reigh-app/src/tools/video-editor/hooks/useTimelineSave.ts`
- `reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts`
- `reigh-app/src/shared/realtime/RealtimeConnection.ts`
- `reigh-app/src/shared/realtime/RealtimeEventProcessor.ts`
- `reigh-app/vendor/timeline-ops/typescript/src/ops.ts`
- `reigh-app/supabase/functions/ai-timeline-agent/tools/timeline.ts`
- `reigh-app/supabase/functions/ai-timeline-agent/db.ts`
- `reigh-app/supabase/functions/timeline-import/handler.ts`
- Clip-rendering components and agent-tool-call view identified by the m6 planner for actor attribution UI.

## Working-tree constraint

The source repo has substantial uncommitted state. The chain runs this milestone in its own worktree at `~/Documents/.megaplan-worktrees/<branch>/` with `--carry-dirty`. **Do not stash, reset, checkout, or `git rm` anything**. Commit the m6 changes as a coherent diff at the end. Respect `.gitignore`. Verify `reigh-app/` dirty state before coordinated edits and do not use `reigh-app-cloud-chain/` unless it has already converged.
