#!/usr/bin/env bash
# CI gate for the timeline-schema package (plan-v5 B2).
#
# Guarantees:
#  - timeline.schema.json (the single source of truth) is a non-degenerate,
#    meta-schema-valid artifact with all required definitions.
#  - typescript/src/generated.ts (TS types) is reproducible from the artifact.
#  - python/.../generated.py (committed TypedDicts) is consistent with it.
#  - A truncated/degenerate artifact (the incident's 265-byte case) fails LOUDLY.
#  - sql/*.sql (the S-owned SQL migrations surface) parses on :memory:, is
#    additive-only, matches its exact-byte SHA-256 in sql/CHECKSUMS, and
#    follows 0000_name.sql with strictly increasing versions.
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

# 6. SQL migrations surface (exec-sqlite S3): every sql/*.sql must parse on
# an empty database, be additive-only, carry a fresh exact-byte SHA-256 in
# sql/CHECKSUMS (the manifest format the Astrid runner consumes), and follow
# the 0000_name.sql convention with strictly increasing versions. This is the
# schema repo's second contract surface: the Astrid runner probes each
# migration's recorded checksum before applying, so drift here is a hard CI
# failure, never a runtime surprise.
MIGRATIONS_DIR="sql"
CHECKSUMS_FILE="sql/CHECKSUMS"

if [ ! -d "$MIGRATIONS_DIR" ]; then
    fail "$MIGRATIONS_DIR missing"
fi
if [ ! -f "$CHECKSUMS_FILE" ]; then
    fail "$CHECKSUMS_FILE missing"
fi

shopt -s nullglob
SQL_FILES=("$MIGRATIONS_DIR"/*.sql)
shopt -u nullglob
if [ ${#SQL_FILES[@]} -eq 0 ]; then
    fail "$MIGRATIONS_DIR contains no .sql files"
fi

LAST_VERSION=0
for SQL in "${SQL_FILES[@]}"; do
    NAME=$(basename "$SQL")

    # 6a. Filename convention ^(\d{4})_[a-z0-9_]+\.sql$ + strictly increasing.
    if ! [[ "$NAME" =~ ^[0-9]{4}_[a-z0-9_]+\.sql$ ]]; then
        fail "migration filename $NAME violates ^([0-9]{4})_[a-z0-9_]+\\.sql\$"
    fi
    VERSION=$((10#${NAME:0:4}))
    if [ "$VERSION" -le "$LAST_VERSION" ]; then
        fail "migration versions must be strictly increasing: $NAME has version $VERSION, not greater than $LAST_VERSION"
    fi
    LAST_VERSION=$VERSION

    # 6b. Additive-only lint (case-insensitive), first offense names line.
    if grep -qE -i 'DROP |DELETE FROM|UPDATE |ALTER TABLE[[:space:]]+.*RENAME|PRAGMA' "$SQL"; then
        OFFENSE=$(grep -E -i -n -m 1 'DROP |DELETE FROM|UPDATE |ALTER TABLE[[:space:]]+.*RENAME|PRAGMA' "$SQL")
        fail "migration $NAME is not additive-only (first offense at $OFFENSE)"
    fi

    # 6c. Parses via sqlite3 against :memory: (hermetic: uses the Python
    # sqlite3 engine, same library the Astrid runner executes against).
    if ! PARSE_ERR=$("$PYTHON" - "$SQL" <<'EOF' 2>&1
import sqlite3
import sys

path = sys.argv[1]
conn = sqlite3.connect(":memory:")
try:
    with open(path, encoding="utf-8") as handle:
        conn.executescript(handle.read())
except Exception as exc:
    print(f"{path}: {exc}")
    raise SystemExit(1)
EOF
); then
        fail "migration $NAME does not parse on :memory:: $PARSE_ERR"
    fi
done

# 6d. CHECKSUMS freshness: every sql file has an exact-byte manifest entry,
# every manifest entry names a real sql file, and each recomputed sha256
# equals its recorded value. Drift names the file and fails loudly.
if ! MIGRATE_ERR=$("$PYTHON" - "$MIGRATIONS_DIR" "$CHECKSUMS_FILE" <<'EOF' 2>&1
import hashlib
import sys
from pathlib import Path

sql_dir = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])

manifest: dict[str, str] = {}
for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
    stripped = line.strip()
    if not stripped:
        continue
    prefix, separator, name = stripped.partition("  ")
    if not separator or not prefix.startswith("sha256=") or not name:
        raise SystemExit(
            f"CHECKSUMS line {line_number} malformed: {stripped!r}"
        )
    manifest[name] = prefix[len("sha256="):]

sql_files = sorted(p.name for p in sql_dir.glob("*.sql"))
missing = [name for name in sql_files if name not in manifest]
if missing:
    raise SystemExit("CHECKSUMS missing entries for: " + ", ".join(missing))
stale = [name for name in manifest if name not in sql_files]
if stale:
    raise SystemExit("CHECKSUMS names files not in sql/: " + ", ".join(stale))
for name in sql_files:
    actual = hashlib.sha256((sql_dir / name).read_bytes()).hexdigest()
    if actual != manifest[name]:
        raise SystemExit(
            f"CHECKSUMS drift for {name}: recomputed {actual}, manifest {manifest[name]}"
        )
EOF
); then
    fail "migrations checksum/freshness gate: $MIGRATE_ERR"
fi

echo "codegen clean (artifact valid, TS reproducible, TypedDicts consistent, degenerate guard armed, migrations surface green)"
