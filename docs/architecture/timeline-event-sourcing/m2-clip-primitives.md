# Milestone 2 — Clip primitives

> **DRAFT** — flesh out fully before this milestone inits. m1's choices around `EventLogBackend`, event typing, actor shape, and backend selection lock the implementation details.

## Outcome

Land the full clip-level mutation surface as backend-agnostic CLI verbs and Python APIs. Every clip edit calls the `EventLogBackend` protocol from m1; no verb should know whether the target log is LocalFs or Supabase. In this milestone the real test backend is still `LocalFsBackend`; `SupabaseBackend` remains a callable stub that raises a clear not-implemented/not-configured error until m6.

The milestone also starts moving packs away from direct `assembly.json` writes by converting clip-level writes to semantic `clip.*` events. `assembly.json` may still be maintained by compatibility code until m4 makes projection authoritative.

## Scope (IN)

CLI verbs under `astrid timelines clip`:

- `add --kind {visual,audio,text} [--at <index>|--after <id>|--before <id>] --asset <id|path>`
- `remove --clip-id <id>`
- `move --clip-id <id> --to {<index>|after:<id>|before:<id>}`
- `retime --clip-id <id> --start <t> --duration <t>`
- `swap --a <id> --b <id>`
- `replace --clip-id <id> --with <asset-id>`
- `set-text --clip-id <id> --text "..."`
- `annotate --clip-id <id> --note "..."`

Python API in a module such as `astrid/core/timeline/edits.py` or `astrid/core/timeline/clip_edits.py`:

- One function per CLI verb.
- Each function accepts a backend or resolves one through the m1 selector.
- Each function returns the emitted `TimelineEvent`.
- Each function calls the canonical protocol method exactly as shaped in m1: `append_event(timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None) -> TimelineEvent`.
- Each function passes actor and optional `expected_version` through unchanged, but enforcement remains a m5 concern.
- Each new `clip.*` event kind extends the canonical event schema package from m1 at `astrid/core/timeline/events/schema/`; this is the only source of truth for payload validation and canonical serialization.

Event kinds added:

- `clip.added`
- `clip.removed`
- `clip.moved`
- `clip.retimed`
- `clip.swapped`
- `clip.replaced`
- `clip.text_set`
- `clip.annotated`

Pack migration:

- Audit `astrid/packs/` for direct clip writes to `assembly.json`, `TimelineConfig`, or clip arrays.
- Convert the high-value clip-producing paths first, especially builtin cut/hype-style flows that assemble visual/audio clips.
- Keep output shape unchanged for current consumers. If compatibility code still writes `assembly.json`, it must do so after event emission and through a narrow helper so m4 can remove it cleanly.
- Full pack/worker bypass closure is intentionally deferred to m3.5; m2 only migrates paths needed to prove clip primitives and avoid obvious duplicate write APIs.

## Anti-scope

- Transition, effect, theme, track, audio, pool, and arrangement primitives; m3 owns those.
- Exhaustive pack and worker write-path migration; m3.5 owns that sweep.
- Projection purity and snapshot replay; m4 owns those.
- CAS enforcement, soft locks, and transactions; m5 owns those.
- Real Supabase implementation or reigh-app changes; m6 owns those.
- Durable local/Supabase sync; deferred beyond this epic.

## Locked Decisions

- Clip APIs are backend-agnostic and call `EventLogBackend`; they do not import `LocalFsBackend` directly except in tests/fixtures.
- Clip event payloads use UUID entity ids where the timeline model permits identity. If legacy clip ids are not UUIDs, the plan must either preserve them as external ids or add stable UUIDs without breaking schema consumers.
- Events are semantic. A drag that moves a clip through 30 positions emits one `clip.moved` when committed.
- CLI verbs and Python APIs share implementation. The CLI should be a thin parser/actor/backend wrapper over the Python functions.
- Supabase stub behavior remains unchanged: selected Supabase paths fail cleanly until m6 rather than silently falling back to LocalFs.

## Open Questions

- What is the canonical clip identity field today, and does it already align with UUIDs?
- Should `--at <index>` or `--after/--before <id>` be the canonical internal payload? Support both in CLI only if the conversion is unambiguous.
- Which packs must migrate in m2 versus stay behind compatibility writes until m4?
- How much validation happens before append? For example, should `clip.retimed` reject negative duration before emitting, or should projection reject bad events?
- Do text clips use the same `clip.added` payload with a text subtype, or a specialized text payload plus `clip.text_set`?

## Constraints

- No clip mutation code may write backend-specific event files directly.
- Tests should run with `LocalFsBackend` temp directories and must not require Supabase.
- Existing render and timeline consumers must continue to see valid `assembly.json`.
- Event payloads must remain JSON-serializable and stable enough for m4 replay.
- Do not change chain identity decisions from m1: UUID timeline/entity ids, ULID event ids.

## Done Criteria

- All eight CLI verbs exist and call the shared Python API.
- The Python API emits the expected `clip.*` events through `EventLogBackend`.
- LocalFs tests cover each primitive and verify appended event shape, actor, timeline id, and payload.
- Supabase-selected tests prove the stub error is explicit and not swallowed.
- Migrated pack paths produce the same externally visible timeline output as before.
- No regressions in existing timeline and pack tests.

## Touchpoints

**Likely new/modified files:**

- `astrid/core/timeline/edits.py` or `astrid/core/timeline/clip_edits.py` — clip mutation API.
- `astrid/core/timeline/eventlog/types.py` — add `clip.*` payload types if m1 uses typed event payloads.
- `astrid/core/timeline/cli.py` or the current `astrid timelines` command module — CLI verbs.
- `astrid/packs/builtin/cut/run.py` — if this is the direct clip assembly writer.
- `astrid/packs/builtin/hype/` — only files that directly create clip assembly data.
- `tests/` locations matching existing timeline CLI/API test conventions.

**Reference reads:**

- `astrid/timeline.py` — clip schema.
- `astrid/core/timeline/eventlog/protocol.py`
- `astrid/core/timeline/eventlog/local_fs.py`
