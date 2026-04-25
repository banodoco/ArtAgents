-- Admin-only RPC for the bottom-right user-switcher widget.
-- Required because RLS on members hides other users' rows from authenticated
-- callers, which makes the `profiles` view return an empty set even for admins.
-- SECURITY DEFINER bypasses RLS; we gate explicitly on is_admin(auth.uid()).
CREATE OR REPLACE FUNCTION public.list_switchable_members()
RETURNS TABLE (
    id UUID,
    discord_username TEXT,
    display_name TEXT,
    avatar_url TEXT,
    is_admin BOOLEAN
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT public.is_admin(auth.uid()) THEN
        RAISE EXCEPTION 'admin only' USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT
        m.auth_user_id AS id,
        m.username AS discord_username,
        COALESCE(m.global_name, m.username) AS display_name,
        COALESCE(m.stored_avatar_url, m.avatar_url) AS avatar_url,
        public.is_admin(m.auth_user_id) AS is_admin
    FROM public.members m
    WHERE m.auth_user_id IS NOT NULL
    ORDER BY COALESCE(m.global_name, m.username) NULLS LAST;
END;
$$;

GRANT EXECUTE ON FUNCTION public.list_switchable_members() TO authenticated;
