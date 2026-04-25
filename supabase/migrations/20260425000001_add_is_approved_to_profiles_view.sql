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
    m.is_speaker AS is_approved
FROM public.members m
WHERE m.auth_user_id IS NOT NULL;

GRANT SELECT ON public.profiles TO anon, authenticated;
