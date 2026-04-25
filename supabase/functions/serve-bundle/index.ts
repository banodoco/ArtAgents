// serve-bundle: public bundle-bytes server with four-gate visibility check.
//
// Routes:  /serve-bundle/:bundleVersionId/:path*?token=...
//
// Public-hit decision tree (returns 200):
//   review_status='approved'
//   AND posts.status='published'
//   AND posts.active_bundle_version_id = :bundleVersionId
//   AND (admin_status IS NULL OR admin_status != 'Hidden')
// Preview-hit decision tree (returns 200):
//   valid HS256 token (BUNDLE_PREVIEW_SECRET)
//   AND token.exp > now
//   AND token.bv === :bundleVersionId
// Everything else → 404.

import { createClient } from 'npm:@supabase/supabase-js@2';
import {
  BUNDLE_BUCKET,
  BUNDLE_CONTENT_TYPES,
} from '../_shared/bundle-constants.ts';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, content-type, apikey, x-client-info',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
};

const FRAME_ANCESTORS_DEFAULT = 'https://banodoco.com https://www.banodoco.com';

function buildSecurityHeaders(frameAncestors: string): Record<string, string> {
  return {
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'geolocation=(), camera=(), microphone=(), payment=()',
    'Cross-Origin-Resource-Policy': 'cross-origin',
    'Content-Security-Policy': [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "media-src 'self' blob:",
      "font-src 'self' data:",
      "connect-src 'self'",
      `frame-ancestors ${frameAncestors}`,
      "base-uri 'none'",
      "form-action 'none'",
      "object-src 'none'",
      "worker-src 'self' blob:",
    ].join('; '),
  };
}

