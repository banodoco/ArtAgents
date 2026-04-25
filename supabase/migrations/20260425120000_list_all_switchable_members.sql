-- Show every member in the switcher, even those who haven't yet linked a
-- Supabase auth user via Discord OAuth. The UI greys those out (impersonation
-- still requires a real auth.users row) but they appear in search so admins
-- can see who exists in the DB without first asking them to log in.
DROP FUNCTION IF EXISTS public.list_switchable_members();

CREATE OR REPLACE FUNCTION public.list_switchable_members()
RETURNS JSONB
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    result JSONB;
BEGIN
    IF NOT public.is_admin(auth.uid()) THEN
        RAISE EXCEPTION 'admin only' USING ERRCODE = '42501';
    END IF;

    SELECT COALESCE(jsonb_agg(row), '[]'::jsonb)
    INTO result
    FROM (
        SELECT
            m.auth_user_id AS id,
            m.member_id::text AS member_id,
            m.username AS discord_username,
            COALESCE(m.global_name, m.username) AS display_name,
            COALESCE(m.stored_avatar_url, m.avatar_url) AS avatar_url,
            (m.auth_user_id IS NOT NULL) AS has_auth,
            CASE WHEN m.auth_user_id IS NOT NULL
                 THEN public.is_admin(m.auth_user_id)
                 ELSE false
            END AS is_admin
        FROM public.members m
        ORDER BY COALESCE(m.global_name, m.username) NULLS LAST
    ) AS row;

    RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.list_switchable_members() TO authenticated;
