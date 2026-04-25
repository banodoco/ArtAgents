-- Bundle-mode posts migration
--
-- Sequenced AFTER 20260420220000_extend_posts_for_authoring.sql, which already
-- adds posts.admin_status, posts.cover_media_id, posts.published_at, and
-- media.source. This migration must not duplicate those columns.
--
-- Adds:
--   • post_bundles table (versioned static ZIP metadata per post)
--   • posts.render_mode + posts.active_bundle_version_id
--   • register_bundle_version / approve_bundle / reject_bundle RPCs
--   • Private post-bundles storage bucket + RLS
--   • Replaces the posts public-read policy with the canonical visibility
--     predicate (status='published' AND admin_status != 'Hidden').

SET search_path = public;

-- 1. post_bundles table ------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.post_bundles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES public.posts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    storage_prefix TEXT NOT NULL,
    manifest JSONB NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    file_count INTEGER NOT NULL CHECK (file_count > 0),
    sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected')),
    review_notes TEXT,
    uploaded_by UUID NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    UNIQUE (post_id, version),
    UNIQUE (post_id, sha256)
);

CREATE INDEX IF NOT EXISTS post_bundles_post_review_idx
    ON public.post_bundles (post_id, review_status, uploaded_at DESC);

-- 2. posts.render_mode + posts.active_bundle_version_id ---------------------

ALTER TABLE public.posts
    ADD COLUMN IF NOT EXISTS render_mode TEXT NOT NULL DEFAULT 'link'
        CHECK (render_mode IN ('link', 'markdown', 'bundle'));

ALTER TABLE public.posts
    ADD COLUMN IF NOT EXISTS active_bundle_version_id UUID
        REFERENCES public.post_bundles(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS posts_active_bundle_version_id_idx
    ON public.posts (active_bundle_version_id)
    WHERE active_bundle_version_id IS NOT NULL;

-- 3. RLS on post_bundles -----------------------------------------------------

ALTER TABLE public.post_bundles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Owners and admins read post_bundles" ON public.post_bundles;
CREATE POLICY "Owners and admins read post_bundles"
ON public.post_bundles
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.posts p
        JOIN public.members m ON m.member_id = p.member_id
        WHERE p.id = post_bundles.post_id
          AND (m.auth_user_id = auth.uid() OR public.is_admin())
    )
);

DROP POLICY IF EXISTS "Public read approved active post_bundles" ON public.post_bundles;
CREATE POLICY "Public read approved active post_bundles"
ON public.post_bundles
FOR SELECT
TO anon, authenticated
USING (
    review_status = 'approved'
    AND EXISTS (
        SELECT 1
        FROM public.posts p
        WHERE p.id = post_bundles.post_id
          AND p.active_bundle_version_id = post_bundles.id
          AND p.status = 'published'
          AND (p.admin_status IS NULL OR p.admin_status != 'Hidden')
    )
);

DROP POLICY IF EXISTS "Owners insert post_bundles" ON public.post_bundles;
CREATE POLICY "Owners insert post_bundles"
ON public.post_bundles
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.posts p
        JOIN public.members m ON m.member_id = p.member_id
        WHERE p.id = post_bundles.post_id
          AND (m.auth_user_id = auth.uid() OR public.is_admin())
    )
);

DROP POLICY IF EXISTS "Admins update post_bundles" ON public.post_bundles;
CREATE POLICY "Admins update post_bundles"
ON public.post_bundles
FOR UPDATE
TO authenticated
USING (public.is_admin())
WITH CHECK (public.is_admin());

-- 4. Replace posts public-read policy ---------------------------------------

DROP POLICY IF EXISTS "Public read published posts" ON public.posts;
CREATE POLICY "Public read published posts"
ON public.posts
FOR SELECT
USING (
    (
        status = 'published'
        AND (admin_status IS NULL OR admin_status != 'Hidden')
    )
    OR member_id IN (
        SELECT m.member_id
        FROM public.members m
        WHERE m.auth_user_id = auth.uid()
    )
    OR public.is_admin()
);

-- 5. SECURITY DEFINER RPCs ---------------------------------------------------

CREATE OR REPLACE FUNCTION public.register_bundle_version(
    p_post_id UUID,
    p_storage_prefix TEXT,
    p_manifest JSONB,
    p_size_bytes BIGINT,
    p_file_count INTEGER,
    p_sha256 TEXT,
    p_uploaded_by UUID
)
RETURNS public.post_bundles
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_post public.posts%ROWTYPE;
    v_next_version INTEGER;
    v_final_storage_prefix TEXT;
    v_bundle public.post_bundles%ROWTYPE;
