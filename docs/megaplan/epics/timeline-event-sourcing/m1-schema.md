# Milestone 1 — Event envelope + backend protocol foundation

## Outcome

Land the foundation for dual-backend event-sourced timelines. This milestone locks the canonical event envelope, `EventLogBackend` protocol, actor model, identity rules, local storage layout, and hash-chain semantics. It implements `LocalFsBackend` end-to-end and adds a callable `SupabaseBackend` stub that preserves the public interface while returning a clear not-configured/not-implemented result until m6.

As proof of life, migrate exactly one mutation, `rename`, through the new protocol against `LocalFsBackend`. The visible behavior of `astrid timelines rename` stays the same, but the write path now appends a `timeline.renamed` event before updating the current legacy files. All later milestones build on this contract.

## Scope (IN)

1. **Canonical event envelope.** Define one shape shared by both backends:
   - `event_id` — ULID, sortable and unique per event.
   - `timeline_id` — UUID, matching reigh-app's timeline identifier model. Local-only projects must still mint UUIDs for event identity even if their directory naming keeps using existing slugs/ULIDs.
   - `ts` — ISO-8601 UTC.
   - `actor` — JSON object, not a string-only field. Minimum fields: `type` (`agent`, `human`, `system`), `id`, and optional `display`.
   - `prev_hash` — sha256 hash of the previous canonical event, or `null` for the first event.
   - `hash` — sha256 hash of this event's canonical form excluding `hash`.
   - `kind` — namespaced event kind such as `timeline.renamed`.
   - `payload` — kind-specific JSON object.
   - `expected_version` — optional integer used by CAS-aware writers; accepted but not enforced until m5.
   - `schema_version` — integer, starting at `1`.
   - `txn_id` — optional ULID for batched operations.
2. **`EventLogBackend` protocol.** Add a narrow storage abstraction, likely under `astrid/core/timeline/eventlog/protocol.py`, with methods equivalent to:
   - `append_event(timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None) -> TimelineEvent`
   - `read_events(timeline_id, *, after=None, limit=None) -> list[TimelineEvent]`
   - `head(timeline_id) -> EventLogHead`
   - `verify_chain(timeline_id) -> EventLogVerification`
   - `backend_name() -> Literal["local_fs", "supabase"]`
   Type names can follow existing style, but the protocol boundary is non-optional.
3. **`LocalFsBackend`.** Implement the real m1 backend:
   - Writes append-only JSONL at the chosen timeline directory path, expected to be `<project>/timelines/<timeline-dir>/assembly.jsonl`.
   - Maintains a sibling head/cache file, likely `assembly.head.json`, with `last_event_id`, `last_hash`, `event_count`, and `version`.
   - Uses `fcntl.flock` or the repo's existing lock helper to make append safe across local processes.
   - Computes the hash chain client-side under the file lock.
   - Uses atomic temp-file + `os.replace` for head/projection side files.
4. **`SupabaseBackend` stub.** Add `astrid/core/timeline/eventlog/supabase.py` as an interface-only implementation. It can be constructed but performs no real network/database writes in m1. Mutating calls fail predictably.
5. **Backend selection skeleton.** Add the minimal selector needed for `rename` to choose LocalFs in local-only projects and leave the Supabase path explicit but inert. The rule is per-timeline and resolved from the timeline's persistent home, with project config/env fallback only when no timeline is named.
6. **Event kinds defined in m1.**
   - `timeline.created` — payload: `{timeline_id, slug, name}`
   - `timeline.renamed` — payload: `{old_slug, new_slug}`
   - `timeline.default_set` — payload: `{timeline_id}`
   - `timeline.tombstoned` — payload: `{reason}`
   - `timeline.deleted` — final tombstone-like lifecycle event; subsequent appends are rejected, events remain readable for audit, and projection refuses to materialize.
   - `timeline.imported` — payload: `{snapshot, source}` where source is `legacy_local`, `supabase_config`, or another explicit import source
   These names lock the `timeline.<verb>` namespace. Later milestones add `clip.*`, `effect.*`, etc.
