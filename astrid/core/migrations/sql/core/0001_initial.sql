-- Astrid v10 kernel creation migration: core/0001_initial
--
-- Transcribed byte-for-semantic-content from the normative v10 DDL
-- (unified-data-model-plan-v10-20260813.md, section 2.2) for the
-- 14-table agent-agnostic kernel only. The timeline, shots, and
-- references tables belong to their respective schema packs and are
-- created by pack-owned migrations.
--
-- Contract notes:
--   * schema_migrations is pack-aware: PRIMARY KEY (pack, version),
--     with pack DEFAULT 'core' for kernel rows.
--   * event_streams.stream_type is intentionally OPEN (no CHECK); the
--     vocabulary is enforced by the composed registry, never kernel DDL.
--   * media, media_locations, and media_relations are kernel citizenship;
--     they are not a pack.
--   * No plan, step, session, thread, lease, account, billing, sync,
--     legacy-alias, importer, or change-cursor tables are created here
--     (see astrid.core.migrations.catalog.FORBIDDEN_TABLES).
--   * The PRAGMA statements below are connection-level settings; the
--     migration runner applies and asserts them on writable opens.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_migrations (
  pack          TEXT NOT NULL DEFAULT 'core' CHECK (length(trim(pack)) > 0),
  version       INTEGER NOT NULL CHECK (version > 0),
  name          TEXT NOT NULL,
  checksum      TEXT NOT NULL,
  applied_at    TEXT NOT NULL,
  PRIMARY KEY (pack, version),
  UNIQUE (pack, name)
);

CREATE TABLE projects (
  id             TEXT PRIMARY KEY,
  slug           TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  settings_json  TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(settings_json)),
  event_head_seq INTEGER NOT NULL DEFAULT 0 CHECK (event_head_seq >= 0),
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE TABLE event_streams (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  stream_type  TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  head_seq     INTEGER NOT NULL DEFAULT 0 CHECK (head_seq >= 0),
  created_at   TEXT NOT NULL,
  UNIQUE (project_id, stream_type, aggregate_id)
);

CREATE TABLE events (
  event_id        TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  project_seq     INTEGER NOT NULL CHECK (project_seq > 0),
  stream_id       TEXT NOT NULL REFERENCES event_streams(id) ON DELETE RESTRICT,
  seq             INTEGER NOT NULL CHECK (seq > 0),
  subject_type    TEXT NOT NULL,
  subject_id      TEXT NOT NULL,
  changes_json    TEXT NOT NULL CHECK
                  (json_valid(changes_json) AND json_type(changes_json) = 'array'),
  kind            TEXT NOT NULL,
  schema_version  INTEGER NOT NULL CHECK (schema_version > 0),
  idempotency_key TEXT NOT NULL,
  txn_id          TEXT NOT NULL,
  actor_kind      TEXT NOT NULL CHECK (actor_kind IN
                  ('local','system','executor')),
  payload_json    TEXT NOT NULL CHECK (json_valid(payload_json)),
  created_at      TEXT NOT NULL,
  UNIQUE (project_id, project_seq),
  UNIQUE (stream_id, seq),
  UNIQUE (stream_id, idempotency_key)
);

CREATE TABLE command_receipts (
  project_id           TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  idempotency_key      TEXT NOT NULL,
  request_hash         TEXT NOT NULL,
  command_kind         TEXT NOT NULL,
  txn_id               TEXT NOT NULL UNIQUE,
  primary_stream_id    TEXT REFERENCES event_streams(id) ON DELETE RESTRICT,
  resulting_stream_seq INTEGER,
  first_project_seq    INTEGER NOT NULL CHECK (first_project_seq > 0),
  last_project_seq     INTEGER NOT NULL CHECK (last_project_seq >= first_project_seq),
  event_ids_json       TEXT NOT NULL CHECK
                       (json_valid(event_ids_json) AND json_type(event_ids_json) = 'array'),
  result_json          TEXT NOT NULL CHECK (json_valid(result_json)),
  created_at           TEXT NOT NULL,
  PRIMARY KEY (project_id, idempotency_key)
);

CREATE TABLE runs (
  id              TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
  kind            TEXT NOT NULL,
  status          TEXT NOT NULL CHECK
                  (status IN ('running','succeeded','failed','cancelled')),
  title           TEXT,
  input_json      TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(input_json)),
  result_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(result_json)),
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  UNIQUE (id, project_id)
);

