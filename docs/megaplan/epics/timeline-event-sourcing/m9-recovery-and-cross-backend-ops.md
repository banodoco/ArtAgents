# Milestone 9 — Recovery + cross-backend operations

## Outcome

Add the operational verbs that make the event-sourced system recoverable and movable after m8 proves both backends and shared tests. This milestone closes the dual-backend-without-sync gap through one-shot push/pull, adds recovery from tamper or bad edits, moves undo/branch out of m7, and defines GDPR erasure semantics without replacing the append-only audit model.

Profile: `partnered/full/medium`. Estimated effort: 2-3 human-weeks.

## Scope (IN)

1. **One-shot cross-backend transfer.**
   - `astrid timelines push <slug-or-id> --to supabase`
   - `astrid timelines pull <slug-or-id> --from supabase`
   These replay LocalFs events into Supabase or Supabase events into LocalFs using backend append APIs and m6 idempotency. They are not continuous sync or conflict merge.
2. **Recovery to anchor.**
   - `astrid timelines recover <slug-or-id> --to-event <id>`
   - `astrid timelines recover <slug-or-id> --to-snapshot <id>`
   Recovery emits `timeline.recovered` with the target anchor, reason, and actor. It resets the projected head to the chosen event/snapshot without deleting historical events.
3. **Branching.**
   - `astrid timelines branch <slug> --from <event-id> --as <new-slug>`
   - `astrid timelines branches <slug>`
   Branch creates a new timeline from the projected state at the chosen event. It emits a `timeline.branched_from` event on the source timeline so branches are enumerable through a reverse index.
4. **Undo.**
   - `astrid timelines undo <slug>`
   Undo emits inverse semantic events where defined. For non-reversible kinds it emits `timeline.reverted` with `{target_event_id, projected_before, projected_after, reason}` or a narrower payload chosen by the planner.
5. **Mass undo.**
   - `astrid timelines mass-undo <slug> --since <time> --actor <pattern>`
   Bulk-revert recent activity by actor/time window. This is the agent-runaway recovery path and must preview the event set before writing unless `--yes` is supplied.
6. **GDPR/right-to-erasure.**
   - Add `timeline.erased`.
   - Erasure bulk-zeros payload fields for events matching a query while retaining metadata required for chain validity: `event_id`, version, hash-chain continuity metadata, kind, actor, and timestamps as permitted by policy. Erased payloads become `{"erased": true, "reason": "<...>"}`.

## Inverse Semantics

Define inverse behavior for every m2/m3 event kind before implementation:

- `clip.added` -> `clip.removed`
- `clip.removed` -> `clip.added` when prior payload/projection contains enough clip data; otherwise `timeline.reverted`
- `clip.moved` -> `clip.moved` back to previous position
- `clip.retimed` -> `clip.retimed` to previous timing
- `clip.swapped` -> `clip.swapped` with the same pair
- `clip.replaced` -> `clip.replaced` with previous asset
- `clip.text_set` -> `clip.text_set` with previous text
- `clip.annotated` -> remove or restore prior annotation according to payload history
- `transition.set` -> previous `transition.set` or `transition.removed`
- `transition.removed` -> `transition.set` when prior transition is known
- `effect.added` -> `effect.removed`
- `effect.removed` -> `effect.added` when prior payload is known
- `effect.tuned` -> `effect.tuned` with previous params
- `theme.set` -> `theme.set` with previous theme
- `theme.overridden` -> previous override value or override removal event if m3 defines one
- `track.added` -> `track.removed`
- `track.removed` -> `track.added` when prior track data is known
- `audio.bound` -> previous `audio.bound` or `audio.unbound`
- `audio.unbound` -> `audio.bound` when prior binding is known
- `pool.asset_added` -> `pool.asset_removed`
- `pool.asset_removed` -> `pool.asset_added` when prior asset metadata is known
- `pool.asset_scored` -> `pool.asset_scored` with previous score
- `arrangement.replaced` -> `timeline.reverted` unless prior semantic diff is available

Lifecycle events require explicit rules:

- `timeline.created`, `timeline.imported`, `timeline.deleted`, `timeline.tombstoned`, `timeline.erased`, `timeline.recovered`, and `timeline.branched_from` are not blindly invertible; use `timeline.reverted` or a dedicated recovery/branch command.

## Anti-scope

- Continuous bidirectional sync, CRDT merge, or background reconcile loops.
- Reigh-app UI for branch/recovery unless the planner finds a narrow reuse of m7/m6 history surfaces.
- Event compaction beyond erasure payload zeroing.
- Changing the canonical event schema rules from m1.

## Locked Decisions

- Recovery/undo/branch are append-only operations unless `timeline.erased` explicitly zeroes payload fields for policy reasons.
- Push/pull uses backend append APIs and the m6 idempotency key; it does not copy compatibility blobs as authority.
- `timeline.branched_from` is emitted on the source timeline so reverse branch lookup does not require scanning all timeline histories.
- Mass undo is preview-first and actor-filtered to protect against accidental broad rewrites.
- Erasure preserves enough metadata to keep audit/version sequencing meaningful, while removing sensitive payload content.

## Open Questions

- Should push/pull preserve original `event_id` values or create new ids with `source_event_id` metadata when crossing backends?
- What query language is acceptable for `timeline.erased` selection without making accidental broad erasure easy?
- Which lifecycle event fields are personal data under the project's policy and may need additional redaction?
- Should `recover --to-snapshot` trust backend snapshots directly or re-verify against full replay before appending `timeline.recovered`?

## Constraints

- Commands must work for LocalFs without Supabase credentials unless the command explicitly names Supabase.
- Push/pull must be idempotent and resumable after interruption.
- Recovery and undo must run `verify_chain` before writing unless an explicit repair mode is added by the planner.
- Mass undo must rate-limit or chunk writes so it cannot create its own runaway event burst.
- Erasure must be tested against hash-chain verification and projection refusal/materialization behavior.

## Done Criteria

- `push --to supabase` and `pull --from supabase` replay event streams through backend append APIs and pass idempotent retry tests.
- `recover --to-event` and `recover --to-snapshot` emit `timeline.recovered` and produce the expected projected head.
- `branch` creates a new timeline at an event anchor and emits `timeline.branched_from` on the source; `branches` lists it through the reverse index.
- `undo` covers every reversible m2/m3 event kind and falls back to `timeline.reverted` for non-reversible kinds.
- `mass-undo` previews and then bulk-reverts a filtered actor/time window.
- `timeline.erased` zeros matching payloads while preserving metadata and keeping audit behavior documented and tested.
- LocalFs and Supabase tests reuse m8 infrastructure and cover failure/retry cases.

## Touchpoints

- Current `astrid timelines` CLI command module.
- `astrid/core/timeline/eventlog/local_fs.py`
- `astrid/core/timeline/eventlog/supabase.py`
- `astrid/core/timeline/projection.py`
- `astrid/core/timeline/events/schema/` — add `timeline.recovered`, `timeline.reverted`, `timeline.branched_from`, and `timeline.erased`.
- m8 shared fixtures and agentic scenarios.
- Supabase objects: `public.timeline_events`, `public.timeline_checkpoints`, `append_timeline_event(...)`, and any reverse-index object selected by the planner.
