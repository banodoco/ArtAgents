-- Astrid timeline schema pack creation migration: timeline/0001_initial
--
-- Transcribed byte-for-semantic-content from the normative v10 DDL
-- (unified-data-model-plan-v10-20260813.md, section 2.2) for the timeline
-- pack's single owned table. Kernel tables (projects, event_streams) are
-- created by the core migration; pack foreign keys point inward to the
-- kernel only (plugin law 1).
--
-- Contract notes (SD1):
--   * The timelines table has NO slug, timeline_ulid, is_default, or event
--     hash convenience columns. Immutable slug and lowercase ULID address
--     metadata live in the timeline.created event payload; the project's
--     default timeline id lives in projects.settings_json. Adding any
--     convenience column would require an explicit v10 amendment.
--   * No PRAGMAs are repeated here: connection-level settings are applied
--     and asserted by the migration runner from the core catalog.

CREATE TABLE timelines (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id     TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
  name                TEXT NOT NULL,
  document_json       TEXT NOT NULL CHECK (json_valid(document_json)),
  asset_registry_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(asset_registry_json)),
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
