"""Create a Sprint 0 multi-root rollback snapshot.

The snapshot layout is intentionally stable:

* ``projects/`` contains the selected Astrid projects root.
* ``repo/`` contains only the declared repo-root rollback subset.
"""

from __future__ import annotations

import argparse
import os
import tarfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.foundation.paths import REPO_ROOT as DEFAULT_REPO_ROOT

DEFAULT_SNAPSHOT_ROOT = Path("~/astrid-snapshots")
_SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
}


def _resolve_existing_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise SystemExit(f"ERROR: {label} does not exist or is not a directory: {resolved}")
    return resolved


def _ensure_outside_repo(out_dir: Path, repo_root: Path) -> Path:
    resolved = out_dir.expanduser().resolve()
    repo = repo_root.resolve()
    try:
        inside_repo = resolved == repo or resolved.is_relative_to(repo)
    except AttributeError:
        inside_repo = resolved == repo or repo in resolved.parents
    if inside_repo:
        raise SystemExit(f"ERROR: snapshot out-dir must live outside the repo: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _iter_tree(root: Path) -> Iterable[Path]:
    yield root
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIR_NAMES)
        current_path = Path(current)
        for dirname in dirs:
            yield current_path / dirname
        for filename in sorted(files):
            yield current_path / filename


def _iter_variant_sidecars(repo_root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(repo_root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIR_NAMES)
        if ".astrid.variants.json" in files:
            yield Path(current) / ".astrid.variants.json"


def _repo_subset_paths(repo_root: Path) -> list[Path]:
    candidates: list[Path] = []
    threads_root = repo_root / ".astrid" / "threads"
    candidates.append(repo_root / ".astrid" / "threads.json")
    if threads_root.is_dir():
        candidates.extend(sorted(threads_root.glob("**/groups.json")))
        candidates.extend(sorted(threads_root.glob("**/selections.jsonl")))
    candidates.extend(_iter_variant_sidecars(repo_root))

    unique: dict[Path, None] = {}
    for path in candidates:
        if path.is_file():
            unique[path.resolve()] = None
    return sorted(unique, key=lambda p: p.relative_to(repo_root.resolve()).as_posix())


def _add_path(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    tar.add(path, arcname=arcname, recursive=False)


def create_snapshot(*, projects_root: Path, repo_root: Path, out_dir: Path, timestamp: str | None = None) -> Path:
    projects_root = _resolve_existing_dir(projects_root, "projects root")
    repo_root = _resolve_existing_dir(repo_root, "repo root")
    out_dir = _ensure_outside_repo(out_dir, repo_root)
    stamp = timestamp or _timestamp()
    tarball = out_dir / f"astrid-state-{stamp}.tar.gz"
    if tarball.exists():
        raise SystemExit(f"ERROR: snapshot tarball already exists: {tarball}")

    with tarfile.open(tarball, "w:gz", format=tarfile.PAX_FORMAT, dereference=False) as tar:
        _add_path(tar, projects_root, "projects")
        for path in _iter_tree(projects_root):
            if path == projects_root:
                continue
            rel = path.relative_to(projects_root).as_posix()
            _add_path(tar, path, f"projects/{rel}")

        repo_info = tarfile.TarInfo("repo")
        repo_info.type = tarfile.DIRTYPE
        repo_info.mode = 0o755
        repo_info.mtime = int(datetime.now(UTC).timestamp())
        tar.addfile(repo_info)
        for path in _repo_subset_paths(repo_root):
            rel = path.relative_to(repo_root).as_posix()
            _add_path(tar, path, f"repo/{rel}")

    if not tarball.is_file() or tarball.stat().st_size == 0:
        raise SystemExit(f"ERROR: snapshot tarball was not created: {tarball}")
    with tarfile.open(tarball, "r:gz") as tar:
        names = set(tar.getnames())
    if "projects" not in names or "repo" not in names:
        tarball.unlink(missing_ok=True)
        raise SystemExit(f"ERROR: snapshot missing required projects/ or repo/ roots: {tarball}")
    return tarball


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a Sprint 0 multi-root rollback snapshot.")
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=None,
        help="Astrid projects root. Defaults to ASTRID_PROJECTS_ROOT or Astrid's configured default.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help=f"Repo root used for repo rollback subset discovery (default: {DEFAULT_REPO_ROOT}).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_ROOT,
        help=f"External snapshot directory (default: {DEFAULT_SNAPSHOT_ROOT}).",
    )
    parser.add_argument(
        "--timestamp",
        help="Override timestamp for deterministic tests. Defaults to current UTC YYYYMMDD-HHMMSS.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    projects_root = resolve_projects_root(args.projects_root)
    tarball = create_snapshot(
        projects_root=projects_root,
        repo_root=args.repo_root,
        out_dir=args.out_dir,
        timestamp=args.timestamp,
    )
    print(tarball)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
