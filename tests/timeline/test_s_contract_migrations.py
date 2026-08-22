"""S-owned SQL migrations surface contract (exec-sqlite S3).

The timeline pack's SQL migrations are authored in the sibling schema repo
(ArtAgents/packages/timeline-schema/sql), checksummed there (sql/CHECKSUMS,
exact-byte SHA-256), and vendored here verbatim. This file locks:

  * the vendored bytes to the S CHECKSUMS manifest entry;
  * the S manifest filenames to the vendored migration set;
  * the schema-pack.yaml descriptor (version/name/path/tables) to the file;
  * the application semantics: fresh databases apply timeline/2 exactly once,
    reopen is a no-op, a tampered COPY of the vendored file is rejected with
    ``MigrationChecksumDriftError`` without mutating the database, and the
    canary table exists and is usable afterwards.

The sibling-path pattern mirrors
``ArtAgents/packages/timeline-schema/tests/test_contract_v2.py``
(``DesertSliceReplayTest``): the schema checkout may be absent, in which
case the byte-consistency checks skip and the A-local application proofs
still run.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from astrid.core.migrations.runner import (
    MigrationChecksumDriftError,
    pack_resource_root,
    probe_database,
    read_schema_migrations,
    sha256_bytes,
)
from astrid.core.store.database import open_database
from astrid.packs import build_standard_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
# Sibling layout: repos/Astrid/tests/timeline and repos/ArtAgents.
S_REPO = Path(__file__).resolve().parents[3] / "ArtAgents"
S_MIGRATIONS_DIR = S_REPO / "packages" / "timeline-schema" / "sql"
S_MIGRATION = S_MIGRATIONS_DIR / "0002_add_history_kind_index.sql"
S_CHECKSUMS = S_MIGRATIONS_DIR / "CHECKSUMS"

VENDORED = (
    REPO_ROOT
    / "astrid"
    / "packs"
    / "timeline"
    / "migrations"
    / "0002_add_history_kind_index.sql"
)


def _s_checksums() -> dict[str, str]:
    """Parse ``sha256=<hex>  <filename>`` lines from the S manifest."""
    result: dict[str, str] = {}
    for line in S_CHECKSUMS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        prefix, separator, name = stripped.partition("  ")
        assert separator and prefix.startswith("sha256="), f"malformed line: {stripped!r}"
        result[name] = prefix[len("sha256="):]
    return result


# ---------------------------------------------------------------------------
# Byte-consistency with the S schema repo (skips without the checkout)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not S_MIGRATION.is_file(),
    reason="ArtAgents schema checkout not present (sibling of Astrid)",
)
class TestSContractConsistency:
    def test_vendored_bytes_match_s_checksums_entry(self) -> None:
        expected = _s_checksums()
        assert VENDORED.name in expected, (
            "S CHECKSUMS has no entry for the vendored migration"
        )
        assert sha256_bytes(VENDORED.read_bytes()) == expected[VENDORED.name]

    def test_s_manifest_filenames_equal_vendored_set(self) -> None:
        # Every S-authored migration (S CHECKSUMS) must be vendored, and the
        # schema-pack.yaml migration descriptors must name exactly the
        # vendored files (0001 is A-authored; S CHECKSUMS covers only the
        # S-owned surface).
        registry = build_standard_registry()
        declared = {
            Path(m.path).name
            for m in registry.migrations
            if m.pack == "timeline"
        }
        vendored = {
            path.name
            for path in (REPO_ROOT / "astrid" / "packs" / "timeline" / "migrations").glob("*.sql")
        }
        assert declared == vendored
        assert set(_s_checksums()) <= vendored

    def test_schema_pack_descriptor_matches_vendored_migration(self) -> None:
        registry = build_standard_registry()
        migration = registry.migration("timeline", 2)
        assert migration is not None, "timeline/2 is not registered"
        assert migration.name == "add_history_kind_index"
        assert migration.path == "migrations/0002_add_history_kind_index.sql"
        assert migration.tables == ("timeline_contract_canary",)
        # The descriptor path must resolve to the vendored bytes.
        assert (pack_resource_root("timeline") / migration.path).resolve() == VENDORED.resolve()
        assert registry.tables["timeline_contract_canary"] == "timeline"


# ---------------------------------------------------------------------------
# Application proofs (A-local, no S checkout required)
# ---------------------------------------------------------------------------


def test_fresh_database_applies_timeline_v2_once(tmp_path) -> None:
    registry = build_standard_registry()
    path = tmp_path / "astrid.sqlite3"
    conn = open_database(path, registry)
    try:
        rows = conn.execute(
            "SELECT pack, version, name, checksum FROM schema_migrations"
            " WHERE pack = 'timeline' ORDER BY version"
        ).fetchall()
    finally:
        conn.close()
    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("timeline", 1, "initial"),
        ("timeline", 2, "add_history_kind_index"),
    ]
    assert len(rows[1][3]) == 64
    assert set(rows[1][3]) <= set("0123456789abcdef")


def test_second_open_is_a_noop(tmp_path) -> None:
    registry = build_standard_registry()
    path = tmp_path / "astrid.sqlite3"
    conn = open_database(path, registry)
    first = read_schema_migrations(conn)
    conn.close()

    # Reopening a migrated database must not raise and must add no rows.
    reopened = open_database(path, registry)
    try:
        second = read_schema_migrations(reopened)
    finally:
        reopened.close()
    assert [(r.pack, r.version, r.name, r.checksum) for r in second] == [
        (r.pack, r.version, r.name, r.checksum) for r in first
    ]
    assert len(second) == len(first)


def _database_bytes(path: Path) -> tuple[bytes, dict[str, bytes]]:
    """Return ``(main database bytes, pre-existing sidecar bytes)``."""
    main = path.read_bytes() if path.exists() else b""
    sidecars: dict[str, bytes] = {}
    for candidate in (Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.exists():
            sidecars[candidate.name] = candidate.read_bytes()
    return main, sidecars


def _assert_database_unchanged(path: Path, before: tuple[bytes, dict[str, bytes]]) -> None:
    """Assert the database content file and pre-existing sidecars are identical.

    A ``-shm`` WAL index is volatile by design (any open may update reader
    markers) and is not database content; a pre-existing ``-wal`` is compared
    byte-for-byte.
    """
    after_main, after_sidecars = _database_bytes(path)
    assert after_main == before[0]
    for name, content in before[1].items():
        if name.endswith("-shm"):
            assert name in after_sidecars, name
            continue
        assert after_sidecars[name] == content, name


def test_tampered_vendored_copy_raises_checksum_drift_without_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    registry = build_standard_registry()
    path = tmp_path / "astrid.sqlite3"
    conn = open_database(path, registry)
    conn.close()

    # Tamper a COPY of the vendored file in a temp pack root. The runner
    # resolves migration paths through pack_resource_root, so point only the
    # timeline pack at the tampered copy.
    temp_pack = tmp_path / "packs" / "timeline"
    shutil.copytree(REPO_ROOT / "astrid" / "packs" / "timeline", temp_pack)
    tampered = temp_pack / "migrations" / "0002_add_history_kind_index.sql"
    tampered.write_text(
        tampered.read_text(encoding="utf-8") + "\n-- tampered copy\n",
        encoding="utf-8",
    )
    real_root = pack_resource_root("timeline")

    def _tampered_root(pack_id: str) -> Path:
        if pack_id == "timeline":
            return temp_pack
        return pack_resource_root(pack_id)

    monkeypatch.setattr(
        "astrid.core.migrations.runner.pack_resource_root", _tampered_root
    )
    assert real_root != temp_pack  # the copy really is a separate tree

    before = _database_bytes(path)
    with pytest.raises(MigrationChecksumDriftError) as excinfo:
        open_database(path, registry)
    assert "checksum drift" in str(excinfo.value)
    assert "timeline/2" in str(excinfo.value)
    _assert_database_unchanged(path, before)

    # The probe itself is the nonmutating gate; it raises before any write.
    before_probe = _database_bytes(path)
    with pytest.raises(MigrationChecksumDriftError):
        probe_database(path, registry)
    _assert_database_unchanged(path, before_probe)


def test_canary_table_exists_and_is_usable_after_migration(tmp_path) -> None:
    registry = build_standard_registry()
    path = tmp_path / "astrid.sqlite3"
    conn = open_database(path, registry)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = 'table' AND name = 'timeline_contract_canary'"
        ).fetchone()
        assert row is not None
        conn.execute(
            "INSERT INTO timeline_contract_canary (id, note, created_at)"
            " VALUES (1, 'canary', '2026-01-01T00:00:00+00:00')"
        )
        note = conn.execute(
            "SELECT note FROM timeline_contract_canary WHERE id = 1"
        ).fetchone()[0]
        assert note == "canary"
        # The CHECK constraint is live.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO timeline_contract_canary (id, note, created_at)"
                " VALUES (0, 'x', 'y')"
            )
    finally:
        conn.close()
