-- Dedicated Banodoco website database tables for agent-node catalog entries.
-- These tables intentionally do not reuse resources/assets catalog rows.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'agent-node-media',
  'agent-node-media',
  true,
  104857600,
  array[
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'video/mp4',
    'video/webm',
    'video/quicktime'
  ]
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create table public.agent_nodes (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  slug text not null,
  name text not null,
  node_type text not null default 'agent',
  short_description text,
  description text,
  repo_url text not null,
  expected_manifest_id text not null,
  manifest jsonb not null default '{}'::jsonb,
  details jsonb not null default '{}'::jsonb,
  creator_discord_id text,
  creator_display_name text,
  is_public boolean not null default false,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_nodes_slug_format_check
    check (slug ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'),
  constraint agent_nodes_name_present_check
    check (length(btrim(name)) > 0),
  constraint agent_nodes_node_type_check
    check (node_type in ('agent', 'orchestrator')),
  constraint agent_nodes_repo_url_present_check
    check (length(btrim(repo_url)) > 0),
  constraint agent_nodes_expected_manifest_id_present_check
    check (length(btrim(expected_manifest_id)) > 0),
  constraint agent_nodes_manifest_object_check
    check (jsonb_typeof(manifest) = 'object'),
  constraint agent_nodes_details_object_check
    check (jsonb_typeof(details) = 'object'),
  constraint agent_nodes_owner_expected_manifest_unique
    unique (id, expected_manifest_id),
  constraint agent_nodes_owner_integrity_unique
    unique (id, owner_user_id)
);

create unique index agent_nodes_slug_unique_idx
  on public.agent_nodes (lower(slug));

create index agent_nodes_owner_created_idx
  on public.agent_nodes (owner_user_id, created_at desc);

create index agent_nodes_public_browse_idx
  on public.agent_nodes (created_at desc, id)
  where is_public;

create index agent_nodes_public_slug_idx
  on public.agent_nodes (slug)
  where is_public;

create table public.agent_node_catalog_metadata (
  agent_node_id uuid primary key references public.agent_nodes(id) on delete cascade,
  review_status text not null default 'pending',
  is_catalog_enabled boolean not null default false,
  is_featured boolean not null default false,
  is_default boolean not null default false,
  is_mandatory boolean not null default false,
  catalog_rank integer not null default 1000,
  catalog_label text,
  catalog_summary text,
  service_metadata jsonb not null default '{}'::jsonb,
  reviewed_at timestamp with time zone,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_node_catalog_review_status_check
    check (review_status in ('pending', 'approved', 'rejected', 'hidden')),
  constraint agent_node_catalog_rank_nonnegative_check
    check (catalog_rank >= 0),
  constraint agent_node_catalog_service_metadata_object_check
    check (jsonb_typeof(service_metadata) = 'object'),
  constraint agent_node_catalog_mandatory_default_check
    check (not is_mandatory or is_default)
);

create index agent_node_catalog_public_filter_idx
  on public.agent_node_catalog_metadata (
    is_catalog_enabled,
    review_status,
    is_default,
    is_mandatory,
    is_featured,
    catalog_rank,
    agent_node_id
  );

create index agent_node_catalog_featured_idx
  on public.agent_node_catalog_metadata (catalog_rank, agent_node_id)
  where is_catalog_enabled and review_status = 'approved' and is_featured;

create index agent_node_catalog_default_mandatory_idx
  on public.agent_node_catalog_metadata (is_mandatory desc, catalog_rank, agent_node_id)
  where is_catalog_enabled and review_status = 'approved' and is_default;

create table public.agent_node_install_targets (
  id uuid primary key default gen_random_uuid(),
  agent_node_id uuid not null references public.agent_nodes(id) on delete cascade,
  label text,
  source_type text not null default 'git',
  repo_url text,
  manifest_url text,
  archive_url text,
  commit_sha text,
  tag text,
  branch text,
  source_ref text,
  manifest_path text,
  expected_node_id text not null,
  install_subdir text,
  is_enabled boolean not null default false,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_node_install_expected_identity_fk
    foreign key (agent_node_id, expected_node_id)
    references public.agent_nodes(id, expected_manifest_id)
    on update cascade
    on delete cascade,
  constraint agent_node_install_source_type_check
    check (source_type in ('git', 'manifest_url', 'archive_url')),
  constraint agent_node_install_expected_node_id_present_check
    check (length(btrim(expected_node_id)) > 0),
  constraint agent_node_install_git_ref_exact_one_check
    check (
      case
        when source_type = 'git' then
          (
            (case when commit_sha is null then 0 else 1 end) +
            (case when tag is null then 0 else 1 end) +
            (case when branch is null then 0 else 1 end) +
            (case when source_ref is null then 0 else 1 end)
          ) = 1
        else
          commit_sha is null
          and tag is null
          and branch is null
          and source_ref is null
      end
    ),
  constraint agent_node_install_source_shape_check
    check (
      (
        source_type = 'git'
        and repo_url is not null
        and length(btrim(repo_url)) > 0
        and manifest_path is not null
        and length(btrim(manifest_path)) > 0
      )
      or (
        source_type = 'manifest_url'
        and manifest_url is not null
        and length(btrim(manifest_url)) > 0
        and repo_url is null
        and archive_url is null
        and manifest_path is null
      )
      or (
        source_type = 'archive_url'
        and archive_url is not null
        and length(btrim(archive_url)) > 0
        and repo_url is null
        and manifest_url is null
        and manifest_path is not null
        and length(btrim(manifest_path)) > 0
      )
    ),
  constraint agent_node_install_commit_sha_format_check
    check (commit_sha is null or commit_sha ~ '^[0-9a-f]{40}$'),
  constraint agent_node_install_tag_format_check
    check (tag is null or (length(btrim(tag)) > 0 and tag !~ '[[:space:]]')),
  constraint agent_node_install_branch_format_check
    check (branch is null or (length(btrim(branch)) > 0 and branch !~ '[[:space:]]')),
  constraint agent_node_install_source_ref_format_check
    check (source_ref is null or (length(btrim(source_ref)) > 0 and source_ref !~ '[[:space:]]')),
  constraint agent_node_install_manifest_path_relative_check
    check (
      manifest_path is null
      or (
        manifest_path !~ '(^/|(^|/)\.\.(/|$)|//)'
        and length(btrim(manifest_path)) > 0
      )
    ),
  constraint agent_node_install_subdir_relative_check
    check (
      install_subdir is null
      or (
        install_subdir !~ '(^/|(^|/)\.\.(/|$)|//)'
        and length(btrim(install_subdir)) > 0
      )
    )
);

create index agent_node_install_targets_node_idx
  on public.agent_node_install_targets (agent_node_id, created_at desc);

create index agent_node_install_targets_enabled_idx
  on public.agent_node_install_targets (agent_node_id, source_type, created_at desc)
  where is_enabled;

create table public.agent_node_media (
  id uuid primary key default gen_random_uuid(),
  agent_node_id uuid not null,
  owner_user_id uuid not null,
  media_type text not null,
  storage_bucket text not null default 'agent-node-media',
  storage_path text not null,
  mime_type text not null,
  file_size_bytes bigint not null,
  width integer,
  height integer,
  duration_seconds numeric(10, 3),
  alt_text text,
  caption text,
  display_order integer not null default 0,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_node_media_node_owner_fk
    foreign key (agent_node_id, owner_user_id)
    references public.agent_nodes(id, owner_user_id)
    on update cascade
    on delete cascade,
  constraint agent_node_media_type_check
    check (media_type in ('image', 'video')),
  constraint agent_node_media_bucket_check
    check (storage_bucket = 'agent-node-media'),
  constraint agent_node_media_mime_type_check
    check (
      (
        media_type = 'image'
        and mime_type in ('image/jpeg', 'image/png', 'image/webp', 'image/gif')
      )
      or (
        media_type = 'video'
        and mime_type in ('video/mp4', 'video/webm', 'video/quicktime')
      )
    ),
  constraint agent_node_media_size_check
    check (
      file_size_bytes > 0
      and (
        (media_type = 'image' and file_size_bytes <= 10485760)
        or (media_type = 'video' and file_size_bytes <= 104857600)
      )
    ),
  constraint agent_node_media_dimensions_check
    check (
      (width is null or width > 0)
      and (height is null or height > 0)
      and (duration_seconds is null or duration_seconds >= 0)
    ),
  constraint agent_node_media_storage_path_scope_check
    check (
      storage_path like (owner_user_id::text || '/' || agent_node_id::text || '/%')
      and storage_path !~ '(^/|(^|/)\.\.(/|$)|//)'
    ),
  constraint agent_node_media_order_nonnegative_check
    check (display_order >= 0)
);

create unique index agent_node_media_storage_path_unique_idx
  on public.agent_node_media (storage_bucket, storage_path);

create index agent_node_media_order_idx
  on public.agent_node_media (agent_node_id, display_order, created_at, id);

create index agent_node_media_owner_idx
  on public.agent_node_media (owner_user_id, created_at desc);

create index agent_node_media_type_idx
  on public.agent_node_media (agent_node_id, media_type, display_order);

create or replace function public.agent_nodes_touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger agent_nodes_touch_updated_at
  before update on public.agent_nodes
  for each row execute function public.agent_nodes_touch_updated_at();

create trigger agent_node_catalog_touch_updated_at
  before update on public.agent_node_catalog_metadata
  for each row execute function public.agent_nodes_touch_updated_at();

create trigger agent_node_install_targets_touch_updated_at
  before update on public.agent_node_install_targets
  for each row execute function public.agent_nodes_touch_updated_at();

create trigger agent_node_media_touch_updated_at
  before update on public.agent_node_media
  for each row execute function public.agent_nodes_touch_updated_at();

create or replace function public.agent_node_catalog_metadata_owner_guard()
returns trigger
language plpgsql
as $$
begin
  if auth.role() = 'service_role' then
    return new;
  end if;

  if tg_op = 'INSERT' then
    if new.review_status <> 'pending'
      or new.is_catalog_enabled
      or new.is_featured
      or new.is_default
      or new.is_mandatory
      or new.catalog_rank <> 1000
      or new.service_metadata <> '{}'::jsonb
      or new.reviewed_at is not null then
      raise exception 'agent node catalog flags are service-role only';
    end if;
    return new;
  end if;

  if new.review_status is distinct from old.review_status
    or new.is_catalog_enabled is distinct from old.is_catalog_enabled
    or new.is_featured is distinct from old.is_featured
    or new.is_default is distinct from old.is_default
    or new.is_mandatory is distinct from old.is_mandatory
    or new.catalog_rank is distinct from old.catalog_rank
    or new.service_metadata is distinct from old.service_metadata
    or new.reviewed_at is distinct from old.reviewed_at then
    raise exception 'agent node catalog flags are service-role only';
  end if;

  return new;
end;
$$;

create trigger agent_node_catalog_metadata_owner_guard
  before insert or update on public.agent_node_catalog_metadata
  for each row execute function public.agent_node_catalog_metadata_owner_guard();

create or replace function public.agent_node_install_targets_owner_guard()
returns trigger
language plpgsql
as $$
begin
  if auth.role() = 'service_role' then
    return new;
  end if;

  if tg_op = 'INSERT' then
    if new.is_enabled then
      raise exception 'agent node install target enablement is service-role only';
    end if;
    return new;
  end if;

  if new.is_enabled is distinct from old.is_enabled then
    raise exception 'agent node install target enablement is service-role only';
  end if;

  return new;
end;
$$;

create trigger agent_node_install_targets_owner_guard
  before insert or update on public.agent_node_install_targets
  for each row execute function public.agent_node_install_targets_owner_guard();

alter table public.agent_nodes enable row level security;
alter table public.agent_node_catalog_metadata enable row level security;
alter table public.agent_node_install_targets enable row level security;
alter table public.agent_node_media enable row level security;

create policy "agent_nodes_public_read"
  on public.agent_nodes for select
  using (is_public);

create policy "agent_nodes_owner_read"
  on public.agent_nodes for select
  using (auth.uid() = owner_user_id);

create policy "agent_nodes_owner_insert"
  on public.agent_nodes for insert
  with check (auth.uid() = owner_user_id);

create policy "agent_nodes_owner_update"
  on public.agent_nodes for update
  using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);

