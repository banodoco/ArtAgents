// Shared constants for bundle-mode edge functions.

export const BUNDLE_MAX_COMPRESSED_BYTES = 20 * 1024 * 1024; // 20 MB
export const BUNDLE_MAX_UNCOMPRESSED_TOTAL_BYTES = 20 * 1024 * 1024; // 20 MB
export const BUNDLE_MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB per file
export const BUNDLE_MAX_ENTRIES = 500;
export const BUNDLE_MAX_EXPANSION_RATIO = 50;

export const BUNDLE_EXTENSION_ALLOWLIST = new Set<string>([
  '.html',
  '.css',
  '.js',
  '.mjs',
  '.json',
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
  '.gif',
  '.svg',
  '.ico',
  '.mp4',
  '.webm',
  '.mp3',
  '.wav',
  '.woff',
  '.woff2',
  '.ttf',
  '.otf',
  '.wasm',
]);

export const BUNDLE_PREVIEW_TTL_SECONDS = 5 * 60;

export const BUNDLE_BUCKET = 'post-bundles';

// Content-type fallback mapping keyed on lowercase extension (including the dot).
export const BUNDLE_CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.wasm': 'application/wasm',
};

export type BundleErrorCode =
  | 'bundle_auth_required'
  | 'bundle_post_not_found'
  | 'bundle_not_zip'
  | 'bundle_zip_too_large'
  | 'bundle_too_many_entries'
  | 'bundle_uncompressed_limit_exceeded'
  | 'bundle_file_too_large'
  | 'bundle_ratio_exceeded'
  | 'bundle_invalid_path'
  | 'bundle_symlink_disallowed'
  | 'bundle_extension_disallowed'
  | 'bundle_manifest_missing'
  | 'bundle_manifest_invalid'
  | 'bundle_duplicate_upload'
  | 'bundle_storage_write_failed'
  | 'bundle_register_failed'
  | 'bundle_promotion_failed';
