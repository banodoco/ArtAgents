-- Simplify banodoco_owner data model.
-- Replaces the denormalized `members.banodoco_owner` boolean (maintained by a
-- duplicate trigger that recomputed membership from a hardcoded function body)
-- with a dedicated `public.banodoco_owners` table. Consolidates four lookup
-- helpers (is_banodoco_owner, ag_is_banodoco_owner, get_banodoco_owner_ids, and
-- the now-unused apply_banodoco_owner_flag trigger function) into a single
-- `public.is_banodoco_owner(bigint)` that queries the new table directly.

BEGIN;

-- 1. New table: curated contributor list.
CREATE TABLE public.banodoco_owners (
    member_id  BIGINT PRIMARY KEY REFERENCES public.members(member_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.banodoco_owners ENABLE ROW LEVEL SECURITY;

CREATE POLICY "banodoco_owners_public_read"
    ON public.banodoco_owners
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "banodoco_owners_admin_insert"
    ON public.banodoco_owners
    FOR INSERT
    TO authenticated
    WITH CHECK (public.is_admin());

CREATE POLICY "banodoco_owners_admin_update"
    ON public.banodoco_owners
    FOR UPDATE
    TO authenticated
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

CREATE POLICY "banodoco_owners_admin_delete"
    ON public.banodoco_owners
    FOR DELETE
    TO authenticated
    USING (public.is_admin());

GRANT SELECT ON public.banodoco_owners TO anon, authenticated;
GRANT INSERT, UPDATE, DELETE ON public.banodoco_owners TO authenticated;

-- 2. Seed from existing denormalized column. Row count asserted below.
INSERT INTO public.banodoco_owners (member_id)
SELECT member_id
FROM public.members
WHERE banodoco_owner = true;

-- Fail-fast sanity check: must match the pre-migration owner count of 184.
DO $mig$
DECLARE
    v_seeded  BIGINT;
    v_source  BIGINT;
BEGIN
    SELECT COUNT(*) INTO v_seeded FROM public.banodoco_owners;
    SELECT COUNT(*) INTO v_source FROM public.members WHERE banodoco_owner = true;
    IF v_seeded <> v_source THEN
        RAISE EXCEPTION 'banodoco_owners seed mismatch: seeded=% source=%', v_seeded, v_source;
    END IF;
    IF v_seeded <> 184 THEN
        RAISE EXCEPTION 'banodoco_owners expected 184 rows, got %', v_seeded;
    END IF;
END
$mig$;

-- 3. Drop the legacy lookup helpers. Must happen before recreating
--    public.is_banodoco_owner with a fresh body (plpgsql -> sql).
DROP FUNCTION IF EXISTS public.is_banodoco_owner(bigint);
DROP FUNCTION IF EXISTS public.ag_is_banodoco_owner(bigint);
DROP FUNCTION IF EXISTS public.get_banodoco_owner_ids();

-- 4. Single canonical lookup. Schema-qualified, STABLE, SECURITY INVOKER.
CREATE FUNCTION public.is_banodoco_owner(p_member_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $fn$
    SELECT EXISTS (
        SELECT 1
        FROM public.banodoco_owners
        WHERE member_id = p_member_id
    );
$fn$;

GRANT EXECUTE ON FUNCTION public.is_banodoco_owner(bigint) TO anon, authenticated, service_role;

-- 5. Rewrite the seven views that read `members.banodoco_owner` so they delegate
--    to the new helper. Column names and types are preserved so dependent views
--    (retrospective_payouts, retrospective_feedback_display) continue to work.

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
    COALESCE(m.is_admin, false) AS is_admin,
    m.created_at,
    m.updated_at
FROM public.members m
WHERE m.auth_user_id IS NOT NULL;

CREATE OR REPLACE VIEW public.submission_details AS
SELECT ce.id,
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
        CASE
            WHEN c.results_announced_at IS NOT NULL AND now() >= c.results_announced_at THEN ce.winner
            ELSE false
        END AS winner,
        CASE
            WHEN c.results_announced_at IS NOT NULL AND now() >= c.results_announced_at THEN ce.prize_tier
            ELSE NULL::text
        END AS prize_tier,
    ce.admin_hidden,
    ce.submitted_at,
    ce.created_at,
    ce.updated_at,
    c.type AS competition_type,
    public.get_verified_vote_count(ce.id) AS verified_vote_count,
    public.get_verified_vote_count_with_judge_multiplier(ce.id, ce.competition_id) AS verified_weighted_vote_count,
    jsonb_build_object(
        'id', m_auth.auth_user_id,
        'discord_id', m_auth.member_id::text,
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
        'banodoco_owner', public.is_banodoco_owner(m_auth.member_id)
    ) AS profile,
        CASE
            WHEN med.web_friendly_serving THEN med.cloudflare_playback_hls_url
            ELSE NULL::text
        END AS hls_url,
    med.url AS fallback_video_url,
    med.storage_provider,
    med.web_friendly_serving,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id', a.id,
            'type', a.type,
            'name', a.name,
            'description', a.description,
            'download_link', a.download_link,
            'lora_link', a.lora_link,
            'lora_base_model', a.lora_base_model
        ) ORDER BY a.created_at) AS jsonb_agg
        FROM public.asset_media am
        JOIN public.assets a ON a.id = am.asset_id
        WHERE am.media_id = ce.media_id
    ), '[]'::jsonb) AS assets,
    eps.priority_score
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m_auth ON m_auth.member_id = ce.member_id
LEFT JOIN public.entry_priority_scores eps ON eps.entry_id = ce.id
WHERE c.type = 'prize'::text
  AND ce.status <> 'rejected'::text
  AND (NOT ce.admin_hidden OR public.is_admin());

