DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
    CREATE EXTENSION IF NOT EXISTS pg_cron;

    IF NOT EXISTS (
      SELECT 1
      FROM cron.job
      WHERE jobname = 'discord-resource-promoter'
    ) THEN
      PERFORM cron.schedule(
        'discord-resource-promoter',
        '*/10 * * * *',
        $$ SELECT internal.discord_promote_resources(); $$
      );
    END IF;
  END IF;
END;
$outer$;
