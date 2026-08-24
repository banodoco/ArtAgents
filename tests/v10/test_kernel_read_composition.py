"""Kernel read helpers open the full standard project composition."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.kernel.read import kernel_run_info, kernel_runs_for_project
from astrid.core.migrations.runner import MigrationTooNewError
from astrid.core.store.database import open_database
from astrid.core.store.writer import DatabaseWriter


def test_kernel_reads_accept_standard_pack_migrations(
    tmp_path: Path,
    standard_database,
) -> None:
    """A project DB with references/shots migrations remains readable.

    The reader used to open this database with ``core_only_registry`` and
    raised ``MigrationTooNewError`` once a pack-backed command had run.  The
    default reader composition must include all shipped schema packs while
    still using the normal migration validation boundary.
    """

    _connection, _database = standard_database
    # ``standard_database`` is at ``tmp_path/astrid.sqlite3``, one of the
    # canonical reader locations.  The calls must complete without the
    # ``MigrationTooNewError`` raised by the old core-only composition.
    assert kernel_runs_for_project("missing", projects_root=tmp_path) == []
    assert kernel_run_info("missing", "run-missing", projects_root=tmp_path) is None

    # An explicitly supplied incomplete composition still fails closed; the
    # fix does not weaken too-new/unregistered migration protection.
    with pytest.raises(MigrationTooNewError):
        kernel_runs_for_project(
            "missing",
            projects_root=tmp_path,
            registry=core_only_registry(),
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
    assert kernel_runs_for_project("missing", projects_root=tmp_path) == []
