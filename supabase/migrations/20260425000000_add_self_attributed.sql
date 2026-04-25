ALTER TABLE public.media
  ADD COLUMN IF NOT EXISTS self_attributed boolean NOT NULL DEFAULT false;

ALTER TABLE public.assets
  ADD COLUMN IF NOT EXISTS self_attributed boolean NOT NULL DEFAULT false;

UPDATE public.media
SET self_attributed = true;

UPDATE public.assets
SET self_attributed = true;
