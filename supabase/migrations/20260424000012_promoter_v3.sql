-- Promoter v3: loosen reaction threshold from 5 -> 3, and stub-insert a
-- minimal members row for OP authors who don't exist yet so the
-- `mem.member_id IS NULL` gate never silently drops an otherwise-eligible OP.
-- The regular member sync will overwrite the stub row's username/avatar
-- fields on its next pass, so this is safe to leave as `username = 'user_'
-- || author_id`. Same 90-day OP-date window as v2 — nothing changes there.

CREATE OR REPLACE FUNCTION internal.discord_promote_resources(dry_run BOOLEAN DEFAULT FALSE)
RETURNS TABLE(
    channel_id BIGINT,
    assets_inserted INT,
    assets_updated INT,
    comments_inserted INT,
    comments_updated INT,
    jobs_enqueued INT,
    members_missing INT,
    comment_media_marked_deleted INT,
    comments_marked_deleted INT,
    dry_run_result BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_channels BIGINT[] := ARRAY[
        1149372684220768367::BIGINT,
        1275200992136400967::BIGINT,
        1373291419434877078::BIGINT,
        1457981813120176138::BIGINT,
        1472633200491626526::BIGINT
    ];
    v_ch BIGINT;
    v_ai INT := 0;
    v_au INT := 0;
    v_ci INT := 0;
    v_cu INT := 0;
    v_j INT := 0;
    v_mm INT := 0;
    v_cmd INT := 0;
    v_cmd_assets INT := 0;
    v_cd INT := 0;
BEGIN
    FOREACH v_ch IN ARRAY v_channels LOOP
        v_ai := 0;
        v_au := 0;
        v_ci := 0;
        v_cu := 0;
        v_j := 0;
        v_mm := 0;
        v_cmd := 0;
        v_cmd_assets := 0;
        v_cd := 0;

        BEGIN
            IF NOT $1 THEN
                INSERT INTO public.members (member_id, username)
                SELECT DISTINCT m.author_id, 'user_' || m.author_id::text
                FROM public.discord_messages AS m
                LEFT JOIN public.members AS mem ON mem.member_id = m.author_id
                WHERE m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND m.created_at >= NOW() - INTERVAL '90 days'
                  AND mem.member_id IS NULL
                  AND NOT EXISTS (SELECT 1 FROM public.assets AS a WHERE a.discord_thread_id = m.message_id)
                ON CONFLICT (member_id) DO NOTHING;
            END IF;

            IF NOT $1 THEN
                INSERT INTO public.system_logs (logger_name, level, message, extra)
                SELECT
                    'discord_resource_promoter',
                    'warning',
                    'skipping OP: missing member',
                    jsonb_build_object(
                        'channel_id', v_ch,
                        'message_id', m.message_id,
                        'author_id', m.author_id
                    )
                FROM public.discord_messages AS m
                LEFT JOIN public.members AS mem
                  ON mem.member_id = m.author_id
                WHERE m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND m.created_at >= NOW() - INTERVAL '90 days'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.assets AS a
                      WHERE a.discord_thread_id = m.message_id
                  )
                  AND mem.member_id IS NULL;

                GET DIAGNOSTICS v_mm = ROW_COUNT;
            ELSE
                SELECT COUNT(*)
                INTO v_mm
                FROM public.discord_messages AS m
                LEFT JOIN public.members AS mem
                  ON mem.member_id = m.author_id
                WHERE m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND m.created_at >= NOW() - INTERVAL '90 days'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.assets AS a
                      WHERE a.discord_thread_id = m.message_id
                  )
                  AND mem.member_id IS NULL;
            END IF;

            IF NOT $1 THEN
                INSERT INTO public.assets (
                    id,
                    name,
                    description,
                    type,
                    member_id,
                    admin_status,
                    source,
                    discord_guild_id,
                    discord_channel_id,
                    discord_thread_id,
                    reactions_reached_threshold_at,
                    imported_at,
                    last_synced_at
                )
                SELECT
                    pg_catalog.gen_random_uuid(),
                    COALESCE(
                        NULLIF(BTRIM(c.channel_name), ''),
                        NULLIF(LEFT(split_part(COALESCE(m.content, ''), E'\n', 1), 120), ''),
                        'Discord resource ' || m.message_id::TEXT
                    ),
                    m.content,
                    CASE m.channel_id
                        WHEN 1149372684220768367 THEN 'workflow'
                        ELSE 'lora'
                    END,
                    m.author_id,
                    'Listed',
                    'discord_import',
                    m.guild_id,
                    m.channel_id,
                    m.message_id,
                    NOW(),
                    NOW(),
                    NOW()
                FROM public.discord_messages AS m
                LEFT JOIN public.discord_channels AS c
                  ON c.channel_id = m.message_id
                 AND c.channel_type = 'thread'
                WHERE m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND m.created_at >= NOW() - INTERVAL '90 days'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.assets AS a
                      WHERE a.discord_thread_id = m.message_id
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM public.members AS mem
                      WHERE mem.member_id = m.author_id
                  )
                ON CONFLICT DO NOTHING;

                GET DIAGNOSTICS v_ai = ROW_COUNT;
            ELSE
                SELECT COUNT(*)
                INTO v_ai
                FROM public.discord_messages AS m
                WHERE m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND m.created_at >= NOW() - INTERVAL '90 days'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.assets AS a
                      WHERE a.discord_thread_id = m.message_id
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM public.members AS mem
                      WHERE mem.member_id = m.author_id
                  );
            END IF;

            IF NOT $1 THEN
                UPDATE public.assets AS a
                SET
                    name = COALESCE(
                        NULLIF(BTRIM(c.channel_name), ''),
                        NULLIF(LEFT(split_part(COALESCE(m.content, ''), E'\n', 1), 120), ''),
                        'Discord resource ' || m.message_id::TEXT
                    ),
                    description = m.content,
                    type = CASE m.channel_id
                        WHEN 1149372684220768367 THEN 'workflow'
                        ELSE 'lora'
                    END,
                    member_id = m.author_id,
                    discord_guild_id = m.guild_id,
                    discord_channel_id = m.channel_id
                FROM public.discord_messages AS m
                LEFT JOIN public.discord_channels AS c
                  ON c.channel_id = m.message_id
                 AND c.channel_type = 'thread'
                WHERE a.discord_thread_id = m.message_id
                  AND a.source = 'discord_import'
                  AND a.discord_channel_id = v_ch
                  AND m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND a.description IS DISTINCT FROM m.content;

                GET DIAGNOSTICS v_au = ROW_COUNT;
            ELSE
                SELECT COUNT(*)
                INTO v_au
                FROM public.assets AS a
                JOIN public.discord_messages AS m
                  ON m.message_id = a.discord_thread_id
                WHERE a.source = 'discord_import'
                  AND a.discord_channel_id = v_ch
                  AND m.channel_id = v_ch
                  AND m.message_id = m.thread_id
                  AND m.reaction_count >= 3
                  AND m.is_deleted = FALSE
                  AND a.description IS DISTINCT FROM m.content;
            END IF;

            IF NOT $1 THEN
                INSERT INTO public.asset_comments (
                    id,
                    asset_id,
                    discord_message_id,
                    discord_thread_id,
                    discord_guild_id,
                    author_member_id,
                    content,
                    reply_to_discord_message_id,
                    reaction_count,
                    discord_created_at,
                    discord_edited_at,
                    is_deleted
                )
                SELECT
                    pg_catalog.gen_random_uuid(),
                    a.id,
                    m.message_id,
                    m.thread_id,
                    m.guild_id,
                    m.author_id,
                    m.content,
                    m.reference_id,
                    m.reaction_count,
                    m.created_at,
                    m.edited_at,
                    FALSE
                FROM public.discord_messages AS m
                JOIN public.assets AS a
                  ON a.discord_thread_id = m.thread_id
                 AND a.discord_channel_id = v_ch
                 AND a.source = 'discord_import'
                WHERE m.message_id <> m.thread_id
                  AND m.is_deleted = FALSE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.asset_comments AS c
                      WHERE c.discord_message_id = m.message_id
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM public.members AS mem
                      WHERE mem.member_id = m.author_id
                  )
                ON CONFLICT DO NOTHING;

                GET DIAGNOSTICS v_ci = ROW_COUNT;
            ELSE
                SELECT COUNT(*)
                INTO v_ci
                FROM public.discord_messages AS m
                JOIN public.assets AS a
                  ON a.discord_thread_id = m.thread_id
                 AND a.discord_channel_id = v_ch
                 AND a.source = 'discord_import'
                WHERE m.message_id <> m.thread_id
                  AND m.is_deleted = FALSE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.asset_comments AS c
                      WHERE c.discord_message_id = m.message_id
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM public.members AS mem
                      WHERE mem.member_id = m.author_id
                  );
            END IF;

            IF NOT $1 THEN
                UPDATE public.asset_comments AS c
                SET
                    content = m.content,
                    reaction_count = m.reaction_count,
                    discord_edited_at = m.edited_at,
                    reply_to_discord_message_id = m.reference_id,
                    author_member_id = m.author_id,
                    discord_guild_id = m.guild_id,
                    updated_at = NOW()
                FROM public.discord_messages AS m,
                     public.assets AS a
                WHERE c.discord_message_id = m.message_id
                  AND a.id = c.asset_id
                  AND a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND (
                      c.content IS DISTINCT FROM m.content
                      OR c.reaction_count IS DISTINCT FROM m.reaction_count
                      OR c.discord_edited_at IS DISTINCT FROM m.edited_at
                      OR c.reply_to_discord_message_id IS DISTINCT FROM m.reference_id
                      OR c.author_member_id IS DISTINCT FROM m.author_id
                      OR c.discord_guild_id IS DISTINCT FROM m.guild_id
                  );

                GET DIAGNOSTICS v_cu = ROW_COUNT;

                UPDATE public.asset_comments AS c
                SET
                    reply_to_comment_id = parent.id,
                    updated_at = NOW()
                FROM public.asset_comments AS parent,
                     public.assets AS a
                WHERE a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND a.id = c.asset_id
                  AND parent.asset_id = c.asset_id
                  AND c.reply_to_discord_message_id = parent.discord_message_id
                  AND c.reply_to_comment_id IS DISTINCT FROM parent.id;
            ELSE
                SELECT COUNT(*)
                INTO v_cu
                FROM public.asset_comments AS c
                JOIN public.discord_messages AS m
                  ON m.message_id = c.discord_message_id
                JOIN public.assets AS a
                  ON a.id = c.asset_id
                WHERE a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND (
                      c.content IS DISTINCT FROM m.content
                      OR c.reaction_count IS DISTINCT FROM m.reaction_count
                      OR c.discord_edited_at IS DISTINCT FROM m.edited_at
                      OR c.reply_to_discord_message_id IS DISTINCT FROM m.reference_id
                      OR c.author_member_id IS DISTINCT FROM m.author_id
                      OR c.discord_guild_id IS DISTINCT FROM m.guild_id
                  );
            END IF;

            IF NOT $1 THEN
                WITH attachment_jobs AS (
                    SELECT
                        ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1])::BIGINT AS discord_attachment_id,
                        m.message_id AS discord_message_id,
                        'asset_media'::TEXT AS target_kind,
                        a.id AS target_id,
                        att.attachment->>'url' AS original_cdn_url,
                        att.attachment->>'filename' AS filename,
                        att.attachment->>'content_type' AS content_type,
                        NULLIF(att.attachment->>'size', '')::BIGINT AS size_bytes
                    FROM public.discord_messages AS m
                    JOIN public.assets AS a
                      ON a.discord_thread_id = m.message_id
                     AND a.discord_channel_id = v_ch
                     AND a.source = 'discord_import'
                    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) WITH ORDINALITY AS att(attachment, ordinality)
                    WHERE m.message_id = m.thread_id

                    UNION ALL

                    SELECT
                        ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1])::BIGINT AS discord_attachment_id,
                        m.message_id AS discord_message_id,
                        'asset_comment_media'::TEXT AS target_kind,
                        c.id AS target_id,
                        att.attachment->>'url' AS original_cdn_url,
                        att.attachment->>'filename' AS filename,
                        att.attachment->>'content_type' AS content_type,
                        NULLIF(att.attachment->>'size', '')::BIGINT AS size_bytes
                    FROM public.discord_messages AS m
                    JOIN public.asset_comments AS c
                      ON c.discord_message_id = m.message_id
                    JOIN public.assets AS a
                      ON a.id = c.asset_id
                     AND a.discord_channel_id = v_ch
                     AND a.source = 'discord_import'
                    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) WITH ORDINALITY AS att(attachment, ordinality)
                )
                INSERT INTO public.media_import_jobs (
                    discord_attachment_id,
                    discord_message_id,
                    target_kind,
                    target_id,
                    original_cdn_url,
                    filename,
                    content_type,
                    size_bytes
                )
                SELECT
                    j.discord_attachment_id,
                    j.discord_message_id,
                    j.target_kind,
                    j.target_id,
                    j.original_cdn_url,
                    j.filename,
                    j.content_type,
                    j.size_bytes
                FROM attachment_jobs AS j
                WHERE j.discord_attachment_id IS NOT NULL
                ON CONFLICT DO NOTHING;

                GET DIAGNOSTICS v_j = ROW_COUNT;
            ELSE
                WITH attachment_jobs AS (
                    SELECT
                        ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1])::BIGINT AS discord_attachment_id
                    FROM public.discord_messages AS m
                    JOIN public.assets AS a
                      ON a.discord_thread_id = m.message_id
                     AND a.discord_channel_id = v_ch
                     AND a.source = 'discord_import'
                    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) WITH ORDINALITY AS att(attachment, ordinality)
                    WHERE m.message_id = m.thread_id

                    UNION ALL

                    SELECT
                        ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1])::BIGINT AS discord_attachment_id
                    FROM public.discord_messages AS m
                    JOIN public.asset_comments AS c
                      ON c.discord_message_id = m.message_id
                    JOIN public.assets AS a
                      ON a.id = c.asset_id
                     AND a.discord_channel_id = v_ch
                     AND a.source = 'discord_import'
                    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) WITH ORDINALITY AS att(attachment, ordinality)
                )
                SELECT COUNT(*)
                INTO v_j
                FROM attachment_jobs AS j
                WHERE j.discord_attachment_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.media_import_jobs AS mij
                      WHERE mij.discord_attachment_id = j.discord_attachment_id
                  );
            END IF;

            IF NOT $1 THEN
                UPDATE public.asset_comment_media AS acm
                SET is_deleted = TRUE
                FROM public.asset_comments AS c,
                     public.assets AS a,
                     public.media AS md,
                     public.discord_messages AS m
                WHERE acm.comment_id = c.id
                  AND c.asset_id = a.id
                  AND acm.media_id = md.id
                  AND c.discord_message_id = m.message_id
                  AND a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND acm.is_deleted = FALSE
                  AND COALESCE(md.metadata->>'discord_attachment_id', '') <> ''
                  AND NOT EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) AS att(attachment)
                      WHERE ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1]) = md.metadata->>'discord_attachment_id'
                  );

                GET DIAGNOSTICS v_cmd = ROW_COUNT;

                UPDATE public.asset_media AS am
                SET is_deleted = TRUE
                FROM public.assets AS a,
                     public.media AS md,
                     public.discord_messages AS m
                WHERE am.asset_id = a.id
                  AND am.media_id = md.id
                  AND a.discord_thread_id = m.message_id
                  AND a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND am.is_deleted = FALSE
                  AND COALESCE(md.metadata->>'discord_attachment_id', '') <> ''
                  AND NOT EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) AS att(attachment)
                      WHERE ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1]) = md.metadata->>'discord_attachment_id'
                  );

                GET DIAGNOSTICS v_cmd_assets = ROW_COUNT;
                v_cmd := v_cmd + v_cmd_assets;
            ELSE
                SELECT COUNT(*)
                INTO v_cmd
                FROM (
                    SELECT acm.comment_id::TEXT
                    FROM public.asset_comment_media AS acm
                    JOIN public.asset_comments AS c
                      ON c.id = acm.comment_id
                    JOIN public.assets AS a
                      ON a.id = c.asset_id
                    JOIN public.media AS md
                      ON md.id = acm.media_id
                    JOIN public.discord_messages AS m
                      ON m.message_id = c.discord_message_id
                    WHERE a.discord_channel_id = v_ch
                      AND a.source = 'discord_import'
                      AND acm.is_deleted = FALSE
                      AND COALESCE(md.metadata->>'discord_attachment_id', '') <> ''
                      AND NOT EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) AS att(attachment)
                          WHERE ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1]) = md.metadata->>'discord_attachment_id'
                      )

                    UNION ALL

                    SELECT am.id::TEXT
                    FROM public.asset_media AS am
                    JOIN public.assets AS a
                      ON a.id = am.asset_id
                    JOIN public.media AS md
                      ON md.id = am.media_id
                    JOIN public.discord_messages AS m
                      ON m.message_id = a.discord_thread_id
                    WHERE a.discord_channel_id = v_ch
                      AND a.source = 'discord_import'
                      AND am.is_deleted = FALSE
                      AND COALESCE(md.metadata->>'discord_attachment_id', '') <> ''
                      AND NOT EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements(COALESCE(m.attachments, '[]'::jsonb)) AS att(attachment)
                          WHERE ((regexp_match(COALESCE(att.attachment->>'url', ''), '/attachments/\d+/(\d+)/'))[1]) = md.metadata->>'discord_attachment_id'
                      )
                ) AS removed_links;
            END IF;

            IF NOT $1 THEN
                UPDATE public.asset_comments AS c
                SET
                    is_deleted = TRUE,
                    updated_at = NOW()
                FROM public.assets AS a,
                     public.discord_messages AS m
                WHERE c.asset_id = a.id
                  AND c.discord_message_id = m.message_id
                  AND a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND c.is_deleted = FALSE
                  AND m.is_deleted = TRUE;

                GET DIAGNOSTICS v_cd = ROW_COUNT;
            ELSE
                SELECT COUNT(*)
                INTO v_cd
                FROM public.asset_comments AS c
                JOIN public.assets AS a
                  ON a.id = c.asset_id
                JOIN public.discord_messages AS m
                  ON m.message_id = c.discord_message_id
                WHERE a.discord_channel_id = v_ch
                  AND a.source = 'discord_import'
                  AND c.is_deleted = FALSE
                  AND m.is_deleted = TRUE;
            END IF;

            INSERT INTO public.system_logs (logger_name, level, message, extra)
            VALUES (
                'discord_resource_promoter',
                'info',
                CASE WHEN $1 THEN 'dry-run summary' ELSE 'channel sync summary' END,
                jsonb_build_object(
                    'dry_run', $1,
                    'channel_id', v_ch,
                    'assets_inserted', v_ai,
                    'assets_updated', v_au,
                    'comments_inserted', v_ci,
                    'comments_updated', v_cu,
                    'jobs_enqueued', v_j,
                    'members_missing', v_mm,
                    'comment_media_marked_deleted', v_cmd,
                    'comments_marked_deleted', v_cd
                )
            );

            IF $1 THEN
                RAISE NOTICE 'discord_resource_promoter dry_run channel=% assets_inserted=% assets_updated=% comments_inserted=% comments_updated=% jobs_enqueued=% members_missing=% comment_media_marked_deleted=% comments_marked_deleted=%',
                    v_ch, v_ai, v_au, v_ci, v_cu, v_j, v_mm, v_cmd, v_cd;
            ELSE
                UPDATE public.assets
                SET last_synced_at = NOW()
                WHERE discord_channel_id = v_ch
                  AND source = 'discord_import';
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                INSERT INTO public.system_logs (logger_name, level, message, extra)
                VALUES (
                    'discord_resource_promoter',
                    'error',
                    SQLERRM,
                    jsonb_build_object(
                        'channel_id', v_ch,
                        'dry_run', $1,
                        'sqlstate', SQLSTATE
                    )
                );
        END;

        channel_id := v_ch;
        assets_inserted := COALESCE(v_ai, 0);
        assets_updated := COALESCE(v_au, 0);
        comments_inserted := COALESCE(v_ci, 0);
        comments_updated := COALESCE(v_cu, 0);
        jobs_enqueued := COALESCE(v_j, 0);
        members_missing := COALESCE(v_mm, 0);
        comment_media_marked_deleted := COALESCE(v_cmd, 0);
        comments_marked_deleted := COALESCE(v_cd, 0);
        dry_run_result := $1;
        RETURN NEXT;
    END LOOP;
END;
$$;
