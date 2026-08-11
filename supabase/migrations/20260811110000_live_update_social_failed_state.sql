-- Honest publish-failure state for the live-update social loop.
-- Publish failures (route missing, provider error) previously stamped the
-- run terminal_status='published' with ok=True — unretryable and misleading.
-- Adds a 'failed' terminal state (retryable via admin publish) and keeps
-- 'proposed' from the earlier migration.
-- Idempotent: safe to replay in production.

alter table public.live_update_social_runs
    drop constraint if exists live_update_social_runs_terminal_status_check;

alter table public.live_update_social_runs
    add constraint live_update_social_runs_terminal_status_check
    check (terminal_status is null or terminal_status in (
        'draft', 'queued', 'published', 'skip', 'needs_review', 'proposed', 'failed'
    ));
