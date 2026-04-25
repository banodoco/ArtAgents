-- Requires operator seed after this migration applies, otherwise the cron job
-- will call the Edge Function without a bearer token and receive HTTP 401:
-- INSERT INTO internal.secrets (name, value)
-- VALUES ('service_role_key', '<SERVICE_ROLE_KEY>')
-- ON CONFLICT (name) DO UPDATE
-- SET value = EXCLUDED.value,
--     updated_at = NOW();

DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron')
     AND EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_net') THEN
    CREATE EXTENSION IF NOT EXISTS pg_cron;
    CREATE EXTENSION IF NOT EXISTS pg_net;

    IF NOT EXISTS (
      SELECT 1
      FROM cron.job
      WHERE jobname = 'discord-media-importer'
    ) THEN
      PERFORM cron.schedule(
        'discord-media-importer',
        '*/2 * * * *',
        $cron$
        SELECT net.http_post(
          url := 'https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/discord-media-importer',
          headers := jsonb_build_object(
            'Authorization', 'Bearer ' || COALESCE(internal.get_service_role_key(), ''),
            'Content-Type', 'application/json'
          ),
          body := '{}'::jsonb
        );
        $cron$
      );
    END IF;
  END IF;
END;
$outer$;
