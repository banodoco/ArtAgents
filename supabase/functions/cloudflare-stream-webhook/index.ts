import { createClient } from "npm:@supabase/supabase-js@2";

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const MAX_SIGNATURE_AGE_SECONDS = 60 * 5

type CloudflareStreamPayload = {
  uid?: string
  thumbnail?: string
  readyToStream?: boolean
  status?: {
    state?: string
    pctComplete?: string
  }
  playback?: {
    hls?: string
  }
}

function jsonResponse(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  })
}

function parseWrappedPayload(payload: unknown): { eventType: string | null; stream: CloudflareStreamPayload } {
  if (!payload || typeof payload !== 'object') {
    return { eventType: null, stream: {} }
  }

  const candidate = payload as Record<string, unknown>
  const nestedData = candidate.data
  const stream =
    nestedData && typeof nestedData === 'object' && !Array.isArray(nestedData)
      ? (nestedData as CloudflareStreamPayload)
      : (candidate as CloudflareStreamPayload)

  const directEventType =
    typeof candidate.event === 'string'
      ? candidate.event
      : candidate.event && typeof candidate.event === 'object' && !Array.isArray(candidate.event)
        ? typeof (candidate.event as Record<string, unknown>).type === 'string'
          ? ((candidate.event as Record<string, unknown>).type as string)
          : null
        : typeof candidate.type === 'string'
          ? candidate.type
          : null

  if (directEventType) {
    return { eventType: directEventType, stream }
  }

  if (stream.readyToStream === true && stream.status?.state === 'ready') {
    return { eventType: 'stream.ready', stream }
  }

  return { eventType: null, stream }
}

function parseSignatureHeader(signatureHeader: string | null) {
  if (!signatureHeader) {
    return null
  }

  const fields = new Map<string, string>()

  for (const part of signatureHeader.split(',')) {
    const [key, value] = part.split('=', 2)

    if (!key || !value) {
      continue
    }

    fields.set(key.trim(), value.trim())
  }

  const timestamp = fields.get('time')
  const signature = fields.get('sig1')

  if (!timestamp || !signature) {
    return null
  }

  return { timestamp, signature }
}

async function createHexHmac(secret: string, message: string) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )

  const signature = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message))

  return Array.from(new Uint8Array(signature), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

function constantTimeEqual(left: string, right: string) {
  if (left.length !== right.length) {
    return false
  }

  let mismatch = 0

  for (let index = 0; index < left.length; index += 1) {
    mismatch |= left.charCodeAt(index) ^ right.charCodeAt(index)
  }

  return mismatch === 0
}

async function verifySignature(req: Request, rawBody: string, secret: string) {
  const parsed = parseSignatureHeader(req.headers.get('Webhook-Signature'))

  if (!parsed) {
    return false
  }

  const timestampSeconds = Number.parseInt(parsed.timestamp, 10)

  if (!Number.isFinite(timestampSeconds)) {
    return false
  }

  const ageSeconds = Math.abs(Math.floor(Date.now() / 1000) - timestampSeconds)

  if (ageSeconds > MAX_SIGNATURE_AGE_SECONDS) {
    return false
  }

  const expectedSignature = await createHexHmac(secret, `${parsed.timestamp}.${rawBody}`)
  return constantTimeEqual(expectedSignature, parsed.signature)
}

function extractCustomerCode(stream: CloudflareStreamPayload) {
  const urls = [stream.playback?.hls, stream.thumbnail]

  for (const value of urls) {
    if (!value) {
      continue
    }

    const match = value.match(/^https:\/\/customer-([^.]+)\.cloudflarestream\.com\//)

    if (match?.[1]) {
      return match[1]
    }
  }

  return Deno.env.get('CLOUDFLARE_STREAM_CUSTOMER_CODE') ?? null
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return jsonResponse(405, { error: 'Method not allowed.' })
  }

  const webhookSecret = Deno.env.get('CLOUDFLARE_STREAM_WEBHOOK_SECRET')
  const supabaseUrl = Deno.env.get('SUPABASE_URL')
  const serviceRoleKey = Deno.env.get('SB_SECRET_KEY')

  if (!webhookSecret || !supabaseUrl || !serviceRoleKey) {
    return jsonResponse(500, { error: 'Missing required environment variables.' })
  }

  const rawBody = await req.text()
  const signatureIsValid = await verifySignature(req, rawBody, webhookSecret)

  if (!signatureIsValid) {
    return jsonResponse(401, { error: 'Invalid webhook signature.' })
  }

  let payload: unknown

  try {
    payload = JSON.parse(rawBody)
  } catch {
    return jsonResponse(400, { error: 'Invalid JSON payload.' })
  }

  const { eventType, stream } = parseWrappedPayload(payload)

  if (eventType !== 'stream.ready') {
    return jsonResponse(400, {
      error: 'Unhandled event type.',
      event_type: eventType,
    })
  }

  const streamUid = typeof stream.uid === 'string' ? stream.uid : null
  const customerCode = extractCustomerCode(stream)

  if (!streamUid || !customerCode) {
    return jsonResponse(400, { error: 'Missing stream UID or customer code.' })
  }

  const hlsUrl = `https://customer-${customerCode}.cloudflarestream.com/${streamUid}/manifest/video.m3u8`
  const thumbnailUrl = `https://customer-${customerCode}.cloudflarestream.com/${streamUid}/thumbnails/thumbnail.jpg`

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  })

  const { data, error } = await supabase
    .from('media')
    .update({
      cloudflare_playback_hls_url: hlsUrl,
      cloudflare_thumbnail_url: thumbnailUrl,
      storage_provider: 'cloudflare',
    })
    .eq('cloudflare_stream_uid', streamUid)
    .select('id')
    .maybeSingle()

  if (error) {
    return jsonResponse(500, {
      error: 'Failed to update media row.',
      details: error.message,
    })
  }

  if (!data) {
    return jsonResponse(404, {
      error: 'No media row found for Cloudflare Stream UID.',
      stream_uid: streamUid,
    })
  }

  return jsonResponse(200, {
    ok: true,
    stream_uid: streamUid,
    hls_url: hlsUrl,
    thumbnail_url: thumbnailUrl,
  })
})
