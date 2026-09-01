"""Packaging contract for the m8 local ``astrid`` wheel."""

from __future__ import annotations

import email
import os
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from astrid.core.migrations.runner import MigrationTooNewError, probe_database
from astrid.packs import compose_standard_pack_database
from scripts.reshape.installed_artifact import build_once


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FAMILIES = "projects timelines media tasks runs serve doctor backup"
EXPECTED_RUNTIME_MODULES = {
    "astrid/__init__.py",
    "astrid/__main__.py",
    "astrid/core/gateway/__init__.py",
    "astrid/core/gateway/dispatch.py",
    "astrid/core/gateway/help.py",
    "astrid/core/cli/domain_product.py",
    "astrid/core/migrations/catalog.py",
    "astrid/core/migrations/runner.py",
    "astrid/core/schema_packs/registry.py",
    "astrid/packs/__init__.py",
    "astrid/packs/timeline/__init__.py",
    "astrid/packs/timeline/bridge.py",
    "astrid/packs/timeline/repository.py",
    "astrid/packs/shots/__init__.py",
    "astrid/packs/shots/repository.py",
    "astrid/packs/references/__init__.py",
    "astrid/packs/references/repository.py",
}
EXPECTED_RESOURCES = {
    "astrid/core/migrations/sql/core/0001_initial.sql",
    "astrid/packs/timeline/pack.yaml",
    "astrid/packs/timeline/migrations/0001_initial.sql",
    "astrid/packs/shots/pack.yaml",
    "astrid/packs/shots/migrations/0001_initial.sql",
    "astrid/packs/references/pack.yaml",
    "astrid/packs/references/migrations/0001_initial.sql",
    "astrid/core/rendering/schemas/v1/request.json",
    "astrid/core/rendering/fixtures/renderer_parity/remotion_backend_wrapper.py",
    "astrid/packs/rendering/pack.yaml",
    "astrid/packs/rendering/backends/remotion/renderer.yaml",
    "astrid/packs/rendering/elements/effects/text-card/element.yaml",
    "astrid/packs/rendering/elements/effects/text-card/component.tsx",
    "astrid/packs/training/orchestrators/dataset_build/review_ui/index.html",
    "astrid/packs/training/orchestrators/dataset_build/review_ui/styles.css",
}
FORBIDDEN_WHEEL_MARKERS = (
    ".megaplan/",
    "/tests/",
    "/skill/",
    "/golden/",
    "/build/",
    "/dist/",
    "__pycache__/",
    ".pyc",
    "STAGE.md",
    "requirements.txt",
)


def _snapshot_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".megaplan",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "out",
        "runs",
        "projects",
        "node_modules",
        ".venv",
        "venv",
        "astrid.egg-info",
    }
    return {name for name in names if name in ignored or name.endswith(".egg-info")}


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("m8-packaging")
    source = root / "source"
    shutil.copytree(REPO_ROOT, source, ignore=_snapshot_ignore)
    dist = root / "dist"
    dist.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = sorted(dist.glob("*.whl"))
    assert len(wheels) == 1, [path.name for path in wheels]
    return wheels[0]


