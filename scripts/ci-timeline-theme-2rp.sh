#!/usr/bin/env bash
# Workspace CI entry point for the @banodoco/timeline-theme-2rp peer-dep
# package (Sprint 5 deliverable).
#
# Runs:
#   1. Asserts package.json shape (peer-deps + exports).
#   2. Asserts theme.json + per-effect schema/defaults/meta exist.
#   3. Tolerant tsc --noEmit against the effect components, with the
#      `@banodoco/timeline-composition/theme-api` sub-path mapped at the
#      workspace location. Workspace-alias and remotion-resolution noise
#      that's bundler-resolved at consume-time is filtered.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="$WORKSPACE_ROOT/packages/timeline-theme-2rp"

cd "$PKG"

# 1. package.json shape.
echo "→ package.json shape"
node -e "
const pkg = require('./package.json');
if (pkg.name !== '@banodoco/timeline-theme-2rp') { console.error('bad name'); process.exit(1); }
const peers = pkg.peerDependencies ?? {};
for (const k of ['@banodoco/timeline-composition', 'react', 'remotion']) {
  if (!peers[k]) { console.error('missing peer dep:', k); process.exit(1); }
}
const xp = pkg.exports ?? {};
if (!xp['./theme.json']) { console.error('exports[\"./theme.json\"] missing'); process.exit(1); }
console.log('ok');
"

# 2. theme.json + per-effect files.
echo "→ theme.json + effect files"
test -f theme.json || { echo "theme.json missing"; exit 1; }
for fx in section-hook art-card cta-card resource-card; do
  for f in component.tsx schema.json defaults.json meta.json; do
    test -f "src/effects/$fx/$f" || { echo "missing src/effects/$fx/$f"; exit 1; }
  done
done
echo "✓ theme.json and 4 effects present"

# 3. tsc --noEmit. We use a one-off tsconfig that resolves react/remotion
# via tools/remotion/node_modules and the timeline-composition sub-path
# at its source.
TMP_TSCONFIG="$(mktemp -t timeline-theme-2rp.XXXXXX.json)"
cat > "$TMP_TSCONFIG" <<EOF
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "strict": false,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true,
    "isolatedModules": true,
    "baseUrl": "$PKG",
    "paths": {
      "@banodoco/timeline-composition/theme-api": ["$WORKSPACE_ROOT/packages/timeline-composition/typescript/src/theme-api.ts"],
      "react": ["$WORKSPACE_ROOT/tools/remotion/node_modules/@types/react/index.d.ts"],
      "remotion": ["$WORKSPACE_ROOT/tools/remotion/node_modules/remotion"],
      "@remotion/layout-utils": ["$WORKSPACE_ROOT/tools/remotion/node_modules/@remotion/layout-utils"]
    },
    "typeRoots": ["$WORKSPACE_ROOT/tools/remotion/node_modules/@types"]
  },
  "include": ["$PKG/src/effects/*/component.tsx"]
}
EOF
trap 'rm -f "$TMP_TSCONFIG"' EXIT

TSC_BIN="$WORKSPACE_ROOT/packages/timeline-composition/node_modules/.bin/tsc"
if [ ! -x "$TSC_BIN" ]; then
  echo "✗ tsc not found at $TSC_BIN — run npm install in packages/timeline-composition first" >&2
  exit 1
fi
echo "→ tsc --noEmit over component.tsx files"
TSC_OUT="$("$TSC_BIN" -p "$TMP_TSCONFIG" 2>&1 || true)"
# Tolerate workspace-only / bundle-only noise. Component-internal errors fail.
TSC_FILTERED="$(echo "$TSC_OUT" | grep -E "src/effects/.*component\.tsx" || true)"
if [ -n "$TSC_FILTERED" ]; then
  echo "✗ tsc surfaced errors in component.tsx files:"
  echo "$TSC_FILTERED"
  exit 1
fi
echo "✓ component.tsx files type-check"
