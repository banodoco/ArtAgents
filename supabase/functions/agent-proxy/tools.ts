// Server-side tool application for the Vibe Mode agent-proxy.
//
// Mirrors the client-side virtualFileTree.ts invariants so the model's
// tool batch is validated identically on both sides. Reuses the shared
// `BUNDLE_EXTENSION_ALLOWLIST` and `BUNDLE_MAX_FILE_BYTES` so an author's
// preview and their final Ship It upload cannot diverge.

import {
  BUNDLE_EXTENSION_ALLOWLIST,
  BUNDLE_MAX_FILE_BYTES,
} from '../_shared/bundle-constants.ts';
import type {
  ToolResultSummary,
  ToolUseCall,
  VirtualFile,
  VirtualFileTree,
} from './types.ts';

export type PathValidation =
  | { ok: true; path: string; extension: string }
  | { ok: false; error: string };

export const validateRelativePath = (raw: unknown): PathValidation => {
  if (typeof raw !== 'string' || raw.length === 0) {
    return { ok: false, error: 'path must be a non-empty string' };
  }
  if (raw.startsWith('/') || raw.startsWith('\\') || raw.includes('\\')) {
    return { ok: false, error: 'path must be POSIX-style and relative (no leading / or backslashes)' };
  }
  if (/^[a-z][a-z0-9+.-]*:/i.test(raw)) {
    return { ok: false, error: 'path must not include a protocol scheme' };
  }
  const parts = raw.split('/');
  if (parts.some((part) => part === '' || part === '.' || part === '..')) {
    return { ok: false, error: 'path may not contain empty, "." or ".." segments' };
  }
  const lastDot = raw.lastIndexOf('.');
  if (lastDot === -1) {
    return { ok: false, error: 'path must carry a known file extension' };
  }
  const extension = raw.slice(lastDot).toLowerCase();
  if (!BUNDLE_EXTENSION_ALLOWLIST.has(extension)) {
    return { ok: false, error: `extension ${extension} is not in the bundle allowlist` };
  }
  return { ok: true, path: raw, extension };
};

export const byteLength = (text: string): number => new TextEncoder().encode(text).length;

const inferMime = (extension: string): string => {
  switch (extension) {
    case '.html':
    case '.htm':
      return 'text/html; charset=utf-8';
    case '.css':
      return 'text/css; charset=utf-8';
    case '.js':
    case '.mjs':
      return 'application/javascript; charset=utf-8';
    case '.json':
      return 'application/json; charset=utf-8';
    case '.svg':
      return 'image/svg+xml';
    default:
      return 'text/plain; charset=utf-8';
  }
};

export const applyWriteFile = (
  tree: VirtualFileTree,
  rawPath: unknown,
  rawContent: unknown,
): { ok: boolean; summary: string; error?: string; path: string } => {
  const pathCheck = validateRelativePath(rawPath);
  if (!pathCheck.ok) return { ok: false, summary: 'write_file rejected', error: pathCheck.error, path: String(rawPath ?? '') };
  if (typeof rawContent !== 'string') {
    return { ok: false, summary: 'write_file rejected', error: 'content must be a string', path: pathCheck.path };
  }
  if (byteLength(rawContent) > BUNDLE_MAX_FILE_BYTES) {
    return {
      ok: false,
      summary: 'write_file rejected',
      error: `content exceeds ${BUNDLE_MAX_FILE_BYTES} bytes`,
      path: pathCheck.path,
    };
  }
  const existing = tree[pathCheck.path];
  const file: VirtualFile = {
    path: pathCheck.path,
    kind: 'text',
    mime: existing?.mime ?? inferMime(pathCheck.extension),
    content: rawContent,
  };
  tree[pathCheck.path] = file;
  return {
    ok: true,
    summary: `write_file ${pathCheck.path} (${byteLength(rawContent)} bytes${existing ? ', overwritten' : ''})`,
    path: pathCheck.path,
  };
};

