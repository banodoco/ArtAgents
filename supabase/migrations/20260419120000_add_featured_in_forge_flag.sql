-- Add a curated "featured in The Forge" flag to assets.
--
-- This column is independent of the art_pieces.featured_on_2rf flag
-- (which drives the Community Art grid / ArcaGidan homepage section).
-- This flag scopes The Forge section on /2RP to a hand-picked subset of
-- resources tied to Arca Gidan Prize entrants (winners, high-priority,
-- high-vote). All rows default to FALSE; curation is applied via a
-- follow-up migration or manual UPDATE that flips specific asset IDs.
--
-- Safe/idempotent: uses IF NOT EXISTS so re-runs are harmless.

ALTER TABLE public.assets
    ADD COLUMN IF NOT EXISTS featured_in_forge BOOLEAN NOT NULL DEFAULT FALSE;

-- Partial index: only the small curated subset is indexed, keeping the
-- index tiny while accelerating the "WHERE featured_in_forge = true" query
-- that drives The Forge.
CREATE INDEX IF NOT EXISTS idx_assets_featured_in_forge
    ON public.assets(featured_in_forge)
    WHERE featured_in_forge = TRUE;
