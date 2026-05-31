#!/usr/bin/env bash
set -euo pipefail

# smoke_fresh_clone.sh
# Reproducible fresh-clone / core smoke path.
#
# Installs ONLY the core + dev dependencies into a throwaway virtual
# environment, then runs the core health check. Private/local
# pack dependencies (e.g. runpod-lifecycle, pyannote.audio) are intentionally
# NOT installed here -- they remain optional and are documented in pyproject.toml
# and the relevant pack-level requirements files.
#
# This mirrors what a brand-new clone on a clean machine would do, so that
# dependency drift surfaces here rather than in someone's first run.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${SMOKE_VENV_DIR:-$(mktemp -d)/astrid-smoke-venv}"

cleanup() {
  if [ "${SMOKE_KEEP_VENV:-0}" != "1" ]; then
    rm -rf "$VENV_DIR"
  fi
}
trap cleanup EXIT

echo "=== fresh-clone core smoke ==="
echo "Repo root: $REPO_ROOT"
echo "Creating throwaway venv at: $VENV_DIR"

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
# requirements.txt declares the direct top-level dependencies for the core smoke.
python -m pip install -r requirements.txt
# Editable core install so `python -m astrid` resolves from the source tree.
python -m pip install -e .

echo ""
echo "=== core health check ==="
python -m astrid doctor --json
