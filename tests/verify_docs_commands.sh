#!/usr/bin/env bash
set -euo pipefail

# verify_docs_commands.sh
# Extract command shapes from README.md and docs/templates/**/STAGE.md,
# skip placeholders/assets, and verify each unique subcommand path exists
# by running it with --help (or directly for doctor).
#
# Also expands [A|B|C] shorthand from README to verify each variant.

PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

FAILED=0
TMPFILE="$(mktemp)"
trap 'rm -f "$TMPFILE"' EXIT

echo "=== verify_docs_commands.sh ==="
echo "Extracting command shapes from docs..."

# 1. Extract python3 -m astrid lines from README.md text block
if [ -f "$REPO_ROOT/README.md" ]; then
  awk '/^```text$/{found=1; next} /^```$/{found=0} found' "$REPO_ROOT/README.md" | \
    grep -Eo 'python3 -m astrid [^ ]+( [^ ]+)?' >> "$TMPFILE" || true
fi

# 2. Extract bash fenced blocks from docs/templates/**/STAGE.md
while IFS= read -r -d '' stage_file; do
  awk '/^```bash$/{found=1; next} /^```$/{found=0} found' "$stage_file" | \
    grep -Eo 'python3 -m astrid [^ ]+( [^ ]+)?' >> "$TMPFILE" || true
done < <(find "$REPO_ROOT/docs/templates" -name 'STAGE.md' -print0 2>/dev/null || true)

echo ""
echo "Raw extracted command prefixes (before dedup):"
if [ -s "$TMPFILE" ]; then
  sort "$TMPFILE" | uniq -c | sort -rn
else
  echo "  (none found)"
fi
echo ""

# Deduplicate
sort -u -o "$TMPFILE" "$TMPFILE"

# Expand shorthand [A|B|C] entries using Python for reliable string handling
EXPANDED="$(mktemp)"
trap 'rm -f "$TMPFILE" "$EXPANDED"' EXIT

python3 - "$TMPFILE" "$EXPANDED" <<'PYEOF'
import sys, re

with open(sys.argv[1]) as f:
    lines = [l.strip() for l in f if l.strip()]

expanded = set()
for line in lines:
    m = re.search(r'\[([^]]+)\]', line)
    if m:
        variants = m.group(1).split('|')
        prefix = line[:m.start()]
        suffix = line[m.end():]
        for v in variants:
            expanded.add(prefix + v + suffix)
    else:
        expanded.add(line)

with open(sys.argv[2], 'w') as f:
    for e in sorted(expanded):
        f.write(e + '\n')
PYEOF

echo "After shorthand expansion:"
if [ -s "$EXPANDED" ]; then
  sort "$EXPANDED" | uniq -c | sort -rn
else
  echo "  (none)"
fi
echo ""

# Classify and verify each unique command shape
echo "Verifying unique subcommand paths..."
echo ""

while IFS= read -r cmd_prefix; do
  [ -z "$cmd_prefix" ] && continue

  # Skip if it contains placeholder tokens that indicate a non-literal example
  if echo "$cmd_prefix" | grep -qE 'builtin\.example|path/to/|<[^>]+>'; then
    echo "  SKIP (placeholder): $cmd_prefix"
    continue
  fi

  # doctor: run directly (safe health check)
  if [ "$cmd_prefix" = "python3 -m astrid doctor" ]; then
    echo -n "  RUN   $cmd_prefix ... "
    if $cmd_prefix >/dev/null 2>&1; then
      echo "OK"
    else
      echo "FAILED (exit=$?)"
      FAILED=1
    fi
    continue
  fi

  # All other commands: verify subcommand path exists via --help
  echo -n "  HELP  $cmd_prefix --help ... "
  if $cmd_prefix --help >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAILED (exit=$?)"
    FAILED=1
  fi
done < "$EXPANDED"

echo ""
if [ $FAILED -eq 0 ]; then
  echo "All docs command verifications passed."
else
  echo "Some verifications FAILED." >&2
  exit 1
fi
