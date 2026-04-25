-- Add IP address tracking to entry_analytics for spoof detection
-- inet_client_addr() captures the connecting client's IP inside SECURITY DEFINER functions

ALTER TABLE public.entry_analytics ADD COLUMN IF NOT EXISTS ip_address inet;

-- Recreate the RPC to capture IP on insert and update
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
  v_ip inet;
BEGIN
  -- Enforce user_id integrity: callers cannot forge attribution
  IF auth.uid() IS NOT NULL THEN
    v_user_id := auth.uid();
  ELSE
    v_user_id := NULL;
  END IF;

  -- Capture client IP server-side (cannot be spoofed from JS)
  v_ip := inet_client_addr();

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
    last_viewed_at,
    ip_address
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
    p_last_viewed_at,
    v_ip
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
    ip_address = coalesce(excluded.ip_address, public.entry_analytics.ip_address),
    updated_at = now();
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_entry_analytics(
  text, text, uuid, uuid, uuid, integer, boolean, integer, boolean, text, text, text, timestamptz
) TO anon, authenticated;
