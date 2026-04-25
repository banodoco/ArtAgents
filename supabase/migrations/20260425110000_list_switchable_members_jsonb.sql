-- Switch list_switchable_members to return jsonb so PostgREST doesn't apply
-- its default 1000-row cap. The previous TABLE-returning version was getting
-- truncated for projects with many auth-linked members.
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
            m.username AS discord_username,
            COALESCE(m.global_name, m.username) AS display_name,
            COALESCE(m.stored_avatar_url, m.avatar_url) AS avatar_url,
            public.is_admin(m.auth_user_id) AS is_admin
        FROM public.members m
        WHERE m.auth_user_id IS NOT NULL
        ORDER BY COALESCE(m.global_name, m.username) NULLS LAST
    ) AS row;

    RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.list_switchable_members() TO authenticated;
