"""Focused contract tests for the m8 installed-artifact harness."""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.reshape.installed_artifact import (
    ArtifactIdentityError,
    InstalledArtifactHarness,
    InstalledArtifactError,
    LaneExecutionError,
    WheelSelectionError,
    build_once,
    is_secret_env_name,
    scrub_environment,
    select_single_wheel,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def harness(tmp_path_factory: pytest.TempPathFactory) -> InstalledArtifactHarness:
    workspace = tmp_path_factory.mktemp("installed-artifact")
    value = build_once(REPO_ROOT, workspace=workspace)
    try:
        yield value
    finally:
        value.close()


def test_build_once_selects_one_hashed_wheel_and_proves_installed_identity(
    harness: InstalledArtifactHarness,
) -> None:
    identity = harness.identity
    assert identity is not None
    assert len(harness.artifact_digest) == 64
    assert harness.artifact.path.is_file()
    assert identity.version == harness.artifact.version == "0.1.0"
    assert "site-packages" in Path(identity.import_path).parts
    assert not Path(identity.import_path).resolve().is_relative_to(REPO_ROOT)
    assert harness.venv_dir.joinpath("pyvenv.cfg").is_file()
    assert "include-system-site-packages = true" not in harness.venv_dir.joinpath(
        "pyvenv.cfg"
    ).read_text(encoding="utf-8").lower()


def test_python_and_console_lanes_record_complete_identity_and_isolated_roots(
    harness: InstalledArtifactHarness,
) -> None:
    module_record = harness.run_lane(
        "module-import",
        [
            "-c",
            "import astrid, importlib.metadata; print(astrid.__file__); print(importlib.metadata.version('astrid'))",
        ],
        check=True,
    )
    version_record = harness.run_lane(
        "module-version",
        ["-c", "import importlib.metadata; print(importlib.metadata.version('astrid'))"],
        check=True,
    )
    for record in (module_record, version_record):
        payload = record.as_dict()
        assert payload["schema"] == "astrid.installed_artifact.v1"
        assert payload["command"]
        assert payload["executable"]
        assert payload["import_path"] == harness.identity.import_path
        assert payload["installed_version"] == "0.1.0"
        assert payload["wheel_sha256"] == harness.artifact_digest
        assert payload["status"] == "passed"
        assert payload["started_at"].endswith("Z")
        assert payload["finished_at"].endswith("Z")
        assert payload["output"]
        assert set(("home", "state", "project", "media", "cache", "config", "browser")) <= set(
            payload["roots"]
        )
        assert "0.1.0" in payload["output"]
    console = harness.venv_dir / ("Scripts/astrid.exe" if os.name == "nt" else "bin/astrid")
    assert console.is_file()


def test_lane_can_run_outside_checkout_with_scrubbed_credentials(
    harness: InstalledArtifactHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-child")
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    script = (
        "import json, os, pathlib, sys; "
        "import astrid; "
        "print(json.dumps({'file': astrid.__file__, 'cwd': str(pathlib.Path.cwd()), "
        "'home': os.environ['HOME'], 'project': os.environ['ASTRID_PROJECTS_ROOT'], "
        "'api': os.environ.get('OPENAI_API_KEY'), 'pythonpath': os.environ.get('PYTHONPATH'), "
        "'checkout': sys.path}))"
    )
    record = harness.run_lane("credential-free-probe", ["-c", script], check=True)
    payload = json.loads(record.stdout)
    assert "site-packages" in Path(payload["file"]).parts
    assert not Path(payload["file"]).resolve().is_relative_to(REPO_ROOT)
    assert Path(payload["cwd"]).resolve().is_relative_to(harness.workspace)
    assert payload["home"] == str(harness.roots.home)
    assert payload["project"] == str(harness.roots.project)
    assert payload["api"] is None
    assert payload["pythonpath"] is None
    assert not any(str(REPO_ROOT) in entry for entry in payload["checkout"])


def test_missing_identity_and_foreign_wheel_selection_fail_closed(
    harness: InstalledArtifactHarness,
    tmp_path: Path,
) -> None:
    with pytest.raises(WheelSelectionError, match="exactly one wheel"):
        select_single_wheel(tmp_path)
    first = tmp_path / "one.whl"
    second = tmp_path / "two.whl"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    with pytest.raises(WheelSelectionError, match="exactly one wheel"):
        select_single_wheel(tmp_path)

    with pytest.raises(InstalledArtifactError, match="checkout imports"):
        harness.environment({"PYTHONPATH": str(REPO_ROOT)})
    with pytest.raises(InstalledArtifactError, match="secret-like"):
        harness.environment({"TEST_API_KEY": "not-allowed"})


def test_scrubber_removes_account_cloud_provider_and_python_path_inputs(
    harness: InstalledArtifactHarness,
) -> None:
    parent = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": "/real/home",
        "OPENAI_API_KEY": "secret",
        "AWS_ACCESS_KEY_ID": "secret",
        "SUPABASE_URL": "https://example.invalid",
        "ASTRID_SESSION_ID": "session",
        "PYTHONPATH": str(REPO_ROOT),
        "PIP_INDEX_URL": "https://user:pass@example.invalid/simple",
    }
    env = scrub_environment(roots=harness.roots, venv_dir=harness.venv_dir, parent=parent)
    assert env["HOME"] == str(harness.roots.home)
    assert env["ASTRID_PROJECTS_ROOT"] == str(harness.roots.project)
    assert "PYTHONPATH" not in env
    assert "ASTRID_SESSION_ID" not in env
    assert "OPENAI_API_KEY" not in env
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "SUPABASE_URL" not in env
    assert "PIP_INDEX_URL" not in env
    assert is_secret_env_name("OPENAI_API_KEY")
    assert is_secret_env_name("SUPABASE_URL")
    assert not is_secret_env_name("LANG")


def test_identity_probe_rejects_a_checkout_import_without_mutating_workspace(
    harness: InstalledArtifactHarness,
) -> None:
    original = harness.identity
    assert original is not None
    # The real lane runner uses -I and a scrubbed environment.  A lane that
    # deliberately exposes the checkout is retained as failed evidence rather
    # than being allowed to masquerade as installed proof.
    record = harness.run_lane(
        "checkout-output-adversary",
        ["-c", f"print({str(REPO_ROOT)!r})"],
    )
    assert record.status == "failed"
    assert record.error and "source-tree path" in record.error
    with pytest.raises(LaneExecutionError):
        harness.run_lane(
            "checkout-output-adversary-checked",
            ["-c", f"print({str(REPO_ROOT)!r})"],
            check=True,
        )
    assert not Path(original.import_path).resolve().is_relative_to(REPO_ROOT)
    assert harness.last_record is not None
    assert not (harness.workspace / "checkout-import-sentinel").exists()


def test_wheel_contains_no_test_or_plan_material(harness: InstalledArtifactHarness) -> None:
    with zipfile.ZipFile(harness.artifact.path) as archive:
        names = set(archive.namelist())
    assert names
    assert not any(".megaplan/" in name or "/tests/" in name for name in names)
    assert not any(name.endswith(".pyc") for name in names)


__all__ = ["test_build_once_selects_one_hashed_wheel_and_proves_installed_identity"]
