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
- Display read repair only projects `timeline.imported`, `timeline.created`,
  `timeline.renamed`, `timeline.default_set`, and `timeline.deleted`.
  `timeline.tombstoned` is schema-defined only in m1.
- Backend selection is per timeline: a known local `timeline_home` resolves to
  `LocalFsBackend`, while explicit `preferred_backend="supabase"` resolves to
  the inert `SupabaseBackend` stub.
- CRUD-side selection keeps using the identity sidecar's `backend` marker when
  present, rather than bypassing the selector with a hard-coded local backend.
- Actor compatibility is intentionally broad in Python m1: `actor.id` is a
  non-empty string and current producers such as `maker`, `codex:test`,
  `migration:m1`, and `claude-code:session-123` remain valid.

## Current lifecycle matrix

This spec documents the implementation actually shipped in Python m1.

| kind | schema-defined | projected today | backend-enforced today | emitted by CRUD/CLI today |
| --- | --- | --- | --- | --- |
| `timeline.imported` | yes | yes | yes, via `LocalFsBackend` bootstrap on first append for true legacy timelines | no |
| `timeline.created` | yes | yes | no | no |
| `timeline.renamed` | yes | yes | no special backend rule | yes, `rename_timeline()` only |
| `timeline.default_set` | yes | yes | no | no |
| `timeline.deleted` | yes | yes | yes, `LocalFsBackend` rejects later appends when it is already present as the tail event | no |
| `timeline.tombstoned` | yes | no | no | no |

The deferred lifecycle behaviors are load-bearing for milestone close-out:

- `create_timeline()` writes legacy files plus `assembly.identity.json`, but it
  does not emit `timeline.created`.
- `set_default()` rewrites `display.json` and `project.json`, but it does not
  emit `timeline.default_set`.
- `tombstone_timeline()` is legacy-only and stamps
  `manifest.json.tombstoned_at`; it does not emit `timeline.tombstoned`.
- `purge_timeline()` hard-deletes the timeline directory and does not emit
  `timeline.deleted`.
- `timeline.deleted` only affects projection/enforcement when it is already
  present in an event stream from some other producer or fixture.
