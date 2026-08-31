import {Config} from '@remotion/cli/config';
import fs from 'node:fs';
import path from 'node:path';

const projectDir = process.cwd();
const activeThemeDir = path.resolve(projectDir, '_active_theme');
const astridDir = path.resolve(projectDir, '..');
const renderingPackElementsDir = path.resolve(astridDir, 'astrid/packs/rendering/elements');
const localPackElementsDir = path.resolve(astridDir, 'astrid/packs/local/elements');

// SDK invocations may explicitly add external pack roots.  The generated
// element registry uses one alias per owning pack; keep those aliases scoped
// to this render process so external components can be bundled without
// changing the durable local pack layout.
const extraPackAliases: Record<string, string> = {};
for (const rawRoot of (process.env.ASTRID_PACKS_PATH ?? '').split(path.delimiter)) {
  if (!rawRoot) continue;
  const root = path.resolve(rawRoot);
  let children: string[] = [];
  try { children = fs.readdirSync(root); } catch { continue; }
  for (const child of children) {
    const packRoot = path.join(root, child);
    let packStat;
    try { packStat = fs.statSync(packRoot); } catch { continue; }
    if (child === 'local' || !packStat.isDirectory()) continue;
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

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
Config.setChromiumOpenGlRenderer('swangle');
Config.overrideWebpackConfig((currentConfiguration) => ({
  ...currentConfiguration,
  resolve: {
    ...currentConfiguration.resolve,
    alias: {
      ...currentConfiguration.resolve?.alias,
      // Keep in sync with tools/remotion/webpack-alias.mjs.
      '@theme-elements-effects': path.resolve(activeThemeDir, 'elements/effects'),
      '@theme-effects': path.resolve(activeThemeDir, 'effects'),
      '@pack-local-elements-effects': path.resolve(localPackElementsDir, 'effects'),
      '@pack-rendering-elements-effects': path.resolve(renderingPackElementsDir, 'effects'),
      '@theme-elements-animations': path.resolve(activeThemeDir, 'elements/animations'),
      '@theme-animations': path.resolve(activeThemeDir, 'animations'),
      '@pack-local-elements-animations': path.resolve(localPackElementsDir, 'animations'),
      '@pack-rendering-elements-animations': path.resolve(renderingPackElementsDir, 'animations'),
      '@theme-elements-transitions': path.resolve(activeThemeDir, 'elements/transitions'),
      '@theme-transitions': path.resolve(activeThemeDir, 'transitions'),
      '@pack-local-elements-transitions': path.resolve(localPackElementsDir, 'transitions'),
      '@pack-rendering-elements-transitions': path.resolve(renderingPackElementsDir, 'transitions'),
      '@workspace-animations': path.resolve(renderingPackElementsDir, 'animations'),
      '@workspace-effects': path.resolve(renderingPackElementsDir, 'effects'),
      '@workspace-transitions': path.resolve(renderingPackElementsDir, 'transitions'),
      ...extraPackAliases,
    },
    modules: [
      ...(currentConfiguration.resolve?.modules ?? ['node_modules']),
      path.resolve(projectDir, 'node_modules'),
    ],
  },
}));
