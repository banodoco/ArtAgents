ALTER TABLE public.members
    ADD COLUMN IF NOT EXISTS profile_links TEXT[] NOT NULL DEFAULT '{}'::TEXT[];

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
    m.updated_at,
    m.is_speaker AS is_approved,
    m.profile_links
FROM public.members m
WHERE m.auth_user_id IS NOT NULL;

GRANT SELECT ON public.profiles TO anon, authenticated;

CREATE OR REPLACE FUNCTION public.update_profile(p_profile JSONB DEFAULT '{}'::jsonb)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_member_id BIGINT;
BEGIN
    SELECT member_id
    INTO v_member_id
    FROM public.members
    WHERE auth_user_id = auth.uid();

    IF v_member_id IS NULL THEN
        RAISE EXCEPTION 'No linked member profile';
    END IF;

    UPDATE public.members AS m
    SET
        bio = CASE
            WHEN p_profile ? 'bio' THEN NULLIF(BTRIM(p_profile->>'bio'), '')
            ELSE m.bio
        END,
        profile_links = CASE
            WHEN p_profile ? 'profile_links' THEN COALESCE(
                ARRAY(
                    SELECT link
                    FROM jsonb_array_elements_text(
                        CASE
                            WHEN jsonb_typeof(p_profile->'profile_links') = 'array'
                                THEN p_profile->'profile_links'
                            ELSE '[]'::jsonb
                        END
                    ) AS link
                ),
                '{}'::TEXT[]
            )
            ELSE m.profile_links
        END,
        real_name = CASE
            WHEN p_profile ? 'real_name' THEN NULLIF(BTRIM(p_profile->>'real_name'), '')
            ELSE m.real_name
        END,
        website_url = CASE
            WHEN p_profile ? 'website_url' THEN NULLIF(BTRIM(p_profile->>'website_url'), '')
            ELSE m.website_url
        END,
        instagram_url = CASE
            WHEN p_profile ? 'instagram_url' THEN NULLIF(BTRIM(p_profile->>'instagram_url'), '')
            ELSE m.instagram_url
        END,
        twitter_url = CASE
            WHEN p_profile ? 'twitter_url' THEN NULLIF(BTRIM(p_profile->>'twitter_url'), '')
            ELSE m.twitter_url
        END,
        stored_avatar_url = CASE
            WHEN p_profile ? 'avatar_url' THEN NULLIF(BTRIM(p_profile->>'avatar_url'), '')
            ELSE m.stored_avatar_url
        END,
        updated_at = NOW()
    WHERE m.member_id = v_member_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_profile(JSONB) TO authenticated;
