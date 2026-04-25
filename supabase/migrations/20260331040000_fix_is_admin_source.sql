-- Fix is_admin() to check members.is_admin instead of admin_users table.
-- This eliminates the dual-source-of-truth problem where members.is_admin
-- (used by the client) and admin_users (used by the DB function) could
-- get out of sync.

CREATE OR REPLACE FUNCTION public.is_admin(check_user_id UUID DEFAULT NULL)
RETURNS BOOLEAN
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF check_user_id IS NULL THEN
        check_user_id := auth.uid();
    END IF;

    RETURN EXISTS (
        SELECT 1
        FROM public.members
        WHERE auth_user_id = check_user_id
          AND is_admin = true
    );
END;
$$;
