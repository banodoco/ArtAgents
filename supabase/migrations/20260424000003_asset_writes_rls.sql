CREATE OR REPLACE FUNCTION public.member_owned(check_user_id UUID DEFAULT NULL)
RETURNS TABLE(member_id BIGINT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT m.member_id
  FROM public.members AS m
  WHERE m.auth_user_id = COALESCE(check_user_id, auth.uid())
$$;

GRANT EXECUTE ON FUNCTION public.member_owned(UUID) TO anon, authenticated;

DROP POLICY IF EXISTS "Users can view their own assets" ON public.assets;
DROP POLICY IF EXISTS assets_select ON public.assets;
CREATE POLICY assets_select
  ON public.assets
  FOR SELECT
  TO anon, authenticated
  USING (
    status = 'published'
    OR member_id IN (SELECT owned.member_id FROM public.member_owned(auth.uid()) AS owned)
    OR public.is_admin(auth.uid())
  );

DROP POLICY IF EXISTS "Users can update their own assets" ON public.assets;
DROP POLICY IF EXISTS assets_update ON public.assets;
CREATE POLICY assets_update
  ON public.assets
  FOR UPDATE
  TO authenticated
  USING (
    member_id IN (SELECT owned.member_id FROM public.member_owned(auth.uid()) AS owned)
    OR public.is_admin(auth.uid())
  )
  WITH CHECK (
    member_id IN (SELECT owned.member_id FROM public.member_owned(auth.uid()) AS owned)
    OR public.is_admin(auth.uid())
  );

DROP POLICY IF EXISTS "Users can update their own asset media status" ON public.asset_media;
DROP POLICY IF EXISTS "Users can delete their own asset_media" ON public.asset_media;
DROP POLICY IF EXISTS asset_media_insert ON public.asset_media;
DROP POLICY IF EXISTS asset_media_update ON public.asset_media;
DROP POLICY IF EXISTS asset_media_delete ON public.asset_media;

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
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  );

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
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_media.asset_id
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  );

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
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  );

DROP POLICY IF EXISTS "Service write asset_models" ON public.asset_models;
DROP POLICY IF EXISTS asset_models_insert ON public.asset_models;
DROP POLICY IF EXISTS asset_models_update ON public.asset_models;
DROP POLICY IF EXISTS asset_models_delete ON public.asset_models;

CREATE POLICY "Service write asset_models"
  ON public.asset_models
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

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
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  );

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
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.assets AS a
      JOIN public.members AS m ON m.member_id = a.member_id
      WHERE a.id = public.asset_models.asset_id
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  );

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
        AND m.auth_user_id = auth.uid()
    )
    OR public.is_admin(auth.uid())
  );
