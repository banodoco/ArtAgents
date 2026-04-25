alter table public.entry_analytics
add column if not exists anonymous_id text;

create index if not exists entry_analytics_anonymous_id_idx
on public.entry_analytics (anonymous_id);

drop function if exists public.upsert_entry_analytics(
  text,
  uuid,
  uuid,
  uuid,
  integer,
  boolean,
  integer,
  boolean,
  text,
  text,
  text,
  timestamptz
);

create or replace function public.upsert_entry_analytics(
  p_anonymous_id text,
  p_session_id text,
  p_entry_id uuid,
  p_competition_id uuid,
  p_user_id uuid default null,
  p_view_duration_seconds integer default 0,
  p_video_played boolean default false,
  p_video_play_duration_seconds integer default 0,
  p_video_completed boolean default false,
  p_device_type text default null,
  p_referrer text default null,
  p_user_agent text default null,
  p_last_viewed_at timestamptz default now()
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.entry_analytics (
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
  values (
    p_anonymous_id,
    p_session_id,
    p_entry_id,
    p_user_id,
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
  on conflict (session_id, entry_id) do update
  set
    anonymous_id = coalesce(public.entry_analytics.anonymous_id, excluded.anonymous_id),
    user_id = coalesce(public.entry_analytics.user_id, excluded.user_id),
    competition_id = excluded.competition_id,
    view_duration_seconds =
      public.entry_analytics.view_duration_seconds + coalesce(excluded.view_duration_seconds, 0),
    video_played = public.entry_analytics.video_played or coalesce(excluded.video_played, false),
    video_play_duration_seconds =
      public.entry_analytics.video_play_duration_seconds + coalesce(excluded.video_play_duration_seconds, 0),
    video_completed =
      public.entry_analytics.video_completed or coalesce(excluded.video_completed, false),
    device_type = coalesce(excluded.device_type, public.entry_analytics.device_type),
    referrer = coalesce(excluded.referrer, public.entry_analytics.referrer),
    user_agent = coalesce(excluded.user_agent, public.entry_analytics.user_agent),
    total_view_duration_seconds =
      public.entry_analytics.total_view_duration_seconds + coalesce(excluded.view_duration_seconds, 0),
    last_viewed_at = coalesce(excluded.last_viewed_at, public.entry_analytics.last_viewed_at),
    updated_at = now();
end;
$$;

grant execute on function public.upsert_entry_analytics(
  text,
  text,
  uuid,
  uuid,
  uuid,
  integer,
  boolean,
  integer,
  boolean,
  text,
  text,
  text,
  timestamptz
) to anon, authenticated;
