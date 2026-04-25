-- Vibe Ship It auto-approve migration
--
-- Problem: `register_bundle_version` (20260421000000_bundle_mode_posts.sql)
-- inserts post_bundles with review_status='pending' and does NOT set
-- posts.active_bundle_version_id. The consumer (BundleView.tsx) gates on
-- active_bundle_version_id being non-NULL, so an author who ships via
-- `process-bundle` sees a "no active bundle version" placeholder on their
-- own post until an admin runs `approve_bundle`.
--
-- Fix: when the uploader IS the post's author, auto-approve the bundle
-- and promote it to active in the same transaction. When an admin uploads
-- on someone else's behalf, preserve the existing pending-review behavior
-- so moderation still applies to non-author uploads.
--
-- The admin flows (`approve_bundle`, `reject_bundle`) are unchanged; admins
-- can still reject/unpublish a bundle after the author has self-published.
--
-- Implementation: replace `register_bundle_version` with a version that
-- conditionally sets review_status, reviewed_by, reviewed_at, and
-- posts.active_bundle_version_id when the uploader is the author.

SET search_path = public;

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
    v_owner_auth_id UUID;
    v_is_author BOOLEAN;
    v_review_status TEXT;
    v_reviewed_by UUID;
    v_reviewed_at TIMESTAMPTZ;
BEGIN
    SELECT p.*
    INTO v_post
    FROM public.posts p
    JOIN public.members m ON m.member_id = p.member_id
    WHERE p.id = p_post_id
      AND (m.auth_user_id = p_uploaded_by OR public.is_admin(p_uploaded_by))
    FOR UPDATE OF p;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'bundle post not found or caller is not allowed';
    END IF;

    -- Resolve the post's author auth_user_id so we can decide whether the
    -- uploader is the author (self-publish fast-path) or an admin acting
    -- on someone else's post (stay pending-review).
    SELECT m.auth_user_id
    INTO v_owner_auth_id
    FROM public.members m
    WHERE m.member_id = v_post.member_id;

    SELECT COALESCE(MAX(version), 0) + 1
    INTO v_next_version
    FROM public.post_bundles
    WHERE post_id = p_post_id;

    v_final_storage_prefix := trim(trailing '/' FROM p_storage_prefix) || '/' || v_next_version::TEXT;

    -- Author self-publish fast-path: if the uploader owns the post, stamp
    -- the bundle as approved and self-reviewed. Admin-uploading-on-behalf
    -- of someone else falls through to the default 'pending' review state
    -- so the existing moderation path still runs.
    v_is_author := (v_owner_auth_id IS NOT NULL AND v_owner_auth_id = p_uploaded_by);

    IF v_is_author THEN
        v_review_status := 'approved';
        v_reviewed_by := p_uploaded_by;
        v_reviewed_at := NOW();
    ELSE
        v_review_status := 'pending';
        v_reviewed_by := NULL;
        v_reviewed_at := NULL;
    END IF;

    INSERT INTO public.post_bundles (
        post_id, version, storage_prefix, manifest,
        size_bytes, file_count, sha256, uploaded_by,
        review_status, reviewed_by, reviewed_at
    )
    VALUES (
        p_post_id, v_next_version, v_final_storage_prefix, p_manifest,
        p_size_bytes, p_file_count, p_sha256, p_uploaded_by,
        v_review_status, v_reviewed_by, v_reviewed_at
    )
    RETURNING *
    INTO v_bundle;

    IF v_is_author THEN
        UPDATE public.posts
        SET render_mode = 'bundle',
            active_bundle_version_id = v_bundle.id
        WHERE id = p_post_id;
    ELSE
        UPDATE public.posts
        SET render_mode = 'bundle'
        WHERE id = p_post_id;
    END IF;

    RETURN v_bundle;
END;
$$;

-- Re-assert grants (CREATE OR REPLACE preserves them but be explicit).
REVOKE ALL ON FUNCTION public.register_bundle_version(UUID, TEXT, JSONB, BIGINT, INTEGER, TEXT, UUID)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.register_bundle_version(UUID, TEXT, JSONB, BIGINT, INTEGER, TEXT, UUID)
    TO service_role;

COMMENT ON FUNCTION public.register_bundle_version(UUID, TEXT, JSONB, BIGINT, INTEGER, TEXT, UUID) IS
    'Registers a new post_bundles version. If the uploader is the post''s author, '
    'the bundle is auto-approved and promoted to active_bundle_version_id in the '
    'same transaction (Vibe Ship It / author-initiated publish). If the uploader '
    'is an admin acting on someone else''s post, the bundle stays pending for '
    'review.';
