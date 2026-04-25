ALTER TABLE public.approval_requests
  ADD COLUMN IF NOT EXISTS embed_dirty boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS embed_updated_at timestamptz;

CREATE OR REPLACE FUNCTION public.mark_approval_dirty_for_member(p_member_id bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.approval_requests AS ar
  SET embed_dirty = true
  FROM public.members AS m
  WHERE ar.status = 'pending'
    AND ar.posted_message_id IS NOT NULL
    AND m.member_id = p_member_id
    AND m.member_id::text = ar.member_id;
END;
$$;

REVOKE ALL ON FUNCTION public.mark_approval_dirty_for_member(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.mark_approval_dirty_for_member(bigint) TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.mark_approval_dirty_for_media(p_media_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.approval_requests AS ar
  SET embed_dirty = true
  FROM public.media AS m
  WHERE m.id = p_media_id
    AND ar.status = 'pending'
    AND ar.posted_message_id IS NOT NULL
    AND m.member_id::text = ar.member_id;
END;
$$;

REVOKE ALL ON FUNCTION public.mark_approval_dirty_for_media(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.mark_approval_dirty_for_media(uuid) TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.mark_approval_dirty_for_asset(p_asset_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.approval_requests AS ar
  SET embed_dirty = true
  FROM public.assets AS a
  WHERE a.id = p_asset_id
    AND ar.status = 'pending'
    AND ar.posted_message_id IS NOT NULL
    AND a.member_id::text = ar.member_id;
END;
$$;

REVOKE ALL ON FUNCTION public.mark_approval_dirty_for_asset(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.mark_approval_dirty_for_asset(uuid) TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.mark_member_approval_dirty_on_bio_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public.mark_approval_dirty_for_member(NEW.member_id);
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_media_approval_dirty_on_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    PERFORM public.mark_approval_dirty_for_member(OLD.member_id);
    RETURN OLD;
  END IF;

  PERFORM public.mark_approval_dirty_for_media(NEW.id);
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_asset_approval_dirty_on_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public.mark_approval_dirty_for_asset(NEW.id);
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.set_approval_request_embed_dirty()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  NEW.embed_dirty = true;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_members_bio_mark_approval_dirty ON public.members;
CREATE TRIGGER trg_members_bio_mark_approval_dirty
  AFTER UPDATE ON public.members
  FOR EACH ROW
  WHEN (OLD.bio IS DISTINCT FROM NEW.bio)
  EXECUTE FUNCTION public.mark_member_approval_dirty_on_bio_update();

DROP TRIGGER IF EXISTS trg_media_update_mark_approval_dirty ON public.media;
CREATE TRIGGER trg_media_update_mark_approval_dirty
  AFTER UPDATE ON public.media
  FOR EACH ROW
  WHEN (
    (OLD.title, OLD.description, OLD.url, OLD.cloudflare_thumbnail_url)
      IS DISTINCT FROM
    (NEW.title, NEW.description, NEW.url, NEW.cloudflare_thumbnail_url)
  )
  EXECUTE FUNCTION public.mark_media_approval_dirty_on_change();

DROP TRIGGER IF EXISTS trg_media_insert_hidden_mark_approval_dirty ON public.media;
CREATE TRIGGER trg_media_insert_hidden_mark_approval_dirty
  AFTER INSERT ON public.media
  FOR EACH ROW
  WHEN (NEW.admin_status = 'Hidden')
  EXECUTE FUNCTION public.mark_media_approval_dirty_on_change();

DROP TRIGGER IF EXISTS trg_media_delete_hidden_mark_approval_dirty ON public.media;
CREATE TRIGGER trg_media_delete_hidden_mark_approval_dirty
  AFTER DELETE ON public.media
  FOR EACH ROW
  WHEN (OLD.admin_status = 'Hidden')
  EXECUTE FUNCTION public.mark_media_approval_dirty_on_change();

DROP TRIGGER IF EXISTS trg_assets_update_mark_approval_dirty ON public.assets;
CREATE TRIGGER trg_assets_update_mark_approval_dirty
  AFTER UPDATE ON public.assets
  FOR EACH ROW
  WHEN (
    (OLD.name, OLD.description, OLD.links, OLD.primary_media_id)
      IS DISTINCT FROM
    (NEW.name, NEW.description, NEW.links, NEW.primary_media_id)
  )
  EXECUTE FUNCTION public.mark_asset_approval_dirty_on_change();

DROP TRIGGER IF EXISTS trg_approval_requests_set_embed_dirty ON public.approval_requests;
CREATE TRIGGER trg_approval_requests_set_embed_dirty
  BEFORE UPDATE ON public.approval_requests
  FOR EACH ROW
  WHEN (
    (OLD.bio_snapshot, OLD.attached_media_id, OLD.attached_resource_id)
      IS DISTINCT FROM
    (NEW.bio_snapshot, NEW.attached_media_id, NEW.attached_resource_id)
  )
  EXECUTE FUNCTION public.set_approval_request_embed_dirty();

DROP POLICY IF EXISTS approval_requests_update_self_pending ON public.approval_requests;
CREATE POLICY approval_requests_update_self_pending
  ON public.approval_requests
  FOR UPDATE
  TO authenticated
  USING (
    status = 'pending'
    AND member_id = (
      SELECT p.discord_id::text
      FROM public.profiles AS p
      WHERE p.id = (SELECT auth.uid())
    )
  )
  WITH CHECK (
    status = 'pending'
    AND member_id = (
      SELECT p.discord_id::text
      FROM public.profiles AS p
      WHERE p.id = (SELECT auth.uid())
    )
    AND (
      attached_media_id IS NULL
      OR EXISTS (
        SELECT 1
        FROM public.media AS m
        WHERE m.id = attached_media_id
          AND m.member_id::text = approval_requests.member_id
      )
    )
    AND (
      attached_resource_id IS NULL
      OR EXISTS (
        SELECT 1
        FROM public.assets AS a
        WHERE a.id = attached_resource_id
          AND a.member_id::text = approval_requests.member_id
      )
    )
  );