CREATE TABLE tasks (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id     TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
  run_id              TEXT,
  run_ordinal         INTEGER CHECK (run_ordinal >= 0),
  capability          TEXT NOT NULL,
  spec_json           TEXT NOT NULL CHECK (json_valid(spec_json)),
  spec_hash           TEXT NOT NULL,
  input_manifest_json TEXT NOT NULL DEFAULT '[]' CHECK
                      (json_valid(input_manifest_json) AND
                       json_type(input_manifest_json) = 'array'),
  status              TEXT NOT NULL CHECK
                      (status IN ('queued','blocked','running','succeeded','failed','cancelled')),
  priority            INTEGER NOT NULL DEFAULT 0,
  available_at        TEXT NOT NULL,
  max_attempts        INTEGER NOT NULL DEFAULT 1 CHECK (max_attempts > 0),
  winning_attempt_id  TEXT,
  cancel_request_id   TEXT,
  cancel_requested_at TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL,
  finished_at         TEXT,
  CHECK ((run_id IS NULL AND run_ordinal IS NULL) OR
         (run_id IS NOT NULL AND run_ordinal IS NOT NULL)),
  FOREIGN KEY (run_id, project_id)
    REFERENCES runs(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE task_dependencies (
  task_id            TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  kind               TEXT NOT NULL DEFAULT 'hard' CHECK (kind IN ('hard','soft')),
  ordinal            INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  PRIMARY KEY (task_id, depends_on_task_id),
  CHECK (task_id <> depends_on_task_id)
);

CREATE TABLE execution_attempts (
  id                TEXT PRIMARY KEY,
  task_id           TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  attempt_no        INTEGER NOT NULL CHECK (attempt_no > 0),
  executor_id       TEXT,
  status            TEXT NOT NULL CHECK
                    (status IN ('claimed','running','succeeded','failed','cancelled','expired')),
  status_version    INTEGER NOT NULL DEFAULT 1 CHECK (status_version > 0),
  lease_id          TEXT,
  lease_expires_at  TEXT,
  heartbeat_counter INTEGER NOT NULL DEFAULT 0 CHECK (heartbeat_counter >= 0),
  last_heartbeat_at TEXT,
  progress_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(progress_json)),
  error_json        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(error_json)),
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  finished_at       TEXT,
  UNIQUE (task_id, attempt_no)
);

CREATE TABLE media (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  media_kind    TEXT NOT NULL CHECK
                (media_kind IN ('image','video','audio','text','document','data','other')),
  mime_type     TEXT NOT NULL,
  byte_size     INTEGER NOT NULL CHECK (byte_size >= 0),
  content_hash  TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  UNIQUE (project_id, content_hash)
);

CREATE TABLE media_locations (
  id          TEXT PRIMARY KEY,
  media_id    TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  realm       TEXT NOT NULL DEFAULT 'managed_local' CHECK
              (realm IN ('managed_local','external_local','remote')),
  locator     TEXT NOT NULL,
  verified_at TEXT,
  created_at  TEXT NOT NULL,
  UNIQUE (media_id, realm, locator)
);

CREATE TABLE media_relations (
  from_media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  to_media_id   TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN
                ('derived_from','variant_of','uses_as_input','mask_for','audio_for')),
  ordinal       INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  PRIMARY KEY (from_media_id, to_media_id, kind, ordinal),
  CHECK (from_media_id <> to_media_id)
);

CREATE TABLE task_outputs (
  task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal     INTEGER NOT NULL CHECK (ordinal >= 0),
  role        TEXT NOT NULL,
  media_id    TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  params_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_json)),
  created_at  TEXT NOT NULL,
  PRIMARY KEY (task_id, ordinal),
  CHECK (role = 'result' OR is_primary = 0)
);

CREATE TABLE evidence_items (
  id        TEXT PRIMARY KEY,
  run_id    TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  task_id   TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  kind      TEXT NOT NULL,
  summary   TEXT NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(data_json)),
  media_id  TEXT REFERENCES media(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX tasks_run_ordinal
  ON tasks(run_id, run_ordinal) WHERE run_id IS NOT NULL;
CREATE UNIQUE INDEX task_one_primary_result
  ON task_outputs(task_id) WHERE role = 'result' AND is_primary = 1;
CREATE INDEX events_project_changes ON events(project_id, project_seq);
CREATE INDEX events_stream_kind_seq ON events(stream_id, kind, seq);
CREATE INDEX events_subject
  ON events(project_id, subject_type, subject_id, project_seq);
CREATE INDEX tasks_claim_order
  ON tasks(status, available_at, priority DESC, id);
CREATE INDEX tasks_project_status
  ON tasks(project_id, status, created_at, id);
CREATE INDEX tasks_run_status
  ON tasks(run_id, status, run_ordinal) WHERE run_id IS NOT NULL;
CREATE INDEX task_dependencies_reverse
  ON task_dependencies(depends_on_task_id, task_id);
CREATE INDEX attempts_lease_expiry
  ON execution_attempts(status, lease_expires_at);
CREATE INDEX task_outputs_media ON task_outputs(media_id, task_id);
CREATE INDEX media_project_page ON media(project_id, created_at, id);
CREATE INDEX media_relations_to
  ON media_relations(to_media_id, kind, from_media_id);
CREATE UNIQUE INDEX media_one_variant_parent
  ON media_relations(from_media_id) WHERE kind = 'variant_of';
CREATE INDEX evidence_run_time ON evidence_items(run_id, created_at, id);
CREATE INDEX evidence_task ON evidence_items(task_id, id) WHERE task_id IS NOT NULL;
