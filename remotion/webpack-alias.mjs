import path from 'node:path';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ACTIVE_THEME_DIR = path.resolve(__dirname, '_active_theme');
const ASTRID_DIR = path.resolve(__dirname, '..');
const RENDERING_PACK_ELEMENTS_DIR = path.resolve(ASTRID_DIR, 'astrid/packs/rendering/elements');
const LOCAL_PACK_ELEMENTS_DIR = path.resolve(ASTRID_DIR, 'astrid/packs/local/elements');

const extraPackAliases = {};
for (const rawRoot of (process.env.ASTRID_PACKS_PATH ?? '').split(path.delimiter)) {
  if (!rawRoot) continue;
  const root = path.resolve(rawRoot);
  let children = [];
  try { children = fs.readdirSync(root); } catch { continue; }
  for (const child of children) {
    const packRoot = path.join(root, child);
    let stat;
    try { stat = fs.statSync(packRoot); } catch { continue; }
    if (child === 'local' || !stat.isDirectory()) continue;
    let packId = child;
    for (const manifestName of ['pack.yaml', 'pack.yml', 'pack.json']) {
      try {
        const manifest = fs.readFileSync(path.join(packRoot, manifestName), 'utf8');
        const match = manifestName === 'pack.json'
          ? JSON.parse(manifest).id
          : manifest.match(/^id:\s*([A-Za-z0-9_-]+)/m)?.[1];
        if (typeof match === 'string' && match) packId = match;
        break;
      } catch { /* try the next manifest */ }
    }
    for (const kind of ['effects', 'animations', 'transitions']) {
      const elements = path.join(packRoot, 'elements', kind);
      try {
        if (fs.statSync(elements).isDirectory()) {
          extraPackAliases[`@pack-${packId}-elements-${kind}`] = elements;
        }
      } catch { /* absent kind root */ }
    }
  }
}
// Workspace-level effects/animations/transitions/themes/* live above the
// Remotion project, so their nearest node_modules walks up past the
// tools/remotion install. Add the Remotion project's node_modules to
// resolve.modules so they can `import` npm packages like
// @remotion/layout-utils that ship with this project.
const REMOTION_NODE_MODULES = path.resolve(__dirname, 'node_modules');

const primitiveAliases = {
  '@theme-elements-effects': path.resolve(ACTIVE_THEME_DIR, 'elements/effects'),
  '@theme-effects': path.resolve(ACTIVE_THEME_DIR, 'effects'),
  '@pack-local-elements-effects': path.resolve(LOCAL_PACK_ELEMENTS_DIR, 'effects'),
  '@pack-rendering-elements-effects': path.resolve(RENDERING_PACK_ELEMENTS_DIR, 'effects'),
  '@theme-elements-animations': path.resolve(ACTIVE_THEME_DIR, 'elements/animations'),
  '@theme-animations': path.resolve(ACTIVE_THEME_DIR, 'animations'),
  '@pack-local-elements-animations': path.resolve(LOCAL_PACK_ELEMENTS_DIR, 'animations'),
  '@pack-rendering-elements-animations': path.resolve(RENDERING_PACK_ELEMENTS_DIR, 'animations'),
  '@theme-elements-transitions': path.resolve(ACTIVE_THEME_DIR, 'elements/transitions'),
  '@theme-transitions': path.resolve(ACTIVE_THEME_DIR, 'transitions'),
  '@pack-local-elements-transitions': path.resolve(LOCAL_PACK_ELEMENTS_DIR, 'transitions'),
  '@pack-rendering-elements-transitions': path.resolve(RENDERING_PACK_ELEMENTS_DIR, 'transitions'),
  '@workspace-animations': path.resolve(RENDERING_PACK_ELEMENTS_DIR, 'animations'),
  '@workspace-effects': path.resolve(RENDERING_PACK_ELEMENTS_DIR, 'effects'),
      '@workspace-transitions': path.resolve(RENDERING_PACK_ELEMENTS_DIR, 'transitions'),
      ...extraPackAliases,
};

export const applyRemotionPrimitiveAliases = (currentConfiguration) => ({
  ...currentConfiguration,
  resolve: {
    ...currentConfiguration.resolve,
    alias: {
      ...currentConfiguration.resolve?.alias,
      ...primitiveAliases,
    },
    modules: [
      ...(currentConfiguration.resolve?.modules ?? ['node_modules']),
      REMOTION_NODE_MODULES,
    ],
  },
});

export const applyWorkspaceEffectsAlias = applyRemotionPrimitiveAliases;
