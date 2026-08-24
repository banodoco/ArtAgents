-- Astrid shots schema pack generation-content migration: shots/0002_generations
--
-- Adds the two relational content tables the Reigh gallery needs
-- (docs-corpus/27-build-spec.md section 2.2; DDL transcribed from
-- docs-corpus/17-pack-v2-ddl.md section 2 minus shot_generation_items).
-- FKs point inward to the kernel only (plugin law 1); media_id is the
-- kernel currency on variants (plugin law 2).
--
-- Contract notes:
--   * There is no generation event stream in v1 (build spec 2.3): star,
--     set-primary, and soft-delete are small writer-serialized commands,
--     so no stream-derived convenience column exists either.
--   * media_id is ON DELETE RESTRICT: a variant pins the kernel media row
--     whose bytes it records.
--   * UNIQUE (generation_id, media_id) is unique media membership; the
--     partial unique index generation_one_primary keeps at most one
--     primary variant per generation.
--   * Soft deletion is deleted_at on generations only; bytes and variants
--     survive a soft delete.
--   * No URL/location/thumbnail columns and no primary_variant_id
--     denormalization (SD1): derived by query.
--   * No PRAGMAs are repeated here: connection-level settings are applied
--     by the migration runner from the core catalog.
--   * Plain DDL only: guard logic lives in repositories, never triggers.

CREATE TABLE generations (
  id                      TEXT PRIMARY KEY,
  project_id              TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  task_id                 TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  type                    TEXT NOT NULL,
  name                    TEXT,
  based_on_generation_id  TEXT REFERENCES generations(id) ON DELETE SET NULL,
  parent_generation_id    TEXT REFERENCES generations(id) ON DELETE CASCADE,
  child_order             INTEGER CHECK (child_order >= 0),
  params_json             TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_json)),
  starred                 INTEGER NOT NULL DEFAULT 0 CHECK (starred IN (0,1)),
  deleted_at              TEXT,
  created_at              TEXT NOT NULL,
  updated_at              TEXT NOT NULL,
  CHECK (based_on_generation_id IS NULL OR based_on_generation_id <> id),
  CHECK (parent_generation_id IS NULL OR parent_generation_id <> id)
);

CREATE TABLE generation_variants (
  id            TEXT PRIMARY KEY,
  generation_id TEXT NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
  media_id      TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  variant_type  TEXT,
  name          TEXT,
  params_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_json)),
  is_primary    INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  starred       INTEGER NOT NULL DEFAULT 0 CHECK (starred IN (0,1)),
  viewed_at     TEXT,
  created_at    TEXT NOT NULL,
  UNIQUE (generation_id, media_id)
);

-- generations page/index queries (gallery)
CREATE INDEX generations_project_page   ON generations(project_id, created_at DESC, id);
CREATE INDEX generations_project_starred ON generations(project_id, starred, created_at DESC, id);
CREATE INDEX generations_project_type   ON generations(project_id, type, created_at DESC, id);
CREATE INDEX generations_based_on       ON generations(based_on_generation_id) WHERE based_on_generation_id IS NOT NULL;
CREATE INDEX generations_parent         ON generations(parent_generation_id) WHERE parent_generation_id IS NOT NULL;
CREATE INDEX generations_task           ON generations(task_id) WHERE task_id IS NOT NULL;

-- variants: one primary per generation + membership lookups
CREATE UNIQUE INDEX generation_one_primary
  ON generation_variants(generation_id) WHERE is_primary = 1;
CREATE INDEX generation_variants_generation
  ON generation_variants(generation_id, is_primary, created_at, id);
CREATE INDEX generation_variants_media
  ON generation_variants(media_id, generation_id);
