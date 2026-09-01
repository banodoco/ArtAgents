-- Astrid shots schema pack: immutable shot-owned text bindings.
--
-- Text bytes remain kernel media rows.  This projection stores only the
-- stable binding pointer and its aggregate stream identity; history is the
-- existing event stream, not a second revisions table.

CREATE TABLE shot_text_bindings (
  id              TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL
                  REFERENCES projects(id) ON DELETE CASCADE,
  shot_id         TEXT NOT NULL
                  REFERENCES shots(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL CHECK (
                    kind IN ('prompt', 'voiceover_script', 'transcript')
                  ),
  slot            TEXT CHECK (
                    slot IS NULL OR (
                      kind = 'prompt'
                      AND length(slot) BETWEEN 1 AND 64
                    )
                  ),
  media_id        TEXT NOT NULL
                  REFERENCES media(id) ON DELETE RESTRICT,
  event_stream_id TEXT NOT NULL UNIQUE
                  REFERENCES event_streams(id) ON DELETE RESTRICT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX shot_text_binding_singleton
  ON shot_text_bindings(project_id, shot_id, kind)
  WHERE slot IS NULL;

CREATE UNIQUE INDEX shot_text_binding_slot
  ON shot_text_bindings(project_id, shot_id, kind, slot)
  WHERE slot IS NOT NULL;

CREATE INDEX shot_text_binding_lookup
  ON shot_text_bindings(project_id, shot_id, kind, slot);
