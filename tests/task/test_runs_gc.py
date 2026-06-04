from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from astrid.core.project.project import create_project
from astrid.core.project.paths import project_dir
from astrid.core.task.run_gc import cmd_runs_gc, select_runs_for_gc
from astrid.core.timeline import crud


OLD_RUN = "01AAA111111111111111111111"
MID_RUN = "01BBB222222222222222222222"
NEW_RUN = "01CCC333333333333333333333"
PROTECTED_RUN = "01DDD444444444444444444444"


def test_select_runs_for_gc_protects_all_contributing_runs(tmp_projects_root: Path) -> None:
    slug = "gc-protect"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)
    _write_run_json(proj_root / "runs" / OLD_RUN, "2026-01-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / PROTECTED_RUN, "2026-01-02T00:00:00Z")
    _write_run_json(proj_root / "runs" / NEW_RUN, "2026-03-30T00:00:00Z")

    protected_ulid = crud.create_timeline(slug, "protected-a", root=tmp_projects_root)["ulid"]
    second_ulid = crud.create_timeline(slug, "protected-b", root=tmp_projects_root)["ulid"]
    _write_manifest(proj_root / "timelines" / protected_ulid / "manifest.json", [PROTECTED_RUN])
    _write_manifest(proj_root / "timelines" / second_ulid / "manifest.json", [PROTECTED_RUN, NEW_RUN])

    selection = select_runs_for_gc(
        slug,
        older_than_days=30,
        root=tmp_projects_root,
        now=_dt("2026-04-15T00:00:00Z"),
    )

    assert selection.protected_run_ids == frozenset({PROTECTED_RUN, NEW_RUN})
    assert [entry.run_id for entry in selection.deletion_candidates] == [OLD_RUN]
    protected = {entry.run_id for entry in selection.runs if entry.protected}
    assert protected == {PROTECTED_RUN, NEW_RUN}


def test_select_runs_for_gc_falls_back_to_mtime_for_missing_or_invalid_run_json(tmp_projects_root: Path) -> None:
    slug = "gc-mtime"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)
    runs_root = proj_root / "runs"

    missing_run = runs_root / OLD_RUN
    missing_run.mkdir(parents=True, exist_ok=True)
    invalid_run = runs_root / MID_RUN
    invalid_run.mkdir(parents=True, exist_ok=True)
    (invalid_run / "run.json").write_text("{not-json", encoding="utf-8")
    fresh_run = runs_root / NEW_RUN
    _write_run_json(fresh_run, "2026-04-10T00:00:00Z")

    old_epoch = _dt("2026-01-01T00:00:00Z").timestamp()
    fresh_epoch = _dt("2026-04-14T00:00:00Z").timestamp()
    os.utime(missing_run, (old_epoch, old_epoch))
    os.utime(invalid_run / "run.json", (old_epoch, old_epoch))
    os.utime(fresh_run / "run.json", (fresh_epoch, fresh_epoch))

    selection = select_runs_for_gc(
        slug,
        older_than_days=30,
        root=tmp_projects_root,
        now=_dt("2026-04-15T00:00:00Z"),
    )

    by_run_id = {entry.run_id: entry for entry in selection.runs}
    assert by_run_id[OLD_RUN].timestamp_source == "mtime"
    assert by_run_id[MID_RUN].timestamp_source == "mtime"
    assert by_run_id[NEW_RUN].timestamp_source == "run_json"
    assert [entry.run_id for entry in selection.deletion_candidates] == [OLD_RUN, MID_RUN]


def test_select_runs_for_gc_respects_keep_last_after_age_filter(tmp_projects_root: Path) -> None:
    slug = "gc-keep-last"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)

    base = _dt("2026-01-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / OLD_RUN, (base + timedelta(days=0)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / MID_RUN, (base + timedelta(days=10)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / NEW_RUN, (base + timedelta(days=20)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / PROTECTED_RUN, (base + timedelta(days=30)).isoformat().replace("+00:00", "Z"))

    selection = select_runs_for_gc(
        slug,
        older_than_days=30,
        keep_last=2,
        root=tmp_projects_root,
        now=_dt("2026-04-15T00:00:00Z"),
    )

    assert [entry.run_id for entry in selection.deletion_candidates] == [OLD_RUN, MID_RUN]
    assert PROTECTED_RUN not in [entry.run_id for entry in selection.deletion_candidates]
    assert NEW_RUN not in [entry.run_id for entry in selection.deletion_candidates]


def _write_run_json(run_root: Path, timestamp: str) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_slug": "unused",
                "run_id": run_root.name,
                "status": "running",
                "auto_bound": False,
                "invocation": "cli",
                "created_at": timestamp,
                "updated_at": timestamp,
                "metadata": {},
                "artifacts": {},
            }
        ),
        encoding="utf-8",
    )


