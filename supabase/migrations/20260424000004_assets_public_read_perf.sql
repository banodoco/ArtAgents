-- Fix slow public reads on assets after the status/is_hidden columns
-- and new RLS landed in 20260424000003. Three problems addressed:
--
--   1. No index supports the main public-read filter combination
--      (is_hidden = false AND status = 'published') with a created_at sort.
--      Add a partial index that matches exactly the public read path.
--
--   2. The assets_select RLS policy calls member_owned() and is_admin()
--      per row. Wrapping those calls in (SELECT ...) turns them into
--      InitPlan subqueries that Postgres evaluates once per statement.
--
--   3. media_source_check allowed only ('art', 'post'), which rejects the
--      'resource' source written by uploadResourceMedia (and would block
--      future 'discord-comment' sources too). Widen it.

DO $$
DECLARE
    v_constraint_def TEXT;
BEGIN
    SELECT pg_get_constraintdef(con.oid)
    INTO v_constraint_def
    FROM pg_constraint AS con
    JOIN pg_class AS rel ON rel.oid = con.conrelid
    JOIN pg_namespace AS nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'public'
      AND rel.relname = 'media'
      AND con.conname = 'media_source_check';

    IF v_constraint_def IS NOT NULL THEN
        ALTER TABLE public.media DROP CONSTRAINT media_source_check;
    END IF;

    ALTER TABLE public.media
        ADD CONSTRAINT media_source_check
        CHECK (source IN ('art', 'post', 'resource', 'discord-comment'));
END;
$$;

CREATE INDEX IF NOT EXISTS assets_public_read_idx
    ON public.assets (created_at DESC)
    WHERE is_hidden = false AND status = 'published';

CREATE INDEX IF NOT EXISTS assets_public_forge_idx
    ON public.assets (created_at DESC)
    WHERE is_hidden = false AND status = 'published' AND featured_in_forge = true;

CREATE INDEX IF NOT EXISTS assets_public_admin_status_idx
    ON public.assets (admin_status, created_at DESC)
    WHERE is_hidden = false AND status = 'published';

DROP POLICY IF EXISTS assets_select ON public.assets;
CREATE POLICY assets_select
  ON public.assets
  FOR SELECT
  TO anon, authenticated
  USING (
    status = 'published'
    OR member_id IN (
        SELECT owned.member_id
        FROM public.member_owned((SELECT auth.uid())) AS owned
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

DROP POLICY IF EXISTS assets_update ON public.assets;
CREATE POLICY assets_update
  ON public.assets
  FOR UPDATE
  TO authenticated
  USING (
    member_id IN (
        SELECT owned.member_id
        FROM public.member_owned((SELECT auth.uid())) AS owned
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  )
  WITH CHECK (
    member_id IN (
        SELECT owned.member_id
        FROM public.member_owned((SELECT auth.uid())) AS owned
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );
