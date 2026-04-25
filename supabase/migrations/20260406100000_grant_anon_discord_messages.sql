-- Grant anon/authenticated SELECT on discord_messages and posts
-- so the new sb_publishable_ API key can read them (RLS policy already allows it,
-- but the new key format requires explicit GRANTs)
GRANT SELECT ON public.discord_messages TO anon, authenticated;
GRANT SELECT ON public.posts TO anon, authenticated;
