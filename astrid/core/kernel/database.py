"""Resolve the single canonical Astrid database authority.

This module resolves paths only. It never opens, creates, migrates, renames,
or deletes a database, making it safe for doctor and read-only consumers.
There is deliberately no historical-path fallback: every caller must use the
managed store derived from the projects root.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from astrid.core.foundation.project_paths import derive_database_path


@dataclass(frozen=True, slots=True)
class KernelDatabaseAuthority:
    """One resolved canonical database authority.

    ``existing_legacy_paths`` remains as an empty compatibility field for
    doctor/reporting callers. It is not populated or inspected by authority
    resolution, so an old file can never become a second database authority.
    """

    projects_root: Path
    canonical_path: Path
    selected_path: Path
    mode: str
    existing_legacy_paths: tuple[Path, ...]

    @property
    def exists(self) -> bool:
        return self.selected_path.is_file()

    @property
    def coexists(self) -> bool:
        return self.canonical_path.is_file() and bool(self.existing_legacy_paths)


def resolve_kernel_database_authority(
    projects_root: str | Path,
) -> KernelDatabaseAuthority:
    """Resolve the sole read authority without mutating the store."""

    root = Path(projects_root).expanduser().resolve()
    canonical = derive_database_path(root)
    return KernelDatabaseAuthority(
        projects_root=root,
        canonical_path=canonical,
        selected_path=canonical,
        mode="canonical" if canonical.is_file() else "missing",
        existing_legacy_paths=(),
    )


def resolve_kernel_database_path(projects_root: str | Path) -> Path:
    """Return the canonical read path for a projects root."""

    return derive_database_path(Path(projects_root).expanduser().resolve())


__all__ = [
    "KernelDatabaseAuthority",
    "resolve_kernel_database_authority",
    "resolve_kernel_database_path",
]
