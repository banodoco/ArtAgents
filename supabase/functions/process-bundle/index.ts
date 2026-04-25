// process-bundle: validate an uploaded ZIP, extract it to private staging,
// register the bundle version atomically via register_bundle_version, then
// promote extracted bytes to the final versioned prefix. Mirrors the
// bearer-auth pattern from cloudflare-stream-ingest.
//
// Security model: the client posts bundle bytes via supabase.functions.invoke
// with the end-user bearer token; we validate the user, then do all service-role
// writes (storage + RPC) with the validated user.id passed into
// register_bundle_version as p_uploaded_by.

import { createClient } from 'npm:@supabase/supabase-js@2';
import {
  BlobReader,
  ZipReader,
  Uint8ArrayWriter,
} from 'jsr:@zip-js/zip-js@2.7.72';
import {
  BUNDLE_BUCKET,
  BUNDLE_EXTENSION_ALLOWLIST,
  BUNDLE_MAX_COMPRESSED_BYTES,
  BUNDLE_MAX_ENTRIES,
  BUNDLE_MAX_EXPANSION_RATIO,
  BUNDLE_MAX_FILE_BYTES,
  BUNDLE_MAX_UNCOMPRESSED_TOTAL_BYTES,
  BUNDLE_CONTENT_TYPES,
  type BundleErrorCode,
} from '../_shared/bundle-constants.ts';
import { parseManifestJson, type BundleManifestV1 } from '../_shared/bundle-manifest.ts';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers':
    'authorization, content-type, x-client-info, apikey, x-supabase-function-secret',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

function errorResponse(status: number, code: BundleErrorCode, message: string) {
  return new Response(JSON.stringify({ error: { code, message } }), {
    status,
    headers: { ...JSON_HEADERS, ...CORS_HEADERS },
  });
}

function okResponse(body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { ...JSON_HEADERS, ...CORS_HEADERS },
  });
}

