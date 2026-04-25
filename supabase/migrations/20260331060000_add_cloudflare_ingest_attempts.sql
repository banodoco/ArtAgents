ALTER TABLE media
  ADD COLUMN IF NOT EXISTS cloudflare_ingest_attempts smallint NOT NULL DEFAULT 0;
