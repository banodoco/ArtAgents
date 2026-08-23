-- Astrid timeline schema pack migration: timeline/turso/0001 (remote replica)
--
-- Pack: timeline   Version: turso-1   Purpose: Turso replica schema for
-- hybrid sync — two tables (documents + events) in the REMOTE replica only.
-- This file is the S-owned DDL for the replica (R1); the Astrid runner may
-- apply it to Turso via the schema-pack runner, but it is NEVER applied to
-- the local SQLite authority (local authority stays on sql/0002,0003).
--
-- Additive-only: creates two new tables and nothing else. No connection
-- settings are repeated here.
--
-- R2 allowlist: documents carries ONLY timeline identity columns + document_json
-- + integer version; asset_registry_json is EXCLUDED. Events carries ONLY
-- scoped timeline event rows: stream/timeline identity + seq + event_id ULID +
-- kind + payload_json + actor fields + created_at + txn/idempotency.
-- Negative tests prove no data-URI/base64/blob payloads ever replicate.
--
-- Provenance v1 decision: events.source_* columns are NOT replicated to
-- Turso (the allowlist is the explicit column list below; negative tests
-- match this choice). If replicated later, a new turso migration will add
-- them additively.

CREATE TABLE documents (
  timeline_id     TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL,
  event_stream_id TEXT NOT NULL,
  name            TEXT NOT NULL,
  document_json   TEXT NOT NULL CHECK (json_valid(document_json)),
  version         INTEGER NOT NULL CHECK (version >= 0),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE events (
  event_id        TEXT PRIMARY KEY,
  timeline_id     TEXT NOT NULL REFERENCES documents(timeline_id) ON DELETE CASCADE,
  project_id      TEXT NOT NULL,
  stream_id       TEXT NOT NULL,
  seq             INTEGER NOT NULL CHECK (seq > 0),
  kind            TEXT NOT NULL,
  payload_json    TEXT NOT NULL CHECK (json_valid(payload_json)),
  actor_kind      TEXT NOT NULL CHECK (actor_kind IN ('local','system','executor')),
  actor_id        TEXT NOT NULL,
  txn_id          TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  created_at      TEXT NOT NULL,
  UNIQUE (timeline_id, seq),
  UNIQUE (timeline_id, idempotency_key)
);

CREATE INDEX events_timeline_seq ON events(timeline_id, seq);
CREATE INDEX events_stream_seq ON events(stream_id, seq);
