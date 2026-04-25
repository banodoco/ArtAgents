-- Discord import quality fixes — acute path. Two changes:
--
-- 1. Add asset_media.sort_order. The new authoring flow and the patched
--    discord-media-importer edge function both reference it, but the
--    column never existed — so the detail page's .order('sort_order')
--    throws 42703, and the edge function attach path would too as soon
--    as its cron starts processing the queued 3099 media jobs.
--
-- 2. Backfill the 139 already-imported assets with the Discord thread's
--    title (from discord_channels.channel_name). The promoter's original
--    name derivation took the first line of the OP message body, which
--    for forum posts is often just a URL. Thread titles are the real
--    human-readable name.
--
-- NOTE: The promoter function's INSERT-time name derivation still uses
-- the old heuristic — so NEW imports (from future promoter runs) will
-- still need a follow-up function rewrite. This migration only fixes
-- the acute symptoms the user is seeing right now.

ALTER TABLE public.asset_media
    ADD COLUMN IF NOT EXISTS sort_order INT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS asset_media_asset_sort_idx
    ON public.asset_media(asset_id, sort_order)
    WHERE is_deleted = FALSE;

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
