# Milestone 7 — Observability + docs

> **SKETCH** — flesh out before this milestone inits.

## Outcome

Add the read-only user-facing commands that make event-sourced timelines inspectable, debuggable, and useful to both humans and agents. The verbs work through backend selection, so the same command can inspect a LocalFs timeline or a Supabase timeline without changing the user's mental model.

## Scope (IN)

CLI verbs:

- `astrid timelines history <slug-or-id> [--since <event-id|N events|time>]` — read events through `read_events(timeline_id, *, after=None, limit=None) -> list[TimelineEvent]` and pretty-print actor attribution plus `backend_name() -> Literal["local_fs", "supabase"]`.
- `astrid timelines diff <slug-or-id> --from <event-id> --to <event-id>` — semantic diff, not raw JSON.
- `astrid timelines audit <slug-or-id>` — call `verify_chain(timeline_id) -> EventLogVerification`, compare `head(timeline_id) -> EventLogHead`, and check projection parity where a derived blob exists.
- `astrid timelines audit <slug-or-id> --include-ops` — include operational failure logs from `events_ops.jsonl` or `public.timeline_event_failures` alongside state-change audit results.
- `astrid timelines preview <slug-or-id> --at <event-id>` — project a past state to stdout or a temp file.
- `astrid timelines who-edited <slug-or-id>` — actor rollup.

Docs:

- Concepts doc for the dual-backend event model.
- Cookbook recipes for audit before publish, preview a past cut, inspect who edited what, and inspect a stale-write failure.
- Pack-author migration guide for any remaining direct-write path.

## Anti-scope

- New m2/m3 mutation primitives.
- `undo`, `branch`, and any state-changing verbs. m7 is read-only: `history`, `diff`, `audit`, `preview`, `who-edited`.
- Local/Supabase sync.
- Reigh-app UI history panels unless they fall out cheaply from existing APIs.
- Event compaction.

## Locked Decisions

- Observability reads through `EventLogBackend`; commands do not parse `assembly.jsonl` directly.
- Output should clearly identify backend, timeline id, event version, event id, actor, and kind.
- `audit` checks both hash-chain integrity and projection consistency where a derived blob exists.
- Operational failure logs are read-only audit inputs; m7 does not mutate or repair them.

## Open Questions

- What semantic diff representation is most useful: operation-level summaries, projected config diffs, or both?
- Should Supabase history read from direct table access or through an RPC for RLS/performance?
- How much of the operational failure log should be shown by default versus only under `--include-ops`?

## Constraints

- Commands must not require Supabase for LocalFs timelines.
- Commands must avoid printing secrets from actor/session metadata.
- Preview output must not overwrite canonical projection unless explicitly requested.
- Large event histories need paging or limits.
- Commands must not append events, repair projections, create branches, or perform undo. Any recovery workflow belongs to m9.

## Done Criteria

- All listed verbs work against LocalFs.
- Supabase-backed history/audit/preview work through `SupabaseBackend` where credentials/config are available.
- Docs accurately explain dual-backend, sync-deferred semantics.
- Tests cover history formatting, audit failure on tampering, operational-log inclusion, preview at event id, and backend selection.

## Touchpoints

- Current `astrid timelines` CLI command module.
- `astrid/core/timeline/eventlog/protocol.py`
- `astrid/core/timeline/eventlog/local_fs.py`
- `astrid/core/timeline/eventlog/supabase.py`
- `astrid/core/timeline/projection.py`
- `docs/TIMELINE.md` or the existing timeline docs location selected by the planner.
- Existing CLI/unit test locations.
