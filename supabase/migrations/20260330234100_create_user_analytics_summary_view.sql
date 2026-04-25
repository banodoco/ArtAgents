create or replace view public.user_analytics_summary as
select
  user_id,
  competition_id,
  count(distinct entry_id) as entries_viewed,
  sum(view_duration_seconds) as total_view_duration_seconds,
  sum(video_play_duration_seconds) as total_video_play_duration_seconds,
  count(distinct entry_id) filter (where video_played) as entries_with_video_played,
  count(distinct entry_id) filter (where video_completed) as entries_with_video_completed,
  max(last_viewed_at) as last_active_at
from public.entry_analytics
where user_id is not null
group by user_id, competition_id;