7. **Hash-chain semantics by backend.** LocalFs computes hashes client-side under file lock. Supabase computes hashes server-side under row lock in m6. The envelope stays identical.
8. **Proposed Supabase table shape.** m1 does not run migrations, but it sketches the m6 target in the contract doc:
   - `public.timeline_events`
   - `id ulid primary key`
   - `timeline_id uuid not null`
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
9. **Semantic-batched events.** The log records meaningful committed edits, not every UI drag tick or per-gesture transient state. `rename` is one event. Later web integration must batch debounced timeline-ops output the same way.
10. **Canonical event schema package.** Ship `astrid/core/timeline/events/schema/` as the source of truth for event shape:
   - Python dataclasses or Pydantic models for every m1 lifecycle event kind.
   - Canonical JSON serializer using the locked rules below.
   - Schema-version bumper.
   - Spec doc that m6's TypeScript implementation in reigh-app must conform to byte-for-byte.
   m2/m3 extend this package for new event kinds, m3.5 consumes it for pack migration, and m6 imports or generates TypeScript from it.
11. **One mutation migrated as proof.** `rename_timeline` appends `timeline.renamed` via the selected `EventLogBackend` and then performs existing legacy updates. If append fails, the rename fails before mutating legacy files. If legacy update fails after append, the event remains the commit point and legacy files are regenerated idempotently on the next read.
12. **Tests and internal contract doc.** Unit tests cover envelope, hashing, canonical serialization, local append/read/head/verify, process-safe appends, selector behavior, Supabase stub failure, and rename integration. Add a short contract doc near the eventlog module if no better docs location exists.

## Anti-scope

- Do not implement real Supabase migrations, RPCs, realtime, or web-app code. m6 owns that.
- Do not build local/Supabase sync or reconciliation.
- Do not migrate clip, transition, effect, theme, track, audio, pool, or arrangement mutations. m2/m3 own those.
- Do not make `assembly.json` a pure derived projection yet. m4 owns projection.
- Do not enforce CAS semantics yet. `expected_version` is accepted for shape compatibility; m5 turns enforcement on.
- Do not add history/diff/audit/preview/undo/branch CLI verbs. m7 owns read-only observability; m9 owns undo/branch/recovery.
- Do not migrate existing timelines in bulk. m8 owns migration sweeps.
- Do not touch non-timeline subsystems except minimal reads needed for backend selection.

## Locked Decisions

- **Dual backend is the design.** LocalFs and Supabase are both first-class storage targets behind `EventLogBackend`. Neither is a temporary bridge.
- **Sync is deferred.** There is no m1-m8 local/Supabase reconcile verb. m9 adds one-shot push/pull on top of the same event envelope; continuous sync remains out of scope.
- **Identity.** `timeline_id` and timeline entities use UUIDs for compatibility with reigh-app. `event_id` and `txn_id` use ULIDs for sortable append identity. Local timeline directory names may continue using the existing local naming scheme, but the event envelope carries UUIDs.
- **Namespacing.** Event kinds use `timeline.<verb>`, `clip.<verb>`, `effect.<verb>`, etc. No bare `timeline_renamed` or `clip_added`.
- **Local storage.** `LocalFsBackend` uses append-only `assembly.jsonl`, one JSON object per line, in the timeline directory.
- **Hashing.** Hashes are sha256 over deterministic canonical JSON: sorted keys, compact separators, UTF-8 bytes, excluding the `hash` field when computing the current event hash.
- **Hash authority differs by backend.** LocalFs hashes client-side; Supabase hashes server-side under row lock.
- **Semantic events.** The log records committed operations, not high-frequency UI gestures.
- **Protocol before CLI breadth.** m1 proves the write path with rename only.

## Open Questions

