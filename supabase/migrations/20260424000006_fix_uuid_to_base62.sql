-- Fix uuid_to_base62(): the NUMERIC-based implementation in
-- 20260424000002 produces tokens that don't round-trip through the
-- client's decodeUuidBase62 (decoded hex is the wrong UUID, not even a
-- valid UUIDv4 shape). Rewrite using byte-array long division, which
-- is all INTEGER arithmetic — no precision artifacts.
--
-- Then backfill every existing assets.slug so the tokens match what
-- the client will produce for the same UUID.

CREATE OR REPLACE FUNCTION public.uuid_to_base62(input_uuid UUID)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    alphabet CONSTANT TEXT := '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
    bytes BYTEA;
    carry INTEGER;
    i INTEGER;
    digit INTEGER;
    encoded TEXT := '';
    any_nonzero BOOLEAN;
BEGIN
    IF input_uuid IS NULL THEN
        RETURN NULL;
    END IF;

    bytes := uuid_send(input_uuid);

    LOOP
        carry := 0;
        any_nonzero := FALSE;
        FOR i IN 0..15 LOOP
            carry := carry * 256 + get_byte(bytes, i);
            digit := carry / 62;
            carry := carry - digit * 62;
            bytes := set_byte(bytes, i, digit);
            IF digit <> 0 THEN
                any_nonzero := TRUE;
            END IF;
        END LOOP;
        encoded := SUBSTRING(alphabet FROM carry + 1 FOR 1) || encoded;
        EXIT WHEN NOT any_nonzero;
    END LOOP;

    RETURN encoded;
END;
$$;

-- Rebuild every slug so the token matches the corrected encoder.
-- assets_slug_unique has to be dropped temporarily because the new
-- slugs would collide with the existing (wrong) ones during UPDATE.
ALTER TABLE public.assets DROP CONSTRAINT IF EXISTS assets_slug_unique;

UPDATE public.assets
SET slug = public.build_asset_slug(name, id);

ALTER TABLE public.assets
    ADD CONSTRAINT assets_slug_unique UNIQUE (slug);
