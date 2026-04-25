CREATE TABLE public.asset_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES public.assets(id) ON DELETE CASCADE,
    discord_message_id BIGINT NOT NULL UNIQUE,
    discord_thread_id BIGINT NOT NULL,
    discord_guild_id BIGINT NOT NULL,
    author_member_id BIGINT REFERENCES public.members(member_id),
    content TEXT,
    reply_to_comment_id UUID REFERENCES public.asset_comments(id) ON DELETE SET NULL,
    reply_to_discord_message_id BIGINT,
    reaction_count INT NOT NULL DEFAULT 0,
    discord_created_at TIMESTAMPTZ NOT NULL,
    discord_edited_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX asset_comments_asset_created_idx
    ON public.asset_comments(asset_id, discord_created_at);

CREATE INDEX asset_comments_thread_idx
    ON public.asset_comments(discord_thread_id);

CREATE TABLE public.asset_comment_media (
    comment_id UUID NOT NULL REFERENCES public.asset_comments(id) ON DELETE CASCADE,
    media_id UUID NOT NULL REFERENCES public.media(id) ON DELETE CASCADE,
    sort_order INT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (comment_id, media_id)
);

ALTER TABLE public.asset_media
    ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.asset_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_comment_media ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read asset_comments" ON public.asset_comments;
CREATE POLICY "Public read asset_comments"
    ON public.asset_comments FOR SELECT
    USING (is_deleted = FALSE);

DROP POLICY IF EXISTS "Public read asset_comment_media" ON public.asset_comment_media;
CREATE POLICY "Public read asset_comment_media"
    ON public.asset_comment_media FOR SELECT
    USING (is_deleted = FALSE);

GRANT SELECT ON public.asset_comments TO anon, authenticated;
GRANT SELECT ON public.asset_comment_media TO anon, authenticated;