1. **Exact LocalFs path.** Existing timeline layout has `assembly.json`, `manifest.json`, and related files. Inspect `astrid/core/timeline/paths.py` and choose the sibling location without breaking current reads.
2. **Module placement.** Prefer `astrid/core/timeline/eventlog/{types.py,protocol.py,local_fs.py,supabase.py}` if it fits the current package structure. Confirm there is no local naming collision.
3. **Reuse task event helpers?** Decide whether to extract a shared helper from `astrid/core/task/events.py` or keep timeline-specific code.
4. **Event type representation.** TypedDict, dataclass, or Pydantic model should match existing Astrid style. Avoid a third serialization idiom.
5. **First event for legacy timelines.** Should first rename emit `timeline.imported` then `timeline.renamed`, or can rename be first until m8?
6. **`expected_version` semantics.** Does version mean event count everywhere, or temporarily map to Supabase `config_version`?
7. **Should Supabase enforce row-level immutability?** Consider a trigger that prevents UPDATE/DELETE on existing `timeline_events` rows in addition to denying direct inserts.
8. **Operational failure log schema.** The state-change log only stores successful appends; decide whether `events_ops.jsonl` / `public.timeline_event_failures` is defined in m4 or its own milestone.
9. **Asset URL stability and orphan-asset semantics under hash-chained events.** `astrid/core/reigh/data_provider.py:177` uses epoch-ms paths that are non-deterministic on retry. Candidate resolutions for the planner:
   - Event payload carries `asset_ref: {registry_id, content_sha256}` and projection resolves the URL from the asset registry; the hash covers the ref, not the URL.
   - Event payload carries the URL directly, but the registry promises URL immutability as a hard contract.

## Constraints

- The event shape must be JSON-serializable end-to-end. No bytes, Decimal, datetime objects, or non-deterministic payload objects.
- Hash-chain verification must be deterministic. Two reads of the same log must produce the same `head`.
- `append_event` on `LocalFsBackend` must be safe across multiple local processes.
- LocalFs opens `assembly.jsonl` with `O_APPEND` so append-only behavior is kernel-enforced at write time.
- LocalFs writers must take `fcntl.LOCK_EX`; this is mandatory for the writer critical section, not an optional advisory convention.
- LocalFs head/projection side files are written with `tmpfile -> fsync -> rename`.
- Supabase m6 must expose `append_timeline_event` as a `SECURITY DEFINER` RPC and deny direct `INSERT INTO public.timeline_events` grants to all roles except `service_role`.
- `SupabaseBackend` must remain a stub in m1 and must not require network access or real credentials for tests.
- Unit tests must run quickly and without network dependencies.
- The rename migration must be backward-compatible with existing timelines that have no event log.
- The public protocol must not expose LocalFs-only concepts such as file paths or fcntl locks.

## Done Criteria

1. `EventLogBackend` exists by name and is used by the migrated rename path.
2. `TimelineEvent`, `TimelineActor`, `EventLogHead`, and verification/result types exist in a concrete module such as `astrid/core/timeline/eventlog/types.py`.
3. `LocalFsBackend` appends, reads, reports head, and verifies hash chains from `assembly.jsonl`.
4. `LocalFsBackend` tests cover healthy chains, tampering detection, empty logs, concurrent appends, and head cache correctness.
5. `SupabaseBackend` stub is importable and callable; mutating calls fail with a clear not-implemented/not-configured error.
6. Backend selection is present enough for local rename and does not accidentally require Supabase for local projects.
7. `rename` emits `timeline.renamed` through `LocalFsBackend` and preserves the existing CLI-visible behavior.
8. Identity rules are implemented or validated: UUID `timeline_id`, ULID `event_id`.
9. Actor JSON is present on every emitted event, including rename.
10. Existing timeline tests still pass, and the rename smoke test still works from the CLI.
11. Internal docs sketch future `public.timeline_events` and `append_timeline_event(...)` without implementing them.
12. `astrid/core/timeline/events/schema/` exists with m1 event models, canonical serializer, schema-version bumper, and a byte-for-byte conformance spec for m6's TypeScript implementation.

## Load-bearing decisions locked here

