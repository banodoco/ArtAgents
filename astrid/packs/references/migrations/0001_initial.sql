-- Astrid references schema pack creation migration: references/0001_initial
--
-- Transcribed byte-for-semantic-content from the normative v10 DDL
-- (unified-data-model-plan-v10-20260813.md, section 2.2) for the references
-- pack's three owned tables and eight named indexes. Kernel tables (media,
-- tasks) are created by the core migration; pack foreign keys point inward
-- to the kernel only (plugin law 1), and cross-pack associations use only
-- kernel currencies (media_id, context_task_id) per plugin law 2.
--
-- Contract notes:
--   * Every locked reference vocabulary is recorded verbatim (decision
--     artifact section 7): project_references.kind, media_references.role,
--     and reference_links.kind. Changing any value requires a v10 amendment.
--   * All normative CHECK constraints are preserved, including the
--     canonical/primary, used_as_input/context_task_id, and
--     context_task_id/role interactions on media_references.
--   * No PRAGMAs are repeated here: connection-level settings are applied
--     and asserted by the migration runner from the core catalog.

CREATE TABLE project_references (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN
                ('character','place','object','clothing','other')),
  name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
  description   TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  archived_at   TEXT
);

CREATE TABLE media_references (
  id              TEXT PRIMARY KEY,
  reference_id    TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  media_id        TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN
                  ('canonical','used_as_input','depicts','inspired_by')),
  context_task_id TEXT REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal         INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  is_primary      INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  metadata_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at      TEXT NOT NULL,
  CHECK (role = 'canonical' OR is_primary = 0),
  CHECK (role <> 'used_as_input' OR context_task_id IS NOT NULL),
  CHECK (context_task_id IS NULL OR role IN ('used_as_input','inspired_by'))
);

CREATE TABLE reference_links (
  from_reference_id TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  to_reference_id   TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  kind              TEXT NOT NULL CHECK (kind IN
                    ('belongs_to','wears','located_in','associated_with','related_to')),
  metadata_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at        TEXT NOT NULL,
  PRIMARY KEY (from_reference_id, to_reference_id, kind),
  CHECK (from_reference_id <> to_reference_id)
);

CREATE UNIQUE INDEX reference_one_primary_canonical
  ON media_references(reference_id) WHERE role = 'canonical' AND is_primary = 1;
CREATE UNIQUE INDEX reference_canonical_ordinal
  ON media_references(reference_id, ordinal) WHERE role = 'canonical';
CREATE UNIQUE INDEX media_reference_global_unique
  ON media_references(reference_id, media_id, role)
  WHERE context_task_id IS NULL;
CREATE UNIQUE INDEX media_reference_context_unique
  ON media_references(reference_id, media_id, role, context_task_id)
  WHERE context_task_id IS NOT NULL;
CREATE INDEX references_project_kind
  ON project_references(project_id, kind, name, id);
CREATE INDEX media_references_media
  ON media_references(media_id, role, reference_id);
CREATE INDEX media_references_task
  ON media_references(context_task_id, role, reference_id)
  WHERE context_task_id IS NOT NULL;
CREATE INDEX reference_links_to
  ON reference_links(to_reference_id, kind, from_reference_id);
