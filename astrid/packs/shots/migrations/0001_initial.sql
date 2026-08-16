-- Astrid shots schema pack creation migration: shots/0001_initial
--
-- Transcribed byte-for-semantic-content from the normative v10 DDL
-- (unified-data-model-plan-v10-20260813.md, section 2.2) for the shots
-- pack's two owned tables. Kernel tables (projects, media) are created by
-- the core migration; pack foreign keys point inward to the kernel only
-- (plugin law 1), and the only cross-pack association used here is the
-- kernel currency media_id on shot_items (plugin law 2).
--
-- Contract notes:
--   * shot_items.sort_key is UNIQUE within its shot and media_id references
--     the kernel media table (ON DELETE RESTRICT: a shot item pins the media
--     row it records).
--   * No PRAGMAs are repeated here: connection-level settings are applied
--     and asserted by the migration runner from the core catalog.

CREATE TABLE shots (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  sort_key      TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  UNIQUE (project_id, sort_key)
);

CREATE TABLE shot_items (
  id           TEXT PRIMARY KEY,
  shot_id      TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  media_id     TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  sort_key     TEXT NOT NULL,
  source_frame INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at   TEXT NOT NULL,
  UNIQUE (shot_id, sort_key)
);

CREATE INDEX shot_items_media ON shot_items(media_id, shot_id);
