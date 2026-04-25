import { createClient } from "npm:@supabase/supabase-js@2";

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const DOWNLOAD_URL_TTL_SECONDS = 60 * 60

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
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'authorization, content-type, x-client-info, apikey',
      },
    })
  }

  if (req.method !== 'POST') {
    return jsonResponse(405, { error: 'Method not allowed' })
  }

  const authHeader = req.headers.get('authorization')
  if (!authHeader) {
    return jsonResponse(401, { error: 'Missing authorization header' })
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL')
  const supabaseServiceKey = Deno.env.get('SB_SECRET_KEY')
  const cloudflareAccountId = Deno.env.get('CLOUDFLARE_ACCOUNT_ID')
  const cloudflareApiToken = Deno.env.get('CLOUDFLARE_API_TOKEN')

  if (!supabaseUrl || !supabaseServiceKey || !cloudflareAccountId || !cloudflareApiToken) {
    return jsonResponse(500, { error: 'Missing required environment variables' })
  }

  const accessToken = authHeader.replace(/^Bearer\s+/i, '').trim()
  if (!accessToken) {
    return jsonResponse(401, { error: 'Invalid authorization header' })
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  })

  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser(accessToken)

  if (authError || !user) {
    return jsonResponse(401, { error: 'Invalid token' })
  }

  let body: { media_id?: string }
  try {
    body = await req.json()
  } catch {
    return jsonResponse(400, { error: 'Invalid JSON body' })
  }

  const mediaId = body.media_id
  if (!mediaId) {
    return jsonResponse(400, { error: 'media_id is required' })
  }

  const { data: media, error: mediaError } = await supabase
    .from('media')
    .select('id, metadata, cloudflare_stream_uid')
    .eq('id', mediaId)
    .maybeSingle()

  if (mediaError || !media) {
    return jsonResponse(404, { error: 'Media not found' })
  }

  if (media.cloudflare_stream_uid) {
    return jsonResponse(200, { stream_uid: media.cloudflare_stream_uid, already_ingested: true })
  }

  const locator = getStorageLocator(media.metadata)

  if (!locator) {
    return jsonResponse(400, { error: 'Media missing storage metadata (bucket/path)' })
  }

  const { data: signedData, error: signedError } = await supabase
    .storage
    .from(locator.bucket)
    .createSignedUrl(locator.path, DOWNLOAD_URL_TTL_SECONDS)

  if (signedError || !signedData?.signedUrl) {
    return jsonResponse(500, { error: 'Failed to generate download URL' })
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
        meta: { name: locator.path, media_id: mediaId },
      }),
    },
  )

  let cfResult: {
    success?: boolean
    errors?: unknown
    result?: {
      uid?: string
    }
  }

  try {
    cfResult = await cfResponse.json()
  } catch {
    return jsonResponse(502, {
      error: 'Cloudflare Stream upload failed',
      details: `Unexpected response status ${cfResponse.status}`,
    })
  }

  if (!cfResponse.ok || !cfResult.success || !cfResult.result?.uid) {
    console.error('Cloudflare Stream upload failed:', cfResult.errors)
    return jsonResponse(502, { error: 'Cloudflare Stream upload failed', details: cfResult.errors })
  }

  const streamUid = cfResult.result.uid

  const { error: updateError } = await supabase
    .from('media')
    .update({ cloudflare_stream_uid: streamUid })
    .eq('id', mediaId)

  if (updateError) {
    console.error('Failed to update media row:', updateError)
    return jsonResponse(500, { error: 'Failed to store stream UID' })
  }

  return jsonResponse(200, { stream_uid: streamUid })
})
