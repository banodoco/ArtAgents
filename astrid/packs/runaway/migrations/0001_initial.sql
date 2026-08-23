-- Astrid runaway schema pack creation migration: runaway/0001_initial
--
-- Typed home for Runaway timing with per-transition prompts, FK-integrated
-- with the kernel run table. The kernel tables (projects, runs, tasks) are
-- created by the core migration; pack foreign keys point inward to the
-- kernel only (plugin law 1).
--
-- Contract notes:
--   * runaway_transitions stores one row per timing transition with a
--     per-run ordinal, start/duration, and non-empty prompt. Ordinal is
--     contiguous within a run; runs with >256 transitions shard across
--     continuation runs via continue_run (ordinal contiguous globally,
--     run_id per shard).
--   * task_id is nullable and SET NULL on task deletion; UNIQUE(run_id,task_id)
--     holds only where task_id IS NOT NULL.
--   * project_id redundantly stored for the covering index and CASCADE on
--     project deletion; run_id FK is RESTRICT (a transition pins its run).
--   * No PRAGMAs repeated here: connection-level settings are applied and
--     asserted by the migration runner from the core catalog.

CREATE TABLE runaway_transitions (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  run_id        TEXT NOT NULL REFERENCES runs(id) ON DELETE RESTRICT,
  task_id       TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  ordinal       INTEGER NOT NULL CHECK (ordinal >= 0),
  start_ms      INTEGER NOT NULL CHECK (start_ms >= 0),
  duration_ms   INTEGER NOT NULL CHECK (duration_ms > 0),
  prompt        TEXT NOT NULL CHECK (length(trim(prompt)) > 0),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  UNIQUE (run_id, ordinal),
  FOREIGN KEY (run_id, project_id) REFERENCES runs(id, project_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX runaway_transitions_run_task_unique
  ON runaway_transitions(run_id, task_id) WHERE task_id IS NOT NULL;

CREATE INDEX runaway_transitions_project_run_ordinal
  ON runaway_transitions(project_id, run_id, ordinal);
