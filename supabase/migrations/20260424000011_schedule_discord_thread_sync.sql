-- Schedule the discord-thread-sync edge function hourly.
-- Why: Discord forum threads get archived automatically, so their metadata
-- (name, type, parent_id) has to be pulled from the parent forum channel's
-- archived-threads endpoint rather than the live /channels/{id} endpoint.
-- Without this sync, newly imported assets fall back to the OP body's first
-- line as their name (which for workflow posts is often just a URL).

SELECT cron.schedule(
    'discord-thread-sync',
    '15 * * * *',
    $$
    SELECT net.http_post(
        url := 'https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/discord-thread-sync',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || COALESCE(internal.get_service_role_key(), ''),
            'Content-Type', 'application/json'
        ),
        body := '{}'::jsonb
    );
    $$
)
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'discord-thread-sync');

-- Re-run the promoter's name/slug backfill (same logic as migration 000008)
-- now that the thread-sync is in place. Safe to run repeatedly.
UPDATE public.assets AS a
SET
    name = c.channel_name,
    slug = public.build_asset_slug(c.channel_name, a.id)
FROM public.discord_channels AS c
WHERE c.channel_id = a.discord_thread_id
  AND c.channel_type = 'thread'
  AND a.source = 'discord_import'
  AND c.channel_name IS NOT NULL
  AND BTRIM(c.channel_name) <> ''
  AND (a.name IS NULL OR a.name <> c.channel_name);
