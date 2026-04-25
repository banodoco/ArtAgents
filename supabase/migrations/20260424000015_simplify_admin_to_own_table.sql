-- Simplify the admin model.
-- Moves admin flagging off `public.members.is_admin` (entangled with Discord
-- membership) onto a dedicated `public.admins` table keyed on auth.users.id.
-- Rewrites `public.is_admin(uuid)`, `add_admin`, `remove_admin`, and the
-- `profiles` view so they read the new table, and drops the now-stale
-- `is_current_user_admin()` helper and the denormalized `members.is_admin`
-- column. `set_primary_media` is updated to use `public.is_admin()` instead
-- of the orphaned `user_roles` lookup it previously hardcoded.

BEGIN;

-- 1. New canonical table. One row per admin, keyed on the auth user id.
CREATE TABLE public.admins (
    user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

ALTER TABLE public.admins ENABLE ROW LEVEL SECURITY;

-- Admin status is not secret; everything else depends on reading it cheaply.
CREATE POLICY "admins_public_read"
    ON public.admins
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Writes go through admin-only policies. Combined with the SECURITY DEFINER
-- add_admin/remove_admin helpers below, this is the chicken-and-egg guard:
-- the very first admin is seeded in step 2; subsequent promotions pass
-- through this RLS.
CREATE POLICY "admins_admin_insert"
    ON public.admins
    FOR INSERT
    TO authenticated
    WITH CHECK (public.is_admin());

CREATE POLICY "admins_admin_update"
    ON public.admins
    FOR UPDATE
    TO authenticated
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

CREATE POLICY "admins_admin_delete"
    ON public.admins
    FOR DELETE
    TO authenticated
    USING (public.is_admin());

GRANT SELECT ON public.admins TO anon, authenticated;
GRANT INSERT, UPDATE, DELETE ON public.admins TO authenticated;

-- 2. Seed from the existing denormalized column. Row count asserted below.
INSERT INTO public.admins (user_id)
SELECT auth_user_id
FROM public.members
WHERE is_admin = true
  AND auth_user_id IS NOT NULL;

DO $mig$
DECLARE
    v_seeded BIGINT;
    v_source BIGINT;
BEGIN
    SELECT COUNT(*) INTO v_seeded FROM public.admins;
    SELECT COUNT(*) INTO v_source
    FROM public.members
    WHERE is_admin = true AND auth_user_id IS NOT NULL;

    IF v_seeded <> v_source THEN
        RAISE EXCEPTION 'admins seed mismatch: seeded=% source=%', v_seeded, v_source;
    END IF;
    IF v_seeded < 1 THEN
        RAISE EXCEPTION 'admins seed produced 0 rows; bootstrap would be impossible';
    END IF;
END
$mig$;

-- 3. Rewrite is_admin to read from the new table. Signature preserved so
--    every existing caller (RLS policies, add_admin/remove_admin, frontend
--    rpc('is_admin', ...)) keeps working. SECURITY DEFINER + search_path=''
--    means we must schema-qualify everything, including auth.uid().
CREATE OR REPLACE FUNCTION public.is_admin(check_user_id uuid DEFAULT NULL::uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $fn$
    SELECT EXISTS (
        SELECT 1
        FROM public.admins
        WHERE user_id = COALESCE(check_user_id, (SELECT auth.uid()))
    );
$fn$;

GRANT EXECUTE ON FUNCTION public.is_admin(uuid) TO anon, authenticated, service_role;

-- 4. Rewrite add_admin / remove_admin so they operate on public.admins.
--    SECURITY DEFINER so the function can bypass RLS when writing, but
--    gated by public.is_admin() as the first statement so only existing
--    admins can promote others. The previous definitions targeted a
--    non-existent `public.admin_users` table, so these are effectively new.
CREATE OR REPLACE FUNCTION public.add_admin(target_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
BEGIN
    IF NOT public.is_admin() THEN
        RAISE EXCEPTION 'not authorized';
    END IF;

    INSERT INTO public.admins (user_id, created_by)
    VALUES (target_user_id, (SELECT auth.uid()))
    ON CONFLICT (user_id) DO NOTHING;
END;
$fn$;

CREATE OR REPLACE FUNCTION public.remove_admin(target_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
BEGIN
    IF NOT public.is_admin() THEN
        RAISE EXCEPTION 'not authorized';
    END IF;

    DELETE FROM public.admins
    WHERE user_id = target_user_id;
END;
$fn$;

GRANT EXECUTE ON FUNCTION public.add_admin(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.remove_admin(uuid) TO authenticated;

-- 5. Drop is_current_user_admin(). It has zero RLS/function/view callers in
--    the database (audited) and its body referenced an unrelated user_roles
--    table that was never wired up to the real admin flag.
DROP FUNCTION IF EXISTS public.is_current_user_admin();

-- 6. Fix set_primary_media: it previously consulted public.user_roles for
--    an admin check, which has never been synced with the real admin model.
--    Route it through public.is_admin() like every other admin-gated
--    function.
CREATE OR REPLACE FUNCTION public.set_primary_media(p_asset_id uuid, p_media_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
BEGIN
    IF auth.role() <> 'authenticated' THEN
        RAISE EXCEPTION 'Not authenticated';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.assets a
        WHERE a.id = p_asset_id
          AND (a.user_id = (SELECT auth.uid()) OR public.is_admin())
    ) THEN
        RAISE EXCEPTION 'Permission denied';
    END IF;

    BEGIN
        UPDATE public.asset_media SET is_primary = false WHERE asset_id = p_asset_id;
        UPDATE public.asset_media SET is_primary = true WHERE asset_id = p_asset_id AND media_id = p_media_id;
        UPDATE public.assets SET primary_media_id = p_media_id WHERE id = p_asset_id;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to set primary media: %', SQLERRM;
    END;
END;
$fn$;

-- 7. Rewrite the profiles view so its `is_admin` column is derived from
--    public.admins via the helper instead of reading members.is_admin
--    directly. This is the only DB object (verified via
--    information_schema.view_column_usage) that reads the column. RLS
--    policies on retrospective_feedback(_groups) select profiles.is_admin;
--    they keep working transparently.
CREATE OR REPLACE VIEW public.profiles AS
SELECT m.auth_user_id AS id,
    m.member_id::text AS discord_id,
    m.username AS discord_username,
    m.discriminator AS discord_discriminator,
    COALESCE(m.global_name, m.username) AS display_name,
    COALESCE(m.stored_avatar_url, m.avatar_url) AS avatar_url,
    NULL::text AS email,
    m.bio,
    m.real_name,
    m.website_url,
    m.instagram_url,
    m.twitter_url,
    m.discord_created_at AS discord_account_created_at,
    public.is_banodoco_owner(m.member_id) AS banodoco_owner,
    public.is_admin(m.auth_user_id) AS is_admin,
    m.created_at,
    m.updated_at
FROM public.members m
WHERE m.auth_user_id IS NOT NULL;

-- 8. Finally drop the denormalized column. Nothing should reference it now.
ALTER TABLE public.members DROP COLUMN is_admin;

COMMIT;
