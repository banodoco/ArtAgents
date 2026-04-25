CREATE OR REPLACE FUNCTION public.compute_priority_scores(target_competition_id UUID DEFAULT NULL)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  comp RECORD;
BEGIN
  FOR comp IN
    SELECT id FROM public.competitions
    WHERE type = 'prize'
      AND is_active = true
      AND (target_competition_id IS NULL OR id = target_competition_id)
  LOOP
    -- Upsert priority scores for all entries in this competition.
    -- Entries with zero foundation votes get priority_score = NULL so the
    -- frontend can distinguish "unscored" from "scored with a low average".
    INSERT INTO public.entry_priority_scores (entry_id, competition_id, priority_score, foundation_vote_count, computed_at)
    SELECT
      ce.id AS entry_id,
      ce.competition_id,
      CASE
        WHEN COUNT(s.score) FILTER (WHERE fv.user_id IS NOT NULL) = 0 THEN NULL
        WHEN COUNT(s.score) FILTER (WHERE fv.user_id IS NOT NULL) < 5 THEN
          -- Simple mean, normalized to 0-1
          (AVG(s.score) FILTER (WHERE fv.user_id IS NOT NULL) - 1) / 9.0
        ELSE
          -- Trimmed mean (drop highest and lowest), normalized to 0-1
          (
            (SUM(s.score) FILTER (WHERE fv.user_id IS NOT NULL) - MIN(s.score) FILTER (WHERE fv.user_id IS NOT NULL) - MAX(s.score) FILTER (WHERE fv.user_id IS NOT NULL))
            / (COUNT(s.score) FILTER (WHERE fv.user_id IS NOT NULL) - 2)::DOUBLE PRECISION
            - 1
          ) / 9.0
      END AS priority_score,
      COUNT(s.score) FILTER (WHERE fv.user_id IS NOT NULL)::INT AS foundation_vote_count,
      now() AS computed_at
    FROM public.competition_entries ce
    LEFT JOIN public.scores s
      ON s.entry_id = ce.id
      AND s.competition_id = comp.id
      AND s.user_id != ce.user_id  -- Exclude self-votes
    LEFT JOIN public.foundation_voters fv
      ON fv.user_id = s.user_id AND fv.competition_id = s.competition_id
    WHERE ce.competition_id = comp.id
      AND ce.status NOT IN ('draft', 'rejected')
    GROUP BY ce.id, ce.competition_id
    ON CONFLICT (entry_id)
    DO UPDATE SET
      priority_score = EXCLUDED.priority_score,
      foundation_vote_count = EXCLUDED.foundation_vote_count,
      computed_at = EXCLUDED.computed_at;
  END LOOP;
END;
$$;

-- Only pg_cron (database owner) should call this function (critique #3).
REVOKE EXECUTE ON FUNCTION public.compute_priority_scores(UUID) FROM public, anon, authenticated;