CREATE OR REPLACE VIEW public.entry_voter_breakdown AS
SELECT s.entry_id,
    s.competition_id,
    med.title AS entry_title,
    s.user_id,
    COALESCE(m.global_name, m.username) AS voter_name,
    public.is_banodoco_owner(m.member_id) AS is_judge,
    s.score,
    public.calculate_score_confidence(s.id) AS confidence,
    s.video_watch_duration_ms AS watch_ms,
    s.vote_duration_ms,
    s.created_at AS scored_at,
    s.created_at = min(s.created_at) OVER (PARTITION BY s.user_id, s.competition_id) AS was_first_score,
    count(*) OVER (PARTITION BY s.user_id, s.competition_id)::integer AS voter_total_scores,
    avg(s.score) OVER (PARTITION BY s.user_id, s.competition_id)::numeric(3,1) AS voter_avg,
    (s.score::numeric - avg(s.score) OVER (PARTITION BY s.user_id, s.competition_id))::numeric(3,1) AS deviation_from_voter_avg,
    (EXISTS (
        SELECT 1
        FROM public.competition_entries ce_1
        JOIN public.members m2 ON m2.member_id = ce_1.member_id
        WHERE ce_1.id = s.entry_id AND m2.auth_user_id = s.user_id
    )) AS is_self_vote
FROM public.scores s
JOIN public.competition_entries ce ON ce.id = s.entry_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.auth_user_id = s.user_id;

