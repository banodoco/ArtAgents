"""Kernel read helpers open the canonical project database composition."""
from __future__ import annotations

from pathlib import Path

import sqlite3
import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.kernel.read import kernel_run_info, kernel_runs_for_project
from astrid.core.migrations.runner import MigrationError, MigrationTooNewError
from astrid.core.store.database import open_database
from astrid.core.store.writer import DatabaseWriter


def test_kernel_reads_accept_standard_pack_migrations(
    tmp_path: Path,
    standard_registry,
) -> None:
    """Canonical reads accept bundled migrations and reject too-new state."""
    canonical = tmp_path / ".astrid" / "astrid.sqlite3"
    canonical.parent.mkdir()
    connection = open_database(canonical, standard_registry)
    connection.close()

    # The canonical authority contains the complete bundled projection, so
    # standard kernel reads do not mistake a missing legacy path for success.
    assert kernel_runs_for_project(
        "missing", projects_root=tmp_path, registry=standard_registry
    ) == []
    assert (
        kernel_run_info(
            "missing", "run-missing", projects_root=tmp_path, registry=standard_registry
        )
        is None
    )

    # Add an applied migration that no composed registry knows.  The explicit
    # incomplete composition must preserve the too-new migration boundary.
    with sqlite3.connect(str(canonical), isolation_level=None) as raw:
        raw.execute(
            "INSERT INTO schema_migrations "
            "(pack, version, name, checksum, applied_at) "
            "VALUES ('future', 1, 'initial', ?, '2026-01-01T00:00:00+00:00')",
            ("0" * 64,),
        )
    with pytest.raises(MigrationTooNewError):
        kernel_runs_for_project(
            "missing",
            projects_root=tmp_path,
            registry=core_only_registry(),
        )


def test_kernel_reads_reject_incomplete_migration_state(
    tmp_path: Path,
    standard_registry,
) -> None:
    database = tmp_path / ".astrid" / "astrid.sqlite3"
    database.parent.mkdir()
    connection = open_database(database, core_only_registry())
    connection.close()

    with pytest.raises(MigrationError, match="incomplete migration state"):
        kernel_runs_for_project(
            "missing",
            projects_root=tmp_path,
            registry=standard_registry,
        )


def test_kernel_reads_prefer_canonical_store_over_legacy_shim(
    tmp_path: Path,
    standard_registry,
) -> None:
    canonical = tmp_path / ".astrid" / "astrid.sqlite3"
    canonical.parent.mkdir()
    connection = open_database(canonical, standard_registry)
    connection.close()
    legacy = DatabaseWriter(tmp_path / "kernel.sqlite3", core_only_registry())
    legacy.close()

    # Both files exist; the canonical standard DB must win over the legacy
    # core-only shim rather than silently consulting the wrong ledger.
    assert (
        kernel_runs_for_project(
            "missing", projects_root=tmp_path, registry=standard_registry
        )
        == []
    )
