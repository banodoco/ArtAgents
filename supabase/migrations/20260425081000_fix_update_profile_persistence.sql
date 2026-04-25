-- Harden profile persistence for Discord OAuth users.
--
-- Some auth users can have the Discord id only in auth.identities rather than
-- auth.users.raw_user_meta_data. Keep members.auth_user_id populated from both
-- sources so update_profile writes the same row the profiles view reads.

CREATE OR REPLACE FUNCTION public.resolve_discord_member_id(
    p_auth_user_id UUID,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS BIGINT
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_discord_id_text TEXT;
BEGIN
    SELECT candidate
    INTO v_discord_id_text
    FROM (
        VALUES
            (p_metadata->>'sub'),
            (p_metadata->>'id'),
            (p_metadata->>'user_id'),
            (p_metadata->>'provider_id')
    ) AS candidates(candidate)
    WHERE candidate ~ '^[0-9]+$'
    LIMIT 1;

    IF v_discord_id_text IS NULL THEN
        SELECT candidate
        INTO v_discord_id_text
        FROM auth.identities AS i
        CROSS JOIN LATERAL (
            VALUES
                (i.provider_id),
                (i.identity_data->>'sub'),
                (i.identity_data->>'id'),
                (i.identity_data->>'user_id'),
                (i.identity_data->>'provider_id')
        ) AS candidates(candidate)
        WHERE i.user_id = p_auth_user_id
          AND i.provider = 'discord'
          AND candidate ~ '^[0-9]+$'
        LIMIT 1;
    END IF;

    IF v_discord_id_text IS NULL THEN
        RETURN NULL;
    END IF;

    RETURN v_discord_id_text::BIGINT;
END;
$$;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    discord_data JSONB;
    discord_id_text TEXT;
    discord_id_bigint BIGINT;
    username_value TEXT;
    display_name_value TEXT;
    avatar_url_value TEXT;
    discriminator_value TEXT;
BEGIN
    discord_data := COALESCE(NEW.raw_user_meta_data, '{}'::jsonb);
    discord_id_bigint := public.resolve_discord_member_id(NEW.id, discord_data);

    IF discord_id_bigint IS NULL THEN
        RETURN NEW;
    END IF;

    discord_id_text := discord_id_bigint::TEXT;

    username_value := COALESCE(
        NULLIF(discord_data->>'username', ''),
        NULLIF(discord_data->>'preferred_username', ''),
        NULLIF(discord_data->>'full_name', ''),
        NULLIF(discord_data->>'name', ''),
        'discord-user-' || discord_id_text
    );

    display_name_value := COALESCE(
        NULLIF(discord_data->'custom_claims'->>'global_name', ''),
        NULLIF(discord_data->>'global_name', ''),
        NULLIF(discord_data->>'full_name', ''),
        NULLIF(discord_data->>'name', ''),
        NULLIF(discord_data->>'preferred_username', ''),
        NULLIF(discord_data->>'username', ''),
        username_value
    );

    avatar_url_value := COALESCE(
        NULLIF(discord_data->>'avatar_url', ''),
        NULLIF(discord_data->>'picture', ''),
        CASE
            WHEN NULLIF(discord_data->>'avatar', '') IS NOT NULL
            THEN 'https://cdn.discordapp.com/avatars/' || discord_id_text || '/' || (discord_data->>'avatar') || '.png'
            ELSE NULL
        END
    );

    discriminator_value := NULLIF(discord_data->>'discriminator', '');

    INSERT INTO public.members (
        member_id,
        username,
        global_name,
        avatar_url,
        discriminator,
        discord_created_at,
        banodoco_owner,
        auth_user_id
    )
    VALUES (
        discord_id_bigint,
        username_value,
        display_name_value,
        avatar_url_value,
        discriminator_value,
        public.extract_discord_created_at(discord_id_text),
        public.is_banodoco_owner(discord_id_bigint),
        NEW.id
    )
    ON CONFLICT (member_id) DO UPDATE
    SET
        username = COALESCE(EXCLUDED.username, public.members.username),
        global_name = COALESCE(EXCLUDED.global_name, public.members.global_name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.members.avatar_url),
        discriminator = COALESCE(EXCLUDED.discriminator, public.members.discriminator),
        discord_created_at = COALESCE(public.members.discord_created_at, EXCLUDED.discord_created_at),
        banodoco_owner = public.is_banodoco_owner(public.members.member_id),
        auth_user_id = COALESCE(public.members.auth_user_id, EXCLUDED.auth_user_id),
        updated_at = NOW();

    RETURN NEW;
EXCEPTION
    WHEN unique_violation THEN
        RETURN NEW;
    WHEN foreign_key_violation THEN
        RAISE WARNING 'handle_new_user foreign key failure for user %: %', NEW.id, SQLERRM;
        RETURN NEW;
    WHEN OTHERS THEN
        RAISE WARNING 'handle_new_user failed for user % (%): %', NEW.id, SQLSTATE, SQLERRM;
        RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

WITH auth_discord_members AS (
    SELECT
        u.id AS auth_user_id,
        public.resolve_discord_member_id(u.id, u.raw_user_meta_data) AS member_id
    FROM auth.users AS u
)
UPDATE public.members AS m
SET
    auth_user_id = auth_discord_members.auth_user_id,
    updated_at = NOW()
FROM auth_discord_members
WHERE auth_discord_members.member_id = m.member_id
  AND auth_discord_members.member_id IS NOT NULL
  AND (m.auth_user_id IS NULL OR m.auth_user_id = auth_discord_members.auth_user_id)
  AND NOT EXISTS (
      SELECT 1
      FROM public.members AS linked
      WHERE linked.auth_user_id = auth_discord_members.auth_user_id
        AND linked.member_id <> m.member_id
  );

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
    v_rows_updated INTEGER;
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

    GET DIAGNOSTICS v_rows_updated = ROW_COUNT;
    IF v_rows_updated = 0 THEN
        RAISE EXCEPTION 'No linked member profile';
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_profile(JSONB) TO authenticated;
