-- Tighten UPDATE RLS on public.assets so only admins can set
-- admin_status='Featured'.
--
-- What: Replaces the UPDATE policy created in
--   supabase/migrations/20260424000003_asset_writes_rls.sql (assets_update)
-- with a version whose WITH CHECK additionally rejects a non-admin
-- setting admin_status to anything other than NULL or 'Listed'.
--
-- Why: The current assets_update policy lets any row owner update
-- every column, including admin_status. Non-admin owners could POST
-- /rest/v1/assets?id=eq.<mine> {"admin_status":"Featured"} and
-- self-promote into the curated grids. The INSERT path already
-- blocks this (see 20260424000007_lock_down_insert_rls.sql); the
-- UPDATE path was the remaining gap.
--
-- Contract: public.is_admin() (SECURITY DEFINER, defaults to
-- auth.uid() when called with no arg) is the single admin check.
-- Its backing store is being refactored in parallel but the
-- function signature is stable.
--
-- Idempotency: DROP POLICY IF EXISTS precedes CREATE POLICY.

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
    (
      member_id IN (
        SELECT owned.member_id
        FROM public.member_owned((SELECT auth.uid())) AS owned
      )
      OR (SELECT public.is_admin((SELECT auth.uid())))
    )
    AND (
      admin_status IS NULL
      OR admin_status = 'Listed'
      OR (SELECT public.is_admin((SELECT auth.uid())))
    )
  );
