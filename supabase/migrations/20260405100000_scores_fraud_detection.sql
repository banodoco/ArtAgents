-- Wire up fraud detection and integrity checks to the scores table.
--
-- What this does:
-- 1. Adds ip_hash column to scores (for IP-based fraud detection)
-- 2. Adds self-voting prevention trigger
-- 3. Adds IP capture trigger (hashes IP on insert/update)
-- 4. Creates calculate_score_confidence() — adapted from calculate_vote_confidence()
-- 5. Creates a voter_confidence view — per-voter legitimacy weight
-- 6. Creates weighted_leaderboard view — scores weighted by voter confidence
-- 7. Backfills ip_hash for existing scores from entry_analytics where possible

-- ============================================================
-- STEP 1: Add ip_hash column to scores
-- ============================================================

ALTER TABLE public.scores ADD COLUMN IF NOT EXISTS ip_hash TEXT;

-- ============================================================
-- STEP 2: Self-voting prevention trigger
-- ============================================================

CREATE OR REPLACE FUNCTION public.prevent_self_scoring()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.competition_entries
        WHERE id = NEW.entry_id AND member_id = (
            SELECT m.member_id FROM public.members m WHERE m.auth_user_id = NEW.user_id
        )
    ) THEN
        RAISE EXCEPTION 'Cannot score your own entry';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_scores_prevent_self_scoring ON public.scores;
CREATE TRIGGER trg_scores_prevent_self_scoring
    BEFORE INSERT ON public.scores
    FOR EACH ROW EXECUTE FUNCTION public.prevent_self_scoring();

-- ============================================================
-- STEP 3: IP capture trigger
-- ============================================================

CREATE OR REPLACE FUNCTION public.capture_score_ip()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
    NEW.ip_hash := public.hash_ip_address(
        COALESCE(current_setting('request.headers', true)::json->>'x-forwarded-for', 'unknown')
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_scores_capture_ip ON public.scores;
CREATE TRIGGER trg_scores_capture_ip
    BEFORE INSERT ON public.scores
    FOR EACH ROW EXECUTE FUNCTION public.capture_score_ip();

-- ============================================================
-- STEP 4: Score confidence function
-- Calculates a 0-100 confidence score for each score entry.
-- Adapted from calculate_vote_confidence but works on the scores table.
-- ============================================================

CREATE OR REPLACE FUNCTION public.calculate_score_confidence(p_score_id UUID)
RETURNS INTEGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_confidence INTEGER := 100;
    v_score_row RECORD;
    v_config RECORD;
    v_ip_count INTEGER;
    v_age_hours NUMERIC;
BEGIN
    SELECT s.*, m.discord_created_at, m.guild_join_date
    INTO v_score_row
    FROM public.scores s
    LEFT JOIN public.members m ON m.auth_user_id = s.user_id
    WHERE s.id = p_score_id;

    IF NOT FOUND THEN RETURN 0; END IF;

    -- 1. Account age penalty (Discord account age)
    SELECT config_value INTO v_config FROM public.fraud_config WHERE config_key = 'account_age_thresholds';
    IF v_config IS NOT NULL AND v_score_row.discord_created_at IS NOT NULL THEN
        v_age_hours := EXTRACT(EPOCH FROM (NOW() - v_score_row.discord_created_at)) / 3600.0;
        IF v_age_hours < COALESCE((v_config.config_value->>'very_new_hours')::NUMERIC, 1) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'very_new_penalty')::INTEGER, 40);
        ELSIF v_age_hours < COALESCE((v_config.config_value->>'new_hours')::NUMERIC, 24) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'new_penalty')::INTEGER, 25);
        ELSIF v_age_hours < COALESCE((v_config.config_value->>'recent_hours')::NUMERIC, 168) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'recent_penalty')::INTEGER, 10);
        END IF;
    END IF;

    -- 2. Vote speed penalty (how quickly they scored after viewing)
    SELECT config_value INTO v_config FROM public.fraud_config WHERE config_key = 'vote_speed_thresholds';
    IF v_config IS NOT NULL AND v_score_row.vote_duration_ms IS NOT NULL THEN
        IF v_score_row.vote_duration_ms < COALESCE((v_config.config_value->>'instant_ms')::INTEGER, 3000) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'instant_penalty')::INTEGER, 30);
        ELSIF v_score_row.vote_duration_ms < COALESCE((v_config.config_value->>'quick_ms')::INTEGER, 10000) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'quick_penalty')::INTEGER, 15);
        END IF;
    END IF;

    -- 3. IP sharing penalty (multiple users voting from same IP)
    SELECT config_value INTO v_config FROM public.fraud_config WHERE config_key = 'ip_sharing_thresholds';
    IF v_config IS NOT NULL AND v_score_row.ip_hash IS NOT NULL AND v_score_row.ip_hash != '' THEN
        SELECT COUNT(DISTINCT user_id) INTO v_ip_count
        FROM public.scores
        WHERE ip_hash = v_score_row.ip_hash
          AND competition_id = v_score_row.competition_id;

        IF v_ip_count > COALESCE((v_config.config_value->>'high_risk_count')::INTEGER, 5) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'high_risk_penalty')::INTEGER, 20);
        ELSIF v_ip_count > COALESCE((v_config.config_value->>'medium_risk_count')::INTEGER, 3) THEN
            v_confidence := v_confidence - COALESCE((v_config.config_value->>'medium_risk_penalty')::INTEGER, 10);
        END IF;
    END IF;

    -- 4. User agent penalty
    SELECT config_value INTO v_config FROM public.fraud_config WHERE config_key = 'user_agent_penalty';
    IF v_config IS NOT NULL AND (v_score_row.user_agent IS NULL OR v_score_row.user_agent = '') THEN
        v_confidence := v_confidence - COALESCE((v_config.config_value->>'missing_penalty')::INTEGER, 10);
    END IF;

    -- 5. Video watch time bonus/penalty — new for scores
    -- If they scored without watching much of the video, that's suspicious
    IF v_score_row.video_watch_duration_ms IS NOT NULL AND v_score_row.video_watch_duration_ms < 3000 THEN
        v_confidence := v_confidence - 10;
    END IF;

    RETURN GREATEST(v_confidence, 0);