CREATE OR REPLACE VIEW public.voter_behavior AS
WITH voter_stats AS (
    SELECT s.user_id,
        s.competition_id,
        COALESCE(m.global_name, m.username) AS voter_name,
        public.is_banodoco_owner(m.member_id) AS is_judge,
        count(*)::integer AS entries_scored,
        avg(s.score)::numeric(3,1) AS avg_score_given,
        stddev(s.score)::numeric(3,1) AS score_spread,
        min(s.score) AS min_score,
        max(s.score) AS max_score,
        count(*) FILTER (WHERE s.score = 10)::integer AS tens_given,
        count(*) FILTER (WHERE s.score <= 3)::integer AS low_scores_given,
        avg(s.video_watch_duration_ms)::integer AS avg_watch_ms,
        min(s.video_watch_duration_ms)::integer AS min_watch_ms,
        count(*) FILTER (WHERE COALESCE(s.video_watch_duration_ms, 0::bigint) < 5000)::integer AS scores_under_5s_watch,
        avg(s.vote_duration_ms)::integer AS avg_vote_ms,
        min(s.created_at) AS first_score_at,
        max(s.created_at) AS last_score_at,
        count(*) FILTER (WHERE (EXISTS (
            SELECT 1
            FROM public.competition_entries ce
            JOIN public.members m2 ON m2.member_id = ce.member_id
            WHERE ce.id = s.entry_id AND m2.auth_user_id = s.user_id
        )))::integer AS self_votes
    FROM public.scores s
    LEFT JOIN public.members m ON m.auth_user_id = s.user_id
    GROUP BY s.user_id, s.competition_id, m.global_name, m.username, m.member_id
)
SELECT voter_stats.user_id,
    voter_stats.competition_id,
    voter_stats.voter_name,
    voter_stats.is_judge,
    voter_stats.entries_scored,
    voter_stats.avg_score_given,
    voter_stats.score_spread,
    voter_stats.min_score,
    voter_stats.max_score,
    voter_stats.tens_given,
    voter_stats.low_scores_given,
    voter_stats.avg_watch_ms,
    voter_stats.min_watch_ms,
    voter_stats.scores_under_5s_watch,
    voter_stats.avg_vote_ms,
    voter_stats.first_score_at,
    voter_stats.last_score_at,
    voter_stats.self_votes,
    voter_stats.entries_scored = 1 AS single_entry_voter,
    voter_stats.score_spread IS NULL OR voter_stats.score_spread < 0.5 AS flat_scorer,
    voter_stats.tens_given = voter_stats.entries_scored AND voter_stats.entries_scored > 1 AS all_tens,
    voter_stats.scores_under_5s_watch > (voter_stats.entries_scored / 2) AS mostly_unwatched,
    EXTRACT(epoch FROM voter_stats.last_score_at - voter_stats.first_score_at)::integer AS session_duration_seconds
FROM voter_stats;

CREATE OR REPLACE VIEW public.voter_confidence AS
SELECT s.user_id,
    s.competition_id,
    COALESCE(m.global_name, m.username) AS voter_name,
    count(*) AS scores_cast,
    avg(public.calculate_score_confidence(s.id))::numeric(5,1) AS avg_confidence,
    min(public.calculate_score_confidence(s.id)) AS min_confidence,
        CASE
            WHEN avg(public.calculate_score_confidence(s.id)) < 40::numeric THEN 0.0
            ELSE (avg(public.calculate_score_confidence(s.id)) / 100.0)::numeric(4,3)
        END AS legitimacy_weight,
    public.is_banodoco_owner(m.member_id) AS is_judge
FROM public.scores s
LEFT JOIN public.members m ON m.auth_user_id = s.user_id
GROUP BY s.user_id, s.competition_id, m.global_name, m.username, m.member_id;

