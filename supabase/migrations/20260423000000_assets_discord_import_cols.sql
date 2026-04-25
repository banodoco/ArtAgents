ALTER TABLE public.assets
    ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'discord_import')),
    ADD COLUMN discord_guild_id BIGINT,
    ADD COLUMN discord_channel_id BIGINT,
    ADD COLUMN discord_thread_id BIGINT,
    ADD COLUMN imported_at TIMESTAMPTZ,
    ADD COLUMN last_synced_at TIMESTAMPTZ,
    ADD COLUMN reactions_reached_threshold_at TIMESTAMPTZ,
    ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX assets_discord_thread_id_unique
    ON public.assets(discord_thread_id)
    WHERE discord_thread_id IS NOT NULL;

CREATE INDEX assets_source_idx
    ON public.assets(source);

CREATE INDEX assets_is_hidden_idx
    ON public.assets(is_hidden)
    WHERE is_hidden = TRUE;
