-- Generalize retrospective feedback scoping from edition text to events FK.
-- Events are guild-scoped (UNIQUE (guild_id, slug)); default to the main Banodoco guild.

insert into public.events (guild_id, slug, name, description, location, start_date, end_date, website_url)
values (
  1076117621407223829,
  'arca-gidan-edition-2',
  'ARCA Gidan — Edition 2',
  null,
  null,
  null,
  null,
  null
)
on conflict (guild_id, slug) do nothing;

insert into public.events (guild_id, slug, name, description, location, start_date, end_date, website_url)
values (
  1076117621407223829,
  'ados-paris-2026',
  'ADOS Paris 2026',
  null,
  'Paris, France',
  '2026-04-17',
  '2026-04-19',
  null
)
on conflict (guild_id, slug) do nothing;

alter table public.retrospective_feedback
  add column if not exists event_id integer references public.events (id) on delete cascade,
  add column if not exists admin_title text,
  add column if not exists admin_response text;

alter table public.retrospective_feedback_groups
  add column if not exists event_id integer references public.events (id) on delete cascade;

create index if not exists retrospective_feedback_event_id_idx
  on public.retrospective_feedback (event_id);

create index if not exists retrospective_feedback_groups_event_id_idx
  on public.retrospective_feedback_groups (event_id);

update public.retrospective_feedback f
set event_id = e.id
from public.events e
where e.slug = 'arca-gidan-edition-2'
  and f.edition = 'edition-2'
  and f.event_id is null;

update public.retrospective_feedback_groups g
set event_id = e.id
from public.events e
where e.slug = 'arca-gidan-edition-2'
  and g.edition = 'edition-2'
  and g.event_id is null;

drop view if exists public.retrospective_feedback_display cascade;

create view public.retrospective_feedback_display as
select
  f.id,
  f.user_id,
  f.content,
  f.created_at,
  f.group_id,
  f.event_id,
  e.slug as event_slug,
  f.admin_title,
  f.admin_response,
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
left join public.events e
  on e.id = f.event_id
where f.is_hidden = false
order by g.sort_order nulls last, f.created_at;

grant select on public.retrospective_feedback_display to anon, authenticated;
