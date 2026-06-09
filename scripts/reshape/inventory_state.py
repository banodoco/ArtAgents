"""Create a stable Sprint 0 multi-root state inventory CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.foundation.paths import REPO_ROOT as DEFAULT_REPO_ROOT

CSV_COLUMNS = [
    "root_kind",
    "project_slug",
    "run_id",
    "state_kind",
    "relative_path",
    "size_bytes",
    "mtime_ns",
    "sha256",
]

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


@dataclass(frozen=True)
class InventoryRow:
    root_kind: str
    project_slug: str
    run_id: str
    state_kind: str
    relative_path: str
    size_bytes: int
    mtime_ns: int
    sha256: str

    def as_csv_row(self) -> dict[str, object]:
        return {
            "root_kind": self.root_kind,
            "project_slug": self.project_slug,
            "run_id": self.run_id,
            "state_kind": self.state_kind,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
        }


def _resolve_existing_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise SystemExit(f"ERROR: {label} does not exist or is not a directory: {resolved}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row(
    *,
    root_kind: str,
    root: Path,
    path: Path,
    state_kind: str,
    project_slug: str = "",
    run_id: str = "",
) -> InventoryRow:
    stat = path.stat()
    return InventoryRow(
        root_kind=root_kind,
        project_slug=project_slug,
        run_id=run_id,
        state_kind=state_kind,
        relative_path=path.relative_to(root).as_posix(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=_sha256(path),
    )


def _add_if_file(
    rows: list[InventoryRow],
    *,
    root_kind: str,
    root: Path,
    path: Path,
    state_kind: str,
    project_slug: str = "",
    run_id: str = "",
) -> None:
    if path.is_file():
        rows.append(
            _row(
                root_kind=root_kind,
                root=root,
                path=path,
                state_kind=state_kind,
                project_slug=project_slug,
                run_id=run_id,
            )
        )


def _iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIR_NAMES)
        current_path = Path(current)
        for filename in sorted(files):
            yield current_path / filename


def _project_rows(projects_root: Path) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    for project_dir in sorted((path for path in projects_root.iterdir() if path.is_dir()), key=lambda p: p.name):
        slug = project_dir.name
        _add_if_file(
            rows,
            root_kind="projects",
            root=projects_root,
            path=project_dir / "active_run.json",
            state_kind="legacy_active_run",
            project_slug=slug,
        )
        _add_if_file(
            rows,
            root_kind="projects",
            root=projects_root,
            path=project_dir / "current_run.json",
            state_kind="current_run",
            project_slug=slug,
        )
        _add_if_file(
            rows,
            root_kind="projects",
            root=projects_root,
            path=project_dir / "timeline.json",
            state_kind="project_timeline",
            project_slug=slug,
        )

        runs_root = project_dir / "runs"
        if not runs_root.is_dir():
            continue
        for run_dir in sorted((path for path in runs_root.iterdir() if path.is_dir()), key=lambda p: p.name):
            run_id = run_dir.name
            for filename, state_kind in (
                ("timeline.json", "run_timeline"),
                ("plan.json", "run_plan"),
                ("lease.json", "run_lease"),
                ("events.jsonl", "run_events"),
                ("hype.plan.json", "hype_plan"),
            ):
                _add_if_file(
                    rows,
                    root_kind="projects",
                    root=projects_root,
                    path=run_dir / filename,
                    state_kind=state_kind,
                    project_slug=slug,
                    run_id=run_id,
                )
            _add_if_file(
                rows,
                root_kind="projects",
                root=projects_root,
                path=run_dir / "audit" / "ledger.jsonl",
                state_kind="audit_ledger",
                project_slug=slug,
                run_id=run_id,
            )
            debug_root = run_dir / "_llm_debug"
            if debug_root.is_dir():
                for path in _iter_files(debug_root):
                    rows.append(
                        _row(
                            root_kind="projects",
                            root=projects_root,
                            path=path,
                            state_kind="llm_debug",
                            project_slug=slug,
                            run_id=run_id,
                        )
                    )
    return rows


def _iter_variant_sidecars(repo_root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(repo_root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIR_NAMES)
        if ".astrid.variants.json" in files:
            yield Path(current) / ".astrid.variants.json"


def _repo_rows(repo_root: Path) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    _add_if_file(
        rows,
        root_kind="repo",
        root=repo_root,
        path=repo_root / ".astrid" / "threads.json",
        state_kind="repo_thread_index",
    )

    threads_root = repo_root / ".astrid" / "threads"
    if threads_root.is_dir():
        for path in sorted(threads_root.glob("**/groups.json")):
            if path.is_file():
                rows.append(
                    _row(root_kind="repo", root=repo_root, path=path, state_kind="repo_thread_group")
                )
        for path in sorted(threads_root.glob("**/selections.jsonl")):
            if path.is_file():
                rows.append(
                    _row(root_kind="repo", root=repo_root, path=path, state_kind="repo_thread_selection")
                )

    seen = {row.relative_path for row in rows}
    for path in sorted(_iter_variant_sidecars(repo_root), key=lambda p: p.relative_to(repo_root).as_posix()):
        rel = path.relative_to(repo_root).as_posix()
        if path.is_file() and rel not in seen:
            rows.append(_row(root_kind="repo", root=repo_root, path=path, state_kind="variant_sidecar"))
            seen.add(rel)
    return rows


def collect_inventory(*, projects_root: Path, repo_root: Path) -> list[InventoryRow]:
    projects_root = _resolve_existing_dir(projects_root, "projects root")
    repo_root = _resolve_existing_dir(repo_root, "repo root")
    rows = [*_project_rows(projects_root), *_repo_rows(repo_root)]
    return sorted(rows, key=lambda row: (row.root_kind, row.project_slug, row.run_id, row.state_kind, row.relative_path))


def write_inventory(rows: Sequence[InventoryRow], out: Path) -> Path:
    resolved = out.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_csv_row())
    return resolved


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a Sprint 0 multi-root state inventory CSV.")
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
        help=f"Repo root used for repo state discovery (default: {DEFAULT_REPO_ROOT}).",
    )
    parser.add_argument("--out", type=Path, required=True, help="CSV inventory output path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    projects_root = resolve_projects_root(args.projects_root)
    rows = collect_inventory(projects_root=projects_root, repo_root=args.repo_root)
    out = write_inventory(rows, args.out)
    print(f"Inventory written to {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
