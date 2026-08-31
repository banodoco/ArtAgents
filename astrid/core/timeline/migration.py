"""Read-only inspection helpers for local timeline migrations.

Migration tooling is deliberately offline.  This module never discovers a
remote timeline, resolves credentials, or imports a provider transport.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

TimelineClassification = Literal[
    "already_event_sourced",
    "legacy_local",
    "malformed_incomplete",
]


@dataclass(frozen=True)
class SkippedTimeline:
    project_slug: str
    timeline_ulid: str | None
    reason: str
    classification: TimelineClassification


@dataclass(frozen=True)
class ParityFailure:
    project_slug: str
    timeline_ulid: str
    source_hash: str
    projected_hash: str
    detail: str = ""


@dataclass(frozen=True)
class ResumableStatus:
    last_completed_project: str | None = None
    last_completed_timeline_ulid: str | None = None
    imported_count: int = 0
    skipped_count: int = 0


@dataclass(frozen=True)
class MigrationResult:
    imported: list[str] = field(default_factory=list)
    skipped: list[SkippedTimeline] = field(default_factory=list)
    parity_failures: list[ParityFailure] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)
    resumable: ResumableStatus = field(default_factory=ResumableStatus)
    started_at: str = ""
    finished_at: str = ""

    @property
    def ok(self) -> bool:
        return not self.parity_failures and not self.malformed


def discover_projects_for_migration(*, root: str | Path | None = None) -> list[str]:
    """Return local project slugs ordered by directory modification time."""
    from astrid.core.foundation.project_paths import resolve_projects_root

    projects_root = resolve_projects_root(root)
    if not projects_root.exists():
        return []
    candidates = [
        (entry.stat().st_mtime, entry.name)
        for entry in projects_root.iterdir()
        if entry.is_dir() and (entry / "project.json").is_file()
    ]
    return [name for _, name in sorted(candidates, reverse=True)]


def discover_timelines_for_project(
    project_slug: str, *, root: str | Path | None = None
) -> list[tuple[str, TimelineClassification]]:
    """List local timeline directories and their on-disk classification."""
    from astrid.core.foundation.project_paths import resolve_projects_root, validate_project_slug
    from astrid.core.ids import is_ulid

    slug = validate_project_slug(project_slug)
    timelines_dir = resolve_projects_root(root) / slug / "timelines"
    if not timelines_dir.is_dir():
        return []
    return [
        (entry.name, classify_timeline_dir(entry))
        for entry in sorted(timelines_dir.iterdir())
        if entry.is_dir() and is_ulid(entry.name)
    ]


def classify_timeline_dir(timeline_home: Path) -> TimelineClassification:
    """Classify a timeline without mutating it."""
    from astrid.core._shared.jsonio import read_json

    events_path = timeline_home / "assembly.jsonl"
    identity_path = timeline_home / "assembly.identity.json"
    assembly_path = timeline_home / "assembly.json"
    if events_path.is_file() and identity_path.is_file():
        try:
            identity = read_json(identity_path)
            if isinstance(identity, dict) and isinstance(identity.get("timeline_id"), str):
                return "already_event_sourced"
        except Exception:
            pass
    if assembly_path.is_file() and not events_path.is_file():
        try:
            if isinstance(read_json(assembly_path), dict):
                return "legacy_local"
        except Exception:
            pass
    return "malformed_incomplete"


def checkpoint_path_for_run(
    project_slug: str,
    *,
    root: str | Path | None = None,
    run_ts: str | None = None,
) -> Path:
    from astrid.core.foundation.project_paths import project_dir, validate_project_slug

    slug = validate_project_slug(project_slug)
    timestamp = run_ts if run_ts is not None else str(int(time.time()))
    return project_dir(slug, root=root) / "runs" / "migrations" / timestamp / "checkpoint.json"


def write_resumable_checkpoint(status: ResumableStatus, checkpoint_file: Path) -> None:
    from astrid.core._shared.jsonio import write_json_atomic

    write_json_atomic(
        checkpoint_file,
        {
            "last_completed_project": status.last_completed_project,
            "last_completed_timeline_ulid": status.last_completed_timeline_ulid,
            "imported_count": status.imported_count,
            "skipped_count": status.skipped_count,
        },
    )


def read_resumable_checkpoint(checkpoint_file: Path) -> ResumableStatus | None:
    from astrid.core._shared.jsonio import read_json

    if not checkpoint_file.is_file():
        return None
    try:
        data = read_json(checkpoint_file)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return ResumableStatus(
        last_completed_project=data.get("last_completed_project"),
        last_completed_timeline_ulid=data.get("last_completed_timeline_ulid"),
        imported_count=data.get("imported_count", 0),
        skipped_count=data.get("skipped_count", 0),
    )


__all__ = [
    "MigrationResult",
    "SkippedTimeline",
    "ParityFailure",
    "ResumableStatus",
    "TimelineClassification",
    "classify_timeline_dir",
    "discover_projects_for_migration",
    "discover_timelines_for_project",
    "checkpoint_path_for_run",
    "write_resumable_checkpoint",
    "read_resumable_checkpoint",
]
