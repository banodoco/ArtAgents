"""T6.6 — golden path proof for the T6.5 renderer scaffold.

End-to-end proof that a scaffolded renderer works from a fresh directory:

* ``create_renderer_scaffold`` writes the four-file pack into a temp dir;
* static validation passes (``validate_pack`` + canonical manifest checks);
* the generated ``test_renderer.py`` passes when run on the scaffold output;
* the pack is installed into a temp ``ASTRID_PACKS_PATH`` root and explicit
  discovery finds ``rendering.<name>``;
* a deterministic smoke render produces a byte-stable, valid output in under
  two seconds (no timestamps, no random ids); and
* an installed revision is intentionally not a public discovery authority.

The installed-wheel leg of the golden path (same flow against the wheel's
``astrid.core.rendering.scaffold`` module inside the wheel venv) is wired into
``scripts/smoke_wheel_install.sh``, which builds/installs the wheel, then runs
the scaffold → validate → install → discover → smoke → generated-test sequence
from the venv.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.pack import discover_packs
from astrid.core.pack.manifest import load_manifest_mapping
from astrid.core.pack.store import InstalledPackStore
from astrid.core.pack.validate import validate_pack
from astrid.core.rendering import RenderResult
from astrid.core.rendering import registry as rendering_registry_module
from astrid.core.rendering.registry import RendererRegistryError, load_default_registries
from astrid.core.rendering.scaffold import SCAFFOLD_FILES, create_renderer_scaffold
from astrid.core.rendering.transport import CommandTransport

RENDERER_ID = "wave.wave"
PACK_ID = "wave"
PACK_DIR_NAME = PACK_ID  # load_pack_manifest requires root.name == pack id
OUTPUT_NAME = "out.mp4"
SMOKE_TIMEOUT_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scanner(source_root: Path):
    def scan(root: str | Path | None = None):
        return discover_packs(source_root if root is None else root)

    return scan


@contextmanager
def _registries_with_empty_source(
    project_root: Path,
    *,
    packs_path: str = "",
    astrid_home: str | None = None,
    include_installed: bool = False,
):
    """Load registries with an empty source tree and controlled pack roots."""
    empty_source = project_root / "empty-source"
    empty_source.mkdir(parents=True, exist_ok=True)
    env_overrides = {"ASTRID_PACKS_PATH": packs_path}
    if astrid_home is not None:
        env_overrides["ASTRID_HOME"] = astrid_home
    with (
        mock.patch.object(
            rendering_registry_module,
            "discover_packs",
            side_effect=_scanner(empty_source),
        ),
        mock.patch.dict(os.environ, env_overrides, clear=False),
    ):
        yield load_default_registries(
            project_root,
            include_installed=include_installed,
        )


def _stage_trusted_install(astrid_home: Path, pack_root: Path, pack_id: str) -> Path:
    """Install *pack_root* through the REAL trusted-install path.

    ``astrid packs install`` semantics (``astrid.core.pack.install_local.
    install_pack``): the pack is copied into
    ``<ASTRID_HOME>/packs/<id>/revisions/<id>``, an active symlink is
    created, and an ``InstallRecord`` is written with the accepted trust
    audit — making the candidate execution-eligible.  The caller sets
    ``ASTRID_HOME`` so the store lands where the registry reads it.
    """
    from astrid.core.pack.install_local import install_pack

    store = InstalledPackStore(astrid_home / "packs")
    exit_code = install_pack(
        pack_root,
        store,
        skip_confirm=True,
        trust_acknowledged=True,
        trust_method="test",
        trust_actor="scaffold-golden-path",
        source_type="local",
    )
    if exit_code != 0:
        raise AssertionError(f"install_pack failed with exit code {exit_code}")
    return astrid_home / "packs" / pack_id / "revisions" / pack_id


def _write_request(workspace: Path, *, output_name: str = OUTPUT_NAME) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    request_path = workspace / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "timeline_path": "timeline.json",
                "output_name": output_name,
                "audio": "rendered",
            }
        ),
        encoding="utf-8",
    )
    return request_path


def _smoke_render(
    pack_root: Path,
    workspace: Path,
    *,
    renderer_id: str = RENDERER_ID,
    verb: str = "render",
) -> tuple[RenderResult, Path, float]:
    """Run one scaffold render/support invocation and return (value, result_path, seconds)."""
    request_path = _write_request(workspace)
    result_path = workspace / "result.json"
    transport = CommandTransport(renderer_id, termination_grace=0.15)
    started = time.perf_counter()
    value = transport.run(
        verb,
        [sys.executable, "render.py"],
        request_path=request_path,
        result_path=result_path,
        cwd=pack_root,
        timeout=30,
    )
    elapsed = time.perf_counter() - started
    return value, result_path, elapsed


def _assert_valid_render(result: RenderResult, workspace: Path) -> None:
    assert isinstance(result, RenderResult)
    assert result.schema_version == 1
    assert result.audio_ownership.value == "rendered"
    assert result.video.path == f"outputs/{OUTPUT_NAME}"
    video_path = workspace / result.video.path
    assert video_path.is_file()
    assert len(result.video.sha256) == 64
    assert result.video.sha256 == sha256_file(video_path)
    assert RENDERER_ID in result.backend_fragments


def _run_generated_test(dest: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(dest / "test_renderer.py"),
        ],
        cwd=dest,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _assert_static_validation(dest: Path) -> None:
    errors, _warnings = validate_pack(dest)
    assert not errors, errors

    pack = load_manifest_mapping(dest / "pack.yaml", manifest_kind="pack")
    assert pack["id"] == PACK_ID
    assert pack["extensions"]["rendering"]["renderers"] == ["renderer.yaml"]
    permission_ids = {permission["id"] for permission in pack["permissions"]}
    assert permission_ids == {"subprocess", "project_files"}

    manifest = load_manifest_mapping(
        dest / "renderer.yaml",
        manifest_kind="renderer",
    )
    assert manifest["id"] == RENDERER_ID
    assert manifest["command"] == ["python3", "render.py"]
    assert manifest["operations"] == ["support", "render"]
    assert manifest["protocol_version"] == 1
    assert manifest["required_permissions"] == ["project_files", "subprocess"]


# ---------------------------------------------------------------------------
# Fresh-directory golden path
# ---------------------------------------------------------------------------


def test_fresh_directory_golden_path(tmp_path: Path) -> None:
    """Scaffold → validate → generated test → install → discover → smoke.

    Runs the complete golden path from a fresh directory: the scaffold is
    created with ``create_renderer_scaffold``, statically validated, its
    generated test passes, the pack is installed into a temp
    ``ASTRID_PACKS_PATH`` root, registry discovery finds ``wave.wave``,
    and a deterministic smoke render produces a valid output in under two
    seconds from the installed (discovered) copy.
    """
    dest = create_renderer_scaffold("wave", tmp_path / "wave")

    # 1. Static validation: validate_pack + canonical manifest checks.
    _assert_static_validation(dest)
    assert sorted(path.name for path in dest.iterdir() if path.is_file()) == sorted(
        SCAFFOLD_FILES
    )

    # 2. The generated test_renderer.py passes on the scaffold output.
    _run_generated_test(dest)

    # 3. Install the pack into a temp ASTRID_PACKS_PATH extra root.
    packs_path = tmp_path / "packs-path"
    installed_copy = packs_path / PACK_DIR_NAME
    shutil.copytree(dest, installed_copy)

    # 4. Registry discovery finds wave.wave from the installed copy.
    with _registries_with_empty_source(
        tmp_path / "project",
        packs_path=str(packs_path),
    ) as (renderers, _planners, _finalizers):
        candidates = renderers.candidates(RENDERER_ID)
        assert len(candidates) == 1, [
            candidate.to_dict() for candidate in candidates
        ]
        candidate = candidates[0]
        assert candidate.id == RENDERER_ID
        assert candidate.source_kind == "env"
        assert candidate.pack_root == installed_copy.resolve()
        assert candidate.manifest.command == ("python3", "render.py")

        # 5. Deterministic smoke render from the discovered pack root (<2s).
        workspace = tmp_path / "workspace"
        result, result_path, elapsed = _smoke_render(candidate.pack_root, workspace)
        assert elapsed < SMOKE_TIMEOUT_SECONDS, (
            f"smoke render took {elapsed:.3f}s (limit {SMOKE_TIMEOUT_SECONDS}s)"
        )
        _assert_valid_render(result, workspace)

        # Byte-stable: a second render produces identical media and result.
        workspace2 = tmp_path / "workspace-2"
        result2, result_path2, elapsed2 = _smoke_render(
            candidate.pack_root, workspace2
        )
        assert elapsed2 < SMOKE_TIMEOUT_SECONDS
        assert (workspace / result.video.path).read_bytes() == (
            workspace2 / result2.video.path
        ).read_bytes()
        assert result_path.read_bytes() == result_path2.read_bytes()
        assert result.video.sha256 == result2.video.sha256


def test_installed_scaffold_is_not_publicly_discovered(tmp_path: Path) -> None:
    """Installed revisions are not a public renderer discovery authority."""
    dest = create_renderer_scaffold("wave", tmp_path / "wave")
    astrid_home = tmp_path / "astrid-home"
    revision = _stage_trusted_install(astrid_home, dest, PACK_ID)

    with _registries_with_empty_source(
        tmp_path / "project",
        astrid_home=str(astrid_home),
        include_installed=True,
    ) as (renderers, _planners, _finalizers):
        assert renderers.inspect(RENDERER_ID) == ()
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get(RENDERER_ID)
        assert caught.value.code == "unknown_capability"


def test_deterministic_smoke_is_byte_stable_and_under_two_seconds(
    tmp_path: Path,
) -> None:
    """The generated renderer is byte-stable for the same input, fast (<2s)."""
    dest = create_renderer_scaffold("wave", tmp_path / "wave")

    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    result_a, result_path_a, elapsed_a = _smoke_render(dest, workspace_a)
    result_b, result_path_b, elapsed_b = _smoke_render(dest, workspace_b)

    for elapsed in (elapsed_a, elapsed_b):
        assert elapsed < SMOKE_TIMEOUT_SECONDS, (
            f"smoke render took {elapsed:.3f}s (limit {SMOKE_TIMEOUT_SECONDS}s)"
        )

    _assert_valid_render(result_a, workspace_a)
    _assert_valid_render(result_b, workspace_b)

    media_a = (workspace_a / result_a.video.path).read_bytes()
    media_b = (workspace_b / result_b.video.path).read_bytes()
    assert media_a == media_b
    assert result_a.video.sha256 == result_b.video.sha256

    # The full result wire payload is deterministic: no timestamps, no random
    # ids, no workspace-dependent paths.
    raw_a = result_path_a.read_bytes()
    raw_b = result_path_b.read_bytes()
    assert raw_a == raw_b
    assert b"installed_at" not in raw_a
    assert b"timestamp" not in raw_a