BEGIN
    SELECT p.*
    INTO v_post
    FROM public.posts p
    JOIN public.members m ON m.member_id = p.member_id
    WHERE p.id = p_post_id
      AND (m.auth_user_id = p_uploaded_by OR public.is_admin(p_uploaded_by))
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'bundle post not found or caller is not allowed';
    END IF;

    SELECT COALESCE(MAX(version), 0) + 1
    INTO v_next_version
    FROM public.post_bundles
    WHERE post_id = p_post_id;

    v_final_storage_prefix := trim(trailing '/' FROM p_storage_prefix) || '/' || v_next_version::TEXT;

    INSERT INTO public.post_bundles (
        post_id, version, storage_prefix, manifest,
        size_bytes, file_count, sha256, uploaded_by
    )
    VALUES (
        p_post_id, v_next_version, v_final_storage_prefix, p_manifest,
        p_size_bytes, p_file_count, p_sha256, p_uploaded_by
    )
    RETURNING *
    INTO v_bundle;

    UPDATE public.posts
    SET render_mode = 'bundle'
    WHERE id = p_post_id;

    RETURN v_bundle;
END;
$$;

CREATE OR REPLACE FUNCTION public.approve_bundle(p_bundle_id UUID)
RETURNS public.post_bundles
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_post_id UUID;
    v_bundle public.post_bundles%ROWTYPE;
BEGIN
    IF NOT public.is_admin() THEN
        RAISE EXCEPTION 'admin only';
    END IF;

    UPDATE public.post_bundles
    SET review_status = 'approved',
        review_notes = NULL,
        reviewed_by = auth.uid(),
        reviewed_at = NOW()
    WHERE id = p_bundle_id
    RETURNING *
    INTO v_bundle;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'bundle not found';
    END IF;

    v_post_id := v_bundle.post_id;

    UPDATE public.posts
    SET active_bundle_version_id = v_bundle.id,
        render_mode = 'bundle'
    WHERE id = v_post_id;

    RETURN v_bundle;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_bundle(
    p_bundle_id UUID,
    p_review_notes TEXT
)
RETURNS public.post_bundles
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_bundle public.post_bundles%ROWTYPE;
BEGIN
    IF NOT public.is_admin() THEN
        RAISE EXCEPTION 'admin only';
    END IF;

    UPDATE public.post_bundles
    SET review_status = 'rejected',
        review_notes = p_review_notes,
        reviewed_by = auth.uid(),
        reviewed_at = NOW()
    WHERE id = p_bundle_id
    RETURNING *
    INTO v_bundle;

    RETURN v_bundle;
END;
$$;

-- 6. GRANTs on RPCs ----------------------------------------------------------

REVOKE ALL ON FUNCTION public.register_bundle_version(UUID, TEXT, JSONB, BIGINT, INTEGER, TEXT, UUID)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.register_bundle_version(UUID, TEXT, JSONB, BIGINT, INTEGER, TEXT, UUID)
    TO service_role;

REVOKE ALL ON FUNCTION public.approve_bundle(UUID)
    FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.approve_bundle(UUID)
    TO authenticated;

REVOKE ALL ON FUNCTION public.reject_bundle(UUID, TEXT)
    FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.reject_bundle(UUID, TEXT)
    TO authenticated;

-- 7. Private post-bundles storage bucket ------------------------------------

INSERT INTO storage.buckets (id, name, public)
VALUES ('post-bundles', 'post-bundles', false)
ON CONFLICT (id) DO UPDATE SET public = false;

DROP POLICY IF EXISTS "Service role writes post-bundles objects" ON storage.objects;
CREATE POLICY "Service role writes post-bundles objects"
ON storage.objects
FOR ALL
TO service_role
USING (bucket_id = 'post-bundles')
WITH CHECK (bucket_id = 'post-bundles');

DROP POLICY IF EXISTS "Owners read post-bundles objects" ON storage.objects;
CREATE POLICY "Owners read post-bundles objects"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'post-bundles'
    AND EXISTS (
        SELECT 1
        FROM public.post_bundles pb
        JOIN public.posts p ON p.id = pb.post_id
        JOIN public.members m ON m.member_id = p.member_id
        WHERE name LIKE pb.storage_prefix || '/%'
          AND (m.auth_user_id = auth.uid() OR public.is_admin())
    )
);

COMMENT ON TABLE public.post_bundles IS
    'Versioned static bundle payload (post.json + static assets) uploaded per post. '
    'Public-read gated by four conditions: review_status=approved AND parent post '
    'published AND posts.active_bundle_version_id=self AND admin_status != Hidden.';
