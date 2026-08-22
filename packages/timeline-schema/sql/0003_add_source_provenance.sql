-- Astrid timeline schema pack migration: timeline/0003 (import provenance)
--
-- Pack: timeline   Version: 3   Purpose: persist import provenance for
-- backfilled events (source_backend/source_timeline_id/source_event_id/
-- source_version/source_hash) as nullable columns on the kernel events
-- table. Additive-only, checksummed, forward-only.
--
-- Columns are nullable so existing rows remain valid; payload bytes are
-- untouched (payload_json still holds the SD2 envelope). Backfill equality
-- is therefore unaffected.

ALTER TABLE events ADD COLUMN source_backend TEXT;
ALTER TABLE events ADD COLUMN source_timeline_id TEXT;
ALTER TABLE events ADD COLUMN source_event_id TEXT;
ALTER TABLE events ADD COLUMN source_version INTEGER;
ALTER TABLE events ADD COLUMN source_hash TEXT;
