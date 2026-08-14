"""Run-retention selection for ``astrid runs gc``.

This module owns the destructive-selection contract: age-based selection,
optional newest-N retention, protection of any run referenced by timeline
``contributing_runs`` manifests, and run-owned evidence retention. The CLI
handler renders stable output and defaults to dry-run so users always see what
*would* happen before any destructive action.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from astrid.core.foundation.project_paths import project_dir, validate_project_slug


@dataclass(frozen=True)
class RunGcEntry:
    run_id: str
    run_root: Path
    age_days: float
    sort_epoch: float
    timestamp_source: str
    selected_by_age: bool
    protected: bool
    evidence: bool = False


@dataclass(frozen=True)
class RunGcSelection:
    project_slug: str
    older_than_days: int
    keep_last: int | None
    protected_run_ids: frozenset[str]
    runs: tuple[RunGcEntry, ...]
    deletion_candidates: tuple[RunGcEntry, ...]
    evidence_run_ids: frozenset[str] = frozenset()
    include_evidence: bool = False


def select_runs_for_gc(
    project_slug: str,
    *,
    older_than_days: int = 30,
    keep_last: int | None = None,
    include_evidence: bool = False,
    root: str | Path | None = None,
    now: datetime | None = None,
) -> RunGcSelection:
    """Return retention metadata for all local run directories in a project.

    Deletion candidates must satisfy all of the following:
    - older than ``older_than_days`` based on run.json timestamps when valid,
      otherwise filesystem mtime fallback
    - not inside the newest ``keep_last`` runs when that retention floor is set
    - not referenced by any timeline manifest ``contributing_runs``
    - not marked ``run.metadata.evidence: true`` unless ``include_evidence``
      was explicitly requested
    """

    slug = validate_project_slug(project_slug)
    if keep_last is not None and keep_last < 0:
        raise ValueError("keep_last must be >= 0")
    current = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    proj_root = project_dir(slug, root=root)
    runs_root = proj_root / "runs"

    protected_run_ids = _protected_contributing_runs(proj_root)
    entries = [
        _run_gc_entry(
            run_root,
            protected_run_ids=protected_run_ids,
            include_evidence=include_evidence,
            now=current,
            older_than_days=older_than_days,
        )
        for run_root in sorted((p for p in runs_root.iterdir() if p.is_dir()), key=lambda p: p.name)
    ] if runs_root.is_dir() else []

    keep_ids: set[str] = set()
    if keep_last:
        newest = sorted(entries, key=lambda entry: (-entry.sort_epoch, entry.run_id))
        keep_ids = {entry.run_id for entry in newest[:keep_last]}

    deletion_candidates = tuple(
        sorted(
            (
                entry
                for entry in entries
                if entry.selected_by_age and not entry.protected and entry.run_id not in keep_ids
            ),
            key=lambda entry: (-entry.age_days, entry.run_id),
        )
    )
    all_runs = tuple(sorted(entries, key=lambda entry: (-entry.age_days, entry.run_id)))
    return RunGcSelection(
        project_slug=slug,
        older_than_days=older_than_days,
        keep_last=keep_last,
        protected_run_ids=frozenset(protected_run_ids),
        runs=all_runs,
        deletion_candidates=deletion_candidates,
        evidence_run_ids=frozenset(entry.run_id for entry in entries if entry.evidence),
        include_evidence=include_evidence,
    )


def _protected_contributing_runs(proj_root: Path) -> set[str]:
    protected: set[str] = set()
    timelines_root = proj_root / "timelines"
    if not timelines_root.is_dir():
        return protected
    for manifest_path in sorted(timelines_root.glob("*/manifest.json")):
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        contributing_runs = raw.get("contributing_runs", [])
        if not isinstance(contributing_runs, list):
            continue
        for item in contributing_runs:
            if isinstance(item, str) and item:
                protected.add(item)
    return protected


def _run_gc_entry(
    run_root: Path,
    *,
    protected_run_ids: set[str],
    include_evidence: bool,
    now: datetime,
    older_than_days: int,
) -> RunGcEntry:
    sort_epoch, source = _run_timestamp_or_mtime(run_root)
    age_days = max(0.0, (now.timestamp() - sort_epoch) / 86400.0)
    evidence = _run_is_evidence(run_root)
    return RunGcEntry(
        run_id=run_root.name,
        run_root=run_root,
        age_days=age_days,
        sort_epoch=sort_epoch,
        timestamp_source=source,
        selected_by_age=age_days > float(older_than_days),
        protected=(
            run_root.name in protected_run_ids
            or (evidence and not include_evidence)
        ),
        evidence=evidence,
    )


def _run_is_evidence(run_root: Path) -> bool:
    run_json_path = run_root / "run.json"
    if not run_json_path.is_file():
        return False
    try:
        raw = json.loads(run_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    metadata = raw.get("metadata") if isinstance(raw, dict) else None
    return isinstance(metadata, dict) and metadata.get("evidence") is True


def _run_timestamp_or_mtime(run_root: Path) -> tuple[float, str]:
    run_json_path = run_root / "run.json"
    if run_json_path.is_file():
        try:
            raw = json.loads(run_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            for field in ("updated_at", "created_at"):
                parsed = _parse_timestamp(raw.get(field))
                if parsed is not None:
                    return parsed.timestamp(), "run_json"
        return run_json_path.stat().st_mtime, "mtime"
    return run_root.stat().st_mtime, "mtime"


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# CLI handler: ``astrid runs gc``
# ---------------------------------------------------------------------------


def cmd_runs_gc(
    argv: Sequence[str],
    *,
    projects_root: str | Path | None = None,
) -> int:
    """Garbage-collect stale run directories.

    Defaults to **dry-run**: lists deletion candidates without touching
    the filesystem.  Pass ``--apply`` to actually remove the listed run
    directories.

    Runs referenced by any timeline ``manifest.json`` ``contributing_runs``
    field are **never** deleted — they are listed as ``(protected)``.
    """
    parser = argparse.ArgumentParser(
        prog="astrid runs gc",
        description="Remove stale run directories from a project.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project slug whose runs should be garbage-collected.",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=30,
        help="Delete runs older than this many days (default: 30).",
    )
    parser.add_argument(
        "--keep-last",
        type=int,
        default=None,
        help="Keep at least this many newest runs regardless of age.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually delete the listed run directories (default: dry-run).",
    )
    parser.add_argument(
        "--include-evidence",
        action="store_true",
        default=False,
        help=(
            "Include evidence-marked runs in age-based selection. Actual deletion "
            "still requires --apply; timeline contributing runs remain protected."
        ),
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        code = exc.code
        return 0 if code == 0 else int(code or 2)

    # Resolve project
    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"runs gc: {exc}", file=sys.stderr)
        return 1

    selection = select_runs_for_gc(
        slug,
        older_than_days=args.older_than_days,
        keep_last=args.keep_last,
        include_evidence=args.include_evidence,
        root=projects_root,
    )

    if not selection.runs:
        print(f"no runs found for project '{slug}'", file=sys.stdout)
        return 0

    dry_run = not args.apply
    header = "[DRY RUN] " if dry_run else ""

    n_protected = len({entry.run_id for entry in selection.runs if entry.protected})
    n_candidates = len(selection.deletion_candidates)

    if n_candidates == 0 and n_protected == 0:
        print(
            f"{header}no stale runs found (cutoff: >{args.older_than_days} days)",
            file=sys.stdout,
        )
        return 0

    print(
        f"{header}{n_candidates} run(s) eligible for deletion "
        f"(older than {args.older_than_days} days"
        + (f", keeping newest {args.keep_last}" if args.keep_last else "")
        + f", {n_protected} protected)",
        file=sys.stdout,
    )
    print(file=sys.stdout)

    # Stable output: candidates oldest-first, then protected runs.
    for entry in selection.deletion_candidates:
        action = "would delete" if dry_run else "deleting"
        age_str = f"{entry.age_days:.1f}d"
        print(
            f"  {action} {entry.run_id}  "
            f"project={slug}  "
            f"age={age_str}  "
            f"path={entry.run_root}",
            file=sys.stdout,
        )

    for entry in selection.runs:
        if entry.protected and entry.run_id not in {
            c.run_id for c in selection.deletion_candidates
        }:
            age_str = f"{entry.age_days:.1f}d"
            reason = (
                "protected"
                if entry.run_id in selection.protected_run_ids
                else "evidence"
            )
            print(
                f"  ({reason}) {entry.run_id}  "
                f"project={slug}  "
                f"age={age_str}  "
                f"path={entry.run_root}",
                file=sys.stdout,
            )

    if dry_run:
        print(file=sys.stdout)
        print("Dry run — no runs were deleted.", file=sys.stdout)
        print("Re-run with --apply to delete the listed runs.", file=sys.stdout)
        return 0

    # Apply mode: actually delete run directories.
    deleted = 0
    errors = 0
    for entry in selection.deletion_candidates:
        try:
            shutil.rmtree(entry.run_root)
            deleted += 1
        except Exception as exc:
            print(f"  error deleting {entry.run_id}: {exc}", file=sys.stderr)
            errors += 1

    print(file=sys.stdout)
    print(f"deleted {deleted} run(s).", file=sys.stdout)
    if errors:
        print(f"{errors} error(s) encountered; see stderr.", file=sys.stdout)
        return 2
    return 0


__all__ = [
    "RunGcEntry",
    "RunGcSelection",
    "cmd_runs_gc",
    "select_runs_for_gc",
]