create policy "agent_nodes_owner_delete"
  on public.agent_nodes for delete
  using (auth.uid() = owner_user_id);

create policy "agent_node_catalog_public_read"
  on public.agent_node_catalog_metadata for select
  using (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_catalog_metadata.agent_node_id
        and node.is_public
    )
  );

create policy "agent_node_catalog_owner_read"
  on public.agent_node_catalog_metadata for select
  using (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_catalog_metadata.agent_node_id
        and node.owner_user_id = auth.uid()
    )
  );

create policy "agent_node_catalog_owner_insert"
  on public.agent_node_catalog_metadata for insert
  with check (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_catalog_metadata.agent_node_id
        and node.owner_user_id = auth.uid()
    )
  );

create policy "agent_node_catalog_owner_update"
  on public.agent_node_catalog_metadata for update
  using (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_catalog_metadata.agent_node_id
        and node.owner_user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_catalog_metadata.agent_node_id
        and node.owner_user_id = auth.uid()
    )
  );

create policy "agent_node_install_targets_public_read"
  on public.agent_node_install_targets for select
  using (
    is_enabled
    and exists (
      select 1
      from public.agent_nodes node
      join public.agent_node_catalog_metadata catalog on catalog.agent_node_id = node.id
      where node.id = public.agent_node_install_targets.agent_node_id
        and node.is_public
        and catalog.review_status = 'approved'
        and catalog.is_catalog_enabled
    )
  );

