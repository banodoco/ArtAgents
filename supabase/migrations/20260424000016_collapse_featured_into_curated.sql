-- Collapse the redundant "Featured" signal on public.assets into "Curated".
--
-- History: the Forge shipped with two overlapping highlights — admin_status
-- could be 'Featured', and a parallel featured_in_forge boolean guarded a
-- separate lane. Both channels ended up representing the same editorial act
-- ("surface this resource") with zero semantic distinction, so the UI, hooks
-- and RLS all had to branch on two shapes. This migration flattens the
-- domain: 'Featured' rows become 'Curated', the boolean is dropped, and a
-- CHECK constrains admin_status to NULL / 'Listed' / 'Curated' going forward.

BEGIN;

-- 1. Rewrite the single existing 'Featured' row to 'Curated'. Assert exactly
--    one row moved — a pre-check snapshot (captured 2026-04-24) showed one
--    'Featured' entry, so any other count means the data drifted and we
--    should abort rather than silently stretch the consolidation.
DO $$
DECLARE
  moved_count integer;
BEGIN
  UPDATE public.assets
     SET admin_status = 'Curated'
   WHERE admin_status = 'Featured';
  GET DIAGNOSTICS moved_count = ROW_COUNT;
  IF moved_count <> 1 THEN
    RAISE EXCEPTION
      'collapse_featured_into_curated: expected 1 Featured row, moved %',
      moved_count;
  END IF;
END
$$;

-- 2. Drop the legacy featured_in_forge boolean. The pre-migration audit (see
--    task notes) confirmed no function, view, trigger, or policy references
--    it; the two indexes that filter on the column (assets_public_forge_idx
--    and idx_assets_featured_in_forge) are cascaded away by DROP COLUMN.
ALTER TABLE public.assets DROP COLUMN IF EXISTS featured_in_forge;

-- 3. Pin the domain. NULL stays permitted because legacy rows and the
--    Discord importer path both leave admin_status unset; only the two
--    curator-facing values join it.
ALTER TABLE public.assets
  ADD CONSTRAINT assets_admin_status_check
  CHECK (admin_status IS NULL OR admin_status IN ('Listed', 'Curated'));

-- 4. Re-issue the INSERT and UPDATE RLS policies so the allowed-values
--    clause reads "only admins set non-Listed" instead of the older
--    "admin_status IS NULL OR admin_status = 'Listed' OR is_admin(...)"
--    shape — semantically identical, but explicit about what the CHECK
--    constraint now permits. The USING clause and the source='manual'
--    enforcement on INSERT are preserved verbatim from 000007 / 000014.

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

COMMIT;
