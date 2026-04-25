-- Restore the admin_hide_entries policy that was accidentally dropped
-- by 20260331050000_drop_admin_users_table.sql.

DROP POLICY IF EXISTS admin_hide_entries ON public.competition_entries;

CREATE POLICY admin_hide_entries
    ON public.competition_entries FOR UPDATE
    TO authenticated
    USING (public.is_admin())
    WITH CHECK (public.is_admin());