create policy "agent_node_install_targets_owner_all"
  on public.agent_node_install_targets for all
  using (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_install_targets.agent_node_id
        and node.owner_user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_install_targets.agent_node_id
        and node.owner_user_id = auth.uid()
    )
  );

create policy "agent_node_media_public_read"
  on public.agent_node_media for select
  using (
    exists (
      select 1
      from public.agent_nodes node
      where node.id = public.agent_node_media.agent_node_id
        and node.is_public
    )
  );

create policy "agent_node_media_owner_all"
  on public.agent_node_media for all
  using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);

create or replace view public.public_agent_node_catalog
with (security_invoker = true) as
select
  node.id,
  node.slug,
  node.name,
  node.node_type,
  node.short_description,
  node.description,
  node.repo_url,
  node.expected_manifest_id,
  node.creator_discord_id,
  node.creator_display_name,
  node.created_at,
  node.updated_at,
  catalog.is_featured,
  catalog.is_default,
  catalog.is_mandatory,
  catalog.catalog_rank,
  catalog.catalog_label,
  catalog.catalog_summary
from public.agent_nodes node
join public.agent_node_catalog_metadata catalog on catalog.agent_node_id = node.id
where node.is_public
  and catalog.is_catalog_enabled
  and catalog.review_status = 'approved';

