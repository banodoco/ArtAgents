-- Read-only audit pack for the OpenMuse profiles consolidation.
-- Run this manually against the shared Supabase database and save the results.

-- 1. Back up the legacy profiles rows before any write migration.
SELECT *
FROM profiles
ORDER BY created_at;

-- 2. Measure OpenMuse table usage before cutover.
SELECT count(*) AS media_count FROM media;
SELECT count(DISTINCT user_id) AS distinct_media_profile_ids FROM media;
SELECT count(*) AS assets_count FROM assets;
SELECT count(DISTINCT user_id) AS distinct_asset_profile_ids FROM assets;

-- 3. Check how many legacy profiles already overlap with discord_members.
SELECT
    p.id,
    p.discord_user_id,
    p.username,
    dm.member_id
FROM profiles p
LEFT JOIN discord_members dm
    ON dm.member_id = p.discord_user_id::BIGINT
WHERE p.discord_user_id ~ '^[0-9]+$'
ORDER BY p.created_at;

-- 4. Flag malformed legacy profile identities that need manual handling.
SELECT id, discord_user_id, username
FROM profiles
WHERE discord_user_id IS NULL
   OR discord_user_id !~ '^[0-9]+$';

-- 5. Inventory tables and row counts in the public schema.
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

SELECT relname, n_live_tup
FROM pg_stat_user_tables
ORDER BY relname;

SELECT relname
FROM pg_stat_user_tables
WHERE n_live_tup = 0
ORDER BY relname;

-- 6. Foreign-key map.
SELECT
    conname,
    conrelid::regclass AS table_name,
    confrelid::regclass AS referenced_table
FROM pg_constraint
WHERE contype = 'f'
ORDER BY conrelid::regclass::TEXT, conname;

-- 7. Low-usage indexes. Review manually before dropping anything.
SELECT
    schemaname,
    relname,
    indexrelname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY relname, indexrelname;

-- 8. Naming consistency checks around the AG migration.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'ag_%'
ORDER BY table_name;

SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name IN ('twitter_handle', 'reddit_handle', 'twitter_url', 'reddit_url')
ORDER BY table_name, column_name;

-- 9. Pre-drop verification once the application cutover is live.
SELECT conname, conrelid::regclass
FROM pg_constraint
WHERE confrelid = 'profiles'::regclass;

SELECT viewname
FROM pg_views
WHERE schemaname = 'public'
  AND definition ILIKE '%profiles%';

SELECT count(*) AS media_missing_member_id
FROM media
WHERE member_id IS NULL;

SELECT count(*) AS assets_missing_member_id
FROM assets
WHERE member_id IS NULL;
