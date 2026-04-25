// issue-preview-token: mint a short-lived JWT that authorizes a single
// bundle-version preview via serve-bundle?token=.
//
// Authorization: caller must be the bundle uploader OR an admin. Tokens expire
// after BUNDLE_PREVIEW_TTL_SECONDS (5 min) and are signed with
// BUNDLE_PREVIEW_SECRET (HMAC-SHA256).

import { createClient } from 'npm:@supabase/supabase-js@2';
import { BUNDLE_PREVIEW_TTL_SECONDS } from '../_shared/bundle-constants.ts';

const JSON_HEADERS = { 'Content-Type': 'application/json' };
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers':
    'authorization, content-type, x-client-info, apikey, x-supabase-function-secret',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

function json(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...JSON_HEADERS, ...CORS_HEADERS },
  });
}

// Base64URL helpers (RFC 4648).
function b64urlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function hmacSha256(secret: string, message: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const signature = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message));
  return new Uint8Array(signature);
}

async function signPreviewToken(secret: string, payload: Record<string, unknown>): Promise<string> {
  const header = { alg: 'HS256', typ: 'JWT' };
  const encoder = new TextEncoder();
  const headerSegment = b64urlEncode(encoder.encode(JSON.stringify(header)));
  const payloadSegment = b64urlEncode(encoder.encode(JSON.stringify(payload)));
  const signingInput = `${headerSegment}.${payloadSegment}`;
  const signatureBytes = await hmacSha256(secret, signingInput);
  const signatureSegment = b64urlEncode(signatureBytes);
  return `${signingInput}.${signatureSegment}`;
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: CORS_HEADERS });
  }
  if (req.method !== 'POST') {
    return json(405, { error: 'Method not allowed' });
  }

  const authHeader = req.headers.get('authorization');
  if (!authHeader) return json(401, { error: 'Missing authorization header' });

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const supabaseServiceKey =
    Deno.env.get('SB_SECRET_KEY') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  const previewSecret = Deno.env.get('BUNDLE_PREVIEW_SECRET');
  if (!supabaseUrl || !supabaseServiceKey || !previewSecret) {
    return json(500, { error: 'Server misconfigured' });
  }

  const accessToken = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (!accessToken) return json(401, { error: 'Invalid authorization header' });

  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: authData, error: authError } = await supabase.auth.getUser(accessToken);
  if (authError || !authData?.user) return json(401, { error: 'Invalid token' });
  const userId = authData.user.id;

  let body: { bundleVersionId?: string };
  try {
    body = await req.json();
  } catch {
    return json(400, { error: 'Invalid JSON body' });
  }
  const bundleVersionId = body?.bundleVersionId;
  if (!bundleVersionId || typeof bundleVersionId !== 'string') {
    return json(400, { error: 'bundleVersionId is required' });
  }

  // Verify the caller is owner or admin for this bundle version.
  const { data: bundle } = await supabase
    .from('post_bundles')
    .select('id, post_id, uploaded_by')
    .eq('id', bundleVersionId)
    .maybeSingle();
  if (!bundle) {
    return json(404, { error: 'bundle not found' });
  }

  let authorized = bundle.uploaded_by === userId;
  if (!authorized) {
    const { data: adminCheck } = await supabase.rpc('is_admin', { check_user_id: userId });
    authorized = Boolean(adminCheck);
  }
  if (!authorized) {
    return json(404, { error: 'bundle not found' });
  }

  const iat = Math.floor(Date.now() / 1000);
  const exp = iat + BUNDLE_PREVIEW_TTL_SECONDS;
  const token = await signPreviewToken(previewSecret, {
    bv: bundleVersionId,
    sub: userId,
    iat,
    exp,
  });

  return json(200, { token, expiresAt: exp });
});
