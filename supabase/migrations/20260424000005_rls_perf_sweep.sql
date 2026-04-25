-- RLS performance sweep for asset-adjacent tables.
--
-- Browser queries against /assets were hitting 57014 statement timeouts.
-- 20260424000004 fixed assets_select and assets_update by wrapping
-- auth.uid(), public.is_admin(...) and public.member_owned(...) in
-- (SELECT ...) so Postgres evaluates them once per statement as an
-- InitPlan subquery instead of once per row. This migration extends the
-- same sweep to the rest of the tables touched by an /assets page load.
--
-- Changes:
--   * asset_media: drops the legacy "Users can view their own
--     asset_media" SELECT policy (unwrapped auth.uid(), OR TRUE making
--     it effectively public — see NOTE below) and replaces it with a
--     scoped public-read policy: rows whose parent asset is published
--     (and not deleted), plus the owner's rows, plus admins. Also
--     rewrites asset_media_insert / asset_media_update / asset_media_delete
--     from 20260424000003 to wrap auth.uid() and is_admin().
--   * asset_models: leaves "Public read asset_models" alone (it is
--     USING (true) so no per-row function calls). Rewrites
--     asset_models_insert / asset_models_update / asset_models_delete
--     from 20260424000003 to wrap auth.uid() and is_admin().
--   * media: rewrites "Users can view their own media" and "Users can
--     update their own media" and "Users can delete their own media"
--     to wrap auth.uid(). Semantics preserved exactly, including the
--     pre-existing OR TRUE on SELECT (see NOTE below).
--   * asset_comments / asset_comment_media: already fine — their only
--     policies are SELECT USING (is_deleted = FALSE) with no auth
--     function calls. Left untouched.
--   * assets_select / assets_update: already fixed in 20260424000004.
--     Left untouched.
--
-- NOTE (flagged, not fixed here): the legacy SELECT policies on media
-- and on asset_media both contain OR TRUE, which makes them effectively
-- fully public to anon + authenticated. That pre-dates this migration.
-- For asset_media we are tightening the scope to "published parent asset
-- OR owner OR admin" because the caller asked for that predicate. For
-- media we preserve the OR TRUE semantics exactly — semantics change
-- there belongs in a separate migration with its own test matrix.
--
-- Rollback: `DROP POLICY IF EXISTS <name> ON public.<table>;` for each
-- policy re-created below. Do NOT attempt to restore the previous
-- unwrapped versions — they were causing the outage this migration
-- fixes. If rollback is required, the correct action is to author a
-- new forward migration with the desired semantics.
--
-- Idempotency: every CREATE POLICY is preceded by DROP POLICY IF EXISTS.

--------------------------------------------------------------------
-- asset_media
--------------------------------------------------------------------

-- Drop the legacy SELECT policy (unwrapped auth.uid() + OR TRUE).
DROP POLICY IF EXISTS "Users can view their own asset_media" ON public.asset_media;
DROP POLICY IF EXISTS asset_media_select ON public.asset_media;

CREATE POLICY asset_media_select
  ON public.asset_media
  FOR SELECT
  TO anon, authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      WHERE a.id = public.asset_media.asset_id
        AND a.status = 'published'
        AND a.is_hidden = false
    )
    OR asset_id IN (
      SELECT a.id
      FROM public.assets AS a
      WHERE a.member_id IN (
        SELECT owned.member_id
        FROM public.member_owned((SELECT auth.uid())) AS owned
      )
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

DROP POLICY IF EXISTS asset_media_insert ON public.asset_media;
CREATE POLICY asset_media_insert
  ON public.asset_media
  FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_media.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

DROP POLICY IF EXISTS asset_media_update ON public.asset_media;
CREATE POLICY asset_media_update
  ON public.asset_media
  FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_media.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_media.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

DROP POLICY IF EXISTS asset_media_delete ON public.asset_media;
CREATE POLICY asset_media_delete
  ON public.asset_media
  FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_media.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

--------------------------------------------------------------------
-- asset_models
--
-- "Public read asset_models" is USING (true) and does not call
-- auth.uid(), is_admin, or member_owned, so it needs no rewrite.
-- Only the write policies from 20260424000003 had unwrapped calls.
--------------------------------------------------------------------

DROP POLICY IF EXISTS asset_models_insert ON public.asset_models;
CREATE POLICY asset_models_insert
  ON public.asset_models
  FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_models.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

DROP POLICY IF EXISTS asset_models_update ON public.asset_models;
CREATE POLICY asset_models_update
  ON public.asset_models
  FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_models.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_models.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

DROP POLICY IF EXISTS asset_models_delete ON public.asset_models;
CREATE POLICY asset_models_delete
  ON public.asset_models
  FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_models.asset_id
        AND m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );

--------------------------------------------------------------------
-- media
--
-- Preserve existing semantics (note the legacy OR TRUE on SELECT).
-- Only change: wrap auth.uid() in (SELECT ...) so it runs once.
--------------------------------------------------------------------

DROP POLICY IF EXISTS "Users can view their own media" ON public.media;
CREATE POLICY "Users can view their own media"
  ON public.media
  FOR SELECT
  USING (
    member_id IN (
      SELECT m.member_id
      FROM public.members AS m
      WHERE m.auth_user_id = (SELECT auth.uid())
    )
    OR TRUE
  );

DROP POLICY IF EXISTS "Users can update their own media" ON public.media;
CREATE POLICY "Users can update their own media"
  ON public.media
  FOR UPDATE
  USING (
    member_id IN (
      SELECT m.member_id
      FROM public.members AS m
      WHERE m.auth_user_id = (SELECT auth.uid())
    )
  );

DROP POLICY IF EXISTS "Users can delete their own media" ON public.media;
CREATE POLICY "Users can delete their own media"
  ON public.media
  FOR DELETE
  USING (
    member_id IN (
      SELECT m.member_id
      FROM public.members AS m
      WHERE m.auth_user_id = (SELECT auth.uid())
    )
  );
