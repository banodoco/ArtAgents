#!/usr/bin/env bash
# Workspace CI entry point for the shared timeline-schema package.
# Re-runs the codegen pipeline, asserts no drift, runs both language test suites.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="$WORKSPACE_ROOT/packages/timeline-schema"

cd "$PKG"

if [ ! -d node_modules ]; then
    npm install
fi

# Verify the editable install is wired up so `from banodoco_timeline_schema ...`
# resolves the local source. Idempotent.
pip install -q -e python

bash scripts/check-codegen.sh
npm test
python -m unittest discover -s tests
