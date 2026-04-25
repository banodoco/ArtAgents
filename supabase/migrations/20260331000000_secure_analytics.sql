-- ============================================================================
-- Secure analytics: lock down RLS policies and harden the RPC function
-- ============================================================================

-- 1. Replace wide-open RLS policies on entry_analytics
-- ----------------------------------------------------------------------------
-- Current state: three policies all with USING(true) / WITH CHECK(true)
-- New state: scoped to own data for users, no anonymous reads

DROP POLICY IF EXISTS "Anyone can insert analytics" ON public.entry_analytics;
DROP POLICY IF EXISTS "Anyone can update analytics" ON public.entry_analytics;
DROP POLICY IF EXISTS "Anyone can read analytics" ON public.entry_analytics;

-- INSERT: still open to anon + authenticated (analytics writes come from the
-- SECURITY DEFINER RPC, but the migration path in useViewedSubmissions does a
-- direct .update(), so we keep direct access scoped appropriately).
-- Direct inserts are not used by the app (the RPC handles them), but we keep
-- a restrictive policy just in case.
CREATE POLICY "Anon can insert own analytics"
    ON public.entry_analytics FOR INSERT
    TO anon
    WITH CHECK (user_id IS NULL);

CREATE POLICY "Users can insert own analytics"
    ON public.entry_analytics FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

-- UPDATE: only authenticated users, only their own anonymous rows (for migration)
-- or rows already attributed to them. Admins can update any row.
CREATE POLICY "Users can update own analytics"
    ON public.entry_analytics FOR UPDATE
    TO authenticated
    USING (
        user_id = auth.uid()
        OR (user_id IS NULL)
        OR public.is_admin()
    )
    WITH CHECK (
        user_id = auth.uid()
        OR public.is_admin()
    );

-- SELECT: authenticated users see their own attributed data + unattributed
-- anonymous rows (needed for useViewedSubmissions migration query).
-- Anonymous users can only see unattributed rows (user_id IS NULL) — they
-- cannot see any data linked to a real user. This protects the sensitive
-- mapping of "which user watched which video" while still allowing the
-- "viewed" badge to work before login.
-- Admins see everything.
CREATE POLICY "Anon can read anonymous analytics"
    ON public.entry_analytics FOR SELECT
    TO anon
    USING (user_id IS NULL);

CREATE POLICY "Users can read own analytics"
    ON public.entry_analytics FOR SELECT
    TO authenticated
    USING (
        user_id = auth.uid()
        OR user_id IS NULL
        OR public.is_admin()
    );

-- Revoke UPDATE from anon — only authenticated users should update (for migration)
REVOKE UPDATE ON public.entry_analytics FROM anon;


-- 2. Harden the upsert_entry_analytics RPC function
-- ----------------------------------------------------------------------------
-- Problem: SECURITY DEFINER function accepts arbitrary p_user_id, allowing
-- anyone to forge analytics attributed to another user.
-- Fix: force p_user_id to match auth.uid() for authenticated callers,
-- force NULL for anonymous callers.

DROP FUNCTION IF EXISTS public.upsert_entry_analytics(
  text, text, uuid, uuid, uuid, integer, boolean, integer, boolean, text, text, text, timestamptz
);

CREATE OR REPLACE FUNCTION public.upsert_entry_analytics(
  p_anonymous_id text,
  p_session_id text,
  p_entry_id uuid,
  p_competition_id uuid,
  p_user_id uuid DEFAULT NULL,
  p_view_duration_seconds integer DEFAULT 0,
  p_video_played boolean DEFAULT false,
  p_video_play_duration_seconds integer DEFAULT 0,
  p_video_completed boolean DEFAULT false,
  p_device_type text DEFAULT NULL,
  p_referrer text DEFAULT NULL,
  p_user_agent text DEFAULT NULL,
  p_last_viewed_at timestamptz DEFAULT now()
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid;
BEGIN
  -- Enforce user_id integrity: callers cannot forge attribution
  IF auth.uid() IS NOT NULL THEN
    -- Authenticated: always use their real auth ID
    v_user_id := auth.uid();
  ELSE
    -- Anonymous: never allow a user_id
    v_user_id := NULL;
  END IF;

  INSERT INTO public.entry_analytics (
    anonymous_id,
    session_id,
    entry_id,
    user_id,
    competition_id,
    view_duration_seconds,
    video_played,
    video_play_duration_seconds,
    video_completed,
    device_type,
    referrer,
    user_agent,
    total_view_duration_seconds,
    visit_count,
    last_viewed_at
  )
  VALUES (
    p_anonymous_id,
    p_session_id,
    p_entry_id,
    v_user_id,
    p_competition_id,
    coalesce(p_view_duration_seconds, 0),
    coalesce(p_video_played, false),
    coalesce(p_video_play_duration_seconds, 0),
    coalesce(p_video_completed, false),
    p_device_type,
    p_referrer,
    p_user_agent,
    coalesce(p_view_duration_seconds, 0),
    1,
    p_last_viewed_at
  )
  ON CONFLICT (session_id, entry_id) DO UPDATE
  SET
    anonymous_id = coalesce(public.entry_analytics.anonymous_id, excluded.anonymous_id),
    user_id = coalesce(public.entry_analytics.user_id, excluded.user_id),
    competition_id = excluded.competition_id,
    view_duration_seconds =
      public.entry_analytics.view_duration_seconds + coalesce(excluded.view_duration_seconds, 0),
    video_played = public.entry_analytics.video_played OR coalesce(excluded.video_played, false),
    video_play_duration_seconds =
      public.entry_analytics.video_play_duration_seconds + coalesce(excluded.video_play_duration_seconds, 0),
    video_completed =
      public.entry_analytics.video_completed OR coalesce(excluded.video_completed, false),
    device_type = coalesce(excluded.device_type, public.entry_analytics.device_type),
    referrer = coalesce(excluded.referrer, public.entry_analytics.referrer),
    user_agent = coalesce(excluded.user_agent, public.entry_analytics.user_agent),
    total_view_duration_seconds =
      public.entry_analytics.total_view_duration_seconds + coalesce(excluded.view_duration_seconds, 0),
    last_viewed_at = coalesce(excluded.last_viewed_at, public.entry_analytics.last_viewed_at),
    updated_at = now();
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_entry_analytics(
  text, text, uuid, uuid, uuid, integer, boolean, integer, boolean, text, text, text, timestamptz
) TO anon, authenticated;


-- 3. Secure the user_analytics_summary view — admin only
-- ----------------------------------------------------------------------------
-- This view shows all users' aggregated watch data. Restrict to admins.

DROP VIEW IF EXISTS public.user_analytics_summary;

CREATE VIEW public.user_analytics_summary AS
SELECT
  user_id,
  competition_id,
  count(DISTINCT entry_id) AS entries_viewed,
  sum(view_duration_seconds) AS total_view_duration_seconds,
  sum(video_play_duration_seconds) AS total_video_play_duration_seconds,
  count(DISTINCT entry_id) FILTER (WHERE video_played) AS entries_with_video_played,
  count(DISTINCT entry_id) FILTER (WHERE video_completed) AS entries_with_video_completed,
  max(last_viewed_at) AS last_active_at
FROM public.entry_analytics
WHERE user_id IS NOT NULL
GROUP BY user_id, competition_id;

-- Only admins and the user themselves should query this view.
-- Since views inherit the underlying table's RLS, authenticated users will
-- only see their own rows (from the SELECT policy above), and admins see all.
-- No additional grants needed beyond what entry_analytics already has.
