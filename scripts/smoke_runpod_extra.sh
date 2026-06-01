#!/usr/bin/env bash
set -euo pipefail

# smoke_runpod_extra.sh
# Optional RunPod-extra validation lane.
#
# Attempts to install astrid[runpod] (which pulls in runpod-lifecycle>=0.3).
# If runpod-lifecycle is not resolvable from configured indices — the expected
# case on public CI without a private package index or local wheelhouse — the
# script exits 0 with a skip message.  This lane is NOT a gate; it cannot
# block the default public install proof.
#
# When private access IS available (e.g. PIP_INDEX_URL points at a private
# index, a pip.conf in the runner image, or a local wheelhouse is mounted),
# the script:
#   1. Installs the built wheel with the [runpod] extra.
#   2. Validates `import astrid`.
#   3. Performs a narrow `import runpod_lifecycle` check.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${SMOKE_RUNPOD_VENV_DIR:-$(mktemp -d)/astrid-runpod-smoke-venv}"
DIST_DIR="$REPO_ROOT/dist"

cleanup() {
  if [ "${SMOKE_KEEP_VENV:-0}" != "1" ]; then
    rm -rf "$VENV_DIR"
  fi
}
trap cleanup EXIT

echo "=== RunPod-extra validation (optional) ==="
echo "Repo root: $REPO_ROOT"

# -------------------------------------------------------------------
# 1. Ensure a wheel exists
# -------------------------------------------------------------------
if [ ! -d "$DIST_DIR" ] || ! ls "$DIST_DIR"/*.whl >/dev/null 2>&1; then
  echo ""
  echo "--- Building wheel (none found in dist/) ---"
  "$PYTHON_BIN" -m build --wheel --no-isolation --outdir "$DIST_DIR"
fi

WHEEL=$(ls -1 "$DIST_DIR"/*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
  echo "SKIP: No wheel found in $DIST_DIR; cannot validate RunPod extra." >&2
  exit 0
fi
echo "Wheel: $WHEEL"

# -------------------------------------------------------------------
# 2. Create isolated venv
# -------------------------------------------------------------------
echo ""
echo "--- Creating throwaway venv at: $VENV_DIR ---"
"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip --quiet

# -------------------------------------------------------------------
# 3. Attempt pip install astrid[runpod]
# -------------------------------------------------------------------
echo ""
echo "--- Attempting: pip install 'astrid[runpod]' ---"

# Capture stderr for diagnosis; pip often writes resolution errors there.
set +e
INSTALL_LOG="$(mktemp)"
python -m pip install "${WHEEL}[runpod]" >"$INSTALL_LOG" 2>&1
INSTALL_RC=$?
set -e

if [ "$INSTALL_RC" -ne 0 ]; then
  if grep -qi "runpod-lifecycle" "$INSTALL_LOG"; then
    echo ""
    echo "SKIP: runpod-lifecycle is not resolvable from the configured indices."
    echo "  This is expected on public CI without a private package index or"
    echo "  local wheelhouse.  Configure PIP_INDEX_URL, a pip.conf with a"
    echo "  private index, or mount a wheelhouse to enable RunPod validation."
    echo ""
    rm -f "$INSTALL_LOG"
    exit 0
  fi
  # Some other, unexpected failure — report but don't block the gate.
  echo ""
  echo "SKIP: pip install astrid[runpod] failed for an unexpected reason:"
  cat "$INSTALL_LOG"
  rm -f "$INSTALL_LOG"
  exit 0
fi
rm -f "$INSTALL_LOG"

# -------------------------------------------------------------------
# 4. Core health checks (same shape as the blocking wheel proof)
# -------------------------------------------------------------------
echo ""
echo "--- import astrid ---"
python -c "import astrid; print('import astrid: OK')"

echo ""
echo "--- import runpod_lifecycle ---"
python -c "import runpod_lifecycle; print('import runpod_lifecycle: OK')"

echo ""
echo "=== RunPod-extra validation PASSED ==="
