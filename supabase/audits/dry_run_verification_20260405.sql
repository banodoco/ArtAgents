-- DRY RUN VERIFICATION SCRIPT
-- Run this BEFORE the actual migration to verify everything will work.
-- This script only does SELECTs — it modifies nothing.
--
-- Run with: psql <connection_string> -f 20260405000000_dry_run_verification.sql

-- ============================================================
-- CHECK 1: Preview what will be inserted into scores
-- ============================================================
-- Should return 208 rows (one per vote), all with score=10

SELECT
    'PREVIEW: votes → scores migration' AS check_name,
    COUNT(*) AS rows_to_insert
FROM public.votes v
JOIN public.competition_entries ce ON ce.id = v.entry_id
WHERE NOT EXISTS (
    SELECT 1 FROM public.scores s
    WHERE s.user_id = v.user_id AND s.entry_id = v.entry_id
);

-- Show a sample of what will be inserted
SELECT
    v.user_id,
    v.entry_id,
    v.competition_id,
    10 AS score,
    ce.theme,
    v.vote_duration_ms,
    v.created_at
FROM public.votes v
JOIN public.competition_entries ce ON ce.id = v.entry_id
WHERE NOT EXISTS (
    SELECT 1 FROM public.scores s
    WHERE s.user_id = v.user_id AND s.entry_id = v.entry_id
)
LIMIT 5;

-- ============================================================
-- CHECK 2: Verify no duplicate conflicts
-- ============================================================
-- Should return 0 rows — no votes already exist in scores

SELECT
    'CONFLICT CHECK: votes already in scores' AS check_name,
    COUNT(*) AS conflicts
FROM public.votes v
WHERE EXISTS (
    SELECT 1 FROM public.scores s
    WHERE s.user_id = v.user_id AND s.entry_id = v.entry_id
);

-- ============================================================
-- CHECK 3: Verify all vote entry_ids exist in competition_entries
-- ============================================================
-- Should return 0 rows — no orphaned votes

SELECT
    'ORPHAN CHECK: votes with missing entries' AS check_name,
    COUNT(*) AS orphans
FROM public.votes v
WHERE NOT EXISTS (
    SELECT 1 FROM public.competition_entries ce
    WHERE ce.id = v.entry_id
);

-- ============================================================
-- CHECK 4: Preview Edition 1 leaderboard after migration
-- ============================================================
-- Simulate what the leaderboard would look like

SELECT
    'EDITION 1 LEADERBOARD PREVIEW' AS check_name,
    ce.id AS entry_id,
    med.title,
    COALESCE(m.global_name, m.username) AS creator,
    ce.theme,
    COUNT(v.id) AS vote_count,
    10.0 AS avg_score  -- all scores will be 10
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
LEFT JOIN public.votes v ON v.entry_id = ce.id
WHERE c.id = 'a852954e-053c-4d08-9b94-a145ec1634ef'
  AND ce.status NOT IN ('draft', 'rejected')
GROUP BY ce.id, med.title, m.global_name, m.username, ce.theme
ORDER BY COUNT(v.id) DESC;

-- ============================================================
-- CHECK 5: Preview Edition 2 leaderboard (should be unchanged)
-- ============================================================

SELECT
    'EDITION 2 LEADERBOARD PREVIEW (top 10)' AS check_name,
    ce.id AS entry_id,
    med.title,
    COALESCE(m.global_name, m.username) AS creator,
    COUNT(s.id) AS score_count,
    AVG(s.score)::NUMERIC(4,2) AS avg_score
FROM public.competition_entries ce
JOIN public.competitions c ON c.id = ce.competition_id
JOIN public.media med ON med.id = ce.media_id
LEFT JOIN public.members m ON m.member_id = ce.member_id
LEFT JOIN public.scores s ON s.entry_id = ce.id
WHERE c.id = '8c1bcdf1-c8ef-4c7e-83c1-091b68e9ca4c'
  AND ce.status NOT IN ('draft', 'rejected')
GROUP BY ce.id, med.title, m.global_name, m.username
ORDER BY AVG(s.score) DESC NULLS LAST
LIMIT 10;

-- ============================================================
-- CHECK 6: Count totals for post-migration verification
-- ============================================================

SELECT 'PRE-MIGRATION COUNTS' AS check_name,
    (SELECT COUNT(*) FROM public.votes) AS votes_count,
    (SELECT COUNT(*) FROM public.scores) AS scores_count,
    (SELECT COUNT(*) FROM public.scores WHERE competition_id = 'a852954e-053c-4d08-9b94-a145ec1634ef') AS ed1_scores,
    (SELECT COUNT(*) FROM public.scores WHERE competition_id = '8c1bcdf1-c8ef-4c7e-83c1-091b68e9ca4c') AS ed2_scores;

-- Expected post-migration:
--   votes_count: 208 (unchanged)
--   scores_count: current + 208
--   ed1_scores: 208
--   ed2_scores: unchanged
