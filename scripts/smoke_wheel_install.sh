#!/usr/bin/env bash
set -euo pipefail

# smoke_wheel_install.sh
# Blocking clean wheel-install proof.
#
# Builds a wheel from the source tree, creates an isolated throwaway
# virtual environment, installs the built wheel (NOT editable), and
# runs the blocking core health check: `import astrid` + `astrid doctor`.
#
# This is the CI hard-gate that proves the package is importable when
# installed from its wheel -- the closest approximation to what a user
# running `pip install astrid` will experience.
#
# Private/local pack dependencies (e.g. runpod-lifecycle, pyannote.audio)
# are intentionally NOT installed here -- they remain optional and are
# documented in pyproject.toml and the relevant pack-level requirements.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${SMOKE_WHEEL_VENV_DIR:-$(mktemp -d)/astrid-wheel-smoke-venv}"
DIST_DIR="$REPO_ROOT/dist"

cleanup() {
  if [ "${SMOKE_KEEP_VENV:-0}" != "1" ]; then
    rm -rf "$VENV_DIR"
  fi
}
trap cleanup EXIT

echo "=== clean wheel-install smoke ==="
echo "Repo root: $REPO_ROOT"

# -------------------------------------------------------------------
# 1. Build the wheel
# -------------------------------------------------------------------
echo ""
echo "--- Building wheel ---"
"$PYTHON_BIN" -m build --wheel --no-isolation --outdir "$DIST_DIR"

# Find the single wheel we just built (there should be exactly one after --no-isolation).
WHEEL=$(ls -1 "$DIST_DIR"/*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
  echo "ERROR: No wheel found in $DIST_DIR after build" >&2
  exit 1
fi
echo "Wheel: $WHEEL"

# -------------------------------------------------------------------
# 2. Create isolated venv and install the wheel
# -------------------------------------------------------------------
echo ""
echo "--- Creating throwaway venv at: $VENV_DIR ---"
"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip --quiet
python -m pip install "$WHEEL"

# -------------------------------------------------------------------
# 3. Blocking core health checks
# -------------------------------------------------------------------
echo ""
echo "--- Blocking import check ---"
python -c "import astrid; print('import astrid: OK')"

echo ""
echo "--- Blocking doctor check ---"
python -m astrid doctor --json

echo ""
echo "=== clean wheel-install smoke PASSED ==="
