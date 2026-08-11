// Generate TypeScript declarations from the canonical timeline.schema.json.
// The JSON Schema is the single source of truth (plan-v5 B2); this script is
// the only generator. Run via `npm run gen:types`.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const schemaPath = resolve(root, 'python/banodoco_timeline_schema/timeline.schema.json');
const outPath = resolve(root, 'typescript/src/generated.ts');

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));

// Guard: refuse to emit a degenerate artifact (the incident's 265-byte
// truncation must fail here, before anything downstream sees it).
// TimelineConfig is the root object; the definitions are the shared types.
const requiredDefinitions = ['TimelineClip', 'Theme', 'ThemeOverrides', 'TimelineOutput', 'AssetEntry'];
const definitions = schema.definitions ?? {};
if (!schema.type || !schema.properties || Object.keys(schema.properties).length === 0) {
  throw new Error('degenerate artifact: root TimelineConfig missing type/properties');
}
for (const name of requiredDefinitions) {
  const def = definitions[name];
  if (!def || typeof def !== 'object' || Object.keys(def).length === 0) {
    throw new Error(`degenerate artifact: definition '${name}' missing or empty`);
  }
}

const ts = await compile(schema, 'TimelineConfig', {
  bannerComment: '/* eslint-disable */\n/**\n * Generated from timeline.schema.json by scripts/emit-ts-types.mjs.\n * Do not edit by hand — regenerate with `npm run gen:types`.\n */',
  // Definitions not referenced from the root (Theme, AssetEntry) must still be
  // emitted — they are part of the public type surface.
  unreachableDefinitions: true,
});

// Backward-compatible inferred-type aliases (previously z.infer<...>).
const aliases = [
  'export type TimelineClipT = TimelineClip;',
  'export type TimelineConfigT = TimelineConfig;',
  'export type ThemeT = Theme;',
  'export type ThemeOverridesT = ThemeOverrides;',
  'export type TimelineOutputT = TimelineOutput;',
  'export type AssetEntryT = AssetEntry;',
].join('\n');

writeFileSync(outPath, `${ts}\n${aliases}\n`);
console.log(`wrote ${outPath} (${ts.length + aliases.length} chars)`);
