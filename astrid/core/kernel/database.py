"""Canonical-versus-legacy kernel database authority resolution.

The v10 application owns ``<projects_root>/.astrid/astrid.sqlite3``. Older
entrypoints may still leave a separate ``kernel.sqlite3`` ledger behind.
Readers must never select that legacy ledger merely because it appears first
on disk: canonical wins whenever it exists, while legacy fallback remains
available only for roots that have not yet acquired the canonical store.

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
    """Resolve the sole read authority without mutating either ledger.

    Precedence is deliberately asymmetric:

    1. canonical ``.astrid/astrid.sqlite3`` whenever it exists;
    2. the first existing historical layout only when canonical is absent;
    3. canonical path as the not-yet-created default when no database exists.

    Existing legacy paths are always reported so doctor can make coexistence
    visible while normal readers continue deterministically on canonical.
    """

    root = Path(projects_root)
    canonical = root / ".astrid" / "astrid.sqlite3"
    legacy_candidates = (
        root / "kernel.sqlite3",
        root / ".astrid" / "kernel.sqlite3",
        root / "astrid.sqlite3",
    )
    existing_legacy = tuple(path for path in legacy_candidates if path.is_file())
    if canonical.is_file():
        return KernelDatabaseAuthority(
            projects_root=root,
            canonical_path=canonical,
            selected_path=canonical,
            mode="canonical",
            existing_legacy_paths=existing_legacy,
        )
    if existing_legacy:
        return KernelDatabaseAuthority(
            projects_root=root,
            canonical_path=canonical,
            selected_path=existing_legacy[0],
            mode="legacy",
            existing_legacy_paths=existing_legacy,
        )
    return KernelDatabaseAuthority(
        projects_root=root,
        canonical_path=canonical,
        selected_path=canonical,
        mode="missing",
        existing_legacy_paths=(),
    )


def resolve_kernel_database_path(projects_root: str | Path) -> Path:
    """Return the selected read path under the frozen authority policy."""

    return resolve_kernel_database_authority(projects_root).selected_path


__all__ = [
    "KernelDatabaseAuthority",
    "resolve_kernel_database_authority",
    "resolve_kernel_database_path",
]