@pytest.fixture(scope="module")
def installed(wheel: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("m8-installed")
    venv = root / "venv"
    result = subprocess.run(
        # T2 is the wheel-content/entry-point contract.  The shared T3
        # harness owns the stricter no-system-site-packages dependency-leak
        # proof; using the already provisioned test dependencies here keeps
        # this package contract deterministic in an offline checkout.
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    child_python = venv / "bin" / "python"
    result = subprocess.run(
        [
            str(child_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    outside = root / "outside-checkout"
    outside.mkdir()
    env = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(root / "home"),
        "ASTRID_HOME": str(root / "state"),
        "ASTRID_PROJECTS_ROOT": str(root / "projects"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
    for value in env.values():
        if value.startswith(str(root)):
            Path(value).mkdir(parents=True, exist_ok=True)
    return child_python, outside


def _run_installed(
    installed: tuple[Path, Path], args: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    child_python, outside = installed
    child_env = os.environ.copy()
    child_env.update(env or {})
    child_env.pop("PYTHONPATH", None)
    child_env.pop("PYTHONHOME", None)
    return subprocess.run(
        # This T2 fixture intentionally reuses the already-provisioned global
        # runtime dependencies through --system-site-packages. T3 owns the
        # stricter no-system-site-packages dependency-leak proof; PYTHONNOUSERSITE
        # and PYTHONSAFEPATH still keep user/site and checkout paths out.
        [str(child_python), *args],
        cwd=outside,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_wheel_metadata_entry_points_and_runtime_modules(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_path = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_path))
        entry_points_path = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entry_points = archive.read(entry_points_path).decode("utf-8")

    assert metadata["Name"] == "astrid"
    assert metadata["Version"] == "0.1.0"
    assert metadata["Requires-Python"] == ">=3.11"
    assert "astrid = astrid.core.gateway:main" in entry_points
    assert EXPECTED_RUNTIME_MODULES <= names
    assert EXPECTED_RESOURCES <= names


def test_wheel_contains_complete_resource_matrix_and_excludes_authoring_material(
    wheel: Path,
) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert EXPECTED_RESOURCES <= names
    forbidden = [name for name in sorted(names) if any(marker in name for marker in FORBIDDEN_WHEEL_MARKERS)]
    assert not forbidden, forbidden[:20]
    assert any(name.endswith("/pack.yaml") for name in names)
    assert {
        "astrid/packs/timeline/pack.yaml",
        "astrid/packs/shots/pack.yaml",
        "astrid/packs/references/pack.yaml",
    } <= names


def test_installed_module_and_console_entry_paths_report_one_version(
    installed: tuple[Path, Path],
) -> None:
    module = _run_installed(installed, ["-m", "astrid", "--version"])
    assert module.returncode == 0, module.stderr
    assert module.stdout.strip() == "astrid"
    probe = _run_installed(
        installed,
        [
            "-c",
            "import astrid, importlib.metadata, json; print(json.dumps({'file': astrid.__file__, 'version': importlib.metadata.version('astrid')}))",
        ],
    )
    assert probe.returncode == 0, probe.stderr
    payload = __import__("json").loads(probe.stdout)
    assert payload["version"] == "0.1.0"
    assert "site-packages" in Path(payload["file"]).parts
    assert not Path(payload["file"]).resolve().is_relative_to(REPO_ROOT)

    console = installed[0].parent / "astrid"
    result = subprocess.run(
        [str(console), "--version"],
        cwd=installed[1],
        env={"HOME": str(installed[1].parent / "home"), "PATH": os.environ.get("PATH", os.defpath)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "astrid"


def test_installed_help_exposes_exact_eight_family_ownership_census(
    installed: tuple[Path, Path],
) -> None:
    result = _run_installed(installed, ["-m", "astrid", "help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert f"Family census (exactly eight families): {EXPECTED_FAMILIES}" in text
    assert "projects    [kernel]" in text
    assert "media       [kernel]" in text
    assert "tasks       [kernel]" in text
    assert "runs        [kernel]" in text
    assert "timelines   [pack: timeline]" in text
    assert "serve       [kernel]" in text
    assert "doctor      [kernel]" in text
    assert "backup      [kernel]" in text
    assert "timelines shots       [pack: shots]" in text
    assert "media references      [pack: references]" in text
    assert "Family census (exactly eight families):" in text
    assert "references [kernel]" not in text


def _too_new_database(path: Path, pack: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE schema_migrations (pack TEXT, version INTEGER, name TEXT, checksum TEXT, applied_at TEXT)"
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, 'future', 'future', 'future')", (pack, 99)
        )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize("pack", ["core", "timeline"])
def test_too_new_core_and_pack_migrations_refuse_without_mutation(
    tmp_path: Path,
    pack: str,
) -> None:
    database = tmp_path / f"{pack}.sqlite3"
    _too_new_database(database, pack)
    before = database.read_bytes()
    with pytest.raises(MigrationTooNewError):
        probe_database(database, compose_standard_pack_database().registry)
    assert database.read_bytes() == before


def test_shared_harness_smoke_checks_installed_basics_and_failure_boundaries(
    tmp_path: Path,
) -> None:
    """Exercise the shared artifact boundary used by the release smoke.

    The packaging fixture above intentionally retains its small T2-specific
    setup.  This test covers the T4 contract: all product checks run through
    the build-once harness, explicit workspaces survive close, and failed
    resource/import probes remain nonzero evidence rather than being hidden.
    """
    workspace = tmp_path / "explicit-installed-workspace"
    harness = build_once(
        REPO_ROOT,
        workspace=workspace,
        # Help and doctor are gateway-level product checks and therefore need
        # the wheel's declared runtime dependencies.  The T3 harness tests
        # retain the no-dependency isolation proof separately.
        install_dependencies=True,
    )
    try:
        version = harness.run_module(
            "installed-version", "astrid", ["--version"], check=True
        )
        assert version.stdout.strip() == "astrid"

        help_record = harness.run_module("installed-help", "astrid", ["help"], check=True)
        assert "Family census (exactly eight families):" in help_record.stdout

        doctor_help = harness.run_module(
            "installed-doctor-help", "astrid", ["doctor", "--help"], check=True
        )
        assert "doctor" in doctor_help.output.lower()

        resources = harness.run_lane(
            "installed-resource-probe",
            [
                "-c",
                "from importlib import resources; "
                "required=('core/migrations/sql/core/0001_initial.sql',"
                "'packs/timeline/pack.yaml','packs/shots/pack.yaml',"
                "'packs/references/pack.yaml'); "
                "root=resources.files('astrid'); "
                "missing=[name for name in required if not root.joinpath(*name.split('/')).is_file()]; "
                "assert not missing, missing; print('resources: OK')",
            ],
            check=True,
        )
        assert "resources: OK" in resources.stdout

        missing = harness.run_lane(
            "missing-resource-adversary",
            [
                "-c",
                "from importlib import resources; "
                "assert resources.files('astrid').joinpath('missing-release-resource').is_file()",
            ],
        )
        assert missing.returncode != 0
        assert missing.status == "failed"
        assert missing.error and "status" in missing.error

        checkout = harness.run_lane(
            "checkout-import-adversary",
            ["-c", f"print({str(REPO_ROOT)!r})"],
        )
        assert checkout.returncode == 0
        assert checkout.status == "failed"
        assert checkout.error and "source-tree path" in checkout.error
    finally:
        harness.close()

    # An explicitly supplied workspace is caller-owned and must remain
    # inspectable after the lane finishes.
    assert workspace.is_dir()
    assert (workspace / "dist").is_dir()

    auto_harness = build_once(REPO_ROOT)
    auto_workspace = auto_harness.workspace
    auto_harness.close()
    assert not auto_workspace.exists()


__all__ = ["test_wheel_metadata_entry_points_and_runtime_modules"]
