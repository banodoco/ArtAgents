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
- deleted timelines refuse display materialization
- `assembly.json` and `manifest.json` are explicitly out of scope for m1

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
