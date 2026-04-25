ALTER TABLE public.posts
    ADD COLUMN IF NOT EXISTS cover_media_id UUID REFERENCES public.media(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS admin_status TEXT DEFAULT 'Listed',
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'posts_admin_status_check'
          AND conrelid = 'public.posts'::regclass
    ) THEN
        ALTER TABLE public.posts
            ADD CONSTRAINT posts_admin_status_check
            CHECK (admin_status IN ('Listed', 'Featured', 'Curated', 'Hidden'));
    END IF;
END;
$$;

ALTER TABLE public.media
    ADD COLUMN IF NOT EXISTS source TEXT;

ALTER TABLE public.media
    ALTER COLUMN source SET DEFAULT 'art';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'media_source_check'
          AND conrelid = 'public.media'::regclass
    ) THEN
        ALTER TABLE public.media
            ADD CONSTRAINT media_source_check
            CHECK (source IN ('art', 'post'));
    END IF;
END;
$$;

UPDATE public.posts
SET admin_status = 'Listed'
WHERE admin_status IS NULL;

UPDATE public.media
SET source = 'art'
WHERE source IS NULL;

ALTER TABLE public.posts
    ALTER COLUMN admin_status SET DEFAULT 'Listed';

CREATE INDEX IF NOT EXISTS posts_member_status_updated_idx
    ON public.posts(member_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS posts_status_published_idx
    ON public.posts(published_at DESC)
    WHERE status = 'published';

CREATE INDEX IF NOT EXISTS media_source_idx
    ON public.media(source);

ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.post_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.post_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.post_models ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read published posts" ON public.posts;
DROP POLICY IF EXISTS "Users create own posts" ON public.posts;
DROP POLICY IF EXISTS "Users update own posts" ON public.posts;
DROP POLICY IF EXISTS "Users delete own posts" ON public.posts;
DROP POLICY IF EXISTS "posts_select" ON public.posts;
DROP POLICY IF EXISTS "posts_insert" ON public.posts;
DROP POLICY IF EXISTS "posts_update" ON public.posts;
DROP POLICY IF EXISTS "posts_delete" ON public.posts;

DROP POLICY IF EXISTS "Public read post_media" ON public.post_media;
DROP POLICY IF EXISTS "Users manage own post_media" ON public.post_media;
DROP POLICY IF EXISTS "post_media_select" ON public.post_media;
DROP POLICY IF EXISTS "post_media_insert" ON public.post_media;
DROP POLICY IF EXISTS "post_media_update" ON public.post_media;
DROP POLICY IF EXISTS "post_media_delete" ON public.post_media;

DROP POLICY IF EXISTS "Public read post_assets" ON public.post_assets;
DROP POLICY IF EXISTS "Users manage own post_assets" ON public.post_assets;
DROP POLICY IF EXISTS "post_assets_select" ON public.post_assets;
DROP POLICY IF EXISTS "post_assets_insert" ON public.post_assets;
DROP POLICY IF EXISTS "post_assets_update" ON public.post_assets;
DROP POLICY IF EXISTS "post_assets_delete" ON public.post_assets;

DROP POLICY IF EXISTS "Public read post_models" ON public.post_models;
DROP POLICY IF EXISTS "Users manage own post_models" ON public.post_models;
DROP POLICY IF EXISTS "post_models_select" ON public.post_models;
DROP POLICY IF EXISTS "post_models_insert" ON public.post_models;
DROP POLICY IF EXISTS "post_models_update" ON public.post_models;
DROP POLICY IF EXISTS "post_models_delete" ON public.post_models;

CREATE POLICY "posts_select"
    ON public.posts FOR SELECT
    USING (
        (
            status = 'published'
            AND (admin_status IS NULL OR admin_status <> 'Hidden')
        )
        OR member_id IN (
            SELECT m.member_id
            FROM public.members AS m
            WHERE m.auth_user_id = auth.uid()
        )
        OR public.is_admin()
    );

CREATE POLICY "posts_insert"
    ON public.posts FOR INSERT TO authenticated
    WITH CHECK (
        member_id IN (
            SELECT m.member_id
            FROM public.members AS m
            WHERE m.auth_user_id = auth.uid()
        )
    );

CREATE POLICY "posts_update"
    ON public.posts FOR UPDATE TO authenticated
    USING (
        member_id IN (
            SELECT m.member_id
            FROM public.members AS m
            WHERE m.auth_user_id = auth.uid()
        )
        OR public.is_admin()
    )
    WITH CHECK (
        member_id IN (
            SELECT m.member_id
            FROM public.members AS m
            WHERE m.auth_user_id = auth.uid()
        )
        OR public.is_admin()
    );

CREATE POLICY "posts_delete"
    ON public.posts FOR DELETE TO authenticated
    USING (
        member_id IN (
            SELECT m.member_id
            FROM public.members AS m
            WHERE m.auth_user_id = auth.uid()
        )
        OR public.is_admin()
    );

CREATE POLICY "post_media_select"
    ON public.post_media FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_media.post_id
              AND (
                  (
                      p.status = 'published'
                      AND (p.admin_status IS NULL OR p.admin_status <> 'Hidden')
                  )
                  OR p.member_id IN (
                      SELECT m.member_id
                      FROM public.members AS m
                      WHERE m.auth_user_id = auth.uid()
                  )
                  OR public.is_admin()
              )
        )
    );

CREATE POLICY "post_media_insert"
    ON public.post_media FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_media.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
        AND EXISTS (
            SELECT 1
            FROM public.media AS med
            WHERE med.id = post_media.media_id
              AND med.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_media_update"
    ON public.post_media FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_media.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_media.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
        AND EXISTS (
            SELECT 1
            FROM public.media AS med
            WHERE med.id = post_media.media_id
              AND med.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_media_delete"
    ON public.post_media FOR DELETE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_media.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_assets_select"
    ON public.post_assets FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_assets.post_id
              AND (
                  (
                      p.status = 'published'
                      AND (p.admin_status IS NULL OR p.admin_status <> 'Hidden')
                  )
                  OR p.member_id IN (
                      SELECT m.member_id
                      FROM public.members AS m
                      WHERE m.auth_user_id = auth.uid()
                  )
                  OR public.is_admin()
              )
        )
    );

CREATE POLICY "post_assets_insert"
    ON public.post_assets FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_assets.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
        AND EXISTS (
            SELECT 1
            FROM public.assets AS a
            WHERE a.id = post_assets.asset_id
              AND a.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_assets_update"
    ON public.post_assets FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_assets.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_assets.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
        AND EXISTS (
            SELECT 1
            FROM public.assets AS a
            WHERE a.id = post_assets.asset_id
              AND a.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_assets_delete"
    ON public.post_assets FOR DELETE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_assets.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_models_select"
    ON public.post_models FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_models.post_id
              AND (
                  (
                      p.status = 'published'
                      AND (p.admin_status IS NULL OR p.admin_status <> 'Hidden')
                  )
                  OR p.member_id IN (
                      SELECT m.member_id
                      FROM public.members AS m
                      WHERE m.auth_user_id = auth.uid()
                  )
                  OR public.is_admin()
              )
        )
    );

CREATE POLICY "post_models_insert"
    ON public.post_models FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_models.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_models_update"
    ON public.post_models FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_models.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_models.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );

CREATE POLICY "post_models_delete"
    ON public.post_models FOR DELETE TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.posts AS p
            WHERE p.id = post_models.post_id
              AND p.member_id IN (
                  SELECT m.member_id
                  FROM public.members AS m
                  WHERE m.auth_user_id = auth.uid()
              )
        )
    );
