# Timeline Eventlog Contract

Milestone 1 locks the storage contract for timeline lifecycle events without
shipping the full projection or Supabase implementation.

## Canonical envelope

Each event uses the shared schema in `astrid/core/timeline/events/schema/`:

- `event_id`: ULID
- `timeline_id`: UUID
- `ts`: ISO-8601 UTC
- `actor`: JSON object with `type`, `id`, optional `display` / `via`
- `prev_hash`: previous event hash or `null`
- `hash`: SHA-256 over canonical JSON excluding top-level `hash`
- `kind`: namespaced kind such as `timeline.renamed`
- `payload`: kind-specific JSON object
- `expected_version`: accepted for shape compatibility, not enforced in m1
- `schema_version`: integer, currently `1`
- `txn_id`: optional ULID

Canonical JSON rules are byte-for-byte authoritative on the Python side:
sorted keys, compact separators, UTF-8, no NaN/Inf, omit `null` object fields,
and exclude the top-level `hash` field from the hashed form.

## LocalFs layout

`LocalFsBackend` is timeline-bound and writes inside the timeline directory:

- `assembly.jsonl`: append-only canonical JSONL event stream
- `assembly.head.json`: cached head with `last_event_id`, `last_hash`,
  `event_count`, and `version`
- `assembly.identity.json`: durable identity/provenance sidecar containing the
  UUID `timeline_id`, ULID `timeline_ulid`, backend marker, provenance marker,
  and creation/import metadata

Writer contract:

- open `assembly.jsonl` with `O_APPEND`
- hold `fcntl.LOCK_EX` across tail read, hash computation, append, and head update
- write newline-terminated canonical JSONL
- update side files with atomic temp-file -> fsync -> rename

Bootstrap contract:

- post-m1 created timelines are distinguished by `assembly.identity.json`
- true legacy timelines emit `timeline.imported` on first append
- `timeline.deleted` is terminal for future appends

## Backend selection in m1

Timeline callers select a backend in two steps:

- `select_timeline_stream(...)` resolves the per-timeline storage target from
  explicit backend preference or persistent local home metadata
- `select_timeline_backend(...)` turns that stream reference into the concrete
  `EventLogBackend` implementation used by callers such as
  `rename_timeline()`

The supported m1 cases are intentionally narrow:

- local timelines with a known `timeline_home` construct `LocalFsBackend`
- CRUD callers pass through the durable `assembly.identity.json["backend"]`
  marker when it exists, so the per-timeline sidecar remains the source of
  truth for local backend selection
- explicit `preferred_backend="supabase"` constructs `SupabaseBackend`
  without network access and remains inert until m6
- if a caller asks for local_fs without a local home, construction fails
  rather than inventing fallback path semantics

This preserves the current fail-closed behavior and keeps backend selection
limited to repository-representable cases.

## Projection scope in m1

The event stream is authoritative, but m1 only repairs the compatibility
projection for `display.json`.

- reads use the on-disk `display.json` when no eventlog exists
- reads repair missing/corrupt/stale `display.json` from lifecycle events when
  an eventlog exists
- reads stay fail-closed when an eventlog exists but identity/projection
  materialization is unusable
- `timeline.deleted` refuses display materialization when that event is already
  present in the stream
- `assembly.json` and `manifest.json` are explicitly out of scope for m1

Current read-side lifecycle handling is intentionally narrower than the schema
surface. `project_display(...)` only branches on:

- `timeline.imported`
- `timeline.created`
- `timeline.renamed`
- `timeline.default_set`
- `timeline.deleted`

There is no `timeline.tombstoned` projector branch in m1.

## Current lifecycle matrix

This is the repository contract today across `crud.py`, `projector.py`,
`paths.py`, and `cli.py`.

| kind | schema-defined | projected by `project_display()` | backend-enforced today | emitted by CRUD/CLI today |
| --- | --- | --- | --- | --- |
| `timeline.imported` | yes | yes | yes, `LocalFsBackend` bootstraps it on first append for true legacy timelines | no |
| `timeline.created` | yes | yes | no | no |
| `timeline.renamed` | yes | yes | no special backend rule | yes, `rename_timeline()` only |
| `timeline.default_set` | yes | yes | no | no |
| `timeline.deleted` | yes | yes | yes, later appends are rejected when it is already the tail event | no |
| `timeline.tombstoned` | yes | no | no | no |

The CLI mirrors that same boundary in code:

- `cmd_rename()` -> `rename_timeline()` is the only timeline CLI path that
  routes through the eventlog write path
- `cmd_create()` still delegates to legacy `create_timeline()` with no event
  emission
- `cmd_set_default()` still delegates to legacy `set_default()` with no event
  emission
- `cmd_tombstone()` still delegates to legacy `tombstone_timeline()` and only
  stamps `manifest.json.tombstoned_at`
- `cmd_purge()` still delegates to legacy `purge_timeline()` and hard-deletes
  the directory tree without emitting `timeline.deleted`

## Actor compatibility in m1

Actor ids remain compatibility-first in the Python implementation.

- `actor.type` is constrained to `agent`, `human`, or `system`
- `actor.id` must be a non-empty string
- existing producers continue to emit ids such as `maker`, `codex:test`,
  `claude-code:session-123`, `timeline-crud:rename`, and `migration:m1`
- m1 does not tighten actor ids to backend-specific formats; docs describe the
  intended patterns while tests preserve current accepted producers

## Future Supabase target

Milestone 1 does not run migrations or RPCs, but the target shape is fixed:

- table: `public.timeline_events`
- columns:
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

Future RPC contract:

- function: `append_timeline_event(...)`
- execution model: `SECURITY DEFINER`
- hashing authority: server-side under row lock
- direct `INSERT` into `public.timeline_events` stays unavailable to non-service roles
