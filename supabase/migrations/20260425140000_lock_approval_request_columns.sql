-- Lock authenticated approval request edits to the columns used by the
-- self-editing UI. The approval_requests_update_self_pending RLS policy
-- constrains row ownership/status, but its WITH CHECK does not protect
-- operational columns such as posted_message_id, embed_dirty, and decision
-- metadata from row-owner updates.
REVOKE UPDATE ON public.approval_requests FROM authenticated;

GRANT UPDATE (bio_snapshot, attached_media_id, attached_resource_id)
ON public.approval_requests
TO authenticated;