function lowerExt(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

function contentTypeFor(name: string): string {
  const ext = lowerExt(name);
  return BUNDLE_CONTENT_TYPES[ext] ?? 'application/octet-stream';
}

function isSafeRelativePath(name: string): boolean {
  if (!name || name.length === 0) return false;
  if (name.includes('\\')) return false;
  if (name.startsWith('/')) return false;
  const parts = name.split('/');
  if (parts.some((p) => p === '' || p === '.' || p === '..')) return false;
  return true;
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const arr = new Uint8Array(digest);
  return Array.from(arr).map((b) => b.toString(16).padStart(2, '0')).join('');
}

interface ExtractedFile {
  name: string;
  bytes: Uint8Array;
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: CORS_HEADERS });
  }

  if (req.method !== 'POST') {
    return errorResponse(405, 'bundle_auth_required', 'Method not allowed');
  }

  const authHeader = req.headers.get('authorization');
  if (!authHeader) {
    return errorResponse(401, 'bundle_auth_required', 'Missing authorization header');
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const supabaseServiceKey =
    Deno.env.get('SB_SECRET_KEY') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

  if (!supabaseUrl || !supabaseServiceKey) {
    return errorResponse(500, 'bundle_register_failed', 'Missing required environment variables');
  }

  const accessToken = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (!accessToken) {
    return errorResponse(401, 'bundle_auth_required', 'Invalid authorization header');
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: authData, error: authError } = await supabase.auth.getUser(accessToken);
  if (authError || !authData?.user) {
    return errorResponse(401, 'bundle_auth_required', 'Invalid token');
  }
  const userId = authData.user.id;

  // Parse multipart form — expect fields: postId, zip (File).
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return errorResponse(400, 'bundle_not_zip', 'Request must be multipart/form-data');
  }

  const postId = formData.get('postId');
  const zipFile = formData.get('zip');
  if (typeof postId !== 'string' || !postId) {
    return errorResponse(400, 'bundle_post_not_found', 'postId is required');
  }
  if (!(zipFile instanceof File)) {
    return errorResponse(400, 'bundle_not_zip', 'zip file is required');
  }

  if (zipFile.size > BUNDLE_MAX_COMPRESSED_BYTES) {
    return errorResponse(413, 'bundle_zip_too_large', 'Compressed ZIP exceeds 20 MB');
  }
  if (zipFile.size === 0) {
    return errorResponse(400, 'bundle_not_zip', 'ZIP is empty');
  }
  if (!/\.zip$/i.test(zipFile.name) && zipFile.type && !/zip/.test(zipFile.type)) {
    return errorResponse(400, 'bundle_not_zip', 'Upload must be a .zip archive');
  }

  // Ownership check: post exists and caller owns it (or is admin). Also
  // capture render_mode so we can restore it if promotion fails later and
  // this upload was the only bundle candidate for the post.
  const { data: postRow, error: postError } = await supabase
    .from('posts')
    .select('id, member_id, render_mode, members!inner(member_id, auth_user_id)')
    .eq('id', postId)
    .maybeSingle();
  if (postError || !postRow) {
    return errorResponse(404, 'bundle_post_not_found', 'Post not found');
  }
  type MemberSlice = { auth_user_id: string | null };
  const memberSlice = Array.isArray(postRow.members)
    ? (postRow.members[0] as MemberSlice | undefined)
    : (postRow.members as MemberSlice | undefined);
  const ownerAuthId = memberSlice?.auth_user_id ?? null;
  const priorRenderMode = (postRow as unknown as { render_mode: string }).render_mode ?? 'link';
  let isAdmin = false;
  if (ownerAuthId !== userId) {
    const { data: adminCheck } = await supabase.rpc('is_admin', { check_user_id: userId });
    isAdmin = Boolean(adminCheck);
    if (!isAdmin) {
      return errorResponse(404, 'bundle_post_not_found', 'Post not found or not owned');
    }
  }

  // Hash the raw ZIP bytes for per-post dedup.
  const zipBytes = new Uint8Array(await zipFile.arrayBuffer());
  const zipSha256 = await sha256Hex(zipBytes);

  const { data: duplicate } = await supabase
    .from('post_bundles')
    .select('id')
    .eq('post_id', postId)
    .eq('sha256', zipSha256)
    .maybeSingle();
  if (duplicate) {
    return errorResponse(409, 'bundle_duplicate_upload', 'This exact ZIP already exists for the post');
  }

  // Stream-extract the ZIP.
  const blob = new Blob([zipBytes as BlobPart], { type: 'application/zip' });
  const reader = new ZipReader(new BlobReader(blob));
  let entries;
  try {
    entries = await reader.getEntries();
  } catch {
    await reader.close();
    return errorResponse(400, 'bundle_not_zip', 'Unable to read ZIP directory');
  }

  if (entries.length > BUNDLE_MAX_ENTRIES) {
    await reader.close();
    return errorResponse(413, 'bundle_too_many_entries', `ZIP has more than ${BUNDLE_MAX_ENTRIES} entries`);
  }

  const extracted: ExtractedFile[] = [];
  let totalUncompressed = 0;
  let manifestRaw: string | null = null;

  try {
    for (const entry of entries) {
      if (!entry.filename) continue;
      if (entry.directory) continue;

      if (
        entry.externalFileAttribute !== undefined &&
        ((entry.externalFileAttribute >>> 16) & 0o170000) === 0o120000
      ) {
        return errorResponse(400, 'bundle_symlink_disallowed', 'Archive contains a symlink');
      }

      if (!isSafeRelativePath(entry.filename)) {
        return errorResponse(400, 'bundle_invalid_path', `Unsafe path: ${entry.filename}`);
      }

      const ext = lowerExt(entry.filename);
      const isManifest = entry.filename === 'post.json';
      if (!isManifest && !BUNDLE_EXTENSION_ALLOWLIST.has(ext)) {
        return errorResponse(400, 'bundle_extension_disallowed', `Extension not allowed: ${entry.filename}`);
      }

      const uncompressed = entry.uncompressedSize ?? 0;
      if (uncompressed > BUNDLE_MAX_FILE_BYTES) {
        return errorResponse(413, 'bundle_file_too_large', `File exceeds 10 MB: ${entry.filename}`);
      }

      totalUncompressed += uncompressed;
      if (totalUncompressed > BUNDLE_MAX_UNCOMPRESSED_TOTAL_BYTES) {
        return errorResponse(413, 'bundle_uncompressed_limit_exceeded', 'Total uncompressed exceeds 20 MB');
      }

      if (entry.getData) {
        const writer = new Uint8ArrayWriter();
        const data = await entry.getData(writer);
        extracted.push({ name: entry.filename, bytes: data });
        if (isManifest) {
          manifestRaw = new TextDecoder().decode(data);
        }
      }
    }
  } finally {
    await reader.close();
  }

  if (zipFile.size > 0) {
    const ratio = totalUncompressed / zipFile.size;
    if (ratio > BUNDLE_MAX_EXPANSION_RATIO) {
      return errorResponse(413, 'bundle_ratio_exceeded', 'Expansion ratio exceeds 50:1');
    }
  }

  if (!manifestRaw) {
    return errorResponse(400, 'bundle_manifest_missing', 'post.json is required at the ZIP root');
  }

  const manifestResult = parseManifestJson(manifestRaw);
  if (!manifestResult.ok) {
    return errorResponse(400, 'bundle_manifest_invalid', manifestResult.message);
  }
  const manifest: BundleManifestV1 = manifestResult.manifest;

  // Stage the extracted files.
  const uploadUuid = crypto.randomUUID();
  const stagingPrefix = `staging/${uploadUuid}`;

  for (const file of extracted) {
    const storagePath = `${stagingPrefix}/${file.name}`;
    const { error: uploadError } = await supabase.storage
      .from(BUNDLE_BUCKET)
      .upload(storagePath, file.bytes, {
        contentType: contentTypeFor(file.name),
        upsert: false,
      });
    if (uploadError) {
      await cleanupPrefix(supabase, stagingPrefix);
      return errorResponse(500, 'bundle_storage_write_failed', uploadError.message);
    }
  }

  // Register the bundle version atomically.
  const storagePrefixRoot = `bundles/${postId}`;
  const { data: registered, error: registerError } = await supabase.rpc(
    'register_bundle_version',
    {
      p_post_id: postId,
      p_storage_prefix: storagePrefixRoot,
      p_manifest: manifest,
      p_size_bytes: zipFile.size,
      p_file_count: extracted.length,
      p_sha256: zipSha256,
      p_uploaded_by: userId,
    },
  );
  if (registerError || !registered) {
    await cleanupPrefix(supabase, stagingPrefix);
    // Distinguish a (post_id, sha256) unique-violation race — another identical
    // bundle won the race between our client-side dedup check and the RPC.
    const errWithDetails = registerError as { code?: string; message?: string } | null;
    const msg = errWithDetails?.message ?? '';
    if (
      errWithDetails?.code === '23505' ||
      /duplicate key value|unique constraint|post_bundles_post_id_sha256_key/i.test(msg)
    ) {
      return errorResponse(409, 'bundle_duplicate_upload', 'This exact ZIP already exists for the post');
    }
    return errorResponse(500, 'bundle_register_failed', msg || 'Register failed');
  }

  type BundleRow = {
    id: string;
    post_id: string;
    version: number;
    storage_prefix: string;
    review_status: string;
    size_bytes: number;
    file_count: number;
    sha256: string;
  };
  const bundleRow = registered as unknown as BundleRow;
  const finalPrefix = bundleRow.storage_prefix;

  // Promote staging → final prefix, then delete staging.
  for (const file of extracted) {
    const fromPath = `${stagingPrefix}/${file.name}`;
    const toPath = `${finalPrefix}/${file.name}`;
    const { error: moveError } = await supabase.storage
      .from(BUNDLE_BUCKET)
      .move(fromPath, toPath);
    if (moveError) {
      await cleanupPrefix(supabase, finalPrefix);
      await cleanupPrefix(supabase, stagingPrefix);
      await supabase.from('post_bundles').delete().eq('id', bundleRow.id);

      // If the row we just deleted was the only bundle for this post,
      // restore the parent post's render_mode to its prior value so the
      // failed upload does not leave the post stuck in 'bundle' mode.
      const { count: remainingCount } = await supabase
        .from('post_bundles')
        .select('id', { count: 'exact', head: true })
        .eq('post_id', postId);
      if ((remainingCount ?? 0) === 0 && priorRenderMode !== 'bundle') {
        await supabase
          .from('posts')
          .update({ render_mode: priorRenderMode })
          .eq('id', postId);
      }

      return errorResponse(500, 'bundle_promotion_failed', moveError.message);
    }
  }
  await cleanupPrefix(supabase, stagingPrefix);

  // register_bundle_version auto-approves + sets active_bundle_version_id
  // when the uploader is the post's author (see 20260421165619 migration).
  // In that case the bundle is already live, so hand back the public post
  // URL. Admin-uploading-on-someone-else's-behalf still lands on
  // ?preview=<id> until an admin runs approve_bundle.
  const isActive = bundleRow.review_status === 'approved';
  const previewUrl = isActive
    ? `/posts/id/${bundleRow.post_id}`
    : `/posts/id/${bundleRow.post_id}?preview=${bundleRow.id}`;

  return okResponse({
    bundleVersionId: bundleRow.id,
    postId: bundleRow.post_id,
    version: bundleRow.version,
    reviewStatus: bundleRow.review_status,
    sizeBytes: bundleRow.size_bytes,
    fileCount: bundleRow.file_count,
    sha256: bundleRow.sha256,
    previewUrl,
  });
});

async function cleanupPrefix(
  supabase: ReturnType<typeof createClient>,
  prefix: string,
): Promise<void> {
  const { data: list } = await supabase.storage.from(BUNDLE_BUCKET).list(prefix, {
    limit: 1000,
    sortBy: { column: 'name', order: 'asc' },
  });
  if (!list || list.length === 0) return;
  const paths = list.map((row) => `${prefix}/${row.name}`);
  await supabase.storage.from(BUNDLE_BUCKET).remove(paths);
}
