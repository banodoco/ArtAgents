-- Lock down INSERT RLS on public.assets and public.media.
--
-- What: Replaces the legacy INSERT policies
--   * "Users can insert their own assets"   (from 20260324100000_redesign_for_elegance.sql, ~L1315)
--   * "Users can insert their own media"    (from 20260324100000_redesign_for_elegance.sql, ~L1269)
-- with tightened, perf-wrapped versions: assets_insert and media_insert.
--
-- Why:
--   1. Security (H) — the legacy assets INSERT policy has NO guard on
--      admin_status. An authenticated user hitting PostgREST directly
--      can POST /rest/v1/assets with {"admin_status":"Featured"} and
--      self-promote into the Forge / curated grids. The frontend hard-
--      codes admin_status='Listed' (see banodoco-website/src/lib/
--      resources.ts:316) but RLS is the only backstop and currently
--      there is none. This migration rejects 'Featured' and 'Curated'
--      (and any other non-Listed value) for non-admins, and pins
--      source='manual' to stop authenticated callers from forging
--      fake discord_import rows.
--   2. Consistency / perf (M) — the legacy policies call bare auth.uid()
--      inside a subquery, which Postgres evaluates once per row. The
--      20260424000004/5 sweep wrapped every other auth.uid/is_admin/
--      member_owned call in (SELECT ...) so they become a once-per-
--      statement InitPlan. The INSERT policies were missed; this
--      migration brings them in line.
--
-- Non-goals:
--   * SELECT / UPDATE / DELETE on assets and media are already handled
--     by 20260424000004 and 20260424000005. Untouched here.
--   * The Discord promoter (public.promote_discord_resources, SECURITY
--     DEFINER) bypasses RLS and is unaffected; it can continue to
--     insert rows with source='discord_import' and any admin_status.
--   * media.admin_status is not guarded here — the callsite at
--     uploadResourceMedia hardcodes 'Listed' and there is no curated
--     grid on media — but auth wrapping is applied for consistency.
--
-- Idempotency: DROP POLICY IF EXISTS precedes every CREATE POLICY.

--------------------------------------------------------------------
-- assets
--------------------------------------------------------------------

DROP POLICY IF EXISTS "Users can insert their own assets" ON public.assets;
DROP POLICY IF EXISTS assets_insert ON public.assets;

CREATE POLICY assets_insert
  ON public.assets
  FOR INSERT
  TO authenticated
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
    AND (
      source = 'manual'
      OR (SELECT public.is_admin((SELECT auth.uid())))
    )
  );

--------------------------------------------------------------------
-- media
--
-- Preserve the legacy semantics (owner-only INSERT) and just wrap
-- auth.uid() so the subquery runs once per statement. Admin bypass
-- is added for symmetry with the assets path — mirrors the pattern
-- used in 20260424000005 for the other media policies.
--------------------------------------------------------------------

DROP POLICY IF EXISTS "Users can insert their own media" ON public.media;
DROP POLICY IF EXISTS media_insert ON public.media;

CREATE POLICY media_insert
  ON public.media
  FOR INSERT
  TO authenticated
  WITH CHECK (
    member_id IN (
      SELECT m.member_id
      FROM public.members AS m
      WHERE m.auth_user_id = (SELECT auth.uid())
    )
    OR (SELECT public.is_admin((SELECT auth.uid())))
  );
