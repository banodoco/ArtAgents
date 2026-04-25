-- Final results dashboard for determining competition winners.
--
-- Combines all scoring signals into a single definitive view:
--   - Self-votes excluded
--   - Low-confidence scores excluded (< 40)
--   - Remaining scores weighted by voter confidence (0-100 → 0.0-1.0)
--   - Banodoco owner (judge) scores get a 3x multiplier
--   - Flags for suspicious activity and judge/community divergence

CREATE OR REPLACE VIEW public.final_results_dashboard AS
WITH entry_members AS (
    SELECT ce.id AS entry_id, m.auth_user_id AS creator_auth_id
    FROM public.competition_entries ce
    LEFT JOIN public.members m ON m.member_id = ce.member_id
),
scored AS (
    SELECT
        s.id AS score_id,
        s.entry_id,
        s.competition_id,
        s.user_id,
        s.score,
        s.video_watch_duration_ms,
        s.vote_duration_ms,
        public.calculate_score_confidence(s.id) AS confidence,
        COALESCE(m_voter.banodoco_owner, FALSE) AS voter_is_judge,
        (em.creator_auth_id IS NOT NULL AND s.user_id = em.creator_auth_id) AS is_self_vote
    FROM public.scores s
    LEFT JOIN public.members m_voter ON m_voter.auth_user_id = s.user_id
    LEFT JOIN entry_members em ON em.entry_id = s.entry_id
),
entry_agg AS (
    SELECT
        entry_id,
        competition_id,

        -- Raw counts
        COUNT(*)::INT AS total_scores,
        COALESCE(AVG(score), 0)::NUMERIC(4,2) AS raw_avg,

        -- Self-vote stats
        COUNT(*) FILTER (WHERE is_self_vote)::INT AS self_votes,

        -- Verified: confidence >= 40, excluding self-votes
        COUNT(*) FILTER (WHERE confidence >= 40 AND NOT is_self_vote)::INT AS verified_scores,
        COALESCE(AVG(score) FILTER (WHERE confidence >= 40 AND NOT is_self_vote), 0)::NUMERIC(4,2) AS verified_avg,

        -- Judge stats (excluding self-votes)
        COUNT(*) FILTER (WHERE confidence >= 40 AND NOT is_self_vote AND voter_is_judge)::INT AS judge_scores,
        COALESCE(AVG(score) FILTER (WHERE confidence >= 40 AND NOT is_self_vote AND voter_is_judge), 0)::NUMERIC(4,2) AS judge_avg,

        -- Community stats (non-judge, excluding self-votes)
        COUNT(*) FILTER (WHERE confidence >= 40 AND NOT is_self_vote AND NOT voter_is_judge)::INT AS community_scores,
        COALESCE(AVG(score) FILTER (WHERE confidence >= 40 AND NOT is_self_vote AND NOT voter_is_judge), 0)::NUMERIC(4,2) AS community_avg,

        -- Final weighted score: confidence-weighted + 3x judge multiplier, no self-votes
        CASE
            WHEN SUM(
                CASE WHEN confidence >= 40 AND NOT is_self_vote
                THEN (confidence / 100.0) * (CASE WHEN voter_is_judge THEN 3 ELSE 1 END)
                END
            ) = 0 THEN 0
            ELSE (
                SUM(
                    CASE WHEN confidence >= 40 AND NOT is_self_vote
                    THEN score * (confidence / 100.0) * (CASE WHEN voter_is_judge THEN 3 ELSE 1 END)
                    END
                )
                /
                SUM(
                    CASE WHEN confidence >= 40 AND NOT is_self_vote
                    THEN (confidence / 100.0) * (CASE WHEN voter_is_judge THEN 3 ELSE 1 END)
                    END
                )
            )::NUMERIC(4,2)
        END AS final_score,

        -- Low-confidence score count
        COUNT(*) FILTER (WHERE confidence < 40 AND NOT is_self_vote)::INT AS rejected_scores,

        -- Avg watch time (verified only)
        COALESCE(AVG(video_watch_duration_ms) FILTER (WHERE confidence >= 40 AND NOT is_self_vote), 0)::INT AS avg_watch_ms
    FROM scored
    GROUP BY entry_id, competition_id
)
SELECT
    RANK() OVER (
        PARTITION BY ea.competition_id
        ORDER BY ea.final_score DESC, ea.verified_scores DESC
    )::INT AS rank,
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
    CASE WHEN ea.self_votes > 0 THEN true ELSE false END AS has_self_votes,
    CASE WHEN ea.rejected_scores > 2 THEN true ELSE false END AS has_suspicious_activity,
    CASE
        WHEN ea.judge_avg > 0 AND ea.community_avg > 0
            AND ABS(ea.judge_avg - ea.community_avg) > 2.0
        THEN true ELSE false
    END AS judge_community_divergence
FROM entry_agg ea
JOIN public.competition_entries ce ON ce.id = ea.entry_id
JOIN public.competitions c ON c.id = ea.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
WHERE c.type = 'prize'
  AND ce.status NOT IN ('draft', 'rejected')
  AND NOT ce.admin_hidden;

GRANT SELECT ON public.final_results_dashboard TO authenticated;

COMMENT ON VIEW public.final_results_dashboard IS
'Definitive competition results dashboard for determining winners.

HOW THE FINAL SCORE IS CALCULATED:
  1. Self-votes are excluded (creator scoring their own entry)
  2. Low-confidence scores are excluded (confidence < 40)
  3. Remaining scores are weighted by voter confidence (0-100 → 0.0-1.0)
  4. Banodoco owner (judge) scores get a 3x multiplier on their weight
  5. Final score = weighted average of (score × confidence_weight × judge_multiplier)

CONFIDENCE SCORING (per score, 0-100):
  Starts at 100, penalties deducted for:
  - New Discord account (< 1hr: -40, < 24hr: -25, < 1 week: -10)
  - Fast voting (< 3s: -30, < 10s: -15)
  - IP sharing (> 5 users on same IP: -20, > 3: -10)
  - Missing user agent: -10
  - Low video watch time (< 3s): -10
  Scores below 40 are rejected entirely.

COLUMNS:
  rank              — Position by final_score (partitioned by competition)
  final_score       — THE score that determines winners (see formula above)
  verified_scores   — Count of scores that passed confidence check (no self-votes)
  judge_scores      — How many of those came from banodoco owners
  judge_avg         — Unweighted average from judges only
  community_scores  — Non-judge scores
  community_avg     — Unweighted average from community only
  self_votes        — Number of self-votes detected (excluded from final)
  rejected_scores   — Scores with confidence < 40 (excluded from final)
  raw_avg           — Simple average of ALL scores (including self-votes, for comparison)
  avg_watch_ms      — Average video watch time of verified voters (context)

FLAGS:
  has_self_votes            — Creator scored their own entry (informational, already excluded)
  has_suspicious_activity   — More than 2 scores were rejected for low confidence
  judge_community_divergence — Judges and community averages differ by > 2 points';

COMMENT ON COLUMN public.final_results_dashboard.final_score IS 'Confidence-weighted average with 3x judge multiplier, self-votes excluded. This is the score used to determine winners.';
COMMENT ON COLUMN public.final_results_dashboard.rank IS 'Position within competition, ordered by final_score DESC then verified_scores DESC.';
COMMENT ON COLUMN public.final_results_dashboard.verified_scores IS 'Scores with confidence >= 40, self-votes excluded. The denominator for final_score.';
COMMENT ON COLUMN public.final_results_dashboard.judge_community_divergence IS 'True when judge_avg and community_avg differ by more than 2 points. Flags entries worth manual review.';
