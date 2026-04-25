-- pg_cron is already enabled on Supabase hosted projects.
-- For local dev, this extension may not be available — wrap in a DO block
-- so the migration doesn't fail in environments without pg_cron.
DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
    CREATE EXTENSION IF NOT EXISTS pg_cron;

    -- Schedule hourly computation of foundation voter priority scores once.
    IF NOT EXISTS (
      SELECT 1
      FROM cron.job
      WHERE jobname = 'compute-priority-scores'
    ) THEN
      PERFORM cron.schedule(
        'compute-priority-scores',
        '0 * * * *',
        'SELECT public.compute_priority_scores()'
      );
    END IF;
  END IF;
END;
$outer$;
