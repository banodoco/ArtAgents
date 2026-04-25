-- Two-level confidence scoring system for competition results.
--
-- Each score's final weight = score_confidence × voter_confidence × judge_multiplier
--
-- Score-level confidence assesses each individual score (did they watch? right theme?).
-- Voter-level confidence assesses the voter's overall pattern (engagement, discrimination,
-- shill detection, IP sharing, speed-running, theme accuracy).
--
-- Self-votes are excluded entirely.

-- ============================================================
-- FUNCTION: Voter-level confidence (0.05-1.0)
-- ============================================================

CREATE OR REPLACE FUNCTION public.calculate_voter_confidence(p_user_id UUID, p_competition_id UUID)
RETURNS NUMERIC
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_conf NUMERIC := 1.0;
    v_entries_scored INT;
    v_score_spread NUMERIC;
    v_avg_watch_ms INT;
    v_unwatch_pct NUMERIC;
    v_avg_gap_s INT;
    v_theme_accuracy NUMERIC;
    v_lazy_theme_pct NUMERIC;
    v_shill_gap NUMERIC;
    v_ip_shared INT;
BEGIN
    -- Gather voter stats
    SELECT
        COUNT(*),
        COALESCE(STDDEV(s.score), 0),
        COALESCE(AVG(s.video_watch_duration_ms) FILTER (WHERE s.video_watch_duration_ms > 0), 0)::INT,
        COUNT(*) FILTER (WHERE COALESCE(s.video_watch_duration_ms, 0) < 3000)::NUMERIC / GREATEST(COUNT(*), 1),
        CASE WHEN COUNT(*) > 1
            THEN (EXTRACT(EPOCH FROM MAX(s.created_at) - MIN(s.created_at)) / (COUNT(*) - 1))::INT
            ELSE 0 END,
        COUNT(*) FILTER (WHERE s.theme = ce.theme)::NUMERIC /
            NULLIF(COUNT(*) FILTER (WHERE s.theme IS NOT NULL AND s.theme != '' AND s.theme NOT IN ('None', 'All')), 0),
        COUNT(*) FILTER (WHERE s.theme IN ('None', 'All') OR s.theme IS NULL OR s.theme = '')::NUMERIC / GREATEST(COUNT(*), 1)
    INTO v_entries_scored, v_score_spread, v_avg_watch_ms, v_unwatch_pct, v_avg_gap_s, v_theme_accuracy, v_lazy_theme_pct
    FROM public.scores s
    JOIN public.competition_entries ce ON ce.id = s.entry_id
    WHERE s.user_id = p_user_id AND s.competition_id = p_competition_id;

    IF v_entries_scored = 0 THEN RETURN 0; END IF;

    -- Shill gap: best artist avg minus overall avg
    SELECT COALESCE(MAX(sub.artist_avg) - AVG(sub.artist_avg), 0)
    INTO v_shill_gap
    FROM (
        SELECT AVG(s.score) AS artist_avg
        FROM public.scores s
        JOIN public.competition_entries ce ON ce.id = s.entry_id
        WHERE s.user_id = p_user_id AND s.competition_id = p_competition_id
        GROUP BY ce.member_id
    ) sub;

    -- IP sharing count
    SELECT COALESCE(COUNT(DISTINCT s2.user_id), 1)
    INTO v_ip_shared
    FROM public.scores s2
    WHERE s2.competition_id = p_competition_id
      AND s2.ip_hash IN (
          SELECT DISTINCT ip_hash FROM public.scores
          WHERE user_id = p_user_id AND competition_id = p_competition_id AND ip_hash IS NOT NULL
      );

    -- === Apply penalties (multiplicative) ===

    -- 1. Engagement depth: how many entries did they score?
    --    1 entry = likely a friend drive-by
    IF v_entries_scored = 1 THEN v_conf := v_conf * 0.3;
    ELSIF v_entries_scored <= 3 THEN v_conf := v_conf * 0.6;
    ELSIF v_entries_scored <= 5 THEN v_conf := v_conf * 0.8;
    END IF;

    -- 2. Score discrimination: are they actually differentiating?
    --    All-10s or all-same-score on 3+ entries = suspicious
    IF v_entries_scored >= 3 AND v_score_spread < 0.5 THEN v_conf := v_conf * 0.5;
    ELSIF v_entries_scored >= 3 AND v_score_spread < 1.0 THEN v_conf := v_conf * 0.8;
    END IF;

    -- 3. Average watch time across all their scores
    IF v_avg_watch_ms < 5000 THEN v_conf := v_conf * 0.5;
    ELSIF v_avg_watch_ms < 15000 THEN v_conf := v_conf * 0.7;
    END IF;

    -- 4. What % of their scores had < 3s watch time?
    IF v_unwatch_pct > 0.7 THEN v_conf := v_conf * 0.6;
    ELSIF v_unwatch_pct > 0.4 THEN v_conf := v_conf * 0.8;
    END IF;

    -- 5. Speed-running: avg gap between consecutive scores
    IF v_entries_scored >= 3 AND v_avg_gap_s > 0 AND v_avg_gap_s < 20 THEN v_conf := v_conf * 0.6;
    ELSIF v_entries_scored >= 3 AND v_avg_gap_s > 0 AND v_avg_gap_s < 45 THEN v_conf := v_conf * 0.8;
    END IF;

    -- 6. Theme accuracy (when they actually picked a theme)
    IF v_theme_accuracy IS NOT NULL AND v_theme_accuracy < 0.2 THEN v_conf := v_conf * 0.7;
    ELSIF v_theme_accuracy IS NOT NULL AND v_theme_accuracy < 0.4 THEN v_conf := v_conf * 0.85;
    END IF;

    -- 7. Shill pattern: boosting one artist while tanking the rest
    IF v_shill_gap > 6 AND v_entries_scored >= 5 THEN v_conf := v_conf * 0.2;
    ELSIF v_shill_gap > 4 AND v_entries_scored >= 5 THEN v_conf := v_conf * 0.5;
    ELSIF v_shill_gap > 3 AND v_entries_scored >= 3 THEN v_conf := v_conf * 0.7;
    END IF;

    -- 8. IP sharing: multiple accounts from same network
    IF v_ip_shared >= 4 THEN v_conf := v_conf * 0.5;
    ELSIF v_ip_shared >= 3 THEN v_conf := v_conf * 0.7;
    END IF;

    RETURN GREATEST(v_conf, 0.05)::NUMERIC(4,3);