1. **Append + legacy-update atomicity.** The event append is the commit point. Legacy `assembly.json` / `timelines.config` updates are best-effort compatibility projections that must be idempotently regenerated on next read if they fail. No compensating event is emitted for a legacy projection failure, because the canonical state change already exists in the hash-chained log and subsequent reads can repair the derived surface.
2. **Backend selection scope.** Backend selection is per timeline, resolved from the timeline's persistent home: a LocalFs timeline directory for local timelines, or `public.timelines.id` UUID for Supabase timelines. A single CLI process can operate on both kinds based on the `timeline_id` passed in. Project config and environment variables are fallback defaults only when no timeline is named.
3. **Canonical JSON authoritative form.** Python-side canonicalization is authoritative. Rules: sorted keys, UTF-8 bytes, compact separators `","` and `":"`, no trailing whitespace, no NaN/Inf, numbers preserve their parsed source form (integers as int, floats as float, no `1.0` to `1` coercion), `null` values are omitted from canonical form, and the `hash` field itself is excluded. Postgres-side hashing in m6's RPC must use a stored procedure that produces the byte-identical form, either PL/pgSQL or a small extension. Cross-backend hash parity is enforced by m8 round-trip tests against shared golden fixtures introduced in m4.
4. **Actor identity for non-human writers.** Actor ids are schema-bound by type:
   - `human` -> Supabase `auth.uid()` UUID string, or local `$USER` when offline.
   - `agent` -> `"<short_agent_name>:<run_id>"`, for example `"ai-timeline-agent:abc123"` or `"claude-code:session-uuid"`.
   - `system` -> `"<subsystem>:<task_id_or_invocation_ref>"`, for example `"banodoco_worker:claim:task-789"` or `"migration:m8-import"`.
   For chained provenance such as human -> agent -> worker, the proximate actor wins in `actor`, and the chain is carried in optional `actor.via: [...]`. This schema is codified in the canonical event schema package.
5. **Projection timing.** Supabase projection is synchronous inside `append_timeline_event`, so callers do not observe an event without the derived config update. LocalFs projection is lazy on first read, so the CLI does not pay projection cost on every append. The asymmetry is safe because the event log is authoritative in both cases. `append_event` returns the post-projection head version on Supabase and the pre-projection event on LocalFs; callers that need the projected blob on LocalFs can call `project()` explicitly.
6. **Failure events and operational logs.** The event log audits state changes only: successful appends. Stale-version rejections, projection failures, RLS denials, and rate-limit hits are written to a separate operational log surface: `events_ops.jsonl` for LocalFs and `public.timeline_event_failures` for Supabase. m7 surfaces both with `astrid timelines audit --include-ops`.
7. **Deletion versus erasure.** `timeline.deleted` is a final tombstone-like event that rejects subsequent appends while keeping the event stream readable for audit and refusing projection materialization. GDPR/right-to-erasure is a separate m9 `timeline.erased` operation that deletes or zeros prior event payload content while preserving event metadata needed for chain validity.

## Touchpoints

**New files:**
- `astrid/core/timeline/eventlog/types.py` — event, actor, head, error/result types.
- `astrid/core/timeline/eventlog/protocol.py` — `EventLogBackend` protocol.
- `astrid/core/timeline/eventlog/local_fs.py` — append-only JSONL backend with local locking.
- `astrid/core/timeline/eventlog/supabase.py` — m1 stub backend.
- `astrid/core/timeline/eventlog/__init__.py` — public exports if needed.
- `astrid/core/timeline/eventlog/README.md` — internal contract reference, if no better local docs pattern exists.
- `astrid/core/timeline/events/schema/` — canonical event schema package, serializer, schema-version bumper, and conformance spec.
- `astrid/core/timeline/test_eventlog.py` or equivalent — unit tests.

**Modified files (minimal touch):**
- `astrid/core/timeline/crud.py` — `rename_timeline` calls `EventLogBackend`.
- `astrid/core/timeline/paths.py` — event log/head path helpers if this is where timeline paths live.
- `astrid/core/timeline/__init__.py` — re-export only if existing package style does that.
- CLI file that wires `astrid timelines rename`, only if rename currently bypasses `crud.py`.

**Reference reads only unless the plan justifies a tiny shared helper extraction:**
- `astrid/core/task/events.py` — hash-chain precedent.
- `astrid/core/timeline/model.py`
- `astrid/core/timeline/paths.py`
- `astrid/core/timeline/integrity.py`
- `astrid/timeline.py`

## Working-tree constraint

The source repo has substantial uncommitted state. The chain runs this milestone in its own worktree at `~/Documents/.megaplan-worktrees/<branch>/` with `--carry-dirty`. **Do not stash, reset, checkout, or `git rm` anything**. Commit the m1 changes as a coherent diff at the end. Respect `.gitignore`.