END;
$$;

-- ============================================================
-- STEP 5: Voter confidence view
-- Aggregates per-voter confidence across all their scores.
-- This gives a single "how legitimate is this voter" weight.
-- ============================================================

CREATE OR REPLACE VIEW public.voter_confidence AS
SELECT
    s.user_id,
    s.competition_id,
    COALESCE(m.global_name, m.username) AS voter_name,
    COUNT(*) AS scores_cast,
    AVG(public.calculate_score_confidence(s.id))::NUMERIC(5,1) AS avg_confidence,
    MIN(public.calculate_score_confidence(s.id)) AS min_confidence,
    -- Legitimacy weight: 0.0 to 1.0
    -- Scores below 40 confidence → weight 0
    -- Scores 40-100 → proportional weight
    CASE
        WHEN AVG(public.calculate_score_confidence(s.id)) < 40 THEN 0.0
        ELSE (AVG(public.calculate_score_confidence(s.id)) / 100.0)::NUMERIC(4,3)
    END AS legitimacy_weight,
    COALESCE(m.banodoco_owner, FALSE) AS is_judge
FROM public.scores s
LEFT JOIN public.members m ON m.auth_user_id = s.user_id
GROUP BY s.user_id, s.competition_id, m.global_name, m.username, m.banodoco_owner;

GRANT SELECT ON public.voter_confidence TO authenticated;

-- ============================================================
-- STEP 6: Weighted leaderboard view
-- Each score is weighted by the voter's confidence.
-- Judge multiplier still applies on top.
-- ============================================================

CREATE OR REPLACE VIEW public.weighted_leaderboard AS
SELECT
    ce.id AS entry_id,
    ce.competition_id,
    med.title,
    COALESCE(m.global_name, m.username) AS creator_name,
    m.member_id AS creator_id,
    -- Raw stats (unweighted)
    COUNT(s.id)::INT AS total_scores,
    COALESCE(AVG(s.score), 0)::NUMERIC(4,2) AS raw_avg,
    -- Confidence-weighted stats
    COUNT(s.id) FILTER (
        WHERE public.calculate_score_confidence(s.id) >= 40
    )::INT AS verified_scores,
    COALESCE(
        AVG(s.score) FILTER (
            WHERE public.calculate_score_confidence(s.id) >= 40
        ), 0
    )::NUMERIC(4,2) AS verified_avg,
    -- Weighted average: each score multiplied by voter's confidence/100
    CASE
        WHEN COUNT(s.id) FILTER (WHERE public.calculate_score_confidence(s.id) >= 40) = 0 THEN 0
        ELSE (
            SUM(
                s.score * (public.calculate_score_confidence(s.id) / 100.0)
            ) FILTER (WHERE public.calculate_score_confidence(s.id) >= 40)
            /
            SUM(
                public.calculate_score_confidence(s.id) / 100.0
            ) FILTER (WHERE public.calculate_score_confidence(s.id) >= 40)
        )::NUMERIC(4,2)
    END AS weighted_avg,
    -- Rank by weighted average
    RANK() OVER (
        PARTITION BY ce.competition_id
        ORDER BY
            CASE
                WHEN COUNT(s.id) FILTER (WHERE public.calculate_score_confidence(s.id) >= 40) = 0 THEN 0
                ELSE (
                    SUM(s.score * (public.calculate_score_confidence(s.id) / 100.0))
                    FILTER (WHERE public.calculate_score_confidence(s.id) >= 40)
                    /
                    SUM(public.calculate_score_confidence(s.id) / 100.0)
                    FILTER (WHERE public.calculate_score_confidence(s.id) >= 40)
                )
            END DESC,
            COUNT(s.id) DESC
    )::INT AS weighted_rank,
    ce.winner
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
LEFT JOIN public.scores s ON s.entry_id = ce.id
WHERE c.type = 'prize'
  AND ce.status NOT IN ('draft', 'rejected')
  AND NOT ce.admin_hidden
GROUP BY ce.id, ce.competition_id, med.title, m.global_name, m.username, m.member_id, ce.winner;

GRANT SELECT ON public.weighted_leaderboard TO authenticated;

-- ============================================================
-- STEP 7: Backfill ip_hash from entry_analytics where possible
-- Match on user_id + entry_id to get the IP from when they viewed
-- ============================================================

UPDATE public.scores s
SET ip_hash = ea.ip_hash
FROM public.entry_analytics ea
WHERE ea.user_id = s.user_id
  AND ea.entry_id = s.entry_id
  AND ea.ip_hash IS NOT NULL
  AND s.ip_hash IS NULL;