CREATE OR REPLACE VIEW public.final_results_dashboard AS
WITH entry_members AS (
    SELECT ce_1.id AS entry_id,
        m_1.auth_user_id AS creator_auth_id
    FROM public.competition_entries ce_1
    LEFT JOIN public.members m_1 ON m_1.member_id = ce_1.member_id
), scored AS (
    SELECT s.id AS score_id,
        s.entry_id,
        s.competition_id,
        s.user_id,
        s.score,
        s.video_watch_duration_ms,
        s.vote_duration_ms,
        public.calculate_score_confidence(s.id) AS confidence,
        public.is_banodoco_owner(m_voter.member_id) AS voter_is_judge,
        em.creator_auth_id IS NOT NULL AND s.user_id = em.creator_auth_id AS is_self_vote,
        COALESCE((c_1.settings ->> 'judge_multiplier'::text)::numeric, 1::numeric) AS judge_multiplier
    FROM public.scores s
    LEFT JOIN public.members m_voter ON m_voter.auth_user_id = s.user_id
    LEFT JOIN entry_members em ON em.entry_id = s.entry_id
    JOIN public.competitions c_1 ON c_1.id = s.competition_id
), entry_agg AS (
    SELECT scored.entry_id,
        scored.competition_id,
        count(*)::integer AS total_scores,
        COALESCE(avg(scored.score), 0::numeric)::numeric(4,2) AS raw_avg,
        count(*) FILTER (WHERE scored.is_self_vote)::integer AS self_votes,
        count(*) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote)::integer AS verified_scores,
        COALESCE(avg(scored.score) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote), 0::numeric)::numeric(4,2) AS verified_avg,
        count(*) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote AND scored.voter_is_judge)::integer AS judge_scores,
        COALESCE(avg(scored.score) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote AND scored.voter_is_judge), 0::numeric)::numeric(4,2) AS judge_avg,
        count(*) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote AND NOT scored.voter_is_judge)::integer AS community_scores,
        COALESCE(avg(scored.score) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote AND NOT scored.voter_is_judge), 0::numeric)::numeric(4,2) AS community_avg,
            CASE
                WHEN sum(
                CASE
                    WHEN scored.confidence >= 40 AND NOT scored.is_self_vote THEN scored.confidence::numeric / 100.0 *
                    CASE
                        WHEN scored.voter_is_judge THEN scored.judge_multiplier
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END) = 0::numeric THEN 0::numeric
                ELSE (sum(
                CASE
                    WHEN scored.confidence >= 40 AND NOT scored.is_self_vote THEN scored.score::numeric * (scored.confidence::numeric / 100.0) *
                    CASE
                        WHEN scored.voter_is_judge THEN scored.judge_multiplier
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END) / sum(
                CASE
                    WHEN scored.confidence >= 40 AND NOT scored.is_self_vote THEN scored.confidence::numeric / 100.0 *
                    CASE
                        WHEN scored.voter_is_judge THEN scored.judge_multiplier
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END))::numeric(4,2)
            END AS final_score,
        count(*) FILTER (WHERE scored.confidence < 40 AND NOT scored.is_self_vote)::integer AS rejected_scores,
        COALESCE(avg(scored.video_watch_duration_ms) FILTER (WHERE scored.confidence >= 40 AND NOT scored.is_self_vote), 0::numeric)::integer AS avg_watch_ms
    FROM scored
    GROUP BY scored.entry_id, scored.competition_id
)
SELECT rank() OVER (PARTITION BY ea.competition_id ORDER BY ea.final_score DESC, ea.verified_scores DESC)::integer AS rank,
    ea.entry_id,
    ea.competition_id,
    med.title,
    COALESCE(m.global_name, m.username) AS creator_name,
    m.member_id AS creator_id,
    ce.theme,
    ce.winner,
    ea.final_score,
    ea.total_scores,
    ea.self_votes,
    ea.rejected_scores,
    ea.verified_scores,
    ea.verified_avg,
    ea.judge_scores,
    ea.judge_avg,
    ea.community_scores,
    ea.community_avg,
    ea.raw_avg,
    ea.avg_watch_ms,
        CASE
            WHEN ea.self_votes > 0 THEN true
            ELSE false
        END AS has_self_votes,
        CASE
            WHEN ea.rejected_scores > 2 THEN true
            ELSE false
        END AS has_suspicious_activity,
        CASE
            WHEN ea.judge_avg > 0::numeric AND ea.community_avg > 0::numeric AND abs(ea.judge_avg - ea.community_avg) > 2.0 THEN true
            ELSE false
        END AS judge_community_divergence
