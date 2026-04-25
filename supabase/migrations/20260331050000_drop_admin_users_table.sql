-- Drop the unused admin_users table. Admin status is determined solely by
-- members.is_admin, which is what is_admin() now checks (since migration
-- 20260331040000). The admin_users table was never populated by any code
-- and is not referenced by any source code in arca-gidan or brain-of-bndc.

-- Drop any RLS policies first
DROP POLICY IF EXISTS "Admins read admin_users" ON public.admin_users;
DROP POLICY IF EXISTS "Admins mutate admin_users" ON public.admin_users;
DROP POLICY IF EXISTS "admin_hide_entries" ON public.competition_entries;

DROP TABLE IF EXISTS public.admin_users;
