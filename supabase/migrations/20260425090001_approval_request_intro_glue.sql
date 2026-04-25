CREATE OR REPLACE FUNCTION public.claim_pending_approval_requests(p_limit int DEFAULT 25)
RETURNS SETOF public.approval_requests
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
  SELECT *
  FROM public.approval_requests
  WHERE status = 'pending'
    AND posted_message_id IS NULL
  ORDER BY created_at
  FOR UPDATE SKIP LOCKED
  LIMIT p_limit
$$;

COMMENT ON FUNCTION public.claim_pending_approval_requests(int)
IS 'MP2: SKIP LOCKED batch claim of pending approval_requests awaiting #introductions post. Single-replica deployment: in-process asyncio.Lock provides additional serialization.';

REVOKE EXECUTE ON FUNCTION public.claim_pending_approval_requests(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_pending_approval_requests(int) TO service_role;

CREATE OR REPLACE FUNCTION public.f_approval_request_on_intro_approved()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
DECLARE
  v_media_id uuid;
  v_asset_id uuid;
BEGIN
  IF NEW.approval_request_id IS NULL THEN
    RETURN NEW;
  END IF;

  UPDATE public.approval_requests
  SET status = 'approved',
      decided_at = NOW()
  WHERE id = NEW.approval_request_id
    AND status <> 'approved'
  RETURNING attached_media_id, attached_resource_id
  INTO v_media_id, v_asset_id;

  IF v_media_id IS NOT NULL THEN
    UPDATE public.media
    SET admin_status = 'Listed'
    WHERE id = v_media_id
      AND admin_status = 'Hidden';
  END IF;

  IF v_asset_id IS NOT NULL THEN
    UPDATE public.assets
    SET status = 'published'
    WHERE id = v_asset_id
      AND status = 'draft';
  END IF;

  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.f_approval_request_on_intro_approved()
IS 'MP2: back-propagate Discord intro approvals to approval_requests and attached public content state.';

DROP TRIGGER IF EXISTS trg_approval_request_on_intro_approved ON public.pending_intros;

CREATE TRIGGER trg_approval_request_on_intro_approved
AFTER UPDATE OF status ON public.pending_intros
FOR EACH ROW
WHEN (OLD.status = 'pending' AND NEW.status = 'approved' AND NEW.approval_request_id IS NOT NULL)
EXECUTE FUNCTION public.f_approval_request_on_intro_approved();
