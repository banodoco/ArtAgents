-- Vibe Mode metering migration
--
-- Purely additive; does NOT touch `posts`, `post_bundles`, or the
-- `render_mode` enum. Introduces:
--   * public.vibe_usage      (per-user-per-day counters)
--   * vibe_usage_check(uuid) (read-only preflight gate)
--   * vibe_usage_charge(uuid, int, int) (single-settle post-turn write)
--
-- Both RPCs are SECURITY DEFINER and granted ONLY to service_role so that
-- the agent-proxy Edge Function (itself using a service-role client after
-- bearer-validating the caller) is the sole execution path.

SET search_path = public;

create table public.vibe_usage (
  user_id uuid not null,
  day date not null,
  req_this_minute int not null default 0,
  minute_window_started_at timestamptz not null default now(),
  tokens_today_input bigint not null default 0,
  tokens_today_output bigint not null default 0,
  updated_at timestamptz not null default now(),
  primary key (user_id, day)
);

create index vibe_usage_updated_at_idx
  on public.vibe_usage (updated_at desc);

alter table public.vibe_usage enable row level security;

revoke all on public.vibe_usage from anon, authenticated;

create or replace function public.vibe_usage_check(p_user_id uuid)
returns table (allowed boolean, reason text, tokens_remaining bigint)
language sql
security definer
set search_path = public
as $$
  select
    true as allowed,
    null::text as reason,
    greatest(
      0::bigint,
      500000::bigint
      - coalesce(v.tokens_today_input, 0::bigint)
      - coalesce(v.tokens_today_output, 0::bigint)
    ) as tokens_remaining
  from (select p_user_id) as input
  left join public.vibe_usage v
    on v.user_id = input.p_user_id
   and v.day = current_date;
$$;

create or replace function public.vibe_usage_charge(p_user_id uuid, p_input int, p_output int)
returns table (ok boolean, daily_tokens bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.vibe_usage%rowtype;
begin
  insert into public.vibe_usage (
    user_id,
    day,
    req_this_minute,
    minute_window_started_at,
    tokens_today_input,
    tokens_today_output,
    updated_at
  )
  values (
    p_user_id,
    current_date,
    1,
    now(),
    greatest(p_input, 0),
    greatest(p_output, 0),
    now()
  )
  on conflict (user_id, day) do update
    set
      req_this_minute = case
        when public.vibe_usage.minute_window_started_at > now() - interval '1 minute'
          then public.vibe_usage.req_this_minute + 1
        else 1
      end,
      minute_window_started_at = case
        when public.vibe_usage.minute_window_started_at > now() - interval '1 minute'
          then public.vibe_usage.minute_window_started_at
        else now()
      end,
      tokens_today_input = public.vibe_usage.tokens_today_input + greatest(p_input, 0),
      tokens_today_output = public.vibe_usage.tokens_today_output + greatest(p_output, 0),
      updated_at = now()
  returning * into v_row;

  return query
  select
    true as ok,
    v_row.tokens_today_input + v_row.tokens_today_output as daily_tokens;
end;
$$;

revoke all on function public.vibe_usage_check(uuid) from public, anon, authenticated;
revoke all on function public.vibe_usage_charge(uuid, int, int) from public, anon, authenticated;
grant execute on function public.vibe_usage_check(uuid) to service_role;
grant execute on function public.vibe_usage_charge(uuid, int, int) to service_role;

comment on table public.vibe_usage is
  'Vibe Mode per-user-per-day usage counters. Written exclusively through '
  'vibe_usage_charge() by the agent-proxy Edge Function under service_role.';
