-- Backfill admin_users from members.is_admin for any that are missing
INSERT INTO public.admin_users (user_id)
SELECT auth_user_id
FROM public.members
WHERE is_admin = true
  AND auth_user_id IS NOT NULL
  AND auth_user_id NOT IN (SELECT user_id FROM public.admin_users)
ON CONFLICT DO NOTHING;
