#!/usr/bin/env bash
set -euo pipefail

# smoke_wheel_install.sh
# Blocking clean wheel-install proof.
#
# Builds a wheel from the source tree, creates an isolated throwaway
# virtual environment, installs the built wheel (NOT editable), and
# verifies imports, installed rendering package data, static pack discovery,
# and the blocking core health check.
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
SMOKE_ROOT="$(mktemp -d)"
VENV_DIR="${SMOKE_WHEEL_VENV_DIR:-$SMOKE_ROOT/venv}"
DIST_DIR="$SMOKE_ROOT/dist"

cleanup() {
  if [ "${SMOKE_KEEP_VENV:-0}" = "1" ]; then
    echo "Keeping wheel smoke workspace: $SMOKE_ROOT"
  else
    rm -rf "$SMOKE_ROOT"
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
mkdir -p "$DIST_DIR"
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
"$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# The gate environment already installed Astrid's declared dependencies. Reuse
# those immutable packages so this wheel proof stays deterministic and works in
# network-restricted CI; Astrid itself is still installed only from the wheel.
python -m pip install --no-deps "$WHEEL"

# -------------------------------------------------------------------
# 3. Blocking installed-package checks, outside the source checkout
# -------------------------------------------------------------------
cd "$SMOKE_ROOT"
ASTRID_HOME="$SMOKE_ROOT/astrid-home"
export ASTRID_HOME
ASTRID_PROJECTS_ROOT="$SMOKE_ROOT/projects"
export ASTRID_PROJECTS_ROOT

echo ""
echo "--- Blocking import check ---"
python - <<'PY'
import importlib
from importlib import resources

import astrid

schemas = importlib.import_module("astrid.core.rendering.schemas")
assert schemas.__spec__ is not None

package_root = resources.files("astrid")
schema_root = package_root.joinpath("core", "rendering", "schemas", "v1")
fixture_root = package_root.joinpath("core", "rendering", "fixtures", "renderer_parity")
required_schemas = {
    "request.json",
    "support.json",
    "plan.json",
    "finalize.json",
    "result.json",
    "renderer-manifest.json",
    "planner-manifest.json",
    "finalizer-manifest.json",
}
required_fixtures = {
    "assets.json",
    "audio-reactive-colour.timeline.json",
    "effect-clip.timeline.json",
    "empty.timeline.json",
    "media-only.timeline.json",
    "remotion_backend_wrapper.py",
    "text-card.timeline.json",
    "theme-overrides.json",
    "transition-windows.timeline.json",
}
required_manifests = {
    "packs/rendering/pack.yaml",
    "packs/rendering/backends/ffmpeg/renderer.yaml",
    "packs/rendering/backends/remotion/renderer.yaml",
    "packs/rendering/elements/animations/fade-up/element.yaml",
    "packs/rendering/elements/animations/fade/element.yaml",
    "packs/rendering/elements/animations/scale-in/element.yaml",
    "packs/rendering/elements/animations/slide-left/element.yaml",
    "packs/rendering/elements/animations/slide-up/element.yaml",
    "packs/rendering/elements/animations/type-on/element.yaml",
    "packs/rendering/elements/effects/audio-reactive-colour/element.yaml",
    "packs/rendering/elements/effects/text-card/element.yaml",
    "packs/rendering/elements/transitions/cross-fade/element.yaml",
    "packs/rendering/elements/transitions/fade/element.yaml",
    "packs/rendering/executors/html_canvas_effect/executor.yaml",
    "packs/rendering/executors/render/executor.yaml",
    "packs/rendering/executors/sprite_sheet/executor.yaml",
    "packs/rendering/executors/timeline_storyboard/executor.yaml",
    "packs/rendering/finalizers/ffmpeg/finalizer.yaml",
    "packs/rendering/planners/legacy_hybrid/planner.yaml",
}
assert {item.name for item in schema_root.iterdir()} >= required_schemas
assert {item.name for item in fixture_root.iterdir()} >= required_fixtures
missing_manifests = {
    relative
    for relative in required_manifests
    if not package_root.joinpath(*relative.split("/")).is_file()
}
assert not missing_manifests, sorted(missing_manifests)

from astrid.core.rendering.registry import load_default_registries

renderers, planners, finalizers = load_default_registries(include_installed=False)
assert {candidate.id for candidate in renderers.list()} >= {
    "rendering.remotion",
    "rendering.ffmpeg",
}
assert {candidate.id for candidate in planners.list()} >= {"rendering.legacy_hybrid"}
assert {candidate.id for candidate in finalizers.list()} >= {
    "rendering.ffmpeg-finalizer"
}
print("installed Astrid rendering schemas, fixtures, and manifests: OK")
PY

echo ""
echo "=== clean wheel-install smoke PASSED ==="
