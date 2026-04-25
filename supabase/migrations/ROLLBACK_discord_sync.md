# Discord Resource Sync Rollback

This rollback applies to the checked-in Discord resource sync work added in:

- `20260423000000_assets_discord_import_cols.sql`
- `20260423000001_asset_comments.sql`
- `20260423000002_media_import_jobs.sql`
- `20260423000003_internal_secrets_bootstrap.sql`
- `20260423000004_discord_messages_resource_op_idx.sql`
- `20260423000005_discord_promoter_fn.sql`
- `20260424000000_schedule_discord_promoter.sql`
- `20260424000001_schedule_discord_media_importer.sql`

Use a maintenance window. Take a fresh database backup first.

## Rollback Order

1. Stop scheduled execution first so no new writes land during rollback.

```sql
SELECT cron.unschedule('discord-resource-promoter')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'discord-resource-promoter');

SELECT cron.unschedule('discord-media-importer')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'discord-media-importer');
```

2. Remove the promoter function before dropping supporting objects.

```sql
DROP FUNCTION IF EXISTS internal.discord_promote_resources(BOOLEAN);
```

3. Drop the comment-media junction table before its parent tables.

```sql
DROP TABLE IF EXISTS public.asset_comment_media;
```

4. Drop imported comment records next. This also removes `asset_comments.discord_guild_id` and the self-referential reply linkage in one step.

```sql
DROP TABLE IF EXISTS public.asset_comments;
```

5. Drop the media import queue.

```sql
DROP TABLE IF EXISTS public.media_import_jobs;
```

6. Remove the Discord-sync column added to `asset_media`.

```sql
ALTER TABLE public.asset_media
    DROP COLUMN IF EXISTS is_deleted;
```

7. Remove Discord-sync indexes on `assets` and `discord_messages`.

```sql
DROP INDEX IF EXISTS public.assets_discord_thread_id_unique;
DROP INDEX IF EXISTS public.assets_source_idx;
DROP INDEX IF EXISTS public.assets_is_hidden_idx;
DROP INDEX IF EXISTS public.discord_messages_resource_op_idx;
```

8. Remove the `assets` Discord-import columns, including `discord_guild_id`.

```sql
ALTER TABLE public.assets
    DROP CONSTRAINT IF EXISTS assets_source_check,
    DROP COLUMN IF EXISTS source,
    DROP COLUMN IF EXISTS discord_guild_id,
    DROP COLUMN IF EXISTS discord_channel_id,
    DROP COLUMN IF EXISTS discord_thread_id,
    DROP COLUMN IF EXISTS imported_at,
    DROP COLUMN IF EXISTS last_synced_at,
    DROP COLUMN IF EXISTS reactions_reached_threshold_at,
    DROP COLUMN IF EXISTS is_hidden;
```

9. Remove the secrets accessor before removing the secrets table. Drop the `internal` schema only if it is otherwise empty.

```sql
DROP FUNCTION IF EXISTS internal.get_service_role_key();
DROP TABLE IF EXISTS internal.secrets;
-- Run only if no unrelated internal objects remain.
DROP SCHEMA IF EXISTS internal;
```

10. Revert the frontend pull request so the website stops querying the rolled-back schema and stops rendering the Discord-specific resource UI.

Frontend revert scope:

- `banodoco-website/src/components/resources/AssetDescription.tsx`
- `banodoco-website/src/hooks/useAssetComments.ts`
- `banodoco-website/src/hooks/useCommunityResource.ts`
- `banodoco-website/src/hooks/useCommunityResources.ts`
- `banodoco-website/src/hooks/useUserProfile.ts`
- `banodoco-website/src/lib/discordResources.ts`
- `banodoco-website/src/pages/ResourceDetail/index.tsx`
- `banodoco-website/src/pages/Resources/ResourceCard.tsx`
- `banodoco-website/src/pages/Resources/ResourceModal.tsx`
- `banodoco-website/src/pages/Resources/types.ts`
- `banodoco-website/src/pages/Resources/useResources.ts`

## Risks

- Cloudflare Stream quota: negligible at the current expected volume of about 15 qualifying OPs per 30 days, but still worth checking before a large backfill rerun.
- Discord rate limits: current pacing is conservative because the importer claims 10 jobs every 2 minutes; raising claim size or manual reruns increases risk.
- Edge-function timeout: the importer has a 400 second budget, and a 10-job claim should remain comfortably inside it unless attachment sizes spike.
- Storage cost: image and file uploads land in Supabase Storage, so monitor the Supabase dashboard during the 60-day backfill window.
- Unseeded `internal.secrets`: if `service_role_key` is missing, the importer cron will send unauthenticated requests and surface as failed importer jobs with HTTP 401 errors.

## Follow-Ups

- Comment-media lightbox remains deferred per DEC-011; v1 stays on outbound links.
- Cloudflare duration webhook extension can be added later if duration becomes product-relevant.
- Move `internal.secrets` to `supabase_vault` when the project is ready to adopt a first-class secret store.