export const applyApplyPatch = (
  tree: VirtualFileTree,
  rawPath: unknown,
  rawSearch: unknown,
  rawReplace: unknown,
): { ok: boolean; summary: string; error?: string; path: string } => {
  const pathCheck = validateRelativePath(rawPath);
  if (!pathCheck.ok) return { ok: false, summary: 'apply_patch rejected', error: pathCheck.error, path: String(rawPath ?? '') };
  if (typeof rawSearch !== 'string' || typeof rawReplace !== 'string') {
    return {
      ok: false,
      summary: 'apply_patch rejected',
      error: 'search and replace must both be strings',
      path: pathCheck.path,
    };
  }
  const existing = tree[pathCheck.path];
  if (!existing || existing.kind !== 'text' || typeof existing.content !== 'string') {
    return {
      ok: false,
      summary: 'apply_patch rejected',
      error: `no text file exists at ${pathCheck.path}`,
      path: pathCheck.path,
    };
  }
  const occurrences = existing.content.split(rawSearch).length - 1;
  if (occurrences === 0) {
    return {
      ok: false,
      summary: 'apply_patch rejected',
      error: 'search block did not match any occurrence',
      path: pathCheck.path,
    };
  }
  if (occurrences > 1) {
    return {
      ok: false,
      summary: 'apply_patch rejected',
      error: `search block matched ${occurrences} occurrences; expected exactly 1`,
      path: pathCheck.path,
    };
  }
  const nextContent = existing.content.replace(rawSearch, rawReplace);
  if (byteLength(nextContent) > BUNDLE_MAX_FILE_BYTES) {
    return {
      ok: false,
      summary: 'apply_patch rejected',
      error: `resulting content exceeds ${BUNDLE_MAX_FILE_BYTES} bytes`,
      path: pathCheck.path,
    };
  }
  tree[pathCheck.path] = { ...existing, content: nextContent };
  return {
    ok: true,
    summary: `apply_patch ${pathCheck.path} (1 match replaced)`,
    path: pathCheck.path,
  };
};

export const applyToolBatch = (
  tree: VirtualFileTree,
  calls: ToolUseCall[],
): ToolResultSummary[] => {
  const results: ToolResultSummary[] = [];
  for (const call of calls) {
    if (call.name === 'write_file') {
      const input = call.input as { path?: unknown; content?: unknown };
      const res = applyWriteFile(tree, input.path, input.content);
      results.push({
        tool_use_id: call.id,
        tool: call.name,
        path: res.path,
        ok: res.ok,
        summary: res.summary,
        error: res.error,
      });
    } else if (call.name === 'apply_patch') {
      const input = call.input as { path?: unknown; search?: unknown; replace?: unknown };
      const res = applyApplyPatch(tree, input.path, input.search, input.replace);
      results.push({
        tool_use_id: call.id,
        tool: call.name,
        path: res.path,
        ok: res.ok,
        summary: res.summary,
        error: res.error,
      });
    } else {
      results.push({
        tool_use_id: call.id,
        tool: call.name,
        path: '',
        ok: false,
        summary: `unknown tool ${call.name}`,
        error: 'tool is not in the Vibe Mode allowlist',
      });
    }
  }
  return results;
};

export const TOOL_SCHEMAS = [
  {
    name: 'write_file',
    description:
      'Replace the full contents of a file in the bundle tree. Use when a full rewrite is clearly simpler than a targeted patch.',
    input_schema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'POSIX-relative path inside the bundle tree (no leading /, no ..).',
        },
        content: {
          type: 'string',
          description: 'Full new file contents. <=10MB.',
        },
      },
      required: ['path', 'content'],
    },
  },
  {
    name: 'apply_patch',
    description:
      'Replace exactly one occurrence of `search` with `replace` inside an existing text file. Fails if the match count is not exactly 1.',
    input_schema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'POSIX-relative path inside the bundle tree.',
        },
        search: {
          type: 'string',
          description: 'Exact substring to find. Must match exactly once.',
        },
        replace: {
          type: 'string',
          description: 'Replacement string.',
        },
      },
      required: ['path', 'search', 'replace'],
    },
  },
] as const;