FROM entry_agg ea
JOIN public.competition_entries ce ON ce.id = ea.entry_id
JOIN public.competitions c ON c.id = ea.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
WHERE c.type = 'prize'::text
  AND (ce.status <> ALL (ARRAY['draft'::text, 'rejected'::text]))
  AND (NOT ce.admin_hidden OR public.is_admin());

CREATE OR REPLACE VIEW public.final_results_dashboard_v2 AS
WITH scored AS (
    SELECT s.id AS score_id,
        s.entry_id,
        s.competition_id,
        s.user_id,
        s.score,
        public.is_banodoco_owner(m_voter.member_id) AS is_judge,
        COALESCE((c_1.settings ->> 'judge_multiplier'::text)::numeric, 1::numeric) AS judge_mult,
        em.auth_user_id IS NOT NULL AND s.user_id = em.auth_user_id AS is_self_vote,
        public.calculate_score_confidence_v2(s.id) AS score_conf,
        public.calculate_voter_confidence(s.user_id, s.competition_id) AS voter_conf
    FROM public.scores s
    JOIN public.competitions c_1 ON c_1.id = s.competition_id
    LEFT JOIN public.members m_voter ON m_voter.auth_user_id = s.user_id
    LEFT JOIN (
        SELECT ce2.id AS entry_id, m2.auth_user_id
        FROM public.competition_entries ce2
        LEFT JOIN public.members m2 ON m2.member_id = ce2.member_id
    ) em ON em.entry_id = s.entry_id
    WHERE c_1.type = 'prize'::text
), entry_agg AS (
    SELECT scored.entry_id,
        scored.competition_id,
        count(*) FILTER (WHERE NOT scored.is_self_vote)::integer AS total_scores,
        count(*) FILTER (WHERE scored.is_self_vote)::integer AS self_votes,
        COALESCE(avg(scored.score) FILTER (WHERE NOT scored.is_self_vote), 0::numeric)::numeric(4,2) AS raw_avg,
            CASE
                WHEN sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN
                    CASE
                        WHEN scored.is_judge THEN scored.judge_mult
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END) = 0::numeric THEN 0::numeric
                ELSE (sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score::numeric *
                    CASE
                        WHEN scored.is_judge THEN scored.judge_mult
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END) / sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN
                    CASE
                        WHEN scored.is_judge THEN scored.judge_mult
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END))::numeric(4,2)
            END AS judge_adj,
            CASE
                WHEN sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score_conf
                    ELSE NULL::numeric
                END) = 0::numeric THEN 0::numeric
                ELSE (sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score::numeric * scored.score_conf
                    ELSE NULL::numeric
                END) / sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score_conf
                    ELSE NULL::numeric
                END))::numeric(4,2)
            END AS score_conf_adj,
            CASE
                WHEN sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.voter_conf
                    ELSE NULL::numeric
                END) = 0::numeric THEN 0::numeric
                ELSE (sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score::numeric * scored.voter_conf
                    ELSE NULL::numeric
                END) / sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.voter_conf
                    ELSE NULL::numeric
                END))::numeric(4,2)
            END AS voter_conf_adj,
            CASE
                WHEN sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score_conf * scored.voter_conf *
                    CASE
                        WHEN scored.is_judge THEN scored.judge_mult
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END) = 0::numeric THEN 0::numeric
                ELSE (sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score::numeric * scored.score_conf * scored.voter_conf *
                    CASE
                        WHEN scored.is_judge THEN scored.judge_mult
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END) / sum(
                CASE
                    WHEN NOT scored.is_self_vote THEN scored.score_conf * scored.voter_conf *
                    CASE
                        WHEN scored.is_judge THEN scored.judge_mult
                        ELSE 1::numeric
                    END
                    ELSE NULL::numeric
                END))::numeric(4,2)
            END AS final_score,
        count(*) FILTER (WHERE NOT scored.is_self_vote AND scored.is_judge)::integer AS judge_scores,
        COALESCE(avg(scored.score) FILTER (WHERE NOT scored.is_self_vote AND scored.is_judge), 0::numeric)::numeric(4,2) AS judge_avg,
        count(*) FILTER (WHERE NOT scored.is_self_vote AND NOT scored.is_judge)::integer AS community_scores,
        COALESCE(avg(scored.score) FILTER (WHERE NOT scored.is_self_vote AND NOT scored.is_judge), 0::numeric)::numeric(4,2) AS community_avg
    FROM scored
    GROUP BY scored.entry_id, scored.competition_id
)
SELECT rank() OVER (PARTITION BY ea.competition_id ORDER BY ea.final_score DESC, ea.total_scores DESC)::integer AS rank,
    ea.entry_id,
    ea.competition_id,
    med.title,
    COALESCE(m.global_name, m.username) AS creator_name,
    m.member_id AS creator_id,
    ce.theme,
    ce.winner,
    ea.total_scores,
    ea.self_votes,
    ea.raw_avg,
    (ea.judge_adj - ea.raw_avg)::numeric(4,2) AS judge_delta,
    (ea.score_conf_adj - ea.raw_avg)::numeric(4,2) AS score_conf_delta,
    (ea.voter_conf_adj - ea.raw_avg)::numeric(4,2) AS voter_conf_delta,
    ea.final_score,
    (ea.final_score - ea.raw_avg)::numeric(4,2) AS total_delta,
    ea.judge_scores,
    ea.judge_avg,
    ea.community_scores,
    ea.community_avg,
        CASE
            WHEN ea.judge_avg > 0::numeric AND ea.community_avg > 0::numeric AND abs(ea.judge_avg - ea.community_avg) > 2.0 THEN true
            ELSE false
        END AS judge_community_divergence
