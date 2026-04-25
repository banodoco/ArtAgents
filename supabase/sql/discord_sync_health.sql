-- Discord resource sync health checks.
-- Run with:
--   psql "$DB_URL" -f supabase/sql/discord_sync_health.sql

\pset pager off

\echo ''
\echo '1) Stuck in_progress media import jobs'
SELECT CASE
  WHEN to_regclass('public.media_import_jobs') IS NULL THEN 'false'
  ELSE 'true'
END AS media_import_jobs_exists \gset
\if :media_import_jobs_exists
SELECT
  id,
  discord_attachment_id,
  discord_message_id,
  target_kind,
  target_id,
  attempts,
  locked_until,
  updated_at,
  last_error
FROM public.media_import_jobs
WHERE status = 'in_progress'
  AND locked_until < NOW()
ORDER BY locked_until ASC NULLS FIRST, updated_at ASC, id ASC;
\else
SELECT 'public.media_import_jobs is absent on this database' AS note;
\endif

\echo ''
\echo '2) Failed media import jobs in the last 24 hours grouped by last_error'
SELECT CASE
  WHEN to_regclass('public.media_import_jobs') IS NULL THEN 'false'
  ELSE 'true'
END AS media_import_jobs_exists \gset
\if :media_import_jobs_exists
SELECT
  COALESCE(NULLIF(BTRIM(last_error), ''), '(empty last_error)') AS last_error,
  COUNT(*) AS failed_jobs,
  MAX(updated_at) AS most_recent_failure_at
FROM public.media_import_jobs
WHERE status = 'failed'
  AND updated_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY failed_jobs DESC, most_recent_failure_at DESC;
\else
SELECT 'public.media_import_jobs is absent on this database' AS note;
\endif

\echo ''
\echo '3) Discord-import asset sync staleness'
SELECT CASE
  WHEN to_regclass('public.assets') IS NULL THEN 'false'
  WHEN NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'assets'
      AND column_name = 'source'
  ) THEN 'false'
  WHEN NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'assets'
      AND column_name = 'last_synced_at'
  ) THEN 'false'
  ELSE 'true'
END AS assets_discord_sync_columns_ready \gset
\if :assets_discord_sync_columns_ready
SELECT
  id,
  name,
  discord_channel_id,
  discord_thread_id,
  imported_at,
  last_synced_at,
  NOW() - last_synced_at AS sync_lag
FROM public.assets
WHERE source = 'discord_import'
ORDER BY last_synced_at ASC NULLS FIRST, imported_at ASC NULLS FIRST, id ASC;
\else
SELECT 'public.assets is missing discord sync columns on this database' AS note;
\endif

\echo ''
\echo '4) Recent promoter/importer system logs'
SELECT CASE
  WHEN to_regclass('public.system_logs') IS NULL THEN 'false'
  ELSE 'true'
END AS system_logs_exists \gset
\if :system_logs_exists
SELECT
  id,
  created_at,
  level,
  logger_name,
  message,
  extra
FROM public.system_logs
WHERE logger_name IN ('discord_resource_promoter', 'discord_media_importer')
ORDER BY created_at DESC NULLS LAST, id DESC
LIMIT 100;
\else
SELECT 'public.system_logs is absent on this database' AS note;
\endif
