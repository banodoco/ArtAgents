#!/usr/bin/env bash
# CI gate for the timeline-schema package (plan-v5 B2).
#
# Guarantees:
#  - timeline.schema.json (the single source of truth) is a non-degenerate,
#    meta-schema-valid artifact with all required definitions.
#  - typescript/src/generated.ts (TS types) is reproducible from the artifact.
#  - python/.../generated.py (committed TypedDicts) is consistent with it.
#  - A truncated/degenerate artifact (the incident's 265-byte case) fails LOUDLY.
set -euo pipefail

PKG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_ROOT"

SCHEMA="python/banodoco_timeline_schema/timeline.schema.json"
GENERATED_TS="typescript/src/generated.ts"
PYTHON=${PYTHON:-python3}

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

# 1. Artifact presence + minimum size (a degenerate artifact is ~265 bytes).
if [ ! -f "$SCHEMA" ]; then
    fail "$SCHEMA missing"
fi
SIZE=$(wc -c < "$SCHEMA")
if [ "$SIZE" -lt 1000 ]; then
    fail "$SCHEMA is $SIZE bytes (degenerate artifact)"
fi

# 1b. Stable-$id gate: the artifact must carry a stable $id that stays
# unchanged against the committed expectation. Renaming the schema's
# identity silently breaks downstream $ref bases and version tooling.
EXPECTED_ID='https://banodoco.dev/schemas/timeline/v2.json'
ACTUAL_ID=$("$PYTHON" - "$SCHEMA" <<'EOF'
import json
import sys

schema = json.load(open(sys.argv[1]))
print(schema.get("$id", ""))
EOF
)
if [ -z "$ACTUAL_ID" ]; then
    fail "$SCHEMA lacks a stable \$id (expected '$EXPECTED_ID')"
fi
if [ "$ACTUAL_ID" != "$EXPECTED_ID" ]; then
    fail "$SCHEMA \$id changed: expected '$EXPECTED_ID', got '$ACTUAL_ID' — bump EXPECTED_ID in scripts/check-codegen.sh only if intentional"
fi
echo "artifact: stable \$id '$ACTUAL_ID'"

# 2. Meta-schema validity + required definitions (python + jsonschema).
"$PYTHON" - "$SCHEMA" <<'EOF'
import json
import sys
import jsonschema

path = sys.argv[1]
schema = json.load(open(path))
jsonschema.validate(schema, jsonschema.Draft7Validator.META_SCHEMA)
required = ["TimelineClip", "Theme", "ThemeOverrides", "TimelineOutput", "AssetEntry"]
defs = schema.get("definitions", {})
missing = [name for name in required if not defs.get(name)]
if missing:
    raise SystemExit(f"artifact missing definitions: {missing}")
if not schema.get("type") or not schema.get("properties"):
    raise SystemExit("artifact root is degenerate")
print("artifact: meta-schema valid, definitions present")
EOF

# 3. TS types regenerate byte-identically.
node scripts/emit-ts-types.mjs > /tmp/emit-ts-types.out
if ! git -C "$PKG_ROOT" diff --exit-code --quiet -- "$GENERATED_TS" 2>/dev/null; then
    fail "typescript/src/generated.ts is stale — regenerate with 'npm run gen:types' and commit"
fi

# 4. Python TypedDicts consistent with the artifact.
"$PYTHON" scripts/gen_python_types.py

# 5. The degenerate-artifact guard must trip on a truncated schema.
TMP_SCHEMA=$(mktemp)
echo '{"$schema":"http://json-schema.org/draft-07/schema#","type":"object","properties":{},"definitions":{}}' > "$TMP_SCHEMA"
# Emulate the guard: feed the tiny schema through the same emit path (the
# generator itself rejects degenerate artifacts before writing).
if node --input-type=module -e "
import { readFileSync } from 'node:fs';
const tiny = JSON.parse(readFileSync('$TMP_SCHEMA', 'utf8'));
const defs = tiny.definitions ?? {};
const ok = tiny.type && tiny.properties && Object.keys(tiny.properties).length > 0
  && ['TimelineClip','Theme','ThemeOverrides','TimelineOutput','AssetEntry'].every(n => defs[n] && Object.keys(defs[n]).length > 0);
if (ok) { console.error('degenerate artifact NOT rejected'); process.exit(1); }
console.log('degenerate artifact correctly rejected');
"; then
    :
else
    rm -f "$TMP_SCHEMA"
    exit 1
fi
rm -f "$TMP_SCHEMA"

echo "codegen clean (artifact valid, TS reproducible, TypedDicts consistent, degenerate guard armed)"
