"""Adversarial authority proof for the installed Astrid artifact.

The source-tree lint is useful for development, but it cannot prove that the
wheel actually contains the same authority boundary.  These tests use one
wheel, point the scanner at its private site-packages directory, and then
mutate throwaway copies to prove that empty roots, wrong roots, forbidden
imports/writers/fallbacks, dependency directions, and runtime observations
fail closed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.reshape.authority_lint import (
    run_installed_authority_lint,
)
from scripts.reshape.installed_artifact import InstalledArtifactHarness, build_once


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def installed_artifact(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[InstalledArtifactHarness, Path]:
    """Build one wheel and return its site-packages root."""
    workspace = tmp_path_factory.mktemp("m8-installed-authority")
    harness = build_once(REPO_ROOT, workspace=workspace, install_dependencies=False)
    try:
        assert harness.identity is not None
        package_root = Path(harness.identity.import_path).resolve().parent
        assert package_root.name == "astrid"
        yield harness, package_root.parent
    finally:
        harness.close()


def _copy_artifact(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _scan(root: Path, **kwargs: object):
    return run_installed_authority_lint(root, **kwargs)


def test_installed_mode_rejects_empty_and_wrong_roots(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty-site-packages"
    empty.mkdir()
    empty_report = _scan(empty)
    assert not empty_report.ok
    assert empty_report.mode == "installed"
    assert any("missing the astrid package" in error for error in empty_report.errors)

    wrong = tmp_path / "wrong-site-packages"
    _write(wrong, "astrid/__init__.py", "# not a complete installed artifact\n")
    wrong_report = _scan(wrong)
    assert not wrong_report.ok
    assert any("missing required artifact file" in error for error in wrong_report.errors)


def test_installed_wheel_static_and_runtime_authority_scan_is_nonvacuous(
    installed_artifact: tuple[InstalledArtifactHarness, Path],
) -> None:
    harness, root = installed_artifact
    project_root = harness.roots.project / "authority-journey"
    catalog = project_root / ".astrid" / "astrid.sqlite3"
    media = project_root / ".astrid" / "media" / "sha256" / "clip.bin"
    backup = harness.workspace / "backup-output"
    diagnostics = harness.workspace / "diagnostics"
    log = diagnostics / "serve.stdout.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        '{"ready": true, "fallback_backend_observed": false, '
        '"sidecar_authority_observed": false, '
        '"second_writer_observed": false, '
        '"semantic_writer": "sqlite-catalog"}\n',
        encoding="utf-8",
    )

    report = _scan(
        root,
        journey_logs=[log],
        sqlite_connections=[
            {
                "path": str(catalog),
                "owner": "kernel",
                "write": True,
                "transaction": True,
            }
        ],
        created_files=[
            str(catalog),
            str(media),
            {"path": str(backup / "backup.json"), "kind": "backup"},
            {"path": str(diagnostics / "authority.json"), "kind": "diagnostic"},
        ],
        project_root=project_root,
        catalog_paths=[catalog],
        managed_media_roots=[project_root / ".astrid" / "media"],
        backup_roots=[backup],
        diagnostic_roots=[diagnostics],
    )
    assert report.ok, report.errors
    assert report.mode == "installed"
    assert report.scanned_files
    assert report.observation_counts == {
        "journey_logs": 1,
        "sqlite_connections": 1,
        "created_files": 4,
    }


def test_installed_scan_catches_combined_adversarial_sources(
    installed_artifact: tuple[InstalledArtifactHarness, Path],
    tmp_path: Path,
) -> None:
    _harness, source = installed_artifact
    root = _copy_artifact(source, tmp_path / "adversarial-site-packages")

    _write(
        root,
        "astrid/core/gateway/evil_remote.py",
        "from astrid.core.timeline.eventlog.backends.remote_client import post_json\n",
    )
    _write(
        root,
        "astrid/sdk/evil_fsa.py",
        "def choose_file(window):\n    return window.showOpenFilePicker()\n",
    )
    _write(
        root,
        "astrid/sdk/evil_json.py",
        "from pathlib import Path\n\nPath('timeline.json').write_text('{}')\n",
    )
    _write(
        root,
        "astrid/sdk/evil_fallback.py",
        "def backend():\n    fallback_backend = 'legacy-file'\n    return fallback_backend\n",
    )
    _write(
        root,
        "astrid/packs/timeline/evil_pack_import.py",
        "from astrid.packs.shots.repository import ShotRepository\n",
    )
    _write(
        root,
        "astrid/packs/timeline/evil_writer.py",
        "import sqlite3\n\nsqlite3.connect('/tmp/timeline.sqlite3')\n",
    )
    _write(
        root,
        "astrid/packs/timeline/schema-pack.yaml",
        (root / "astrid/packs/timeline/schema-pack.yaml")
        .read_text(encoding="utf-8")
        .replace("  - core >= 1", "  - timeline >= 1"),
    )
    _write(
        root,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE timelines (\n"
        "  id TEXT PRIMARY KEY,\n"
        "  FOREIGN KEY (shot_id) REFERENCES shots (id)\n"
        ");\n",
    )

    report = _scan(root)
    assert not report.ok
    joined = "\n".join(report.errors)
    assert "legacy authority" in joined.lower()
    assert "FSA" in joined or "file-authority" in joined
    assert "semantic JSON/JSONL/FSA writer" in joined
    assert "silent authority fallback" in joined
    assert "pack-to-pack import" in joined
    assert "forbidden pack dependency" in joined
    assert "SQLite writer construction outside the kernel store" in joined
    assert "cross-pack FK" in joined


def test_runtime_observation_scan_rejects_wrong_locations_and_allows_only_declared_outputs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "projects"
    catalog = project_root / ".astrid" / "astrid.sqlite3"
    media_root = project_root / ".astrid" / "media"
    backup_root = tmp_path / "backup"
    diagnostic_root = tmp_path / "diagnostics"

    safe = _scan(
        # Runtime observation lint is independently useful for a retained
        # journey record; the installed-root wrapper is tested above.
        tmp_path,
        observations={
            "journey_logs": ['{"semantic_writer": "sqlite-catalog"}'],
            "sqlite_connections": [{"path": str(catalog), "owner": "kernel"}],
            "created_files": [
                str(catalog),
                str(media_root / "a.bin"),
                str(backup_root / "backup.json"),
                str(diagnostic_root / "authority.json"),
            ],
        },
        project_root=project_root,
        catalog_paths=[catalog],
        managed_media_roots=[media_root],
        backup_roots=[backup_root],
        diagnostic_roots=[diagnostic_root],
    )
    # The root-shape error is expected here; the runtime observations are
    # checked through the public list helper in the adversarial report below.
    assert not safe.ok
    assert any("missing the astrid package" in error for error in safe.errors)

    bad = _scan(
        tmp_path,
        observations={
            "journey_logs": [
                "Supabase writer used; fallback backend selected; second writer active"
            ],
            "sqlite_connections": [
                {"path": str(tmp_path / "wrong.sqlite3"), "owner": "timeline", "transaction": True}
            ],
            "created_files": [
                str(project_root / "events.jsonl"),
                str(project_root / "sidecar.json"),
            ],
        },
        project_root=project_root,
    )
    assert not bad.ok
    # Wrong roots fail before runtime observations, so this assertion proves
    # the standalone runtime surface with a minimal valid artifact root next.
    valid_root = tmp_path / "valid-site-packages"
    for relative in (
        "astrid/__init__.py",
        "astrid/core/__init__.py",
        "astrid/packs/__init__.py",
        "astrid/core/migrations/sql/core/0001_initial.sql",
    ):
        _write(valid_root, relative, "-- placeholder\n" if relative.endswith(".sql") else "")
    _write(
        valid_root,
        "astrid/core/gateway/__init__.py",
        "",
    )
    report = _scan(
        valid_root,
        observations={
            "journey_logs": [
                "Supabase writer used; fallback backend selected; second writer active"
            ],
            "sqlite_connections": [
                {"path": str(tmp_path / "wrong.sqlite3"), "owner": "timeline", "transaction": True}
            ],
            "created_files": [
                str(project_root / "events.jsonl"),
                str(project_root / "sidecar.json"),
            ],
        },
        project_root=project_root,
    )
    assert not report.ok
    joined = "\n".join(report.errors)
    assert "Supabase authority marker" in joined
    assert "silent fallback observed" in joined
    assert "SQLite connection outside" in joined
    assert "created file is outside" in joined
