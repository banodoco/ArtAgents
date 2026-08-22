-- Astrid timeline schema pack migration: timeline/0002 (contract canary)
--
-- Pack: timeline   Version: 2   Purpose: second contract surface for the
-- SQLite migration set (additive-only, checksummed, forward-only). The
-- migrations directory of the timeline pack is the S-owned surface
-- (ArtAgents/packages/timeline-schema/sql): A vendors each file verbatim
-- and the runner applies it once, transactionally, in version order.
--
-- Decision (index vs canary), recorded honestly from EXPLAIN evidence:
--   The history SELECT in astrid/packs/timeline/repository.py
--   (_lifecycle_events) filters the events table with
--   stream_id = ? AND kind IN ('timeline.created','timeline.saved',
--   'timeline.archived') ORDER BY seq ASC. Measured on a seeded 4000-event
--   database (SQLite 3.37.2, exact query with bound parameters):
--     * baseline plan: SEARCH events USING INDEX sqlite_autoindex_events_3
--       (stream_id=?) -- the core (stream_id, seq) unique index already
--       yields seq order with no temp b-tree; kind is filtered in-scan.
--     * a candidate (stream_id, kind, seq) index does not change the plan;
--       the kernel's own events_stream_kind_seq index (stream_id, kind,
--       seq) is likewise ignored, because the kind IN-list merge plus sort
--       is estimated costlier than the ordered scan.
--     * a partial index over the three history kinds is selected only when
--       the kinds are inlined as literals; the repository binds parameters,
--       so the planner can never prove the inclusion and never uses it.
--   No additive index measurably helps this query (no rows-examined drop,
--   no scan-to-seek change), so this migration carries a contract canary
--   instead: a table that must exist on every migrated database, proving
--   the S-owned surface applies, without touching any kernel table.
--
-- Additive-only: creates one new table and changes nothing existing. No
-- connection-level settings are repeated here: the migration runner applies
-- those from the core catalog around each transaction.

CREATE TABLE timeline_contract_canary (
  id         INTEGER PRIMARY KEY CHECK (id > 0),
  note       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
