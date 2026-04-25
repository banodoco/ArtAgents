// Edge-side mirror of serializeForClaude() — builds the <file_tree> XML
// content part that opens every turn-1 user message. Keeps files in
// alphabetical path order so Anthropic's cache breakpoint stays stable.
// Binary assets emit path + ref only; blob bytes are NEVER sent to the
// model.

import type { VirtualFile, VirtualFileTree } from './types.ts';

const escapeXml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const escapeCdata = (value: string): string => value.replace(/]]>/g, ']]]]><![CDATA[>');

const renderFile = (file: VirtualFile): string => {
  if (file.kind === 'binary-asset') {
    const ref = file.assetId ? `asset-${file.assetId}` : 'asset-missing';
    return `<file path="${escapeXml(file.path)}" encoding="binary-asset" ref="${escapeXml(ref)}"/>`;
  }
  const content = typeof file.content === 'string' ? file.content : '';
  return `<file path="${escapeXml(file.path)}" mime="${escapeXml(file.mime || 'text/plain')}"><![CDATA[${escapeCdata(content)}]]></file>`;
};

export const serializeTreeForClaude = (tree: VirtualFileTree): string => {
  const paths = Object.keys(tree).sort();
  const body = paths.map((path) => renderFile(tree[path])).join('\n');
  return `<file_tree>\n${body}\n</file_tree>`;
};
