ALTER TABLE public.pending_intros
  ADD COLUMN IF NOT EXISTS approval_request_id uuid
  REFERENCES public.approval_requests(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS pending_intros_approval_request_id_uniq
  ON public.pending_intros (approval_request_id)
  WHERE approval_request_id IS NOT NULL;

ALTER TABLE public.approval_requests
  ADD COLUMN IF NOT EXISTS posted_message_id bigint NULL;

CREATE INDEX IF NOT EXISTS approval_requests_pending_for_post_idx
  ON public.approval_requests (created_at)
  WHERE status='pending' AND posted_message_id IS NULL;