FROM entry_agg ea
JOIN public.competition_entries ce ON ce.id = ea.entry_id
JOIN public.competitions c ON c.id = ea.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
WHERE (ce.status <> ALL (ARRAY['draft'::text, 'rejected'::text]))
  AND (NOT ce.admin_hidden OR public.is_admin());

-- 6. Rewrite the two helper functions that read members.banodoco_owner.
CREATE OR REPLACE FUNCTION public.get_verified_vote_count_with_judge_multiplier(p_entry_id uuid, p_competition_id uuid DEFAULT NULL::uuid)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $fn$
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
    WHERE s.entry_id = p_entry_id AND NOT public.is_banodoco_owner(m.member_id);

    SELECT COUNT(*) INTO v_judge
    FROM public.scores s
    JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.entry_id = p_entry_id AND public.is_banodoco_owner(m.member_id);

    RETURN v_regular + (v_judge * v_multiplier);
END;
$fn$;

CREATE OR REPLACE FUNCTION public.get_vote_count_with_judge_multiplier(p_entry_id uuid, p_competition_id uuid DEFAULT NULL::uuid)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $fn$
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
    WHERE s.entry_id = p_entry_id AND NOT public.is_banodoco_owner(m.member_id);

    SELECT COUNT(*) INTO v_judge
    FROM public.scores s
    JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.entry_id = p_entry_id AND public.is_banodoco_owner(m.member_id);

    RETURN v_regular + (v_judge * v_multiplier);
END;
$fn$;

-- 7. Drop the duplicate triggers and the now-unused trigger function.
DROP TRIGGER IF EXISTS trg_members_owner_flag ON public.members;
DROP TRIGGER IF EXISTS trg_members_banodoco_owner_flag ON public.members;
DROP FUNCTION IF EXISTS public.apply_banodoco_owner_flag();

-- 8. Finally drop the denormalized column. Nothing should reference it now.
ALTER TABLE public.members DROP COLUMN banodoco_owner;

COMMIT;