create or replace view public.public_agent_node_install_targets
with (security_invoker = true) as
select
  target.id,
  target.agent_node_id,
  target.label,
  target.source_type,
  target.repo_url,
  target.manifest_url,
  target.archive_url,
  target.commit_sha,
  target.tag,
  target.branch,
  target.source_ref,
  target.manifest_path,
  target.expected_node_id,
  target.install_subdir,
  target.created_at
from public.agent_node_install_targets target
join public.public_agent_node_catalog catalog on catalog.id = target.agent_node_id
where target.is_enabled;

create or replace view public.public_agent_node_media
with (security_invoker = true) as
select
  media.id,
  media.agent_node_id,
  media.media_type,
  media.storage_bucket,
  media.storage_path,
  media.mime_type,
  media.file_size_bytes,
  media.width,
  media.height,
  media.duration_seconds,
  media.alt_text,
  media.caption,
  media.display_order,
  media.created_at
from public.agent_node_media media
join public.public_agent_node_catalog catalog on catalog.id = media.agent_node_id;

create policy "agent_node_media_storage_public_read"
  on storage.objects for select
  using (
    bucket_id = 'agent-node-media'
    and exists (
      select 1
      from public.agent_node_media media
      join public.agent_nodes node on node.id = media.agent_node_id
      where media.storage_bucket = bucket_id
        and media.storage_path = name
        and node.is_public
    )
  );

create policy "agent_node_media_storage_owner_insert"
  on storage.objects for insert
  with check (
    bucket_id = 'agent-node-media'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "agent_node_media_storage_owner_update"
  on storage.objects for update
  using (
    bucket_id = 'agent-node-media'
    and auth.uid()::text = (storage.foldername(name))[1]
  )
  with check (
    bucket_id = 'agent-node-media'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "agent_node_media_storage_owner_delete"
  on storage.objects for delete
  using (
    bucket_id = 'agent-node-media'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
