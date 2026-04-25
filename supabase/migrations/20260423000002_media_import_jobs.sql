DO $$
DECLARE
    v_data_type TEXT;
    v_udt_schema TEXT;
    v_udt_name TEXT;
    v_constraint_name TEXT;
    v_constraint_def TEXT;
    v_constraint_expr TEXT;
BEGIN
    SELECT
        c.data_type,
        c.udt_schema,
        c.udt_name
    INTO
        v_data_type,
        v_udt_schema,
        v_udt_name
    FROM information_schema.columns AS c
    WHERE c.table_schema = 'public'
      AND c.table_name = 'media'
      AND c.column_name = 'classification';

    IF NOT FOUND THEN
        ALTER TABLE public.media
            ADD COLUMN classification TEXT;
        v_data_type := 'text';
        v_udt_schema := 'pg_catalog';
        v_udt_name := 'text';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type AS t
        JOIN pg_namespace AS n
          ON n.oid = t.typnamespace
        WHERE n.nspname = v_udt_schema
          AND t.typname = v_udt_name
          AND t.typtype = 'e'
    ) THEN
        EXECUTE format(
            'ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L',
            v_udt_schema,
            v_udt_name,
            'discord-comment'
        );
    ELSE
        SELECT
            con.conname,
            pg_get_constraintdef(con.oid)
        INTO
            v_constraint_name,
            v_constraint_def
        FROM pg_constraint AS con
        JOIN pg_class AS rel
          ON rel.oid = con.conrelid
        JOIN pg_namespace AS nsp
          ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'media'
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) ILIKE '%classification%'
        ORDER BY con.conname
        LIMIT 1;

        IF v_constraint_name IS NOT NULL THEN
            v_constraint_expr := regexp_replace(
                v_constraint_def,
                '^CHECK \\((.*)\\)$',
                '\\1'
            );

            EXECUTE format(
                'ALTER TABLE public.media DROP CONSTRAINT %I',
                v_constraint_name
            );

            EXECUTE format(
                'ALTER TABLE public.media ADD CONSTRAINT %I CHECK ((classification = %L) OR (%s))',
                v_constraint_name,
                'discord-comment',
                v_constraint_expr
            );
        ELSE
            -- No pre-existing CHECK on classification — leave the column
            -- unconstrained so legacy values ('art', 'gen', etc.) keep working.
            -- 'discord-comment' is implicitly allowed.
            NULL;
        END IF;
    END IF;
END;
$$;

CREATE TABLE public.media_import_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discord_attachment_id BIGINT,
    discord_message_id BIGINT,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('asset_media', 'asset_comment_media')),
    target_id UUID NOT NULL,
    original_cdn_url TEXT,
    filename TEXT,
    content_type TEXT,
    size_bytes BIGINT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'done', 'failed', 'skipped')),
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    media_id UUID REFERENCES public.media(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_until TIMESTAMPTZ
);

CREATE UNIQUE INDEX media_import_jobs_discord_attachment_id_idx
    ON public.media_import_jobs(discord_attachment_id)
    WHERE discord_attachment_id IS NOT NULL;

CREATE INDEX media_import_jobs_claim_idx
    ON public.media_import_jobs(status, locked_until)
    WHERE status IN ('pending', 'in_progress');

ALTER TABLE public.media_import_jobs ENABLE ROW LEVEL SECURITY;
