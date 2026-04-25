-- Hide Discord-imported assets whose thread OP is older than 90 days.
-- Operator intent: "only show resource posts from the last 90 days."
-- We flip is_hidden = true instead of deleting so the rows are recoverable
-- if the window widens later. The public feeds already exclude is_hidden,
-- so these disappear from /2RP immediately.

UPDATE public.assets AS a
SET is_hidden = TRUE
FROM public.discord_messages AS m
WHERE a.source = 'discord_import'
  AND a.is_hidden = FALSE
  AND m.message_id = a.discord_thread_id
  AND m.created_at < NOW() - INTERVAL '90 days';
