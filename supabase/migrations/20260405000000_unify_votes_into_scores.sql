-- Migrate Edition 1 binary votes into the scores table and update all
-- views/functions to query scores instead of votes.
--
-- The old votes table had binary "yes" votes (max 5 per voter).
-- Each vote becomes a score of 10 in the scores table.
-- The votes table is left untouched as a historical record.
--
-- A local JSON backup of both tables was taken before this migration:
--   backups_votes_edition1.json  (208 rows)
--   backups_scores_edition2.json (5556 rows)

-- ============================================================
-- STEP 1: Migrate Edition 1 votes → scores (score = 10)
-- ============================================================
-- Only insert votes that don't already exist in scores (idempotent).
-- The scores table has a unique constraint on (user_id, entry_id).

INSERT INTO public.scores (
    user_id,
    entry_id,
    competition_id,
    score,
    theme,
    comment,
    user_agent,
    vote_duration_ms,
    video_watch_duration_ms,
    page_duration_ms,
    created_at,
    updated_at
)
SELECT
    v.user_id,
    v.entry_id,
    v.competition_id,
    10,                          -- binary "yes" → score of 10
    ce.theme,                    -- pull theme from the entry
    NULL,                        -- no comments in old system
    v.user_agent,
    v.vote_duration_ms,
    0,                           -- not tracked in old system
    0,                           -- not tracked in old system
    v.created_at,
    v.created_at                 -- updated_at = created_at (never modified)
FROM public.votes v
JOIN public.competition_entries ce ON ce.id = v.entry_id
WHERE NOT EXISTS (
    SELECT 1 FROM public.scores s
    WHERE s.user_id = v.user_id AND s.entry_id = v.entry_id
);

-- ============================================================
-- STEP 2: Update functions to use scores instead of votes
-- ============================================================

-- 2a. get_verified_vote_count — now counts scores (all scores are "verified")
-- For Edition 1, every score came from a vote so it's inherently verified.
-- For Edition 2, there's no confidence-scoring system yet, so count all.
CREATE OR REPLACE FUNCTION public.get_verified_vote_count(p_entry_id UUID)
RETURNS BIGINT
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE v_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM public.scores s
    WHERE s.entry_id = p_entry_id;
    RETURN v_count;
END;
$$;

-- 2b. get_vote_count_with_judge_multiplier — uses scores, applies multiplier
CREATE OR REPLACE FUNCTION public.get_vote_count_with_judge_multiplier(
    p_entry_id UUID,
    p_competition_id UUID DEFAULT NULL
)
RETURNS NUMERIC
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_multiplier NUMERIC := 1;
    v_regular BIGINT := 0;
    v_judge BIGINT := 0;
BEGIN
    IF p_competition_id IS NOT NULL THEN
        SELECT COALESCE((c.settings->>'judge_multiplier')::NUMERIC, 1) INTO v_multiplier
        FROM public.competitions c WHERE c.id = p_competition_id;
    END IF;

    SELECT COUNT(*) INTO v_regular
    FROM public.scores s
    JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.entry_id = p_entry_id AND NOT COALESCE(m.banodoco_owner, FALSE);

    SELECT COUNT(*) INTO v_judge
    FROM public.scores s
    JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.entry_id = p_entry_id AND COALESCE(m.banodoco_owner, FALSE);

    RETURN v_regular + (v_judge * v_multiplier);
END;
$$;

-- 2c. get_verified_vote_count_with_judge_multiplier — same, using scores
CREATE OR REPLACE FUNCTION public.get_verified_vote_count_with_judge_multiplier(
    p_entry_id UUID,
    p_competition_id UUID DEFAULT NULL
)
RETURNS NUMERIC
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_multiplier NUMERIC := 1;
    v_regular BIGINT := 0;
    v_judge BIGINT := 0;
BEGIN
    IF p_competition_id IS NOT NULL THEN
        SELECT COALESCE((c.settings->>'judge_multiplier')::NUMERIC, 1) INTO v_multiplier
        FROM public.competitions c WHERE c.id = p_competition_id;
    END IF;

    SELECT COUNT(*) INTO v_regular
    FROM public.scores s
    JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.entry_id = p_entry_id AND NOT COALESCE(m.banodoco_owner, FALSE);

    SELECT COUNT(*) INTO v_judge
    FROM public.scores s
    JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.entry_id = p_entry_id AND COALESCE(m.banodoco_owner, FALSE);

    RETURN v_regular + (v_judge * v_multiplier);
END;
$$;

-- ============================================================
-- STEP 3: Recreate views to use scores
-- ============================================================

-- 3a. submission_details — add avg_score and score_count columns
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

-- 3b. public_vote_counts — add live score aggregation
CREATE VIEW public.public_vote_counts AS
SELECT
    ce.id AS entry_id,
    ce.competition_id,
    med.title,
    ce.vote_count,
    ce.score,
    ce.winner,
    score_agg.avg_score,
    score_agg.score_count
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN LATERAL (
    SELECT
        AVG(s.score)::NUMERIC(4,2) AS avg_score,
        COUNT(*)::INT AS score_count
    FROM public.scores s
    WHERE s.entry_id = ce.id
) score_agg ON true
WHERE c.type = 'prize'
  AND ce.status NOT IN ('draft', 'rejected')
  AND NOT ce.admin_hidden;

GRANT SELECT ON public.public_vote_counts TO anon, authenticated;

-- 3c. competition_leaderboard — recreate using scores
CREATE OR REPLACE VIEW public.competition_leaderboard AS
SELECT
    ce.id AS entry_id,
    ce.competition_id,
    med.title,
    COALESCE(m.global_name, m.username) AS creator_name,
    m.member_id AS creator_id,
    COUNT(s.id)::INT AS score_count,
    COALESCE(AVG(s.score), 0)::NUMERIC(4,2) AS avg_score,
    RANK() OVER (
        PARTITION BY ce.competition_id
        ORDER BY COALESCE(AVG(s.score), 0) DESC, COUNT(s.id) DESC
    )::INT AS rank,
    ce.winner
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
LEFT JOIN public.scores s ON s.entry_id = ce.id
WHERE c.type = 'prize'
  AND ce.status NOT IN ('draft', 'rejected')
  AND NOT ce.admin_hidden
GROUP BY ce.id, ce.competition_id, med.title, m.global_name, m.username, m.member_id, ce.winner
ORDER BY ce.competition_id, rank;

GRANT SELECT ON public.competition_leaderboard TO authenticated;
