CREATE INDEX IF NOT EXISTS discord_messages_resource_op_idx
    ON public.discord_messages (channel_id, reaction_count DESC)
    WHERE message_id = thread_id
      AND is_deleted = FALSE;
