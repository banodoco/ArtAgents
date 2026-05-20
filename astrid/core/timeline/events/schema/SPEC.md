# Timeline Event Canonicalization

This package is the byte-for-byte source of truth for timeline event envelope
serialization. The TypeScript implementation planned for m6 must conform to
these rules exactly.

- Envelope keys are sorted lexicographically.
- JSON uses compact separators: `","` and `":"`.
- Bytes are UTF-8 encoded with `ensure_ascii=False`.
- `allow_nan=False`; NaN and Infinity are invalid.
- Object fields with `null` values are omitted from canonical form.
- Event hashes are SHA-256 hex digests of the canonical event object with the
  top-level `hash` field removed.
- `event_id` and `txn_id` are ULIDs.
- `timeline_id` is a UUID string.
- `actor` is an object with `type`, `id`, and optional `display` / `via`.

## Current m1 semantics

- Legacy local timelines bootstrap on first append with `timeline.imported`
  before the requested lifecycle event.
- Local read repair is intentionally fail-closed when an eventlog exists but
  the identity sidecar or projection cannot materialize a valid display state.
- Backend selection is per timeline: a known local `timeline_home` resolves to
  `LocalFsBackend`, while explicit `preferred_backend="supabase"` resolves to
  the inert `SupabaseBackend` stub.
- CRUD-side selection keeps using the identity sidecar's `backend` marker when
  present, rather than bypassing the selector with a hard-coded local backend.
- Actor compatibility is intentionally broad in Python m1: `actor.id` is a
  non-empty string and current producers such as `maker`, `codex:test`,
  `migration:m1`, and `claude-code:session-123` remain valid.
