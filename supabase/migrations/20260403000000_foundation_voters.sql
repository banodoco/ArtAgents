CREATE TABLE public.foundation_voters (
  competition_id UUID NOT NULL REFERENCES public.competitions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (competition_id, user_id)
);

ALTER TABLE public.foundation_voters ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admins_manage_foundation_voters" ON public.foundation_voters
  FOR ALL
  USING (public.is_admin())
  WITH CHECK (public.is_admin());