END;
$$;

COMMENT ON FUNCTION public.calculate_voter_confidence(UUID, UUID) IS
'Calculates a 0.05-1.0 confidence weight for a voter based on their overall behavior pattern.

Penalties (multiplicative):
  Engagement:     1 entry → ×0.3, 2-3 → ×0.6, 4-5 → ×0.8
  Discrimination: stddev < 0.5 on 3+ entries → ×0.5, < 1.0 → ×0.8
  Watch time:     avg < 5s → ×0.5, < 15s → ×0.7
  Unwatched %:    > 70% → ×0.6, > 40% → ×0.8
  Speed-running:  < 20s avg gap → ×0.6, < 45s → ×0.8
  Theme accuracy: < 20% correct → ×0.7, < 40% → ×0.85
  Shill pattern:  gap > 6 → ×0.2, > 4 → ×0.5, > 3 → ×0.7
  IP sharing:     4+ users → ×0.5, 3 users → ×0.7

A voter hitting multiple penalties can compound to near-zero (floor 0.05).';

-- ============================================================
-- FUNCTION: Score-level confidence v2 (0.1-1.0)
-- ============================================================

CREATE OR REPLACE FUNCTION public.calculate_score_confidence_v2(p_score_id UUID)
RETURNS NUMERIC
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_conf NUMERIC := 1.0;
    v_score RECORD;
