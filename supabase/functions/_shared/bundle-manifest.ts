// Shared bundle manifest validator — Deno/Edge-compatible mirror of
// banodoco-website/src/features/bundlePosts/manifestSchema.ts.
//
// Keep these two files in lockstep: the parity test at
// banodoco-website/scripts/check-manifest-schemas.mjs iterates the fixtures
// in banodoco-website/testdata/bundle-manifests/ through BOTH validators
// and fails on any divergence.

export interface BundleManifestV1 {
  schemaVersion: 1;
  title: string;
  summary?: string;
  entry: string;
  ogImage?: string;
  source?: 'vibe' | 'manual';
  layout: {
    mode: 'inline-fixed' | 'inline-auto' | 'fullscreen';
    minHeight?: number;
    maxHeight?: number;
    aspectRatio?: number;
    allowFullscreenToggle?: boolean;
  };
  capabilities?: {
    scripts?: boolean;
    pointerLock?: boolean;
    popups?: boolean;
  };
  authoredAt?: string;
}

type ManifestValidationResult =
  | { ok: true; manifest: BundleManifestV1 }
  | { ok: false; code: 'bundle_manifest_invalid'; message: string };

const fail = (message: string): ManifestValidationResult => ({
  ok: false,
  code: 'bundle_manifest_invalid',
  message,
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const hasHtmlMarkup = (value: string): boolean => /[<>]/.test(value);

const isRelativeBundlePath = (
  value: unknown,
  { requireHtml = false }: { requireHtml?: boolean } = {},
): value is string => {
  if (typeof value !== 'string' || value.length === 0) return false;
  if (value.startsWith('/') || value.startsWith('\\') || value.includes('\\')) return false;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return false;

  const parts = value.split('/');
  if (parts.some((part) => part === '' || part === '.' || part === '..')) return false;

  return requireHtml ? /\.html?$/i.test(value) : true;
};

const isPositiveInteger = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value > 0;

const isPositiveNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;

const isIsoTimestamp = (value: unknown): value is string => {
  if (typeof value !== 'string') return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && value.includes('T');
};

export function validateManifest(input: unknown): ManifestValidationResult {
  if (!isRecord(input)) return fail('Manifest must be a JSON object.');
  if (input.schemaVersion !== 1) return fail('schemaVersion must equal 1.');

  if (
    typeof input.title !== 'string' ||
    input.title.trim().length === 0 ||
    input.title.length > 120 ||
    hasHtmlMarkup(input.title)
  ) {
    return fail('title must be plain text between 1 and 120 characters.');
  }

  if (input.summary !== undefined) {
    if (
      typeof input.summary !== 'string' ||
      input.summary.length > 200 ||
      hasHtmlMarkup(input.summary)
    ) {
      return fail('summary must be plain text up to 200 characters.');
    }
  }

  if (!isRelativeBundlePath(input.entry, { requireHtml: true })) {
    return fail('entry must be a relative .html path inside the bundle.');
  }

  if (input.ogImage !== undefined && !isRelativeBundlePath(input.ogImage)) {
    return fail('ogImage must be a relative bundle path when present.');
  }

  if (input.source !== undefined && input.source !== 'vibe' && input.source !== 'manual') {
    return fail("source must be 'vibe' or 'manual' when present.");
  }

  if (!isRecord(input.layout)) return fail('layout is required.');

  const { layout } = input;
  if (layout.mode !== 'inline-fixed' && layout.mode !== 'inline-auto' && layout.mode !== 'fullscreen') {
    return fail('layout.mode must be inline-fixed, inline-auto, or fullscreen.');
  }

  if (layout.allowFullscreenToggle !== undefined && typeof layout.allowFullscreenToggle !== 'boolean') {
    return fail('layout.allowFullscreenToggle must be a boolean when present.');
  }

  if (layout.mode === 'inline-fixed') {
    if (!isPositiveNumber(layout.aspectRatio)) return fail('inline-fixed layout requires a positive aspectRatio.');
    if (layout.minHeight !== undefined || layout.maxHeight !== undefined) {
      return fail('inline-fixed layout does not allow minHeight or maxHeight.');
    }
  }

  if (layout.mode === 'inline-auto') {
    if (
      !isPositiveInteger(layout.minHeight) ||
      !isPositiveInteger(layout.maxHeight) ||
      (layout.minHeight as number) > (layout.maxHeight as number)
    ) {
      return fail('inline-auto layout requires positive minHeight and maxHeight with minHeight <= maxHeight.');
    }
    if (layout.aspectRatio !== undefined) return fail('inline-auto layout does not allow aspectRatio.');
  }

  if (
    layout.mode === 'fullscreen' &&
    (layout.aspectRatio !== undefined || layout.minHeight !== undefined || layout.maxHeight !== undefined)
  ) {
    return fail('fullscreen layout does not allow inline sizing fields.');
  }

  if (input.capabilities !== undefined) {
    if (!isRecord(input.capabilities)) return fail('capabilities must be an object when present.');

    for (const key of ['scripts', 'pointerLock', 'popups'] as const) {
      const value = input.capabilities[key];
      if (value !== undefined && typeof value !== 'boolean') {
        return fail(`capabilities.${key} must be a boolean when present.`);
      }
    }
  }

  if (input.authoredAt !== undefined && !isIsoTimestamp(input.authoredAt)) {
    return fail('authoredAt must be a valid ISO-8601 timestamp when present.');
  }

  return { ok: true, manifest: input as unknown as BundleManifestV1 };
}

export function parseManifestJson(raw: string): ManifestValidationResult {
  try {
    return validateManifest(JSON.parse(raw));
  } catch {
    return fail('Manifest must be valid JSON.');
  }
}
