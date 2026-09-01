"""Canonical kernel database authority resolution.

The v10 application owns ``<projects_root>/.astrid/astrid.sqlite3``. Older
entrypoints may leave separate historical ledgers behind, but those paths are
diagnostic evidence only and are never selected for reads or writes.

This module resolves paths only. It never opens, creates, migrates, renames,
or deletes a database, making it safe for doctor and read-only consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class KernelDatabaseAuthority:
    """One resolved database authority and its coexistence evidence."""

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
    """Resolve the canonical read authority without mutating any ledger.

    The canonical ``.astrid/astrid.sqlite3`` path is always authoritative,
    whether it exists yet or not. Existing historical paths are reported so
    doctor can make stale files visible, but they never become an active
    fallback.
    """

    root = Path(projects_root)
    canonical = root / ".astrid" / "astrid.sqlite3"
    legacy_candidates = (
        root / "kernel.sqlite3",
        root / ".astrid" / "kernel.sqlite3",
        root / "astrid.sqlite3",
    )
    existing_legacy = tuple(path for path in legacy_candidates if path.is_file())
    return KernelDatabaseAuthority(
        projects_root=root,
        canonical_path=canonical,
        selected_path=canonical,
        mode="canonical" if canonical.is_file() else "missing",
        existing_legacy_paths=existing_legacy,
    )


def resolve_kernel_database_path(projects_root: str | Path) -> Path:
    """Return the selected read path under the frozen authority policy."""

    return resolve_kernel_database_authority(projects_root).selected_path


__all__ = [
    "KernelDatabaseAuthority",
    "resolve_kernel_database_authority",
    "resolve_kernel_database_path",
]
