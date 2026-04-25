ALTER TABLE public.assets
    ADD COLUMN IF NOT EXISTS slug TEXT,
    ADD COLUMN IF NOT EXISTS links JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'published'
        CHECK (status IN ('draft', 'published'));

CREATE INDEX IF NOT EXISTS assets_member_status_idx
    ON public.assets(member_id, status)
    WHERE member_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.assets_slugify(input_text TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    normalized TEXT;
BEGIN
    normalized := LOWER(COALESCE(input_text, ''));
    normalized := REGEXP_REPLACE(normalized, '[^a-z0-9\s-]+', '', 'g');
    normalized := REGEXP_REPLACE(BTRIM(normalized), '[\s-]+', '-', 'g');
    normalized := REGEXP_REPLACE(normalized, '(^-+|-+$)', '', 'g');

    IF normalized = '' THEN
        RETURN 'item';
    END IF;

    RETURN normalized;
END;
$$;

CREATE OR REPLACE FUNCTION public.uuid_to_base62(input_uuid UUID)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    alphabet CONSTANT TEXT := '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
    uuid_bytes BYTEA;
    value NUMERIC := 0;
    remainder INTEGER;
    encoded TEXT := '';
    byte_index INTEGER;
BEGIN
    IF input_uuid IS NULL THEN
        RETURN NULL;
    END IF;

    uuid_bytes := uuid_send(input_uuid);

    FOR byte_index IN 0..15 LOOP
        value := (value * 256) + get_byte(uuid_bytes, byte_index);
    END LOOP;

    IF value = 0 THEN
        RETURN '0';
    END IF;

    WHILE value > 0 LOOP
        remainder := MOD(value, 62);
        encoded := SUBSTRING(alphabet FROM remainder + 1 FOR 1) || encoded;
        value := TRUNC(value / 62);
    END LOOP;

    RETURN encoded;
END;
$$;

CREATE OR REPLACE FUNCTION public.build_asset_slug(input_name TEXT, input_id UUID)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT public.assets_slugify(input_name) || '--' || public.uuid_to_base62(input_id);
$$;

UPDATE public.assets
SET slug = public.build_asset_slug(name, id)
WHERE slug IS NULL OR BTRIM(slug) = '';

ALTER TABLE public.assets
    ADD CONSTRAINT assets_slug_unique UNIQUE (slug);

ALTER TABLE public.assets
    ALTER COLUMN slug SET NOT NULL;

CREATE OR REPLACE FUNCTION public.assets_fill_slug()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.slug IS NULL OR BTRIM(NEW.slug) = '' THEN
        NEW.slug := public.build_asset_slug(NEW.name, NEW.id);
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_assets_fill_slug ON public.assets;

CREATE TRIGGER trg_assets_fill_slug
    BEFORE INSERT OR UPDATE ON public.assets
    FOR EACH ROW
    EXECUTE FUNCTION public.assets_fill_slug();