BEGIN
    SELECT s.*, ce.theme AS actual_theme
    INTO v_score
    FROM public.scores s
    JOIN public.competition_entries ce ON ce.id = s.entry_id
    WHERE s.id = p_score_id;

    IF NOT FOUND THEN RETURN 0; END IF;

    -- 1. Watch time for THIS specific score
    IF COALESCE(v_score.video_watch_duration_ms, 0) < 3000 THEN v_conf := v_conf * 0.5;
    ELSIF COALESCE(v_score.video_watch_duration_ms, 0) < 10000 THEN v_conf := v_conf * 0.7;
    ELSIF COALESCE(v_score.video_watch_duration_ms, 0) < 30000 THEN v_conf := v_conf * 0.85;
    END IF;

    -- 2. Theme accuracy for THIS specific score
    IF v_score.theme IS NULL OR v_score.theme = '' OR v_score.theme IN ('None', 'All') THEN
        v_conf := v_conf * 0.9;
    ELSIF v_score.theme != v_score.actual_theme THEN
        v_conf := v_conf * 0.75;
    END IF;

    RETURN GREATEST(v_conf, 0.1)::NUMERIC(4,3);
END;
$$;

COMMENT ON FUNCTION public.calculate_score_confidence_v2(UUID) IS
'Calculates a 0.1-1.0 confidence weight for an individual score.

Penalties (multiplicative):
  Watch time: < 3s → ×0.5, < 10s → ×0.7, < 30s → ×0.85
  Theme:      wrong → ×0.75, lazy (None/All/blank) → ×0.9, correct → ×1.0';

-- ============================================================
-- VIEW: Final results dashboard v2
-- ============================================================

DROP VIEW IF EXISTS public.final_results_dashboard_v2;

CREATE VIEW public.final_results_dashboard_v2 AS
WITH scored AS (
    SELECT
        s.id AS score_id,
        s.entry_id,
        s.competition_id,
        s.user_id,
        s.score,
        COALESCE(m_voter.banodoco_owner, FALSE) AS is_judge,
        COALESCE((c.settings->>'judge_multiplier')::NUMERIC, 1) AS judge_mult,
        (em.auth_user_id IS NOT NULL AND s.user_id = em.auth_user_id) AS is_self_vote,
        public.calculate_score_confidence_v2(s.id) AS score_conf,
        public.calculate_voter_confidence(s.user_id, s.competition_id) AS voter_conf
    FROM public.scores s
    JOIN public.competitions c ON c.id = s.competition_id
    LEFT JOIN public.members m_voter ON m_voter.auth_user_id = s.user_id
    LEFT JOIN (
        SELECT ce2.id AS entry_id, m2.auth_user_id
        FROM competition_entries ce2
        LEFT JOIN members m2 ON m2.member_id = ce2.member_id
    ) em ON em.entry_id = s.entry_id
    WHERE c.type = 'prize'
),
entry_agg AS (
    SELECT
        entry_id,
        competition_id,
        COUNT(*) FILTER (WHERE NOT is_self_vote)::INT AS total_scores,
        COUNT(*) FILTER (WHERE is_self_vote)::INT AS self_votes,

        -- Raw average (no weighting, no self-votes)
        COALESCE(AVG(score) FILTER (WHERE NOT is_self_vote), 0)::NUMERIC(4,2) AS raw_avg,

        -- Judge multiplier delta
        CASE WHEN SUM(CASE WHEN NOT is_self_vote THEN (CASE WHEN is_judge THEN judge_mult ELSE 1 END) END) = 0 THEN 0
        ELSE (
            SUM(CASE WHEN NOT is_self_vote THEN score * (CASE WHEN is_judge THEN judge_mult ELSE 1 END) END)
            / SUM(CASE WHEN NOT is_self_vote THEN (CASE WHEN is_judge THEN judge_mult ELSE 1 END) END)
        )::NUMERIC(4,2) END AS judge_adj,

        -- Score confidence delta
        CASE WHEN SUM(CASE WHEN NOT is_self_vote THEN score_conf END) = 0 THEN 0
        ELSE (SUM(CASE WHEN NOT is_self_vote THEN score * score_conf END)
              / SUM(CASE WHEN NOT is_self_vote THEN score_conf END))::NUMERIC(4,2) END AS score_conf_adj,

        -- Voter confidence delta
        CASE WHEN SUM(CASE WHEN NOT is_self_vote THEN voter_conf END) = 0 THEN 0
        ELSE (SUM(CASE WHEN NOT is_self_vote THEN score * voter_conf END)
              / SUM(CASE WHEN NOT is_self_vote THEN voter_conf END))::NUMERIC(4,2) END AS voter_conf_adj,

        -- Full combined: score_conf × voter_conf × judge_mult
        CASE WHEN SUM(CASE WHEN NOT is_self_vote THEN score_conf * voter_conf * (CASE WHEN is_judge THEN judge_mult ELSE 1 END) END) = 0 THEN 0
        ELSE (
            SUM(CASE WHEN NOT is_self_vote THEN score * score_conf * voter_conf * (CASE WHEN is_judge THEN judge_mult ELSE 1 END) END)
            / SUM(CASE WHEN NOT is_self_vote THEN score_conf * voter_conf * (CASE WHEN is_judge THEN judge_mult ELSE 1 END) END)
        )::NUMERIC(4,2) END AS final_score,

        -- Judge/community breakdown
        COUNT(*) FILTER (WHERE NOT is_self_vote AND is_judge)::INT AS judge_scores,
        COALESCE(AVG(score) FILTER (WHERE NOT is_self_vote AND is_judge), 0)::NUMERIC(4,2) AS judge_avg,
        COUNT(*) FILTER (WHERE NOT is_self_vote AND NOT is_judge)::INT AS community_scores,
        COALESCE(AVG(score) FILTER (WHERE NOT is_self_vote AND NOT is_judge), 0)::NUMERIC(4,2) AS community_avg
    FROM scored
    GROUP BY entry_id, competition_id
)
SELECT
    RANK() OVER (
        PARTITION BY ea.competition_id
        ORDER BY ea.final_score DESC, ea.total_scores DESC
    )::INT AS rank,
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
    (ea.judge_adj - ea.raw_avg)::NUMERIC(4,2) AS judge_delta,
    (ea.score_conf_adj - ea.raw_avg)::NUMERIC(4,2) AS score_conf_delta,
    (ea.voter_conf_adj - ea.raw_avg)::NUMERIC(4,2) AS voter_conf_delta,
    ea.final_score,
    (ea.final_score - ea.raw_avg)::NUMERIC(4,2) AS total_delta,
    ea.judge_scores,
    ea.judge_avg,
    ea.community_scores,
    ea.community_avg,
    CASE WHEN ea.judge_avg > 0 AND ea.community_avg > 0
         AND ABS(ea.judge_avg - ea.community_avg) > 2.0 THEN true ELSE false END AS judge_community_divergence
