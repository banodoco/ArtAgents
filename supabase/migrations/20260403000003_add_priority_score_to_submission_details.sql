DROP VIEW IF EXISTS public.public_vote_counts;
DROP VIEW IF EXISTS public.submission_details;

CREATE VIEW public.submission_details AS
SELECT
    ce.id,
    ce.competition_id,
    m_auth.auth_user_id AS user_id,
    ce.media_id,
    ce.theme,
    CASE
        WHEN med.web_friendly_serving THEN COALESCE(med.cloudflare_playback_hls_url, med.url)
        ELSE med.url
    END AS video_url,
    med.title,
    med.description,
    med.tools_used,
    med.additional_links,
    COALESCE(med.backup_thumbnail_url, med.cloudflare_thumbnail_url) AS thumbnail_url,
    med.thumbnail_placeholder,
    med.subtitle_url,
    ce.status,
    ce.admin_notes,
    ce.score,
    ce.vote_count,
    ce.winner,
    ce.admin_hidden,
    ce.submitted_at,
    ce.created_at,
    ce.updated_at,
    c.type AS competition_type,
    public.get_verified_vote_count(ce.id) AS verified_vote_count,
    public.get_verified_vote_count_with_judge_multiplier(ce.id, ce.competition_id) AS verified_weighted_vote_count,
    jsonb_build_object(
        'id', m_auth.auth_user_id,
        'discord_id', m_auth.member_id::TEXT,
        'discord_username', m_auth.username,
        'discord_discriminator', m_auth.discriminator,
        'display_name', COALESCE(m_auth.global_name, m_auth.username),
        'avatar_url', COALESCE(m_auth.stored_avatar_url, m_auth.avatar_url),
        'bio', m_auth.bio,
        'real_name', m_auth.real_name,
        'website_url', m_auth.website_url,
        'instagram_url', m_auth.instagram_url,
        'twitter_url', m_auth.twitter_url,
        'discord_account_created_at', m_auth.discord_created_at,
        'banodoco_owner', COALESCE(m_auth.banodoco_owner, FALSE)
    ) AS profile,
    CASE
        WHEN med.web_friendly_serving THEN med.cloudflare_playback_hls_url
        ELSE NULL
    END AS hls_url,
    med.url AS fallback_video_url,
    med.storage_provider,
    med.web_friendly_serving,
    COALESCE(
        (SELECT jsonb_agg(jsonb_build_object(
            'id', a.id,
            'type', a.type,
            'name', a.name,
            'description', a.description,
            'download_link', a.download_link,
            'lora_link', a.lora_link,
            'lora_base_model', a.lora_base_model
        ) ORDER BY a.created_at)
        FROM public.asset_media am
        JOIN public.assets a ON a.id = am.asset_id
        WHERE am.media_id = ce.media_id),
        '[]'::jsonb
    ) AS assets,
    eps.priority_score
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m_auth ON m_auth.member_id = ce.member_id
LEFT JOIN public.entry_priority_scores eps ON eps.entry_id = ce.id
WHERE c.type = 'prize'
  AND ce.status <> 'rejected'
  AND (NOT ce.admin_hidden OR public.is_admin());

GRANT SELECT ON public.submission_details TO anon, authenticated;

CREATE VIEW public.public_vote_counts AS
SELECT
    ce.id AS entry_id,
    ce.competition_id,
    med.title,
    ce.vote_count,
    ce.score,
    ce.winner
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
WHERE c.type = 'prize'
  AND ce.status NOT IN ('draft', 'rejected')
  AND NOT ce.admin_hidden;

GRANT SELECT ON public.public_vote_counts TO anon, authenticated;
