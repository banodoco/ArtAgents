# Milestone 4 — Backend-agnostic replay + projection layer

> **DRAFT** — flesh out before this milestone inits. This is the point where blobs become derived from events.

## Outcome

Make `assembly.json` a derived projection rather than the source of truth. Projection is one backend-agnostic function `project_to_assembly(events: list[TimelineEvent]) -> dict`: if a caller provides the same event sequence from `LocalFsBackend` or `SupabaseBackend`, it produces the identical timeline config. Remotion and current Astrid consumers continue reading the same `assembly.json` shape, but mutation code stops treating that blob as canonical.

This milestone is simpler than the original storage-coupled plan because it does not care where events came from. It consumes `TimelineEvent` objects from `EventLogBackend.read_events(timeline_id, *, after=None, limit=None) -> list[TimelineEvent]` and emits the current config/projection.

## Scope (IN)

- Implement a pure projection function, likely `project_to_assembly(events: Sequence[TimelineEvent]) -> dict`, in `astrid/core/timeline/projection.py`.
- Cover all event kinds defined in m1, m2, and m3: lifecycle, clip, transition, effect, theme, track, audio, pool, and arrangement.
- Add `regenerate_projection(timeline_id, backend, ...)` or equivalent orchestration that reads events, projects, and writes the compatibility `assembly.json`.
- Remove or narrow direct `assembly.json` writes from mutation paths. After m4, mutation code appends events and projection code writes the blob.
- Add snapshot/projection anchors for bounded replay in a backend-agnostic way. Projection must work regardless of where anchors live: LocalFs may use a sibling checkpoint file or a `timeline.snapshot` event if the m4 planner chooses that representation; Supabase mapping to `public.timeline_checkpoints` is owned by m6.
- Support import behavior for timelines with `assembly.json` but no event log by emitting or requiring a `timeline.imported` event before projection becomes authoritative. The exact migration sweep is m8, but m4 needs the on-demand compatibility rule.
- Add deterministic replay tests: full replay and snapshot-based replay produce equivalent projections.
- Ship a shared `tests/golden/` fixture directory of event sequences and expected projected assemblies. These fixtures cover every event kind from m1, m2, and m3, and m6/m8 consume them unchanged for cross-backend parity.
- Add benchmark targets for replay and projection, chosen at plan time and recorded in tests or docs.

## Anti-scope

- Real Supabase implementation and reigh-app write-path migration.
- CAS enforcement and soft locks.
- User-facing history/diff/preview/undo/branch commands.
- Bulk migration of every existing local or Supabase timeline.
- Event compaction beyond snapshot anchors.
- New mutation verbs or mutation payload surfaces; m2/m3 own write APIs, m7 owns read-only observability, and m9 owns recovery/undo/branch.

## Locked Decisions

- Projection is backend-agnostic and accepts event objects, not file paths or Supabase rows.
- `assembly.json` remains the compatibility output for local Astrid/Remotion consumers.
- The event log is canonical after m4. Any compatibility blob must be reproducible from events.
- Snapshot anchors are optimization, not authority. A replay from genesis and a replay from the latest valid snapshot must match.
- `timeline.imported` is the only sanctioned way to seed a legacy blob into the event-sourced model.

## Open Questions

- Snapshot cadence: every N events, every time interval, on finalize, or explicit command?
- What exact LocalFs anchor representation should be used: sibling checkpoint file, `timeline.snapshot` event, or both?
- Eager vs lazy projection: regenerate immediately after append, on first read after dirty head, or both depending on call site?
- What normalization is acceptable when comparing legacy `assembly.json` to projected output: byte-identical, sorted-key JSON equivalent, or schema-normalized equivalent?
- What performance budget is required for expected event counts?
- Should invalid events fail projection hard, or produce a typed diagnostic usable by m7 audit?

## Constraints

- Projection must be deterministic: no current time, random ids, filesystem reads, or network calls inside `project_to_assembly`.
- Projection must project asset URLs exactly as stored in event payloads. URL stability/orphan-asset cleanup is owned by m3.5/m6; m4 must not resolve or rewrite URLs during projection.
- Projection must not mutate the input event list.
- The local compatibility writer must use atomic temp-file + replace semantics.
- Existing Remotion/render paths should not need to know event sourcing exists.
- Snapshot replay must verify hash/head assumptions before trusting a snapshot.

## Done Criteria

- `project_to_assembly(...)` exists and covers every event kind from m1-m3.
- `tests/golden/` contains events-sequence-to-projected-assembly fixtures covering every m1+m2+m3 event kind; m6 and m8 tests consume these fixtures unchanged.
- Mutation paths no longer directly write `assembly.json`; they trigger projection or mark it dirty through one shared helper.
- LocalFs end-to-end tests append event sequences and verify projected `assembly.json` matches expected timeline config.
- Snapshot replay and full replay produce equivalent results.
- Legacy timelines without logs have a documented on-demand import behavior, even if bulk migration waits for m8.
- Existing render and timeline tests pass.

## Touchpoints

**Likely new/modified files:**

- `astrid/core/timeline/projection.py` — pure projection and snapshot replay.
- `astrid/core/timeline/eventlog/types.py` — add `timeline.snapshot` payload type only if m4 chooses event-based LocalFs anchors.
- `astrid/core/timeline/eventlog/local_fs.py` — helper hooks for snapshot/head reads if needed.
- `astrid/core/timeline/crud.py` and edit modules from m2/m3 — replace compatibility writes with projection calls.
- Current timeline path helper module, likely `astrid/core/timeline/paths.py`.
- Projection tests in the existing timeline test location.

**Reference reads:**

- `astrid/timeline.py`
- `examples/hype.timeline.json`
- `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`