FROM entry_agg ea
JOIN public.competition_entries ce ON ce.id = ea.entry_id
JOIN public.competitions c ON c.id = ea.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
WHERE ce.status NOT IN ('draft', 'rejected')
  AND (NOT ce.admin_hidden OR public.is_admin());

GRANT SELECT ON public.final_results_dashboard_v2 TO authenticated;

COMMENT ON VIEW public.final_results_dashboard_v2 IS
'Final results dashboard v2 with two-level confidence weighting.

Each score''s weight = score_confidence × voter_confidence × judge_multiplier

SCORE-LEVEL CONFIDENCE (per individual score, 0.1-1.0):
  - Watch time: < 3s → ×0.5, < 10s → ×0.7, < 30s → ×0.85
  - Theme: wrong → ×0.75, lazy (None/All/blank) → ×0.9, correct → ×1.0

VOTER-LEVEL CONFIDENCE (per voter across all their scores, 0.05-1.0):
  - Engagement depth: 1 entry → ×0.3, 2-3 → ×0.6, 4-5 → ×0.8
  - Score discrimination: stddev < 0.5 → ×0.5, < 1.0 → ×0.8
  - Avg watch time: < 5s → ×0.5, < 15s → ×0.7
  - Unwatched rate: > 70% → ×0.6, > 40% → ×0.8
  - Speed-running: < 20s avg gap → ×0.6, < 45s → ×0.8
  - Theme accuracy: < 20% → ×0.7, < 40% → ×0.85
  - Shill pattern: gap > 6 → ×0.2, > 4 → ×0.5, > 3 → ×0.7
  - IP sharing: 4+ users → ×0.5, 3 users → ×0.7

DELTA COLUMNS show impact of each factor vs raw average:
  judge_delta       — effect of judge multiplier alone
  score_conf_delta  — effect of score-level confidence alone
  voter_conf_delta  — effect of voter-level confidence alone
  total_delta       — combined effect (final_score - raw_avg)';