function notFound(frameAncestors: string): Response {
  return new Response('Not Found', {
    status: 404,
    headers: {
      ...CORS_HEADERS,
      ...buildSecurityHeaders(frameAncestors),
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

function b64urlDecodeToString(segment: string): string {
  const padded = segment.replace(/-/g, '+').replace(/_/g, '/') +
    '='.repeat((4 - (segment.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

async function verifyPreviewToken(
  token: string,
  secret: string,
  expectedBundleVersionId: string,
): Promise<boolean> {
  const parts = token.split('.');
  if (parts.length !== 3) return false;
  const [headerSeg, payloadSeg, signatureSeg] = parts;

  const signingInput = `${headerSeg}.${payloadSeg}`;
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify'],
  );

  // Normalize the received signature to bytes.
  const padded = signatureSeg.replace(/-/g, '+').replace(/_/g, '/') +
    '='.repeat((4 - (signatureSeg.length % 4)) % 4);
  const binary = atob(padded);
  const signature = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) signature[i] = binary.charCodeAt(i);

  const ok = await crypto.subtle.verify(
    'HMAC',
    key,
    signature,
    new TextEncoder().encode(signingInput),
  );
  if (!ok) return false;

  let payload: { bv?: string; exp?: number };
  try {
    payload = JSON.parse(b64urlDecodeToString(payloadSeg));
  } catch {
    return false;
  }
  if (!payload.bv || payload.bv !== expectedBundleVersionId) return false;
  const now = Math.floor(Date.now() / 1000);
  if (!payload.exp || payload.exp <= now) return false;
  return true;
}

function extForPath(path: string): string {
  const idx = path.lastIndexOf('.');
  return idx >= 0 ? path.slice(idx).toLowerCase() : '';
}

function responseHeaders(
  contentType: string,
  cacheControl: string,
  frameAncestors: string,
): Headers {
  const headers = new Headers();
  headers.set('Content-Type', contentType);
  headers.set('Cache-Control', cacheControl);
  for (const [key, value] of Object.entries(buildSecurityHeaders(frameAncestors))) {
    headers.set(key, value);
  }
  for (const [key, value] of Object.entries(CORS_HEADERS)) headers.set(key, value);
  return headers;
}

Deno.serve(async (req) => {
  const frameAncestors = Deno.env.get('BUNDLE_FRAME_ANCESTORS') ?? FRAME_ANCESTORS_DEFAULT;

  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: CORS_HEADERS });
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') return notFound(frameAncestors);

  const url = new URL(req.url);
  // Path shape: /<function-name>/<bundleVersionId>[/<...asset-path>]
  // In Supabase Edge Functions the function name becomes the first segment.
  const segments = url.pathname.split('/').filter(Boolean);
  // Drop the first "serve-bundle" segment if present.
  const leading = segments[0];
  const withoutFn = leading === 'serve-bundle' ? segments.slice(1) : segments;
  if (withoutFn.length < 1) return notFound(frameAncestors);

  const bundleVersionId = withoutFn[0];
  let assetPath = withoutFn.slice(1).join('/');

  if (!bundleVersionId) return notFound(frameAncestors);
  // Reject traversal attempts in the asset path (if present).
  if (assetPath && (assetPath.includes('..') || assetPath.includes('\\'))) {
    return notFound(frameAncestors);
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const supabaseServiceKey =
    Deno.env.get('SB_SECRET_KEY') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !supabaseServiceKey) return notFound(frameAncestors);

  const previewSecret = Deno.env.get('BUNDLE_PREVIEW_SECRET') ?? '';

  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  // Look up the bundle row plus its parent post for gating.
  type BundleLookupRow = {
    id: string;
    post_id: string;
    storage_prefix: string;
    review_status: 'pending' | 'approved' | 'rejected';
    manifest: { entry?: string } | null;
    posts: {
      status: string | null;
      admin_status: string | null;
      active_bundle_version_id: string | null;
    } | {
      status: string | null;
      admin_status: string | null;
      active_bundle_version_id: string | null;
    }[] | null;
  };

  // Disambiguate the embed: posts ↔ post_bundles has TWO FKs —
  // post_bundles.post_id → posts.id AND posts.active_bundle_version_id →
  // post_bundles.id. Without naming the relationship PostgREST returns
  // PGRST201 and we 404 every request.
  const { data: bundleRow, error: lookupError } = await supabase
    .from('post_bundles')
    .select(
      `id, post_id, storage_prefix, review_status, manifest,
       posts:post_bundles_post_id_fkey(status, admin_status, active_bundle_version_id)`,
    )
    .eq('id', bundleVersionId)
    .maybeSingle();

  if (lookupError) {
    console.warn('[serve-bundle] bundle lookup failed', {
      bundleVersionId,
      code: lookupError.code,
      message: lookupError.message,
    });
    return notFound(frameAncestors);
  }
  if (!bundleRow) {
    console.info('[serve-bundle] bundle row not found', { bundleVersionId });
    return notFound(frameAncestors);
  }
  const row = bundleRow as BundleLookupRow;
  const post = Array.isArray(row.posts) ? row.posts[0] : row.posts;

  // Default-path behavior: when the caller requests /serve-bundle/:id (no
  // asset path), fall back to manifest.entry so the post page can serve the
  // bundle root without hard-coding "index.html".
  if (!assetPath) {
    const manifestEntry = row.manifest?.entry;
    if (typeof manifestEntry === 'string' && manifestEntry.length > 0) {
      assetPath = manifestEntry;
    } else {
      return notFound(frameAncestors);
    }
  }

  const publicGateHolds =
    row.review_status === 'approved' &&
    post?.status === 'published' &&
    post?.active_bundle_version_id === bundleVersionId &&
    (post?.admin_status === null || post?.admin_status !== 'Hidden');

  let previewGateHolds = false;
  const token = url.searchParams.get('token');
  if (token && previewSecret) {
    previewGateHolds = await verifyPreviewToken(token, previewSecret, bundleVersionId);
  }

  if (!publicGateHolds && !previewGateHolds) {
    console.info('[serve-bundle] gate rejected', {
      bundleVersionId,
      reviewStatus: row.review_status,
      postStatus: post?.status,
      activeBundleVersionId: post?.active_bundle_version_id,
      adminStatus: post?.admin_status,
      hasToken: Boolean(token),
    });
    return notFound(frameAncestors);
  }

  const cacheControl = publicGateHolds
    ? 'public, max-age=31536000, immutable'
    : 'private, no-store';

  // Fetch the file from storage via signed URL (bucket is private). We
  // proxy the bytes rather than redirecting because the client will read
  // this response with `fetch()` and feed the body into an iframe via
  // `srcdoc` — that path is what bypasses Supabase's text/html rewrite.
  // For non-HTML assets (CSS, JS, images) the iframe loads them directly
  // from this URL and the correct content-type passes through untouched.
  const objectPath = `${row.storage_prefix}/${assetPath}`;
  const { data: signed, error: signError } = await supabase.storage
    .from(BUNDLE_BUCKET)
    .createSignedUrl(objectPath, 60);
  if (signError || !signed?.signedUrl) {
    console.warn('[serve-bundle] signed URL failed', {
      bundleVersionId,
      objectPath,
      message: signError?.message,
    });
    return notFound(frameAncestors);
  }

  const upstream = await fetch(signed.signedUrl, { method: req.method });
  if (!upstream.ok) {
    console.warn('[serve-bundle] upstream fetch failed', {
      bundleVersionId,
      objectPath,
      upstreamStatus: upstream.status,
    });
    return notFound(frameAncestors);
  }

  const ext = extForPath(assetPath);
  const contentType =
    BUNDLE_CONTENT_TYPES[ext] ?? upstream.headers.get('content-type') ?? 'application/octet-stream';
  console.info('[serve-bundle] serving', {
    bundleVersionId,
    assetPath,
    ext,
    contentType,
    publicGate: publicGateHolds,
    previewGate: previewGateHolds,
  });

  return new Response(upstream.body, {
    status: 200,
    headers: responseHeaders(contentType, cacheControl, frameAncestors),
  });
});
