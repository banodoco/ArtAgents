CREATE TABLE public.approval_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id text NOT NULL,
  bio_snapshot text,
  attached_media_id uuid REFERENCES public.media(id) ON DELETE CASCADE,
  attached_resource_id uuid REFERENCES public.assets(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz,
  decided_by uuid REFERENCES auth.users(id),
  decision_note text,
  CHECK (num_nonnulls(attached_media_id, attached_resource_id) = 1)
);

CREATE UNIQUE INDEX approval_requests_one_pending_per_member
  ON public.approval_requests (member_id)
  WHERE status = 'pending';

ALTER TABLE public.approval_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY approval_requests_insert_self
  ON public.approval_requests
  FOR INSERT
  TO authenticated
  WITH CHECK (
    status = 'pending'
    AND member_id = (
      SELECT p.discord_id
      FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
    )
    AND (
      attached_media_id IS NULL
      OR EXISTS (
        SELECT 1
        FROM public.media m
        WHERE m.id = attached_media_id
          AND m.member_id::text = approval_requests.member_id
      )
    )
    AND (
      attached_resource_id IS NULL
      OR EXISTS (
        SELECT 1
        FROM public.assets a
        WHERE a.id = attached_resource_id
          AND a.member_id::text = approval_requests.member_id
      )
    )
  );

CREATE POLICY approval_requests_select_self_or_admin
  ON public.approval_requests
  FOR SELECT
  TO authenticated
  USING (
    member_id = (
      SELECT p.discord_id
      FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
    )
    OR public.is_admin((SELECT auth.uid()))
  );

CREATE POLICY approval_requests_update_admin
  ON public.approval_requests
  FOR UPDATE
  TO authenticated
  USING (public.is_admin((SELECT auth.uid())))
  WITH CHECK (public.is_admin((SELECT auth.uid())));

GRANT SELECT, INSERT, UPDATE ON public.approval_requests TO authenticated;
