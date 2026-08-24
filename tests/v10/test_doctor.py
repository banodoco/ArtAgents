"""Focused read-only doctor regressions for external media and staging."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from astrid.core import doctor
from astrid.core.doctor import run_checks


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ASTRID_PROJECTS_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, "-m", "astrid", *args, "--json"],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _media_check(root: Path):
    return next(check for check in run_checks(projects_root=root) if check.name == "media_paths")


def test_doctor_distinguishes_pristine_root_from_unhealthy_store(
    tmp_path: Path, capsys
) -> None:
    root = tmp_path / "pristine"
    assert doctor.main(["--projects-root", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["state"] == "uninitialized"
    assert payload["next_action"] == (
        "Initialize a project with `python3 -m astrid projects create "
        "<slug> --name <Name>`"
    )
    statuses = {check["name"]: check["status"] for check in payload["checks"]}
    assert statuses["data_paths"] == "uninitialized"
    assert statuses["sqlite_quick_check"] == "uninitialized"
    assert statuses["fk_integrity"] == "uninitialized"
    assert statuses["schema_versions"] == "uninitialized"
    assert all(check["status"] != "fail" for check in payload["checks"])


def test_doctor_rejects_mutated_and_missing_external_media_without_writing(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    source = tmp_path / "external.bin"
    source.write_bytes(b"external-good")
    assert _cli(projects_root, "projects", "create", "demo", "--name", "Demo").returncode == 0
    imported = _cli(
        projects_root,
        "media",
        "import",
        str(source),
        "--project",
        "demo",
        "--realm",
        "external_local",
    )
    assert imported.returncode == 0, imported.stderr
    media_id = json.loads(imported.stdout)["data"]["id"]
    assert media_id
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    before = db_path.read_bytes()

    source.write_bytes(b"external-mutated")
    mutated = _media_check(projects_root)
    assert mutated.status == "fail"
    assert media_id in mutated.detail
    assert "hash mismatch" in mutated.detail
    assert "media verify" in mutated.detail
    assert db_path.read_bytes() == before

    source.unlink()
    missing = _media_check(projects_root)
    assert missing.status == "fail"
    assert media_id in missing.detail
    assert "unavailable" in missing.detail
    assert "media relocate" in missing.detail
    assert db_path.read_bytes() == before

    source.write_bytes(b"external-good")
    healthy = _media_check(projects_root)
    assert healthy.status == "ok"
    assert "external_local integrity verified (1 locator(s))" in healthy.detail


def test_doctor_names_bounded_orphan_staging_and_never_deletes_it(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    assert _cli(projects_root, "projects", "create", "demo", "--name", "Demo").returncode == 0
    staging = projects_root / ".astrid" / "media" / ".staging"
    alpha = staging / "alpha"
    zeta = staging / "zeta"
    alpha.mkdir(parents=True)
    zeta.mkdir()

    check = _media_check(projects_root)
    assert check.status == "warn"
    assert str(alpha) in check.detail
    assert str(zeta) in check.detail
    assert "safe cleanup" in check.detail
    assert alpha.is_dir()
    assert zeta.is_dir()
    strict = _cli(projects_root, "doctor", "--strict-optional")
    assert strict.returncode == 1


def test_doctor_aggregates_multiple_external_failures_without_short_circuiting(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    source_a = tmp_path / "external-a.bin"
    source_b = tmp_path / "external-b.bin"
    source_a.write_bytes(b"external-a-good")
    source_b.write_bytes(b"external-b-good")
    assert _cli(projects_root, "projects", "create", "demo", "--name", "Demo").returncode == 0
    imported_a = _cli(
        projects_root,
        "media",
        "import",
        str(source_a),
        "--project",
        "demo",
        "--realm",
        "external_local",
    )
    imported_b = _cli(
        projects_root,
        "media",
        "import",
        str(source_b),
        "--project",
        "demo",
        "--realm",
        "external_local",
    )
    assert imported_a.returncode == 0, imported_a.stderr
    assert imported_b.returncode == 0, imported_b.stderr
    media_a = json.loads(imported_a.stdout)["data"]["id"]
    media_b = json.loads(imported_b.stdout)["data"]["id"]
    before = (projects_root / ".astrid" / "astrid.sqlite3").read_bytes()

    source_a.write_bytes(b"external-a-mutated")
    source_b.unlink()
    check = _media_check(projects_root)
    assert check.status == "fail"
    assert "checked 2 locator(s), failed 2" in check.detail
    assert "hash_mismatch=1" in check.detail
    assert "unavailable=1" in check.detail
    assert media_a in check.detail
    assert media_b in check.detail
    assert "cap=8" in check.detail
    assert "truncated=0" in check.detail
    assert (projects_root / ".astrid" / "astrid.sqlite3").read_bytes() == before
