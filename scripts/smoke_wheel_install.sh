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

# -------------------------------------------------------------------
# 4. Installed-wheel scaffold golden path (T6.6)
# -------------------------------------------------------------------
# Uses the INSTALLED astrid.core.rendering.scaffold module and its installed
# fixture templates: scaffold -> static validation -> install into a temp
# ASTRID_PACKS_PATH root -> registry discovery finds wave.wave ->
# deterministic two-second smoke render -> generated test_renderer.py passes
# inside this wheel venv.
echo ""
echo "--- Installed-wheel scaffold golden path ---"
ASTRID_PACKS_PATH="$SMOKE_ROOT/packs-path"
export ASTRID_PACKS_PATH
mkdir -p "$ASTRID_PACKS_PATH"

python - <<'PY'
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import astrid

# Prove we are running against the installed wheel, not the source checkout.
package_root = Path(astrid.__file__).resolve().parent
assert "site-packages" in package_root.parts, (
    f"astrid was imported from {package_root}, not the installed wheel"
)

from astrid.core.foundation.hash import sha256_file
from astrid.core.pack.manifest import load_manifest_mapping
from astrid.core.pack.validate import validate_pack
from astrid.core.rendering import RenderResult
from astrid.core.rendering.scaffold import SCAFFOLD_FILES, create_renderer_scaffold
from astrid.core.rendering.registry import load_default_registries
from astrid.core.rendering.transport import CommandTransport

RENDERER_ID = "wave.wave"
PACK_ID = "wave"
OUTPUT_NAME = "out.mp4"
SMOKE_LIMIT_SECONDS = 2.0

work = Path.cwd()
dest = create_renderer_scaffold("wave", work / "wave")

# 1. Static validation of the scaffolded pack (installed templates).
errors, _warnings = validate_pack(dest)
assert not errors, errors
pack = load_manifest_mapping(dest / "pack.yaml", manifest_kind="pack")
assert pack["id"] == PACK_ID
assert pack["extensions"]["rendering"]["renderers"] == ["renderer.yaml"]
manifest = load_manifest_mapping(dest / "renderer.yaml", manifest_kind="renderer")
assert manifest["id"] == RENDERER_ID
assert manifest["command"] == ["python3", "render.py"]
assert manifest["operations"] == ["support", "render"]
assert sorted(path.name for path in dest.iterdir() if path.is_file()) == sorted(SCAFFOLD_FILES)
print(f"scaffold + static validation: OK ({RENDERER_ID})")

# 2. Install the pack into the temp ASTRID_PACKS_PATH root.
packs_path = Path(os.environ["ASTRID_PACKS_PATH"])
installed_copy = packs_path / PACK_ID
shutil.copytree(dest, installed_copy)

# 3. Registry discovery finds wave.wave from the installed copy.
renderers, _planners, _finalizers = load_default_registries(work, include_installed=False)
candidates = renderers.candidates(RENDERER_ID)
assert len(candidates) == 1, [candidate.to_dict() for candidate in candidates]
candidate = candidates[0]
assert candidate.id == RENDERER_ID
assert candidate.source_kind == "env"
assert candidate.pack_root == installed_copy.resolve()
print(f"registry discovery: OK (source_kind={candidate.source_kind}, pack_root={candidate.pack_root})")

# 4. Deterministic two-second smoke render from the discovered pack root.
def smoke(workspace: Path) -> tuple[RenderResult, Path, float]:
    workspace.mkdir(parents=True, exist_ok=True)
    request_path = workspace / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "timeline_path": "timeline.json",
                "output_name": OUTPUT_NAME,
                "audio": "rendered",
            }
        ),
        encoding="utf-8",
    )
    result_path = workspace / "result.json"
    transport = CommandTransport(RENDERER_ID, termination_grace=0.15)
    started = time.perf_counter()
    result = transport.run(
        "render",
        [sys.executable, "render.py"],
        request_path=request_path,
        result_path=result_path,
        cwd=candidate.pack_root,
        timeout=30,
    )
    return result, result_path, time.perf_counter() - started

result_a, result_path_a, elapsed_a = smoke(work / "smoke-workspace")
assert elapsed_a < SMOKE_LIMIT_SECONDS, f"smoke render took {elapsed_a:.3f}s"
assert isinstance(result_a, RenderResult)
assert result_a.audio_ownership.value == "rendered"
video_a = work / "smoke-workspace" / result_a.video.path
assert video_a.is_file()
assert len(result_a.video.sha256) == 64
assert result_a.video.sha256 == sha256_file(video_a)

result_b, result_path_b, elapsed_b = smoke(work / "smoke-workspace-2")
assert elapsed_b < SMOKE_LIMIT_SECONDS, f"smoke render took {elapsed_b:.3f}s"
assert (work / "smoke-workspace-2" / result_b.video.path).read_bytes() == video_a.read_bytes()
assert result_path_a.read_bytes() == result_path_b.read_bytes()
print(
    f"deterministic smoke render: OK ({elapsed_a:.3f}s / {elapsed_b:.3f}s, "
    f"sha256={result_a.video.sha256[:16]}..., byte-stable)"
)

# 5. Generated test_renderer.py passes inside this wheel venv.
completed = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(dest / "test_renderer.py")],
    cwd=dest,
    capture_output=True,
    text=True,
    timeout=120,
)
assert completed.returncode == 0, completed.stdout + completed.stderr
print("generated test_renderer.py (wheel venv): OK")
print("installed-wheel scaffold golden path: PASSED")
PY

echo ""
echo "=== clean wheel-install smoke PASSED ==="
