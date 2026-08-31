from __future__ import annotations

import tarfile
from io import BytesIO
from pathlib import Path

import pytest

from scripts.reshape.restore_rehearsal import rehearse_restore
from scripts.reshape.snapshot_state import create_snapshot


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot_fixture(tmp_path: Path) -> Path:
    projects_root = tmp_path / "projects-root"
    repo_root = tmp_path / "repo-root"
    out_dir = tmp_path / "snapshots"
    _write(projects_root / "alpha" / "current_run.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "events.jsonl")
    _write(repo_root / "runs" / "out-1" / ".astrid.variants.json")
    return create_snapshot(
        projects_root=projects_root,
        repo_root=repo_root,
        out_dir=out_dir,
        timestamp="20260524-030405",
    )


def test_restore_rehearsal_extracts_and_reads_multiroot_snapshot(tmp_path: Path) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    restore_dir = tmp_path / "restore"

    report = rehearse_restore(snapshot=snapshot, out_dir=restore_dir)

    assert report.restore_dir == restore_dir.resolve()
    assert report.projects_dir == restore_dir.resolve() / "projects"
    assert report.repo_dir == restore_dir.resolve() / "repo"
    assert report.project_file_count == 2
    assert report.repo_state_file_count == 1
    assert (report.projects_dir / "alpha" / "current_run.json").read_text(encoding="utf-8") == "{}\n"
    assert (report.repo_dir / "runs" / "out-1" / ".astrid.variants.json").read_text(encoding="utf-8") == "{}\n"


def test_restore_rehearsal_rejects_target_roots_without_destructive_flag(tmp_path: Path) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    target_projects = tmp_path / "live-projects"
    target_repo = tmp_path / "live-repo"
    _write(target_projects / "sentinel.txt", "keep\n")
    _write(target_repo / "sentinel.txt", "keep\n")

    with pytest.raises(SystemExit, match="--destructive-restore"):
        rehearse_restore(
            snapshot=snapshot,
            out_dir=tmp_path / "restore",
            target_projects_root=target_projects,
            target_repo_root=target_repo,
        )

    assert (target_projects / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert (target_repo / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (target_projects / "alpha" / "current_run.json").exists()


def test_restore_rehearsal_requires_both_targets_for_destructive_restore(tmp_path: Path) -> None:
    snapshot = _snapshot_fixture(tmp_path)

    with pytest.raises(SystemExit, match="--target-projects-root and --target-repo-root"):
        rehearse_restore(
            snapshot=snapshot,
            out_dir=tmp_path / "restore",
            target_projects_root=tmp_path / "live-projects",
            destructive_restore=True,
        )


def test_restore_rehearsal_destructive_restore_copies_only_after_full_opt_in(tmp_path: Path) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    target_projects = tmp_path / "live-projects"
    target_repo = tmp_path / "live-repo"

    rehearse_restore(
        snapshot=snapshot,
        out_dir=tmp_path / "restore",
        target_projects_root=target_projects,
        target_repo_root=target_repo,
        destructive_restore=True,
    )

    assert (target_projects / "alpha" / "current_run.json").read_text(encoding="utf-8") == "{}\n"
    assert (target_repo / "runs" / "out-1" / ".astrid.variants.json").read_text(encoding="utf-8") == "{}\n"


def test_restore_rehearsal_rejects_retired_thread_state(tmp_path: Path) -> None:
    snapshot = tmp_path / "malicious.tar.gz"
    with tarfile.open(snapshot, "w:gz") as tar:
        for name in ("projects", "repo", "repo/.astrid", "repo/.astrid/threads.json"):
            if name.endswith(".json"):
                payload = b"{}\n"
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                tar.addfile(info, BytesIO(payload))
            else:
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)

    with pytest.raises(SystemExit, match="retired thread state"):
        rehearse_restore(snapshot=snapshot, out_dir=tmp_path / "restore")


def test_restore_rehearsal_rejects_retired_thread_state_variants(tmp_path: Path) -> None:
    snapshot = tmp_path / "malicious-thread-state.tar.gz"
    with tarfile.open(snapshot, "w:gz") as tar:
        for name in ("projects", "repo", "repo/.astrid", "repo/.astrid/thread_state.json"):
            if name.endswith(".json"):
                payload = b"{}\n"
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                tar.addfile(info, BytesIO(payload))
            else:
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)

    with pytest.raises(SystemExit, match="retired thread state"):
        rehearse_restore(snapshot=snapshot, out_dir=tmp_path / "restore")


def test_restore_rehearsal_rejects_symlink_members(tmp_path: Path) -> None:
    snapshot = tmp_path / "symlink.tar.gz"
    with tarfile.open(snapshot, "w:gz") as tar:
        for name in ("projects", "repo"):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        info = tarfile.TarInfo("repo/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/outside"
        tar.addfile(info)

    with pytest.raises(SystemExit, match="unsupported archive member type"):
        rehearse_restore(snapshot=snapshot, out_dir=tmp_path / "restore")


def test_restore_rehearsal_rejects_traversal_members(tmp_path: Path) -> None:
    snapshot = tmp_path / "traversal.tar.gz"
    with tarfile.open(snapshot, "w:gz") as tar:
        for name in ("projects", "repo", "../escaped.txt"):
            info = tarfile.TarInfo(name)
            if name.endswith("/") or name in {"projects", "repo"}:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
                continue
            payload = b"must not escape\n"
            info.size = len(payload)
            tar.addfile(info, BytesIO(payload))

    with pytest.raises(SystemExit, match="unsafe path"):
        rehearse_restore(snapshot=snapshot, out_dir=tmp_path / "restore")
