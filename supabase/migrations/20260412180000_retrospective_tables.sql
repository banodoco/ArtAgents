-- Retrospective feedback tables, views, RLS, and grants

create table if not exists public.retrospective_feedback_groups (
  id uuid primary key default gen_random_uuid(),
  edition text not null default 'edition-2',
  title text not null,
  admin_response text,
  sort_order integer,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.retrospective_feedback (
  id uuid primary key default gen_random_uuid(),
  edition text not null default 'edition-2',
  user_id uuid not null references auth.users (id) on delete cascade,
  content text not null check (char_length(trim(content)) > 0),
  group_id uuid references public.retrospective_feedback_groups (id) on delete set null,
  is_hidden boolean not null default false,
  created_at timestamptz not null default timezone('utc', now())
);

create or replace view public.retrospective_payouts as
select
  p.recipient_discord_id::text as discord_id,
  p.recipient_wallet::text as wallet,
  p.is_test,
  p.amount_token::numeric(10,4) as sol,
  p.amount_usd::numeric(10,2) as usd,
  p.status::text as status,
  p.tx_signature::text as tx_signature,
  p.last_error::text as last_error,
  p.created_at::timestamp(0) as created,
  p.submitted_at::timestamp(0) as submitted,
  p.completed_at::timestamp(0) as completed,
  i.intent_id::text as intent_id,
  i.status::text as intent_status,
  i.requested_amount_sol::numeric(10,4) as intent_sol,
  prof.display_name,
  prof.avatar_url,
  sd.id::text as entry_id,
  sd.title as entry_title,
  sd.thumbnail_url as entry_thumbnail,
  sd.prize_tier as entry_prize_tier
from public.payment_requests p
left join public.admin_payment_intents i
  on i.test_payment_id = p.payment_id
  or i.final_payment_id = p.payment_id
left join public.profiles prof
  on prof.discord_id = p.recipient_discord_id::text
left join public.competition_entries ce
  on ce.member_id = p.recipient_discord_id
left join public.submission_details sd
  on sd.id = ce.id
where p.provider = 'solana_payouts'
  and p.created_at >= '2026-04-11 00:00:00+00'::timestamptz
  and p.is_test = false
  and p.status in ('confirmed', 'completed')
  and p.amount_token::numeric > 1
order by p.created_at;

create or replace view public.retrospective_feedback_display as
select
  f.id,
  f.user_id,
  f.content,
  f.created_at,
  f.group_id,
  g.title as group_title,
  g.admin_response as group_admin_response,
  g.sort_order as group_sort_order,
  prof.display_name,
  prof.avatar_url
from public.retrospective_feedback f
left join public.retrospective_feedback_groups g
  on g.id = f.group_id
left join public.profiles prof
  on prof.id = f.user_id
where f.is_hidden = false
order by g.sort_order nulls last, f.created_at;

alter table public.retrospective_feedback enable row level security;
alter table public.retrospective_feedback_groups enable row level security;

drop policy if exists "Public read visible retrospective feedback" on public.retrospective_feedback;
create policy "Public read visible retrospective feedback"
  on public.retrospective_feedback
  for select
  to anon, authenticated
  using (is_hidden = false);

drop policy if exists "Authenticated users insert own retrospective feedback" on public.retrospective_feedback;
create policy "Authenticated users insert own retrospective feedback"
  on public.retrospective_feedback
  for insert
  to authenticated
  with check (user_id = auth.uid());

drop policy if exists "Admins update retrospective feedback" on public.retrospective_feedback;
create policy "Admins update retrospective feedback"
  on public.retrospective_feedback
  for update
  to authenticated
  using (
    exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and is_admin = true
    )
  )
  with check (
    exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and is_admin = true
    )
  );

drop policy if exists "Users delete own retrospective feedback" on public.retrospective_feedback;
create policy "Users delete own retrospective feedback"
  on public.retrospective_feedback
  for delete
  to authenticated
  using (user_id = auth.uid());

drop policy if exists "Public read retrospective feedback groups" on public.retrospective_feedback_groups;
create policy "Public read retrospective feedback groups"
  on public.retrospective_feedback_groups
  for select
  to anon, authenticated
  using (true);

drop policy if exists "Admins insert retrospective feedback groups" on public.retrospective_feedback_groups;
create policy "Admins insert retrospective feedback groups"
  on public.retrospective_feedback_groups
  for insert
  to authenticated
  with check (
    exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and is_admin = true
    )
  );

drop policy if exists "Admins update retrospective feedback groups" on public.retrospective_feedback_groups;
create policy "Admins update retrospective feedback groups"
  on public.retrospective_feedback_groups
  for update
  to authenticated
  using (
    exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and is_admin = true
    )
  )
  with check (
    exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and is_admin = true
    )
  );

drop policy if exists "Admins delete retrospective feedback groups" on public.retrospective_feedback_groups;
create policy "Admins delete retrospective feedback groups"
  on public.retrospective_feedback_groups
  for delete
  to authenticated
  using (
    exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and is_admin = true
    )
  );

grant select on public.retrospective_payouts to anon, authenticated;
grant select on public.retrospective_feedback_display to anon, authenticated;
grant select on public.retrospective_feedback to anon, authenticated;
grant insert, update, delete on public.retrospective_feedback to authenticated;
grant select on public.retrospective_feedback_groups to anon, authenticated;
grant insert, update, delete on public.retrospective_feedback_groups to authenticated;
