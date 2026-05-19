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
