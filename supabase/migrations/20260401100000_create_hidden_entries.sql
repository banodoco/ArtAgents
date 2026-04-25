CREATE TABLE IF NOT EXISTS public.hidden_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  entry_id UUID NOT NULL REFERENCES public.competition_entries(id) ON DELETE CASCADE,
  competition_id UUID NOT NULL REFERENCES public.competitions(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, entry_id)
);

ALTER TABLE public.hidden_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own hidden entries"
  ON public.hidden_entries
  FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, DELETE ON public.hidden_entries TO authenticated;
