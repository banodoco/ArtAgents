# Milestone 8 — Migration + comprehensive test coverage

> **SKETCH** — flesh out before this milestone inits.

## Outcome

Finish the migration/test spine by migrating existing timelines and proving both backends behave the same for the shared event model. LocalFs timelines and Supabase timelines should round-trip equivalent event sequences through projection, audit, and concurrency tests. Migration emits `timeline.imported` events rather than silently blessing old blobs. Shared round-trip tests consume the m4 `tests/golden/` fixtures unchanged.

## Scope (IN)

Migration:

- Sweep local project timelines discovered through `astrid projects ls` / current project APIs.
- For each local timeline missing events, emit `timeline.imported` with `source: "legacy_local"` and a full `assembly.json` snapshot.
- Sweep Supabase timelines that have `public.timelines.config` but no `public.timeline_events`.
- For each Supabase timeline, emit `timeline.imported` with `source: "supabase_config"` through `append_timeline_event(...)`, the RPC backing `append_event(timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None) -> TimelineEvent`.
- Verify projection parity after import for both backends.
- Make migration idempotent and resumable.

Tests:

- Round-trip the same event sequences through `LocalFsBackend` and `SupabaseBackend`, including every m4 golden fixture.
- Agentic scenarios for clip, transition, effect, theme, track, audio, pool, arrangement, preview, history, diff, and audit.
- Multi-agent collision scenarios for stale `expected_version` on both backends.
- Tamper/integrity scenarios for LocalFs JSONL and Supabase event rows where feasible.
- Performance checks for projection, event reads, and CAS contention.

## Anti-scope

- Production rollout scheduling.
- Local/Supabase sync or merge.
- Event compaction beyond snapshots/checkpoints already designed.
- Rewriting unrelated pack workflows.

## Locked Decisions

- Migration uses `timeline.imported`; it does not fabricate historical fine-grained edits.
- Local and Supabase import paths use their native backend append methods.
- Idempotence is mandatory: rerunning migration should not duplicate import events.
- Tests must prove the shared event envelope, not just backend-specific happy paths.

## Open Questions

- Is migration opt-in, project-scoped, or automatic during first read?
- Where should agentic timeline scenarios live: existing `tests/agentic/scenarios/` root or a `timeline/` subdirectory?
- What Supabase test environment is acceptable for CI: local Supabase, mocked RPC, or gated integration job?
- What parity tolerance applies to old blobs with formatting/key-order differences?

## Constraints

- Do not require Supabase credentials for local-only test runs.
- Migration must not delete or mutate source blobs until parity is verified.
- The migration command must be resumable after interruption.
- Generated migration artifacts belong under ignored run/output locations.

## Done Criteria

- Local migration command imports existing local timelines and verifies projected output.
- Supabase migration path imports existing `public.timelines.config` rows and verifies projected output.
- Both backends pass shared round-trip event tests.
- Agentic coverage includes each primitive and the main read-only observability commands.
- Stale-write/collision tests pass for both backends.
- Full test suite for the epic passes, with Supabase integration tests clearly gated when credentials are unavailable.

## Touchpoints

- `astrid/core/timeline/eventlog/local_fs.py`
- `astrid/core/timeline/eventlog/supabase.py`
- `astrid/core/timeline/projection.py`
- Current `astrid projects` discovery APIs.
- Current `astrid timelines` CLI command module.
- Existing test directories selected by the planner, including agentic scenarios if present.
- Supabase objects: `public.timelines`, `public.timeline_events`, `public.timeline_checkpoints`, `append_timeline_event(...)`.
