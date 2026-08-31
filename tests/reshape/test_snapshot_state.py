from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from scripts.reshape.snapshot_state import create_snapshot, main


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_snapshot_state_writes_stable_multi_root_tarball(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects-root"
    repo_root = tmp_path / "repo-root"
    out_dir = tmp_path / "outside-snapshots"

    _write(projects_root / "alpha" / "current_run.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "lease.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "events.jsonl", "{}\n")
    _write(projects_root / "alpha" / "runs" / "run-1" / "media.mp4", "not-real-media\n")

    _write(repo_root / "runs" / "out-1" / ".astrid.variants.json")
    _write(repo_root / "src" / "not-rollback-state.py", "print('no')\n")

    tarball = create_snapshot(
        projects_root=projects_root,
        repo_root=repo_root,
        out_dir=out_dir,
        timestamp="20260524-010203",
    )

    assert tarball == out_dir / "astrid-state-20260524-010203.tar.gz"
    assert tarball.is_file()
    assert not tarball.resolve().is_relative_to(repo_root.resolve())

    with tarfile.open(tarball, "r:gz") as tar:
        names = set(tar.getnames())

    assert "projects" in names
    assert "repo" in names
    assert "projects/alpha/current_run.json" in names
    assert "projects/alpha/runs/run-1/lease.json" in names
    assert "projects/alpha/runs/run-1/events.jsonl" in names
    assert "projects/alpha/runs/run-1/media.mp4" in names
    assert "repo/runs/out-1/.astrid.variants.json" in names
    assert not any("threads" in name for name in names)
    assert "repo/src/not-rollback-state.py" not in names


def test_snapshot_state_excludes_nested_retired_thread_state_but_keeps_json(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects-root"
    repo_root = tmp_path / "repo-root"
    out_dir = tmp_path / "outside-snapshots"

    _write(projects_root / "alpha" / "current_run.json")
    _write(projects_root / "alpha" / "notes" / "threading.json", "keep\n")
    _write(projects_root / "alpha" / "notes" / "threading.threading.json", "keep\n")
    _write(projects_root / "alpha" / ".astrid" / "threads.json", "retired\n")
    _write(projects_root / "alpha" / "state" / "thread_groups.json", "retired\n")
    _write(projects_root / "alpha" / "nested" / "threads" / "secret.json", "retired\n")
    _write(projects_root / "alpha" / "runs" / "run-1" / "attempt.thread.json", "retired\n")
    _write(repo_root / "runs" / "out-1" / ".astrid.variants.json")
    _write(repo_root / "retired" / "threads" / ".astrid.variants.json", "retired\n")

    tarball = create_snapshot(
        projects_root=projects_root,
        repo_root=repo_root,
        out_dir=out_dir,
        timestamp="20260524-010204",
    )

    with tarfile.open(tarball, "r:gz") as tar:
        names = set(tar.getnames())

    assert "projects/alpha/notes/threading.json" in names
    assert "projects/alpha/notes/threading.threading.json" in names
    assert "projects/alpha/.astrid/threads.json" not in names
    assert "projects/alpha/state/thread_groups.json" not in names
    assert "projects/alpha/nested/threads" not in names
    assert "projects/alpha/runs/run-1/attempt.thread.json" not in names
    assert "repo/retired/threads/.astrid.variants.json" not in names


def test_snapshot_state_rejects_out_dir_inside_repo(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects-root"
    repo_root = tmp_path / "repo-root"
    projects_root.mkdir()
    repo_root.mkdir()

    with pytest.raises(SystemExit, match="outside the repo"):
        create_snapshot(
            projects_root=projects_root,
            repo_root=repo_root,
            out_dir=repo_root / "snapshots",
            timestamp="20260524-010203",
        )


def test_snapshot_state_cli_accepts_explicit_roots(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    projects_root = tmp_path / "projects-root"
    repo_root = tmp_path / "repo-root"
    out_dir = tmp_path / "outside-snapshots"
    repo_root.mkdir(parents=True)
    _write(projects_root / "alpha" / "active_run.json")

    rc = main(
        [
            "--projects-root",
            str(projects_root),
            "--repo-root",
            str(repo_root),
            "--out-dir",
            str(out_dir),
            "--timestamp",
            "20260524-010203",
        ]
    )

    assert rc == 0
    printed = Path(capsys.readouterr().out.strip())
    assert printed == out_dir / "astrid-state-20260524-010203.tar.gz"
    assert printed.is_file()
