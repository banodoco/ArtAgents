"""Focused B3 tests for canonical database projection.

These tests copy the converted database-bearing packs into an isolated catalog
root.  The reserved kernel is projected from code; no legacy schema manifest is
used by the canonical path.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from astrid.core.migrations.runner import (
    MigrationApplyError,
    MigrationChecksumDriftError,
    MigrationNameDriftError,
    MigrationTooNewError,
    probe_database,
    read_schema_migrations,
    topological_migration_order,
)
from astrid.core.pack.canonical import (
    BundledCatalog,
    CanonicalPackValidationError,
    project_catalog_database,
)
from astrid.core.store.database import open_database

ROOT = Path(__file__).resolve().parents[2]
PACKS_ROOT = ROOT / "astrid" / "packs"
DATABASE_PACKS = ("timeline", "shots", "references", "runaway")
EXPECTED_TABLES = {
    "core": {
        "schema_migrations",
        "projects",
        "event_streams",
        "events",
        "command_receipts",
        "runs",
        "evidence_items",
        "tasks",
        "task_dependencies",
        "execution_attempts",
        "task_outputs",
        "media",
        "media_locations",
        "media_relations",
    },
    "timeline": {"timelines"},
    "shots": {"shots", "shot_items"},
    "references": {"project_references", "media_references", "reference_links"},
    "runaway": {"runaway_transitions"},
}


def _catalog_root(tmp_path: Path) -> Path:
    root = tmp_path / "packs"
    root.mkdir(parents=True)
    for pack_id in DATABASE_PACKS:
        shutil.copytree(
            PACKS_ROOT / pack_id,
            root / pack_id,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    return root


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in rows}
def test_default_and_explicit_runaway_use_one_projection(tmp_path: Path) -> None:
    catalog = BundledCatalog.from_root(_catalog_root(tmp_path))

    default = project_catalog_database(catalog)
    explicit = project_catalog_database(catalog, additional_pack_ids=("runaway",))

    assert default.canonical_projection is True
    assert tuple(default.packs) == ("core", "references", "shots", "timeline")
    assert tuple(explicit.packs) == (
        "core",
        "references",
        "runaway",
        "shots",
        "timeline",
    )
    assert default.pack("core").source_path is None
    assert default.pack("timeline").default_enabled is True
    assert explicit.pack("runaway").default_enabled is False
    assert [migration.pack for migration in topological_migration_order(default)] == [
        "core",
        "references",
        "shots",
        "timeline",
    ]
    assert all(migration.resource is not None for migration in explicit.migrations)
    assert all(
        migration.resource.resolved.is_relative_to(migration.resource.root)
        for migration in explicit.migrations
    )

def test_fresh_schema_has_exact_declared_table_ownership(tmp_path: Path) -> None:
    catalog = BundledCatalog.from_root(_catalog_root(tmp_path))
    registry = project_catalog_database(catalog, ("runaway",))
    connection = open_database(tmp_path / "fresh.sqlite3", registry)
    try:
        tables = _table_names(connection)
        assert tables == set().union(*EXPECTED_TABLES.values())
        for pack_id, owned in EXPECTED_TABLES.items():
            assert {table for table, owner in registry.tables.items() if owner == pack_id} == owned
        assert len(read_schema_migrations(connection)) == len(registry.migrations)
    finally:
        connection.close()
def test_existing_reopen_and_read_only_pending_do_not_apply_extra_migrations(
    tmp_path: Path,
) -> None:
    catalog = BundledCatalog.from_root(_catalog_root(tmp_path))
    default = project_catalog_database(catalog)
    extended = project_catalog_database(catalog, ("runaway",))
    database = tmp_path / "existing.sqlite3"

    connection = open_database(database, default)
    connection.close()
    before = database.read_bytes()

    read_only = open_database(database, extended, read_only=True)
    baseline = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        assert "runaway_transitions" not in _table_names(read_only)
        assert read_schema_migrations(read_only) == read_schema_migrations(baseline)
    finally:
        read_only.close()
        baseline.close()
    assert database.read_bytes() == before


def test_canonical_migrations_never_rediscover_pack_roots(tmp_path: Path, monkeypatch) -> None:
    from astrid.core.migrations import runner

    catalog = BundledCatalog.from_root(_catalog_root(tmp_path))
    registry = project_catalog_database(catalog, ("runaway",))
    monkeypatch.setattr(
        runner,
        "pack_resource_root",
        lambda _pack_id: (_ for _ in ()).throw(AssertionError("legacy root lookup")),
    )
    assert all(runner.read_migration_bytes(migration) for migration in registry.migrations)



def test_catalog_enforces_dependency_heads_and_cycles(tmp_path: Path) -> None:
    root = _catalog_root(tmp_path)
    timeline_manifest = root / "timeline" / "pack.yaml"
    timeline_manifest.write_text(
        timeline_manifest.read_text(encoding="utf-8").replace(
            "min_migration: 1", "min_migration: 2", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(CanonicalPackValidationError, match="requires 2"):
        BundledCatalog.from_root(root)

    root = _catalog_root(tmp_path / "cycle")
    timeline_manifest = root / "timeline" / "pack.yaml"
    shots_manifest = root / "shots" / "pack.yaml"
    timeline_manifest.write_text(
        timeline_manifest.read_text(encoding="utf-8").replace(
            "pack: core", "pack: shots", 1
        ),
        encoding="utf-8",
    )
    shots_manifest.write_text(
        shots_manifest.read_text(encoding="utf-8").replace(
            "pack: core", "pack: timeline", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(CanonicalPackValidationError, match="cycle"):
        BundledCatalog.from_root(root)

def test_canonical_resource_bytes_drive_checksum_drift(tmp_path: Path) -> None:
    catalog_root = _catalog_root(tmp_path)
    catalog = BundledCatalog.from_root(catalog_root)
    registry = project_catalog_database(catalog)
    database = tmp_path / "drift.sqlite3"
    connection = open_database(database, registry)
    connection.close()

    migration_path = catalog.get("timeline").root / "migrations" / "0001_initial.sql"
    migration_path.write_bytes(migration_path.read_bytes() + b"\n")
    with pytest.raises(MigrationChecksumDriftError):
        probe_database(database, registry)


def test_projection_rejects_reserved_core_and_unknown_selection(tmp_path: Path) -> None:
    catalog = BundledCatalog.from_root(_catalog_root(tmp_path))
    with pytest.raises(CanonicalPackValidationError, match="reserved"):
        project_catalog_database(catalog, ("core",))
    with pytest.raises(CanonicalPackValidationError, match="unknown"):
        project_catalog_database(catalog, ("missing",))


def test_canonical_drift_and_too_new_probes_are_read_only(tmp_path: Path) -> None:
    catalog = BundledCatalog.from_root(_catalog_root(tmp_path))
    registry = project_catalog_database(catalog)
    database = tmp_path / "drift.sqlite3"
    connection = open_database(database, registry)
    connection.close()

    raw = sqlite3.connect(str(database), isolation_level=None)
    try:
        raw.execute(
            "UPDATE schema_migrations SET name = ? "
            "WHERE pack = 'timeline' AND version = 1",
            ("renamed",),
        )
    finally:
        raw.close()
    with pytest.raises(MigrationNameDriftError):
        probe_database(database, registry)

    raw = sqlite3.connect(str(database), isolation_level=None)
    try:
        raw.execute(
            "UPDATE schema_migrations SET name = ?, version = ? "
            "WHERE pack = 'timeline' AND version = 1",
            ("initial", 2),
        )
    finally:
        raw.close()
    with pytest.raises(MigrationTooNewError):
        probe_database(database, registry)


def test_canonical_migration_failure_rolls_back_its_transaction(tmp_path: Path) -> None:
    root = _catalog_root(tmp_path)
    timeline_sql = root / "timeline" / "migrations" / "0001_initial.sql"
    timeline_sql.write_bytes(
        timeline_sql.read_bytes()
        + b"\nCREATE TABLE should_rollback (id INTEGER PRIMARY KEY);\n"
        + b"THIS IS NOT VALID SQL;\n"
    )
    catalog = BundledCatalog.from_root(root)
    registry = project_catalog_database(catalog)
    database = tmp_path / "rollback.sqlite3"

    with pytest.raises(MigrationApplyError):
        open_database(database, registry)

    connection = sqlite3.connect(str(database), isolation_level=None)
    try:
        assert "timelines" not in _table_names(connection)
        assert "should_rollback" not in _table_names(connection)
        assert {
            row[0] for row in connection.execute(
                "SELECT pack FROM schema_migrations"
            )
        } == {"core", "references", "shots"}
    finally:
        connection.close()
