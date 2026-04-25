import { createClient } from 'npm:@supabase/supabase-js@2';
const JSON_HEADERS = {
  'Content-Type': 'application/json'
};
const IMPORTER_NAME = 'discord_media_importer';
const USER_UPLOADS_BUCKET = 'user-uploads';
const STORAGE_PREFIX = 'discord-imports';
const JOB_BATCH_SIZE = 10;
const JOB_LOCK_MINUTES = 10;
const JOB_MAX_ATTEMPTS = 5;
const WALL_CLOCK_BUDGET_MS = 400_000;
const DOWNLOAD_URL_TTL_SECONDS = 60 * 60;
const COMMENT_MEDIA_CLASSIFICATION = 'discord-comment';
const ASSET_MEDIA_CLASSIFICATION = 'submission';
const MEDIA_SOURCE = 'post';
function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: JSON_HEADERS
  });
}
function nowIso() {
  return new Date().toISOString();
}
function getServiceRoleKey() {
  return Deno.env.get('SB_SECRET_KEY') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? null;
}
function sanitizeFilename(filename) {
  return filename.replace(/[^a-zA-Z0-9._-]+/g, '-');
}
function parseDiscordAttachmentId(value) {
  if (!value) return null;
  const trimmed = value.trim();
  return /^\d+$/.test(trimmed) ? trimmed : null;
}
function extractExpiryMs(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    const ex = parsed.searchParams.get('ex');
    if (!ex) return null;
    const seconds = Number.parseInt(ex, 16);
    if (Number.isNaN(seconds)) return null;
    return seconds * 1000;
  } catch  {
    return null;
  }
}
function isDiscordUrlStillFresh(url) {
  const expiryMs = extractExpiryMs(url);
  if (!expiryMs) return false;
  return expiryMs > Date.now();
}
function isGif(contentType, filename) {
  if (contentType === 'image/gif') return true;
  return Boolean(filename?.toLowerCase().endsWith('.gif'));
}
function getUploadKind(contentType, filename) {
  if (contentType?.startsWith('video/') || isGif(contentType, filename)) return 'video';
  if (contentType?.startsWith('image/')) return 'image';
  return 'other';
}
function getMediaType(contentType, filename) {
  const kind = getUploadKind(contentType, filename);
  if (kind === 'video') return 'video';
  if (kind === 'image') return 'image';
  return contentType ?? 'file';
}
async function logSystem(supabase, level, message, extra) {
  const { error } = await supabase.from('system_logs').insert({
    logger_name: IMPORTER_NAME,
    level,
    message,
    extra
  });
  if (error) {
    console.error(`[${IMPORTER_NAME}] failed to write system log`, error.message, extra);
  }
}
async function fetchDiscordMessage(token, channelId, messageId) {
  const response = await fetch(`https://discord.com/api/v10/channels/${channelId}/messages/${messageId}`, {
    headers: {
      Authorization: `Bot ${token}`,
      'Content-Type': 'application/json'
    }
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Discord API ${response.status}: ${await response.text()}`);
  }
  return await response.json();
}
async function refreshAttachmentIfNeeded(supabase, discordToken, message, attachmentId, fallbackAttachment) {
  if (fallbackAttachment?.url && isDiscordUrlStillFresh(fallbackAttachment.url)) {
    return {
      attachment: fallbackAttachment
    };
  }
  const channelIds = [
    message.channel_id,
    message.thread_id
  ].filter((value)=>Boolean(value));
  for (const channelId of channelIds){
    const refreshed = await fetchDiscordMessage(discordToken, channelId, message.message_id);
    if (!refreshed?.attachments?.length) continue;
    const matched = refreshed.attachments.find((attachment)=>attachment.id === attachmentId);
    if (!matched) continue;
    const attachmentsToPersist = refreshed.attachments.map((attachment)=>({
        id: attachment.id,
        filename: attachment.filename,
        url: attachment.url,
        proxy_url: attachment.proxy_url,
        size: attachment.size,
        content_type: attachment.content_type
      }));
    const { error } = await supabase.from('discord_messages').update({
      attachments: attachmentsToPersist
    }).eq('message_id', message.message_id);
    if (error) {
      console.error(`[${IMPORTER_NAME}] failed to persist refreshed attachments`, error.message);
    }
    return {
      attachment: matched,
      attachmentsToPersist
    };
  }
  return fallbackAttachment ? {
    attachment: fallbackAttachment
  } : null;
}
async function claimJobsFallback(supabase) {
  const claimed = [];
  const lockUntil = new Date(Date.now() + JOB_LOCK_MINUTES * 60_000).toISOString();
  const selectedIds = new Set();
  const pendingQuery = await supabase.from('media_import_jobs').select(`
      id,
      discord_attachment_id:discord_attachment_id::text,
      discord_message_id:discord_message_id::text,
      target_kind,
      target_id,
      original_cdn_url,
      filename,
      content_type,
      size_bytes,
      attempts
    `).eq('status', 'pending').order('created_at', {
    ascending: true
  }).limit(JOB_BATCH_SIZE);
  if (pendingQuery.error) {
    throw new Error(`Failed to query pending media_import_jobs: ${pendingQuery.error.message}`);
  }
  const pendingJobs = pendingQuery.data ?? [];
  for (const job of pendingJobs){
    selectedIds.add(job.id);
  }
  if (pendingJobs.length < JOB_BATCH_SIZE) {
    const remaining = JOB_BATCH_SIZE - pendingJobs.length;
    const staleQuery = await supabase.from('media_import_jobs').select(`
        id,
        discord_attachment_id:discord_attachment_id::text,
        discord_message_id:discord_message_id::text,
        target_kind,
        target_id,
        original_cdn_url,
        filename,
        content_type,
        size_bytes,
        attempts
      `).eq('status', 'in_progress').lt('locked_until', nowIso()).order('created_at', {
      ascending: true
    }).limit(remaining);
    if (staleQuery.error) {
      throw new Error(`Failed to query stale media_import_jobs: ${staleQuery.error.message}`);
    }
    for (const job of staleQuery.data ?? []){
      if (!selectedIds.has(job.id)) pendingJobs.push(job);
    }
  }
  for (const job of pendingJobs){
    const pendingClaim = await supabase.from('media_import_jobs').update({
      status: 'in_progress',
      locked_until: lockUntil,
      updated_at: nowIso()
    }).eq('id', job.id).eq('status', 'pending').select(`
        id,
        discord_attachment_id:discord_attachment_id::text,
        discord_message_id:discord_message_id::text,
        target_kind,
        target_id,
        original_cdn_url,
        filename,
        content_type,
        size_bytes,
        attempts
      `).maybeSingle();
    if (pendingClaim.error) {
      throw new Error(`Failed to claim pending job ${job.id}: ${pendingClaim.error.message}`);
    }
    if (pendingClaim.data) {
      claimed.push(pendingClaim.data);
      continue;
    }
    const staleClaim = await supabase.from('media_import_jobs').update({
      status: 'in_progress',
      locked_until: lockUntil,
      updated_at: nowIso()
    }).eq('id', job.id).eq('status', 'in_progress').lt('locked_until', nowIso()).select(`
        id,
        discord_attachment_id:discord_attachment_id::text,
        discord_message_id:discord_message_id::text,
        target_kind,
        target_id,
        original_cdn_url,
        filename,
        content_type,
        size_bytes,
        attempts
      `).maybeSingle();
    if (staleClaim.error) {
      throw new Error(`Failed to reclaim stale job ${job.id}: ${staleClaim.error.message}`);
    }
    if (staleClaim.data) {
      claimed.push(staleClaim.data);
    }
  }
  return claimed;
}
async function claimJobs(supabase) {
  return await claimJobsFallback(supabase);
}
async function fetchMessagesForJobs(supabase, jobs) {
  const messageIds = [
    ...new Set(jobs.map((job)=>job.discord_message_id))
  ];
  if (messageIds.length === 0) return new Map();
  const { data, error } = await supabase.from('discord_messages').select(`
      message_id:message_id::text,
      channel_id:channel_id::text,
      thread_id:thread_id::text,
      guild_id:guild_id::text,
      author_id:author_id::text,
      attachments
    `).in('message_id', messageIds);
  if (error) {
    throw new Error(`Failed to fetch discord_messages: ${error.message}`);
  }
  return new Map((data ?? []).map((message)=>[
      message.message_id,
      message
    ]));
}
async function findExistingMediaId(supabase, attachmentId) {
  const { data, error } = await supabase.from('media').select('id').filter('metadata->>discord_attachment_id', 'eq', attachmentId).maybeSingle();
  if (error) {
    throw new Error(`Failed to query existing media: ${error.message}`);
  }
  return data?.id ?? null;
}
async function attachMediaToTarget(supabase, job, mediaId, attachmentIndex) {
  if (job.target_kind === 'asset_comment_media') {
    const { error } = await supabase.from('asset_comment_media').upsert({
      comment_id: job.target_id,
      media_id: mediaId,
      sort_order: attachmentIndex,
      is_deleted: false
    }, {
      onConflict: 'comment_id,media_id'
    });
    if (error) throw new Error(`Failed to attach comment media: ${error.message}`);
    return;
  }
  const { error } = await supabase.from('asset_media').upsert({
    asset_id: job.target_id,
    media_id: mediaId,
    sort_order: attachmentIndex,
    is_deleted: false
  }, {
    onConflict: 'asset_id,media_id'
  });
  if (error) throw new Error(`Failed to attach asset media: ${error.message}`);
  // Bug B fix: ensure the parent asset has a primary_media_id so the Forge grid
  // can resolve its thumbnail via media:primary_media_id(...). First successful
  // attach per asset wins -- the `primary_media_id IS NULL` guard enforces that.
  const { error: primaryUpdateError } = await supabase.from('assets').update({
    primary_media_id: mediaId
  }).eq('id', job.target_id).is('primary_media_id', null);
  if (primaryUpdateError) {
    // Non-fatal: the attach itself succeeded. Log so we can notice if this
    // regresses, but don't fail the job (which would retry and re-attach).
    console.error(`[${IMPORTER_NAME}] failed to set primary_media_id on asset ${job.target_id}:`, primaryUpdateError.message);
  }
}
async function markJobDone(supabase, jobId, mediaId) {
  const { error } = await supabase.from('media_import_jobs').update({
    status: 'done',
    media_id: mediaId,
    last_error: null,
    locked_until: null,
    updated_at: nowIso()
  }).eq('id', jobId);
  if (error) throw new Error(`Failed to mark job done: ${error.message}`);
}
async function markJobSkipped(supabase, jobId, reason) {
  const { error } = await supabase.from('media_import_jobs').update({
    status: 'skipped',
    last_error: reason,
    locked_until: null,
    updated_at: nowIso()
  }).eq('id', jobId);
  if (error) {
    console.error(`[${IMPORTER_NAME}] failed to mark job skipped`, error.message);
  }
}
async function markJobFailed(supabase, job, errorMessage) {
  const nextAttempts = job.attempts + 1;
  const permanentlyFailed = nextAttempts >= JOB_MAX_ATTEMPTS;
  const lockedUntil = permanentlyFailed ? null : new Date(Date.now() + 2 ** nextAttempts * 60_000).toISOString();
  const { error } = await supabase.from('media_import_jobs').update({
    attempts: nextAttempts,
    status: permanentlyFailed ? 'failed' : 'pending',
    last_error: errorMessage,
    locked_until: lockedUntil,
    updated_at: nowIso()
  }).eq('id', job.id);
  if (error) {
    console.error(`[${IMPORTER_NAME}] failed to update failed job`, error.message);
  }
  await logSystem(supabase, 'error', 'media import job failed', {
    job_id: job.id,
    discord_message_id: job.discord_message_id,
    discord_attachment_id: job.discord_attachment_id,
    attempts: nextAttempts,
    status: permanentlyFailed ? 'failed' : 'pending',
    error: errorMessage
  });
}
async function uploadToStorage(supabase, attachment, messageId, attachmentId, response) {
  const safeFilename = sanitizeFilename(attachment.filename);
  const storagePath = `${STORAGE_PREFIX}/${messageId}/${attachmentId}-${safeFilename}`;
  const blob = await response.blob();
  const { error: uploadError } = await supabase.storage.from(USER_UPLOADS_BUCKET).upload(storagePath, blob, {
    contentType: attachment.content_type ?? undefined,
    upsert: true
  });
  if (uploadError) {
    throw new Error(`Storage upload failed: ${uploadError.message}`);
  }
  const { data: publicUrlData } = supabase.storage.from(USER_UPLOADS_BUCKET).getPublicUrl(storagePath);
  return {
    path: storagePath,
    publicUrl: publicUrlData.publicUrl
  };
}
async function createCloudflareStream(supabase, accountId, apiToken, bucketPath) {
  const { data: signedData, error: signedError } = await supabase.storage.from(bucketPath.bucket).createSignedUrl(bucketPath.path, DOWNLOAD_URL_TTL_SECONDS);
  if (signedError || !signedData?.signedUrl) {
    throw new Error(`Failed to create signed URL for Cloudflare: ${signedError?.message ?? 'missing signed URL'}`);
  }
  const cfResponse = await fetch(`https://api.cloudflare.com/client/v4/accounts/${accountId}/stream/copy`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      url: signedData.signedUrl,
      meta: {
        name: bucketPath.path
      }
    })
  });
  const result = await cfResponse.json();
  if (!cfResponse.ok || !result.success || !result.result?.uid) {
    throw new Error(`Cloudflare Stream rejected upload: ${JSON.stringify(result.errors ?? result)}`);
  }
  return result.result.uid;
}
async function insertMediaRow(supabase, job, message, attachment, storage, streamUid) {
  const kind = getUploadKind(attachment.content_type ?? job.content_type, attachment.filename ?? job.filename);
  const importedAt = nowIso();
  const metadata = {
    bucket: storage.bucket,
    path: storage.path,
    discord_message_id: message.message_id,
    discord_channel_id: message.channel_id,
    discord_attachment_id: attachment.id,
    original_cdn_url: job.original_cdn_url ?? attachment.url,
    imported_at: importedAt
  };
  const insertPayload = {
    title: attachment.filename,
    url: storage.publicUrl,
    type: getMediaType(attachment.content_type ?? job.content_type, attachment.filename ?? job.filename),
    classification: job.target_kind === 'asset_comment_media' ? COMMENT_MEDIA_CLASSIFICATION : ASSET_MEDIA_CLASSIFICATION,
    description: null,
    admin_status: 'Listed',
    user_status: 'Listed',
    metadata,
    member_id: message.author_id,
    source: MEDIA_SOURCE,
    storage_provider: 'supabase'
  };
  if (kind === 'image') {
    insertPayload.cloudflare_thumbnail_url = storage.publicUrl;
    insertPayload.backup_thumbnail_url = storage.publicUrl;
  }
  if (kind === 'video' && streamUid) {
    insertPayload.cloudflare_stream_uid = streamUid;
  }
  const { data, error } = await supabase.from('media').insert(insertPayload).select('id').single();
  if (error || !data) {
    throw new Error(`Failed to insert media row: ${error?.message ?? 'missing media row'}`);
  }
  return data.id;
}
async function processJob(supabase, job, message, discordToken, cloudflareAccountId, cloudflareApiToken) {
  const attachmentId = parseDiscordAttachmentId(job.discord_attachment_id);
  if (!attachmentId) {
    await markJobSkipped(supabase, job.id, 'Missing discord_attachment_id');
    return 'skipped';
  }
  const attachments = message.attachments ?? [];
  const attachmentIndex = attachments.findIndex((attachment)=>attachment.id === attachmentId);
  const attachmentFromMessage = attachmentIndex >= 0 ? attachments[attachmentIndex] : null;
  const refreshed = await refreshAttachmentIfNeeded(supabase, discordToken, message, attachmentId, attachmentFromMessage);
  if (!refreshed) {
    await markJobSkipped(supabase, job.id, 'Attachment no longer exists on Discord');
    return 'skipped';
  }
  const attachment = refreshed.attachment;
  const effectiveIndex = attachmentIndex >= 0 ? attachmentIndex : Math.max((refreshed.attachmentsToPersist ?? []).findIndex((item)=>item.id === attachmentId), 0);
  const existingMediaId = await findExistingMediaId(supabase, attachmentId);
  if (existingMediaId) {
    await attachMediaToTarget(supabase, job, existingMediaId, effectiveIndex);
    await markJobDone(supabase, job.id, existingMediaId);
    return 'done';
  }
  const downloadResponse = await fetch(attachment.url);
  if (!downloadResponse.ok) {
    throw new Error(`Failed to download Discord attachment: HTTP ${downloadResponse.status}`);
  }
  const storage = await uploadToStorage(supabase, attachment, job.discord_message_id, attachmentId, downloadResponse);
  const uploadKind = getUploadKind(attachment.content_type ?? job.content_type, attachment.filename ?? job.filename);
  let streamUid = null;
  if (uploadKind === 'video') {
    if (!cloudflareAccountId || !cloudflareApiToken) {
      throw new Error('Missing Cloudflare Stream credentials');
    }
    streamUid = await createCloudflareStream(supabase, cloudflareAccountId, cloudflareApiToken, {
      bucket: USER_UPLOADS_BUCKET,
      path: storage.path
    });
  }
  const mediaId = await insertMediaRow(supabase, job, message, attachment, {
    bucket: USER_UPLOADS_BUCKET,
    path: storage.path,
    publicUrl: storage.publicUrl
  }, streamUid);
  await attachMediaToTarget(supabase, job, mediaId, effectiveIndex);
  await markJobDone(supabase, job.id, mediaId);
  return 'done';
}
Deno.serve(async (req)=>{
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'authorization, content-type, x-client-info, apikey'
      }
    });
  }
  if (req.method !== 'POST') {
    return jsonResponse(405, {
      error: 'Method not allowed'
    });
  }
  const serviceRoleKey = getServiceRoleKey();
  const authHeader = req.headers.get('authorization');
  if (!serviceRoleKey || !authHeader) {
    return jsonResponse(401, {
      error: 'Unauthorized'
    });
  }
  const token = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (token !== serviceRoleKey) {
    return jsonResponse(401, {
      error: 'Unauthorized'
    });
  }
  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const discordToken = Deno.env.get('DISCORD_BOT_TOKEN');
  const cloudflareAccountId = Deno.env.get('CLOUDFLARE_STREAM_ACCOUNT_ID') ?? Deno.env.get('CLOUDFLARE_ACCOUNT_ID');
  const cloudflareApiToken = Deno.env.get('CLOUDFLARE_STREAM_API_TOKEN') ?? Deno.env.get('CLOUDFLARE_API_TOKEN');
  if (!supabaseUrl || !serviceRoleKey || !discordToken) {
    return jsonResponse(500, {
      error: 'Missing required environment variables'
    });
  }
  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  });
  const startedAt = Date.now();
  let processed = 0;
  let succeeded = 0;
  let failed = 0;
  let skipped = 0;
  let claimed = 0;
  while(Date.now() - startedAt < WALL_CLOCK_BUDGET_MS){
    const jobs = await claimJobs(supabase);
    if (jobs.length === 0) break;
    claimed += jobs.length;
    const messageMap = await fetchMessagesForJobs(supabase, jobs);
    for (const job of jobs){
      if (Date.now() - startedAt >= WALL_CLOCK_BUDGET_MS) break;
      const message = messageMap.get(job.discord_message_id);
      if (!message) {
        await markJobSkipped(supabase, job.id, 'discord_messages row not found');
        skipped += 1;
        processed += 1;
        continue;
      }
      try {
        const status = await processJob(supabase, job, message, discordToken, cloudflareAccountId, cloudflareApiToken);
        if (status === 'skipped') {
          skipped += 1;
        } else {
          succeeded += 1;
        }
      } catch (error) {
        failed += 1;
        await markJobFailed(supabase, job, error instanceof Error ? error.message : String(error));
      } finally{
        processed += 1;
      }
    }
  }
  await logSystem(supabase, 'info', 'discord media importer run complete', {
    claimed,
    processed,
    succeeded,
    failed,
    skipped,
    budget_ms: WALL_CLOCK_BUDGET_MS
  });
  return jsonResponse(200, {
    claimed,
    processed,
    succeeded,
    failed,
    skipped
  });
});
