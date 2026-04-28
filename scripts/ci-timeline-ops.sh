#!/usr/bin/env bash
# Workspace CI entry point for the shared timeline-ops package.
# Builds the TS package and runs node:test against the compiled tests.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="$WORKSPACE_ROOT/packages/timeline-ops"

cd "$PKG"

if [ ! -d node_modules ]; then
    npm install
fi

npm run build
npm test
