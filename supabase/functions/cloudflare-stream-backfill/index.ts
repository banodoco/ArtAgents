import { createClient } from "npm:@supabase/supabase-js@2";

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const DOWNLOAD_URL_TTL_SECONDS = 60 * 60
const MAX_INGEST_ATTEMPTS = 5

function jsonResponse(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  })
}

function getStorageLocator(metadata: unknown) {
  if (!metadata || Array.isArray(metadata) || typeof metadata !== 'object') {
    return null
  }

  const candidate = metadata as Record<string, unknown>
  const bucket = typeof candidate.bucket === 'string' ? candidate.bucket.trim() : ''
  const path = typeof candidate.path === 'string' ? candidate.path.trim() : ''

  if (!bucket || !path) {
    return null
  }

  return { bucket, path }
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return jsonResponse(405, { error: 'Method not allowed' })
  }

  // Secured via service role key — only callable by admins / cron
  const authHeader = req.headers.get('authorization')
  const supabaseServiceKey = Deno.env.get('SB_SECRET_KEY')

  if (!authHeader || !supabaseServiceKey) {
    return jsonResponse(401, { error: 'Unauthorized' })
  }

  const token = authHeader.replace(/^Bearer\s+/i, '').trim()
  if (token !== supabaseServiceKey) {
    return jsonResponse(401, { error: 'Unauthorized' })
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL')
  const cloudflareAccountId = Deno.env.get('CLOUDFLARE_ACCOUNT_ID')
  const cloudflareApiToken = Deno.env.get('CLOUDFLARE_API_TOKEN')

  if (!supabaseUrl || !cloudflareAccountId || !cloudflareApiToken) {
    return jsonResponse(500, { error: 'Missing required environment variables' })
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  })

  // Optional: pass { media_id } to retry a single video (ignores attempt cap)
  let body: { media_id?: string } = {}
  try {
    body = await req.json()
  } catch {
    // empty body is fine — means backfill all
  }

  const isSingleRetry = Boolean(body.media_id)

  // Find media rows that need Cloudflare ingestion:
  // - Has a storage URL (uploaded to Supabase)
  // - Missing HLS playback URL (Cloudflare hasn't processed it)
  // - Under the retry cap (unless single-video manual retry)
  let query = supabase
    .from('media')
    .select('id, metadata, cloudflare_stream_uid, url, cloudflare_ingest_attempts')
    .is('cloudflare_playback_hls_url', null)
    .not('url', 'is', null)

  if (body.media_id) {
    query = query.eq('id', body.media_id)
  } else {
    query = query.lt('cloudflare_ingest_attempts', MAX_INGEST_ATTEMPTS)
  }

  const { data: mediaRows, error: queryError } = await query.limit(50)

  if (queryError) {
    return jsonResponse(500, { error: 'Failed to query media', details: queryError.message })
  }

  if (!mediaRows || mediaRows.length === 0) {
    return jsonResponse(200, { message: 'No media rows need backfill', processed: 0 })
  }

  const results: { media_id: string; status: string; attempts?: number; detail?: string }[] = []

  for (const media of mediaRows) {
    const attempts = (media.cloudflare_ingest_attempts ?? 0) as number

    // Skip if over the cap (only reachable for single-video manual retries
    // where we still want to show the status)
    if (!isSingleRetry && attempts >= MAX_INGEST_ATTEMPTS) {
      results.push({ media_id: media.id, status: 'max_attempts_reached', attempts })
      continue
    }

    // Already has a stream UID — Cloudflare accepted it but webhook hasn't
    // arrived yet (or failed). Check Cloudflare for its status.
    if (media.cloudflare_stream_uid) {
      const checkResp = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${cloudflareAccountId}/stream/${media.cloudflare_stream_uid}`,
        { headers: { 'Authorization': `Bearer ${cloudflareApiToken}` } },
      )

      if (checkResp.ok) {
        const checkResult = await checkResp.json() as {
          result?: {
            readyToStream?: boolean
            playback?: { hls?: string }
            thumbnail?: string
            status?: { state?: string }
          }
        }

        if (checkResult.result?.readyToStream && checkResult.result.playback?.hls) {
          // Video is ready — write the URLs that the webhook should have written
          const hlsUrl = checkResult.result.playback.hls
          const thumbnailUrl = checkResult.result.thumbnail ?? null

          const { error: updateErr } = await supabase
            .from('media')
            .update({
              cloudflare_playback_hls_url: hlsUrl,
              cloudflare_thumbnail_url: thumbnailUrl,
              storage_provider: 'cloudflare',
            })
            .eq('id', media.id)

          results.push({
            media_id: media.id,
            status: updateErr ? 'update_failed' : 'recovered_from_cloudflare',
            attempts,
            detail: updateErr?.message,
          })
          continue
        }

        if (checkResult.result?.status?.state === 'error') {
          // Cloudflare failed to process — clear the UID so we can re-upload
          await supabase
            .from('media')
            .update({ cloudflare_stream_uid: null })
            .eq('id', media.id)
          // Fall through to re-upload below
        } else {
          // Still processing — skip
          results.push({ media_id: media.id, status: 'still_processing', attempts })
          continue
        }
      }
    }

    // No stream UID (or we just cleared a failed one) — upload to Cloudflare
    const locator = getStorageLocator(media.metadata)
    if (!locator) {
      results.push({ media_id: media.id, status: 'skipped_no_metadata', attempts })
      continue
    }

    // Increment attempt counter before trying
    await supabase
      .from('media')
      .update({ cloudflare_ingest_attempts: attempts + 1 })
      .eq('id', media.id)

    const { data: signedData, error: signedError } = await supabase
      .storage
      .from(locator.bucket)
      .createSignedUrl(locator.path, DOWNLOAD_URL_TTL_SECONDS)

    if (signedError || !signedData?.signedUrl) {
      results.push({ media_id: media.id, status: 'signed_url_failed', attempts: attempts + 1, detail: signedError?.message })
      continue
    }

    const cfResponse = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${cloudflareAccountId}/stream/copy`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${cloudflareApiToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: signedData.signedUrl,
          meta: { name: locator.path, media_id: media.id },
        }),
      },
    )

    let cfResult: { success?: boolean; errors?: unknown; result?: { uid?: string } }
    try {
      cfResult = await cfResponse.json()
    } catch {
      results.push({ media_id: media.id, status: 'cloudflare_error', attempts: attempts + 1, detail: `HTTP ${cfResponse.status}` })
      continue
    }

    if (!cfResponse.ok || !cfResult.success || !cfResult.result?.uid) {
      results.push({ media_id: media.id, status: 'cloudflare_rejected', attempts: attempts + 1, detail: JSON.stringify(cfResult.errors) })
      continue
    }

    const { error: updateError } = await supabase
      .from('media')
      .update({ cloudflare_stream_uid: cfResult.result.uid })
      .eq('id', media.id)

    results.push({
      media_id: media.id,
      status: updateError ? 'uid_update_failed' : 'ingestion_triggered',
      attempts: attempts + 1,
      detail: updateError?.message,
    })
  }

  return jsonResponse(200, {
    processed: results.length,
    results,
  })
})
