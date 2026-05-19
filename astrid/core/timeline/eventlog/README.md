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

## Projection scope in m1

The event stream is authoritative, but m1 only repairs the compatibility
projection for `display.json`.

- reads use the on-disk `display.json` when no eventlog exists
- reads repair missing/corrupt/stale `display.json` from lifecycle events when
  an eventlog exists
- deleted timelines refuse display materialization
- `assembly.json` and `manifest.json` are explicitly out of scope for m1

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
