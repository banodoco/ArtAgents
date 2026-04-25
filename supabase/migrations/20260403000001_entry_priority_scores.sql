CREATE TABLE public.entry_priority_scores (
  entry_id UUID NOT NULL REFERENCES public.competition_entries(id) ON DELETE CASCADE,
  competition_id UUID NOT NULL REFERENCES public.competitions(id) ON DELETE CASCADE,
  priority_score DOUBLE PRECISION,  -- NULL when unscored (foundation_vote_count = 0)
  foundation_vote_count INT NOT NULL DEFAULT 0,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (entry_id)
);

ALTER TABLE public.entry_priority_scores ENABLE ROW LEVEL SECURITY;

-- Keep the permissive SELECT policy so submission_details can LEFT JOIN this
-- table, but revoke direct table privileges from browser-facing roles.
CREATE POLICY "anyone_can_read_priority_scores" ON public.entry_priority_scores
  FOR SELECT USING (true);

REVOKE ALL ON public.entry_priority_scores FROM PUBLIC, anon, authenticated;
