"""Rehearse extraction of a Sprint 0 multi-root rollback snapshot."""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RestoreReport:
    restore_dir: Path
    projects_dir: Path
    repo_dir: Path
    project_file_count: int
    repo_state_file_count: int


def _safe_member_names(tar: tarfile.TarFile) -> list[str]:
    names: list[str] = []
    for member in tar.getmembers():
        name = member.name
        parts = Path(name).parts
        if not name or Path(name).is_absolute() or ".." in parts:
            raise SystemExit(f"ERROR: unsafe path in snapshot: {name!r}")
        if parts[0] not in {"projects", "repo"}:
            raise SystemExit(f"ERROR: unexpected top-level snapshot path: {name!r}")
        names.append(name)
    return names


def _prepare_restore_dir(out_dir: Path | None) -> Path:
    if out_dir is None:
        return Path(tempfile.mkdtemp(prefix="astrid-restore-")).resolve()
    resolved = out_dir.expanduser().resolve()
    if resolved.exists() and any(resolved.iterdir()):
        raise SystemExit(f"ERROR: restore out-dir must be empty: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _project_files(projects_dir: Path) -> list[Path]:
    return sorted(path for path in projects_dir.rglob("*") if path.is_file())


def _repo_state_files(repo_dir: Path) -> list[Path]:
    return sorted({path.resolve() for path in repo_dir.rglob(".astrid.variants.json") if path.is_file()})


def _prove_readable(paths: Iterable[Path], label: str) -> None:
    for path in paths:
        try:
            with path.open("rb") as fh:
                fh.read(1)
        except OSError as exc:
            raise SystemExit(f"ERROR: unreadable {label} file {path}: {exc}") from exc


def _copy_tree_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir(), key=lambda p: p.name):
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(child, destination)


def _maybe_copy_to_targets(
    report: RestoreReport,
    *,
    target_projects_root: Path | None,
    target_repo_root: Path | None,
    destructive_restore: bool,
) -> None:
    requested = target_projects_root is not None or target_repo_root is not None or destructive_restore
    if not requested:
        return
    if not destructive_restore:
        raise SystemExit("ERROR: live restore requires --destructive-restore")
    if target_projects_root is None or target_repo_root is None:
        raise SystemExit("ERROR: live restore requires --target-projects-root and --target-repo-root")
    _copy_tree_contents(report.projects_dir, target_projects_root.expanduser().resolve())
    _copy_tree_contents(report.repo_dir, target_repo_root.expanduser().resolve())


def rehearse_restore(
    *,
    snapshot: Path,
    out_dir: Path | None,
    target_projects_root: Path | None = None,
    target_repo_root: Path | None = None,
    destructive_restore: bool = False,
) -> RestoreReport:
    snapshot = snapshot.expanduser().resolve()
    if not snapshot.is_file():
        raise SystemExit(f"ERROR: snapshot does not exist: {snapshot}")
    restore_dir = _prepare_restore_dir(out_dir)

    with tarfile.open(snapshot, "r:gz") as tar:
        names = set(_safe_member_names(tar))
        if "projects" not in names or "repo" not in names:
            raise SystemExit("ERROR: snapshot must contain stable projects/ and repo/ roots")
        tar.extractall(restore_dir)

    projects_dir = restore_dir / "projects"
    repo_dir = restore_dir / "repo"
    if not projects_dir.is_dir() or not repo_dir.is_dir():
        raise SystemExit("ERROR: extracted snapshot missing projects/ or repo/ directory")

    project_files = _project_files(projects_dir)
    repo_files = _repo_state_files(repo_dir)
    if not project_files:
        raise SystemExit("ERROR: extracted projects/ contains no readable project files")
    if not repo_files:
        raise SystemExit("ERROR: extracted repo/ contains no declared variant rollback files")

    _prove_readable(project_files, "project")
    _prove_readable(repo_files, "repo rollback")

    report = RestoreReport(
        restore_dir=restore_dir,
        projects_dir=projects_dir,
        repo_dir=repo_dir,
        project_file_count=len(project_files),
        repo_state_file_count=len(repo_files),
    )
    _maybe_copy_to_targets(
        report,
        target_projects_root=target_projects_root,
        target_repo_root=target_repo_root,
        destructive_restore=destructive_restore,
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rehearse a Sprint 0 multi-root snapshot restore.")
    parser.add_argument("--snapshot", type=Path, required=True, help="Snapshot tarball to extract.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Empty restore directory. Defaults to a new temporary directory.",
    )
    parser.add_argument("--target-projects-root", type=Path, help="Destructive live restore target for projects/.")
    parser.add_argument("--target-repo-root", type=Path, help="Destructive live restore target for repo/.")
    parser.add_argument(
        "--destructive-restore",
        action="store_true",
        help="Actually copy extracted projects/ and repo/ into the explicit target roots.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = rehearse_restore(
        snapshot=args.snapshot,
        out_dir=args.out_dir,
        target_projects_root=args.target_projects_root,
        target_repo_root=args.target_repo_root,
        destructive_restore=args.destructive_restore,
    )
    print(f"restore_dir={report.restore_dir}")
    print(f"projects_dir={report.projects_dir}")
    print(f"repo_dir={report.repo_dir}")
    print(f"project_file_count={report.project_file_count}")
    print(f"repo_state_file_count={report.repo_state_file_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
