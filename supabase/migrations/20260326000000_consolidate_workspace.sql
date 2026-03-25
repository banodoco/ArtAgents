-- ============================================================================
-- Workspace consolidation migration
--
-- This is the first migration applied from the workspace-level supabase/.
-- It does NOT redefine handle_new_user() — brain-of-bndc's 20260324100000
-- already has the correct version targeting public.members.
--
-- Changes:
-- 1. Extend trigger to fire on UPDATE too (so returning users get linked)
-- 2. Backfill any auth users missing member links
-- 3. Add user-uploads storage bucket + RLS (from banodoco-website)
-- 4. Add get_top_community_topics RPC (from banodoco-website)
-- ============================================================================

-- ============================================================================
-- 1. Extend trigger to fire on INSERT OR UPDATE
-- ============================================================================
-- The handle_new_user() function is already correct (targets members table,
-- sets auth_user_id). We just need the trigger to also fire on UPDATE so
-- returning sign-ins link the auth user if the profile is missing.

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- 2. Backfill: link auth users to their member rows
-- ============================================================================

UPDATE members m
SET auth_user_id = u.id
FROM auth.users u
WHERE m.member_id::text = u.raw_user_meta_data->>'sub'
  AND m.auth_user_id IS NULL;

-- ============================================================================
-- 3. Storage bucket for user uploads (from banodoco-website)
-- ============================================================================

INSERT INTO storage.buckets (id, name, public)
VALUES ('user-uploads', 'user-uploads', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies (idempotent — drop if exists then create)
DROP POLICY IF EXISTS "Users can upload to own folder" ON storage.objects;
CREATE POLICY "Users can upload to own folder"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'user-uploads'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Public can read user uploads" ON storage.objects;
CREATE POLICY "Public can read user uploads"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'user-uploads');

DROP POLICY IF EXISTS "Users can update own uploads" ON storage.objects;
CREATE POLICY "Users can update own uploads"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'user-uploads'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users can delete own uploads" ON storage.objects;
CREATE POLICY "Users can delete own uploads"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'user-uploads'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- ============================================================================
-- 4. get_top_community_topics RPC (from banodoco-website)
-- ============================================================================

DROP FUNCTION IF EXISTS get_top_community_topics(DATE);
DROP FUNCTION IF EXISTS get_top_community_topics();

CREATE OR REPLACE FUNCTION get_top_community_topics()
RETURNS TABLE (
  channel_id BIGINT,
  channel_name TEXT,
  topic_title TEXT,
  topic_main_text TEXT,
  topic_sub_topics JSONB,
  media_message_ids TEXT[],
  media_count INT,
  summary_date DATE
)
LANGUAGE plpgsql
AS $$
DECLARE
  latest_date DATE;
BEGIN
  SELECT MAX(ds.date) INTO latest_date
  FROM daily_summaries ds
  WHERE ds.channel_id != 1138790297355174039;

  IF latest_date IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  WITH parsed_topics AS (
    SELECT
      ds.channel_id AS ch_id,
      dc.channel_name AS ch_name,
      ds.date AS s_date,
      topic->>'title' AS t_title,
      topic->>'mainText' AS t_main_text,
      topic->'subTopics' AS t_sub_topics,
      ARRAY_REMOVE(
        ARRAY[topic->>'mainMediaMessageId'] ||
        COALESCE(
          ARRAY(
            SELECT jsonb_array_elements_text(sub->'subTopicMediaMessageIds')
            FROM jsonb_array_elements(COALESCE(topic->'subTopics', '[]'::jsonb)) AS sub
            WHERE sub->'subTopicMediaMessageIds' IS NOT NULL
          ),
          ARRAY[]::TEXT[]
        ),
        NULL
      ) AS media_ids
    FROM daily_summaries ds
    JOIN discord_channels dc ON ds.channel_id = dc.channel_id
    CROSS JOIN LATERAL jsonb_array_elements(ds.full_summary::jsonb) AS topic
    WHERE ds.date = latest_date
      AND ds.channel_id != 1138790297355174039
  ),
  ranked_topics AS (
    SELECT
      pt.ch_id,
      pt.ch_name,
      pt.s_date,
      pt.t_title,
      pt.t_main_text,
      pt.t_sub_topics,
      pt.media_ids,
      CARDINALITY(pt.media_ids) AS m_count,
      ROW_NUMBER() OVER (
        PARTITION BY pt.ch_id
        ORDER BY CARDINALITY(pt.media_ids) DESC
      ) AS rank_in_channel
    FROM parsed_topics pt
  )
  SELECT
    rt.ch_id,
    rt.ch_name,
    rt.t_title,
    rt.t_main_text,
    rt.t_sub_topics,
    rt.media_ids,
    rt.m_count::INT,
    rt.s_date
  FROM ranked_topics rt
  WHERE rt.rank_in_channel = 1
  ORDER BY rt.m_count DESC
  LIMIT 3;
END;
$$;

GRANT EXECUTE ON FUNCTION get_top_community_topics() TO anon, authenticated, service_role;

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
DECLARE
  unlinked_count integer;
BEGIN
  SELECT COUNT(*) INTO unlinked_count
  FROM auth.users u
  LEFT JOIN members m ON m.auth_user_id = u.id
  WHERE m.auth_user_id IS NULL
    AND u.raw_user_meta_data->>'sub' IS NOT NULL;

  IF unlinked_count > 0 THEN
    RAISE WARNING 'Still have % auth users not linked to members', unlinked_count;
  ELSE
    RAISE NOTICE 'All auth users are linked to members';
  END IF;
END $$;
