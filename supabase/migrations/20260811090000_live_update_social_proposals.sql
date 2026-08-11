-- Propose mode for the live-update social loop.
-- Adds the `proposals` JSONB column (idea proposals: theme + media strategy)
-- and widens the terminal_status check to include 'proposed'.
-- Idempotent: safe to replay in production.

alter table public.live_update_social_runs
    add column if not exists proposals jsonb;

-- Drop the old terminal_status check constraint (auto-named from the column
-- definition) and re-add it with 'proposed' allowed.
alter table public.live_update_social_runs
    drop constraint if exists live_update_social_runs_terminal_status_check;

alter table public.live_update_social_runs
    add constraint live_update_social_runs_terminal_status_check
    check (terminal_status is null or terminal_status in (
        'draft', 'queued', 'published', 'skip', 'needs_review', 'proposed'
    ));
