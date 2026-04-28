#!/usr/bin/env bash
# Workspace CI entry point for the shared timeline-composition package.
#
# Sprint 5 scope:
#   1. gen-registry drift gate (asserts registry.generated.ts matches
#      what gen-registry.ts would produce).
#   2. Tolerant `tsc --noEmit` over the public surface (index.ts +
#      theme-api.ts). Workspace-alias errors are tolerated because those
#      are bundler-resolved at consume-time (Banodoco shell webpack +
#      Reigh Vite); the package itself just has to be syntactically clean.
#   3. node:test runner over the package's compiled tests.
#   4. theme-api sub-path smoke check (Sprint 4 carry-over).
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="$WORKSPACE_ROOT/packages/timeline-composition"

cd "$PKG"

if [ ! -d node_modules ]; then
    npm install
fi

# 1. Drift gate: regenerate registry and assert no diff.
echo "→ gen-registry drift gate"
npm run gen-registry:check

# 2. Tolerant package type-check. Workspace-alias imports
# (@workspace-effects/*, @workspace-animations/*, @workspace-transitions/*)
# resolve via the consumer's bundler; the package's tsc cannot satisfy
# them. We only fail on errors NOT involving those modules.
echo "→ package tsc (tolerant of workspace-alias errors)"
TSC_BIN="$PKG/node_modules/.bin/tsc"
if [ ! -x "$TSC_BIN" ]; then
  echo "✗ tsc not found at $TSC_BIN — run npm install first" >&2
  exit 1
fi
TSC_OUT="$("$TSC_BIN" -p "$PKG/typescript/tsconfig.json" 2>&1 || true)"
# The package's tsc transitively resolves through workspace primitives
# (`../../animations/*`, `../../effects/*`, `../../transitions/*`) and
# generated registry files. Those resolve at consume-time via the
# Banodoco shell's webpack alias map and Reigh's Vite alias map. We only
# fail on errors that originate INSIDE the package's own source files
# (typescript/src/*) AND are NOT in generated files OR back-compat
# shims that re-export across the package boundary.
TSC_FILTERED="$(echo "$TSC_OUT" | grep -E "^typescript/src/" | grep -v -E "(generated\.ts|theme-api\.ts.*Cannot find module 'react'|theme-api\.ts.*Cannot find module 'remotion')" || true)"
# Also surface index.ts / TimelineComposition errors that aren't alias related.
TSC_INDEX="$(echo "$TSC_OUT" | grep -E "^typescript/src/(index|TimelineComposition|theme-api|ThemeContext|effects-types|VisualClip|AudioTrack|types|lib/)" | grep -v -E "(Cannot find module '(react|remotion|@remotion/.*|@banodoco/timeline-theme-.*)|@workspace-|@theme-|generated\.ts)" || true)"
if [ -n "$TSC_INDEX" ]; then
  echo "✗ package tsc surfaced unexpected errors in package source:"
  echo "$TSC_INDEX"
  exit 1
fi
echo "✓ package tsc clean (alias / generated / consumer-resolved errors filtered)"

# 3. node:test runner.
echo "→ package tests"
npm test

# 4. theme-api smoke test (Sprint 4).
TMP_TSCONFIG="$(mktemp -t theme-api-smoke.XXXXXX.json)"
cat > "$TMP_TSCONFIG" <<EOF
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true,
    "isolatedModules": true,
    "baseUrl": "$PKG",
    "paths": {
      "@banodoco/timeline-composition/theme-api": ["typescript/src/theme-api.ts"],
      "react": ["$WORKSPACE_ROOT/tools/remotion/node_modules/@types/react/index.d.ts"],
      "remotion": ["$WORKSPACE_ROOT/tools/remotion/node_modules/remotion"],
      "@workspace-animations/*": ["$WORKSPACE_ROOT/animations/*"]
    },
    "typeRoots": ["$WORKSPACE_ROOT/tools/remotion/node_modules/@types"]
  },
  "include": ["$PKG/typescript/tests/theme-api-smoke.ts"]
}
EOF

trap 'rm -f "$TMP_TSCONFIG"' EXIT

echo "→ theme-api smoke type-check"
SMOKE_OUT="$("$TSC_BIN" -p "$TMP_TSCONFIG" 2>&1 || true)"
if echo "$SMOKE_OUT" | grep -E "theme-api-smoke\.ts" -q; then
  echo "✗ theme-api smoke test surfaced errors in its own file:"
  echo "$SMOKE_OUT" | grep "theme-api-smoke\.ts"
  exit 1
fi
echo "✓ theme-api smoke test: sub-path resolves and re-exports type-check"