def _write_manifest(path: Path, run_ids: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": run_ids,
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# CLI tests for ``astrid runs gc``
# ---------------------------------------------------------------------------


def test_gc_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """--help prints usage and returns 0 (SystemExit caught by handler)."""
    rc = cmd_runs_gc(["--help"])
    # argparse --help returns 0 after printing; handler catches SystemExit
    assert rc == 0
    captured = capsys.readouterr()
    assert "--project" in captured.out
    assert "--older-than-days" in captured.out
    assert "--keep-last" in captured.out
    assert "--apply" in captured.out


def test_gc_missing_project_errors(capsys: pytest.CaptureFixture[str]) -> None:
    """Missing --project prints error and returns non-zero."""
    rc = cmd_runs_gc([])
    assert rc != 0
    captured = capsys.readouterr()
    assert "required" in captured.err.lower() or "--project" in captured.err.lower()


def test_gc_dry_run_default(tmp_projects_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Dry-run is the default: lists candidates but does not delete."""
    slug = "gc-dry-default"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)

    base = _dt("2026-01-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / OLD_RUN, (base + timedelta(days=0)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / NEW_RUN, (base + timedelta(days=10)).isoformat().replace("+00:00", "Z"))

    rc = cmd_runs_gc(
        ["--project", slug, "--older-than-days", "30"],
        projects_root=tmp_projects_root,
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "[DRY RUN]" in captured.out
    assert "would delete" in captured.out
    assert OLD_RUN in captured.out
    assert "Dry run — no runs were deleted." in captured.out
    assert "Re-run with --apply" in captured.out
    # Runs still exist
    assert (proj_root / "runs" / OLD_RUN).is_dir()
    assert (proj_root / "runs" / NEW_RUN).is_dir()


def test_gc_apply_deletes_candidates(tmp_projects_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--apply actually removes the candidate directories."""
    slug = "gc-apply"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)

    base = _dt("2025-06-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / OLD_RUN, (base + timedelta(days=0)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / MID_RUN, (base + timedelta(days=1)).isoformat().replace("+00:00", "Z"))

    rc = cmd_runs_gc(
        ["--project", slug, "--older-than-days", "30", "--apply"],
        projects_root=tmp_projects_root,
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "[DRY RUN]" not in captured.out
    assert "deleting" in captured.out
    assert "deleted 2 run(s)" in captured.out
    # Runs are actually deleted
    assert not (proj_root / "runs" / OLD_RUN).is_dir()
    assert not (proj_root / "runs" / MID_RUN).is_dir()


def test_gc_custom_older_than_days(tmp_projects_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--older-than-days flag is respected."""
    slug = "gc-custom-age"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)

    base = _dt("2026-01-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / OLD_RUN, (base + timedelta(days=0)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / NEW_RUN, (base + timedelta(days=180)).isoformat().replace("+00:00", "Z"))

    rc = cmd_runs_gc(
        ["--project", slug, "--older-than-days", "60"],
        projects_root=tmp_projects_root,
    )
    assert rc == 0
    captured = capsys.readouterr()
    # OLD_RUN is still >60 days (around 167 days from Jan 1 to now if now is around June)
    # With a cutoff of 60 days, a Jan 1 run is definitely old.
    assert OLD_RUN in captured.out
    assert "would delete" in captured.out


def test_gc_keep_last_preserves_newest(tmp_projects_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--keep-last preserves the newest N runs regardless of age."""
    slug = "gc-keep-last"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)

    base = _dt("2025-06-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / OLD_RUN, (base + timedelta(days=0)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / MID_RUN, (base + timedelta(days=10)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / NEW_RUN, (base + timedelta(days=20)).isoformat().replace("+00:00", "Z"))

    rc = cmd_runs_gc(
        ["--project", slug, "--older-than-days", "30", "--keep-last", "2"],
        projects_root=tmp_projects_root,
    )
    assert rc == 0
    captured = capsys.readouterr()
    # All 3 are very old (>30 days, they're from 2025), but newest 2 should be preserved.
    assert "keeping newest 2" in captured.out
    assert OLD_RUN in captured.out  # oldest should be a candidate
    assert "would delete" in captured.out


def test_gc_protected_runs_survive_apply(tmp_projects_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Protected (contributing) runs are never deleted, even with --apply."""
    slug = "gc-protected-survive"
    create_project(slug, root=tmp_projects_root)
    proj_root = project_dir(slug, root=tmp_projects_root)

    base = _dt("2025-06-01T00:00:00Z")
    _write_run_json(proj_root / "runs" / OLD_RUN, (base + timedelta(days=0)).isoformat().replace("+00:00", "Z"))
    _write_run_json(proj_root / "runs" / PROTECTED_RUN, (base + timedelta(days=5)).isoformat().replace("+00:00", "Z"))

    protected_ulid = crud.create_timeline(slug, "protected", root=tmp_projects_root)["ulid"]
    _write_manifest(
        proj_root / "timelines" / protected_ulid / "manifest.json",
        [PROTECTED_RUN],
    )

    rc = cmd_runs_gc(
        ["--project", slug, "--older-than-days", "30", "--apply"],
        projects_root=tmp_projects_root,
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "deleting" in captured.out
    assert OLD_RUN in captured.out  # was deleted
    assert "(protected)" in captured.out
    assert PROTECTED_RUN in captured.out
    # OLD_RUN is gone, PROTECTED_RUN survives
    assert not (proj_root / "runs" / OLD_RUN).is_dir()
    assert (proj_root / "runs" / PROTECTED_RUN).is_dir()


def test_gc_no_runs(tmp_projects_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Empty project prints a message and exits cleanly."""
    slug = "gc-empty"
    create_project(slug, root=tmp_projects_root)

    rc = cmd_runs_gc(
        ["--project", slug],
        projects_root=tmp_projects_root,
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "no runs found" in captured.out


def test_gc_bad_project(capsys: pytest.CaptureFixture[str]) -> None:
    """Invalid project slug produces an error on stderr."""
    rc = cmd_runs_gc(["--project", "not/a/slug!"])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err != ""
