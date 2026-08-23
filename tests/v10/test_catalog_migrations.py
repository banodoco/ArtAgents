"""Catalog tests: manifest-derived catalogs match their executed SQL.

(m1 plan steps 3 and 4.) These tests execute the registered migrations into
fresh on-disk databases and compare **six schema sources** against one
another:

1. ``sqlite_master`` table SQL (columns, DDL text, pack-aware
   ``schema_migrations``);
2. ``PRAGMA foreign_key_list`` (FK targets and delete actions);
3. CHECK constraints transcribed from the normative v10 DDL;
4. named indexes and partial-index WHERE clauses;
5. ownership (every table's owning pack, derived from the composed registry);
6. forbidden vocabulary (v10 "no dormant platform" tables must be absent).

Counts are always derived from manifests and the catalog declaration:
the valid kernel is ``len(CORE_TABLES)`` (14) and the standard composition
is that kernel plus the packs' declared owned tables (1 timeline + 2 shots +
3 references). ``20`` is an observation of that derivation, never a universal
kernel constant, so a core-only database must never claim it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from astrid.core.events.registry import CORE_PACK_ID
from astrid.core.migrations.catalog import (
    CORE_INDEXES,
    CORE_TABLES,
    FORBIDDEN_TABLES,
    KERNEL_MEDIA_TABLES,
    OPEN_STREAM_TYPE,
    PARTIAL_INDEXES,
)
from astrid.core.migrations.runner import (
    MigrationChecksumDriftError,
    MigrationCycleError,
    MigrationError,
    MigrationNameDriftError,
    MigrationTooNewError,
    probe_database,
    read_migration_bytes,
    read_schema_migrations,
    sha256_bytes,
    topological_migration_order,
)
from astrid.core.schema_packs.manifest import parse_schema_pack_manifest
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
    SchemaPackRegistry,
)
from astrid.core.store.database import inspect_connection_pragmas, open_database

# ---------------------------------------------------------------------------
# sqlite_master / PRAGMA inspection helpers
# ---------------------------------------------------------------------------


def _table_names(conn: sqlite3.Connection) -> set[str]:
    """Return every real table name (excluding sqlite_* internals)."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master"
        " WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    """Return the stored CREATE TABLE SQL text for ``table``."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    assert row is not None, f"table {table!r} missing from sqlite_master"
    return row[0]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return column names in declared order via ``PRAGMA table_info``."""
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _named_indexes(conn: sqlite3.Connection) -> dict[str, str]:
    """Return ``name -> sql`` for every non-auto index."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master"
        " WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex_%'"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _index_columns(conn: sqlite3.Connection, index: str) -> list[str]:
    """Return indexed column names in order via ``PRAGMA index_info``."""
    return [row[2] for row in conn.execute(f"PRAGMA index_info({index})").fetchall()]


def _foreign_keys(conn: sqlite3.Connection, table: str) -> dict[int, dict]:
    """Return ``fk_id -> {table, on_delete, cols}`` via ``PRAGMA foreign_key_list``.

    A NULL ``to`` column means the referenced table's primary key; it is
    normalized to ``"id"`` so assertions read naturally. SQLite numbers FK
    ids in parse order, so callers must look rows up by column, never by id.
    """
    result: dict[int, dict] = {}
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    for fk_id, _seq, ref_table, from_col, to_col, on_update, on_delete, _match in rows:
        entry = result.setdefault(
            fk_id,
            {
                "table": ref_table,
                "on_update": on_update,
                "on_delete": on_delete,
                "cols": [],
            },
        )
        entry["cols"].append((from_col, to_col or "id"))
    return result


def _fk_by_column(
    conn: sqlite3.Connection, table: str, from_column: str
) -> dict:
    """Return the FK of ``table`` whose ``from`` column is ``from_column``."""
    for fk in _foreign_keys(conn, table).values():
        if any(from_col == from_column for from_col, _ in fk["cols"]):
            return fk
    raise AssertionError(
        f"table {table!r} has no foreign key from column {from_column!r}"
    )


# ---------------------------------------------------------------------------
# Section 1: the valid 14-table kernel (core-only composition)
# ---------------------------------------------------------------------------


def test_core_only_database_contains_exactly_the_declared_kernel_tables(
    core_database,
) -> None:
    conn, _ = core_database
    # Derived from the catalog declaration, not from a hardcoded count.
    assert len(CORE_TABLES) == 14
    assert _table_names(conn) == set(CORE_TABLES)
    assert len(_table_names(conn)) == len(CORE_TABLES)


def test_core_only_database_never_claims_the_standard_count(core_database) -> None:
    conn, _ = core_database
    # 20 is a property of the *standard* composition; a kernel-only database
    # must never be described by it.
    assert len(_table_names(conn)) != 20
    assert len(_table_names(conn)) == len(CORE_TABLES)


def test_schema_migrations_sql_is_pack_aware(core_database) -> None:
    conn, _ = core_database
    sql = _table_sql(conn, "schema_migrations")
    assert "pack" in sql and "TEXT NOT NULL DEFAULT 'core'" in sql
    assert "PRIMARY KEY (pack, version)" in sql
    assert "UNIQUE (pack, name)" in sql
    assert "checksum" in sql and "applied_at" in sql


def test_events_table_has_no_hash_columns_and_opens_stream_type(core_database) -> None:
    conn, _ = core_database
    columns = _columns(conn, "events")
    assert "previous_event_hash" not in columns
    assert "event_hash" not in columns
    sql = _table_sql(conn, "events")
    assert "event_hash" not in sql
    # stream_type is OPEN: no DDL CHECK constrains it (registry-enforced).
    assert OPEN_STREAM_TYPE is True
    stream_declaration = _table_sql(conn, "event_streams").split(
        "stream_type", 1
    )[1].split(",", 1)[0]
    assert "CHECK" not in stream_declaration.upper()


def test_events_table_declares_the_normative_columns(core_database) -> None:
    conn, _ = core_database
    assert _columns(conn, "events") == [
        "event_id",
        "project_id",
        "project_seq",
        "stream_id",
        "seq",
        "subject_type",
        "subject_id",
        "changes_json",
        "kind",
        "schema_version",
        "idempotency_key",
        "txn_id",
        "actor_kind",
        "payload_json",
        "created_at",
    ]


def test_kernel_ddl_declares_the_normative_json_constraints(core_database) -> None:
    conn, _ = core_database
    assert "json_valid(settings_json)" in _table_sql(conn, "projects")
    assert "json_valid(payload_json)" in _table_sql(conn, "events")
    assert "json_type(changes_json) = 'array'" in _table_sql(conn, "events")
    assert "json_valid(result_json)" in _table_sql(conn, "command_receipts")
    assert "json_valid(metadata_json)" in _table_sql(conn, "media")


# ---------------------------------------------------------------------------
# Section 2: CHECK constraints (locked v10 vocabularies, verbatim)
# ---------------------------------------------------------------------------


def test_kernel_check_constraints_preserve_locked_vocabularies(core_database) -> None:
    conn, _ = core_database
    sql = {table: _table_sql(conn, table) for table in _table_names(conn)}

    assert "'local','system','executor'" in sql["events"]
    assert "'running','succeeded','failed','cancelled'" in sql["runs"]
    assert (
        "'queued','blocked','running','succeeded','failed','cancelled'"
        in sql["tasks"]
    )
    assert "'hard','soft'" in sql["task_dependencies"]
    assert (
        "'claimed','running','succeeded','failed','cancelled','expired'"
        in sql["execution_attempts"]
    )
    assert (
        "'image','video','audio','text','document','data','other'"
        in sql["media"]
    )
    assert "'managed_local','external_local','remote'" in sql["media_locations"]
    assert (
        "'derived_from','variant_of','uses_as_input','mask_for','audio_for'"
        in sql["media_relations"]
    )


def test_kernel_check_constraints_preserve_integrity_rules(core_database) -> None:
    conn, _ = core_database
    sql = {table: _table_sql(conn, table) for table in _table_names(conn)}

    assert "from_media_id <> to_media_id" in sql["media_relations"]
    assert "task_id <> depends_on_task_id" in sql["task_dependencies"]
    assert "role = 'result' OR is_primary = 0" in sql["task_outputs"]
    # A task is either runless (both NULL) or run-attached (both set).
    assert "run_id IS NULL AND run_ordinal IS NULL" in sql["tasks"]
    assert "run_id IS NOT NULL AND run_ordinal IS NOT NULL" in sql["tasks"]
    # Receipt sequence range sanity.
    assert "last_project_seq >= first_project_seq" in sql["command_receipts"]


# ---------------------------------------------------------------------------
# Section 3: foreign-key lists
# ---------------------------------------------------------------------------


def test_kernel_foreign_keys_match_the_normative_ddl(core_database) -> None:
    conn, _ = core_database

    events_project = _fk_by_column(conn, "events", "project_id")
    assert (events_project["table"], events_project["on_delete"]) == (
        "projects",
        "CASCADE",
    )
    assert events_project["cols"] == [("project_id", "id")]
    events_stream = _fk_by_column(conn, "events", "stream_id")
    assert (events_stream["table"], events_stream["on_delete"]) == (
        "event_streams",
        "RESTRICT",
    )
    assert events_stream["cols"] == [("stream_id", "id")]

    tasks_run = _fk_by_column(conn, "tasks", "run_id")
    # Composite FK (run_id, project_id) -> runs(id, project_id).
    assert tasks_run["table"] == "runs"
    assert tasks_run["cols"] == [("run_id", "id"), ("project_id", "project_id")]
    assert tasks_run["on_delete"] == "RESTRICT"

    task_deps = _fk_by_column(conn, "task_dependencies", "task_id")
    assert (task_deps["table"], task_deps["on_delete"]) == ("tasks", "CASCADE")
    task_deps_reverse = _fk_by_column(conn, "task_dependencies", "depends_on_task_id")
    assert (task_deps_reverse["table"], task_deps_reverse["on_delete"]) == (
        "tasks",
        "RESTRICT",
    )
    assert _fk_by_column(conn, "media_locations", "media_id")["cols"] == [
        ("media_id", "id")
    ]
    task_output = _fk_by_column(conn, "task_outputs", "task_id")
    assert (task_output["table"], task_output["on_delete"]) == ("tasks", "RESTRICT")

    evidence_run = _fk_by_column(conn, "evidence_items", "run_id")
    assert evidence_run["on_delete"] == "CASCADE"  # run_id -> runs
    evidence_task = _fk_by_column(conn, "evidence_items", "task_id")
    assert evidence_task["on_delete"] == "SET NULL"  # task_id -> tasks
    evidence_media = _fk_by_column(conn, "evidence_items", "media_id")
    assert evidence_media["on_delete"] == "SET NULL"  # media_id -> media


# ---------------------------------------------------------------------------
# Section 4: indexes (16 named kernel indexes, 5 partial)
# ---------------------------------------------------------------------------


def test_kernel_named_indexes_match_the_declaration(core_database) -> None:
    conn, _ = core_database
    # Derived from the catalog declaration (16), never a hardcoded number.
    assert len(CORE_INDEXES) == 16
    assert set(_named_indexes(conn)) == set(CORE_INDEXES)


def test_kernel_partial_indexes_carry_where_clauses(core_database) -> None:
    conn, _ = core_database
    indexes = _named_indexes(conn)
    assert len(PARTIAL_INDEXES) == 5
    for name in PARTIAL_INDEXES:
        assert name in indexes, f"partial index {name!r} missing"
        assert "WHERE" in indexes[name].upper(), f"{name!r} lost its WHERE clause"


def test_kernel_index_columns_and_order(core_database) -> None:
    conn, _ = core_database
    assert _index_columns(conn, "events_project_changes") == [
        "project_id",
        "project_seq",
    ]
    assert _index_columns(conn, "events_stream_kind_seq") == [
        "stream_id",
        "kind",
        "seq",
    ]
    assert _index_columns(conn, "task_dependencies_reverse") == [
        "depends_on_task_id",
        "task_id",
    ]
    assert _index_columns(conn, "media_relations_to") == [
        "to_media_id",
        "kind",
        "from_media_id",
    ]
    # DESC is preserved in the DDL text (priority DESC).
    assert "priority DESC" in _named_indexes(conn)["tasks_claim_order"]


# ---------------------------------------------------------------------------
# Section 5: ownership (registry-derived, never inferred from SQL)
# ---------------------------------------------------------------------------


def test_kernel_ownership_derives_from_the_registry(core_database, core_registry) -> None:
    conn, _ = core_database
    for table in _table_names(conn):
        assert core_registry.tables[table] == CORE_PACK_ID, table


def test_media_is_kernel_citizenship(core_database, core_registry) -> None:
    conn, _ = core_database
    assert KERNEL_MEDIA_TABLES == {"media", "media_locations", "media_relations"}
    for table in KERNEL_MEDIA_TABLES:
        assert table in _table_names(conn)
        assert core_registry.tables[table] == CORE_PACK_ID


# ---------------------------------------------------------------------------
# Section 6: the standard 14+1+2+3+1 composition
# ---------------------------------------------------------------------------


def test_standard_database_contains_14_plus_1_plus_2_plus_3_tables(
    standard_database,
    standard_registry,
) -> None:
    conn, _ = standard_database
    # Counts are derived from the composed registry, not from a fixed "20".
    expected = len(standard_registry.tables)
    assert expected == len(CORE_TABLES) + 1 + 2 + 3 + 1
    assert _table_names(conn) == set(standard_registry.tables)
    assert len(_table_names(conn)) == expected


def test_standard_ownership_matches_the_registry(
    standard_database,
    standard_registry,
) -> None:
    conn, _ = standard_database
    registry: FrozenSchemaPackRegistry = standard_registry
    assert registry.tables["timelines"] == "timeline"
    assert registry.tables["shots"] == "shots"
    assert registry.tables["shot_items"] == "shots"
    assert registry.tables["project_references"] == "references"
    assert registry.tables["media_references"] == "references"
    assert registry.tables["reference_links"] == "references"
    for table in _table_names(conn):
        assert registry.tables[table], f"table {table!r} has no owning pack"


def test_timelines_table_has_no_convenience_columns(standard_database) -> None:
    conn, _ = standard_database
    # SD1: identity (slug, ULID, default) is projected, never stored.
    columns = _columns(conn, "timelines")
    assert columns == [
        "id",
        "project_id",
        "event_stream_id",
        "name",
        "document_json",
        "asset_registry_json",
        "created_at",
        "updated_at",
    ]
    sql = _table_sql(conn, "timelines")
    for forbidden in ("slug", "timeline_ulid", "is_default", "event_hash"):
        assert forbidden not in sql, f"timelines must not gain a {forbidden!r} column"


def test_pack_foreign_keys_point_inward_to_the_kernel(standard_database) -> None:
    conn, _ = standard_database

    timelines_project = _fk_by_column(conn, "timelines", "project_id")
    assert timelines_project["cols"] == [("project_id", "id")]
    assert timelines_project["table"] == "projects"
    assert timelines_project["on_delete"] == "CASCADE"
    timelines_stream = _fk_by_column(conn, "timelines", "event_stream_id")
    assert timelines_stream["cols"] == [("event_stream_id", "id")]
    assert timelines_stream["table"] == "event_streams"
    assert timelines_stream["on_delete"] == "RESTRICT"

    shots_project = _fk_by_column(conn, "shots", "project_id")
    assert shots_project["table"] == "projects"
    assert shots_project["on_delete"] == "CASCADE"

    shot_items_shot = _fk_by_column(conn, "shot_items", "shot_id")
    assert shot_items_shot["cols"] == [("shot_id", "id")]
    assert shot_items_shot["table"] == "shots"
    assert shot_items_shot["on_delete"] == "CASCADE"
    shot_items_media = _fk_by_column(conn, "shot_items", "media_id")
    assert shot_items_media["cols"] == [("media_id", "id")]
    assert shot_items_media["table"] == "media"
    assert shot_items_media["on_delete"] == "RESTRICT"

    media_ref = _fk_by_column(conn, "media_references", "reference_id")
    assert media_ref["table"] == "project_references"
    assert media_ref["on_delete"] == "CASCADE"
    media_ref_media = _fk_by_column(conn, "media_references", "media_id")
    assert media_ref_media["table"] == "media"
    assert media_ref_media["on_delete"] == "CASCADE"
    media_ref_task = _fk_by_column(conn, "media_references", "context_task_id")
    assert media_ref_task["table"] == "tasks"
    assert media_ref_task["on_delete"] == "RESTRICT"

    links_from = _fk_by_column(conn, "reference_links", "from_reference_id")
    assert links_from["table"] == "project_references"
    assert links_from["on_delete"] == "CASCADE"
    links_to = _fk_by_column(conn, "reference_links", "to_reference_id")
    assert links_to["table"] == "project_references"
    assert links_to["on_delete"] == "CASCADE"


def test_reference_tables_preserve_locked_enum_checks(standard_database) -> None:
    conn, _ = standard_database
    sql = {
        "project_references": _table_sql(conn, "project_references"),
        "media_references": _table_sql(conn, "media_references"),
        "reference_links": _table_sql(conn, "reference_links"),
    }
    assert "'character','place','object','clothing','other'" in sql[
        "project_references"
    ]
    assert (
        "'canonical','used_as_input','depicts','inspired_by'"
        in sql["media_references"]
    )
    assert (
        "'belongs_to','wears','located_in','associated_with','related_to'"
        in sql["reference_links"]
    )
    # media_references interaction checks (verbatim from v10 section 2.2).
    assert "role = 'canonical' OR is_primary = 0" in sql["media_references"]
    assert "role <> 'used_as_input' OR context_task_id IS NOT NULL" in sql[
        "media_references"
    ]
    assert (
        "context_task_id IS NULL OR role IN ('used_as_input','inspired_by')"
        in sql["media_references"]
    )
    assert "from_reference_id <> to_reference_id" in sql["reference_links"]


def test_pack_indexes_match_their_declarations(standard_database) -> None:
    conn, _ = standard_database
    indexes = _named_indexes(conn)
    # shots owns one index; references owns eight.
    assert _index_columns(conn, "shot_items_media") == ["media_id", "shot_id"]
    expected_reference_indexes = {
        "reference_one_primary_canonical",
        "reference_canonical_ordinal",
        "media_reference_global_unique",
        "media_reference_context_unique",
        "references_project_kind",
        "media_references_media",
        "media_references_task",
        "reference_links_to",
    }
    assert expected_reference_indexes <= set(indexes)
    # The reference partial indexes keep their WHERE clauses.
    for name in (
        "reference_one_primary_canonical",
        "reference_canonical_ordinal",
        "media_reference_global_unique",
        "media_reference_context_unique",
        "media_references_task",
    ):
        assert "WHERE" in indexes[name].upper(), f"{name!r} lost its WHERE clause"
    assert _index_columns(conn, "reference_links_to") == [
        "to_reference_id",
        "kind",
        "from_reference_id",
    ]


def test_pack_tables_never_gain_kernel_or_foreign_tables(standard_database) -> None:
    conn, _ = standard_database
    # The four packs add exactly their seven owned tables and nothing else.
    pack_tables = _table_names(conn) - set(CORE_TABLES)
    assert pack_tables == {
        "timelines",
        "shots",
        "shot_items",
        "project_references",
        "media_references",
        "reference_links",
        "runaway_transitions",
    }


# ---------------------------------------------------------------------------
# Section 7: forbidden vocabulary (v10 "no dormant platform" invariant)
# ---------------------------------------------------------------------------


def test_forbidden_vocabulary_absent_from_the_kernel(core_database) -> None:
    conn, _ = core_database
    tables = _table_names(conn)
    assert tables.isdisjoint(FORBIDDEN_TABLES)


def test_m2_plan_step_tables_are_absent_from_fresh_core(core_database) -> None:
    """m2 adds no plan/step machinery: every v9 plan/step table name stays
    absent from a fresh core database (v10 \"no dormant platform\" invariant)."""
    conn, _ = core_database
    tables = _table_names(conn)
    for name in (
        "plans",
        "steps",
        "plan_steps",
        "step_tasks",
        "run_steps",
        "run_step_tasks",
    ):
        assert name not in tables, f"forbidden plan/step table {name!r} was created"
        assert name in FORBIDDEN_TABLES, f"{name!r} must stay on the forbidden list"


def test_m2_media_tables_never_contain_blob_columns(core_database) -> None:
    """Media bytes never enter SQLite: every column of the three kernel media
    tables is a declared scalar type, and no BLOB column can ever appear."""
    conn, _ = core_database
    for table in ("media", "media_locations", "media_relations"):
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall():
            _cid, name, declared_type, _not_null, _default, _pk = row
            assert declared_type.upper() != "BLOB", (
                f"{table}.{name} must not be a BLOB column"
            )
        sql = _table_sql(conn, table)
        assert "BLOB" not in sql.upper(), f"{table} DDL contains a BLOB column"


def test_m2_media_tables_store_only_bytes_metadata(core_database) -> None:
    """The media table stores content hash, byte size, and metadata JSON —
    never the bytes themselves (byte SHA-256 is the sole media identity)."""
    conn, _ = core_database
    assert _columns(conn, "media") == [
        "id",
        "project_id",
        "media_kind",
        "mime_type",
        "byte_size",
        "content_hash",
        "metadata_json",
        "created_at",
    ]
    assert "content_hash" in _columns(conn, "media")
    assert "byte_size" in _columns(conn, "media")
    assert "metadata_json" in _columns(conn, "media")


def test_forbidden_vocabulary_absent_from_the_standard_catalog(
    standard_database,
) -> None:
    conn, _ = standard_database
    tables = _table_names(conn)
    assert tables.isdisjoint(FORBIDDEN_TABLES)
    # Affirmative spot checks of the most likely regressions.
    for name in (
        "run_steps",
        "plans",
        "sessions",
        "leases",
        "identity",
        "accounts",
        "sync_state",
        "event_chain",
    ):
        assert name not in tables, f"forbidden table {name!r} was created"


# ---------------------------------------------------------------------------
# Section 8: migration application (exact rows, once-only, writable PRAGMAs)
# ---------------------------------------------------------------------------


def test_schema_migrations_rows_match_the_registry_exactly(
    standard_database,
    standard_registry,
) -> None:
    conn, _ = standard_database
    registry: FrozenSchemaPackRegistry = standard_registry
    applied = read_schema_migrations(conn)
    registered = sorted(
        (m.pack, m.version, m.name) for m in registry.migrations
    )
    assert [(row.pack, row.version, row.name) for row in applied] == registered
    for row in applied:
        assert len(row.checksum) == 64
        assert set(row.checksum) <= set("0123456789abcdef")


def test_reopen_is_idempotent_and_once_only(standard_database, standard_registry) -> None:
    conn, path = standard_database
    first_rows = read_schema_migrations(conn)
    reopened = open_database(path, standard_registry)
    try:
        reopened_rows = read_schema_migrations(reopened)
    finally:
        reopened.close()
    assert len(reopened_rows) == len(first_rows)
    assert [(r.pack, r.version) for r in reopened_rows] == [
        (r.pack, r.version) for r in first_rows
    ]


def test_writable_pragmas_are_inspectable(standard_database) -> None:
    conn, _ = standard_database
    pragmas = inspect_connection_pragmas(conn)
    assert pragmas["foreign_keys"] == 1
    assert pragmas["journal_mode"] == "wal"
    assert pragmas["synchronous"] == 1  # NORMAL
    assert pragmas["busy_timeout"] == 5000


# ---------------------------------------------------------------------------
# Section 9: migration replay, drift, cycles, too-new probes, and PRAGMAs
# (plan step 5 edge matrix: exact rows, idempotent reopen, deterministic
# checksum/name drift, dependency-cycle rejection, byte-for-byte nonmutation
# on too-new schemas, and the writable PRAGMA surface.)
# ---------------------------------------------------------------------------


def _database_bytes(path: Path) -> tuple[bytes, dict[str, bytes]]:
    """Return ``(main database bytes, sidecar bytes that already exist)``.

    A read-only open of a persistent-WAL database materializes an empty
    ``-wal`` file and the fixed-size ``-shm`` index; those artifacts carry
    no database content and are removed on the next clean close, so the
    byte-for-byte nonmutation proof targets the database content file and
    any sidecar that already existed before the probe.
    """
    main = path.read_bytes() if path.exists() else b""
    sidecars: dict[str, bytes] = {}
    for candidate in (Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.exists():
            sidecars[candidate.name] = candidate.read_bytes()
    return main, sidecars


def _assert_database_unchanged(path: Path, before: tuple[bytes, dict[str, bytes]]) -> None:
    """Assert the database content file and pre-existing sidecars are identical.

    The ``-shm`` WAL index is volatile by design: any open — including a
    read-only probe — may update its reader markers, so its content is not
    database content. Pre-existing ``-wal`` content is compared byte-for-byte;
    a pre-existing ``-shm`` is only required to still exist.
    """
    after_main, after_sidecars = _database_bytes(path)
    assert after_main == before[0]
    for name, content in before[1].items():
        if name.endswith("-shm"):
            assert name in after_sidecars, name
            continue
        assert after_sidecars[name] == content, name


def _empty_pack_manifest(pack_id: str, depends_on: list[str]):
    """Build a minimal migration-less manifest for ordering/cycle tests."""
    return parse_schema_pack_manifest(
        {
            "id": pack_id,
            "version": 1,
            "depends_on": depends_on,
            "migrations": [],
            "stream_types": [],
            "event_kinds": [],
            "command_kinds": [],
            "repositories": [],
            "conformance": [],
            "cli_mounts": {},
            "bridge_mounts": [],
        }
    )


def test_applied_migration_rows_record_exact_byte_checksums(
    standard_database,
    standard_registry,
) -> None:
    conn, _ = standard_database
    registry: FrozenSchemaPackRegistry = standard_registry
    by_key = {(m.pack, m.version): m for m in registry.migrations}
    for row in read_schema_migrations(conn):
        registered = by_key[(row.pack, row.version)]
        # The recorded checksum is the exact-byte SHA-256 of the SQL file.
        assert row.checksum == sha256_bytes(read_migration_bytes(registered))
        # applied_at is a deterministic aware-UTC ISO-8601 timestamp.
        applied_at = datetime.fromisoformat(row.applied_at)
        assert applied_at.tzinfo is not None


def test_applied_migration_rows_follow_topological_order(
    standard_database,
    standard_registry,
) -> None:
    conn, _ = standard_database
    registry: FrozenSchemaPackRegistry = standard_registry
    expected = [
        (m.pack, m.version, m.name)
        for m in topological_migration_order(registry)
    ]
    assert [
        (row.pack, row.version, row.name)
        for row in read_schema_migrations(conn)
    ] == expected


def test_reopen_after_full_close_is_idempotent(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "closed_reopen.sqlite3"
    conn = open_database(path, standard_registry)
    first = read_schema_migrations(conn)
    conn.close()
    reopened = open_database(path, standard_registry)
    try:
        second = read_schema_migrations(reopened)
    finally:
        reopened.close()
    assert [(r.pack, r.version, r.name, r.checksum) for r in second] == [
        (r.pack, r.version, r.name, r.checksum) for r in first
    ]


def test_checksum_drift_is_rejected_without_mutation(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "checksum_drift.sqlite3"
    conn = open_database(path, standard_registry)
    conn.close()
    raw = sqlite3.connect(str(path), isolation_level=None)
    raw.execute(
        "UPDATE schema_migrations SET checksum = ?"
        " WHERE pack = 'core' AND version = 1",
        ("f" * 64,),
    )
    raw.close()
    before = _database_bytes(path)
    with pytest.raises(MigrationChecksumDriftError) as excinfo:
        probe_database(path, standard_registry)
    assert "checksum drift" in str(excinfo.value)
    # The writable open refuses through the same nonmutating probe.
    with pytest.raises(MigrationChecksumDriftError):
        open_database(path, standard_registry)
    _assert_database_unchanged(path, before)
    # The tampered row is untouched: the runner never "repairs" drift.
    check = sqlite3.connect(str(path), isolation_level=None)
    try:
        row = check.execute(
            "SELECT checksum FROM schema_migrations"
            " WHERE pack = 'core' AND version = 1"
        ).fetchone()
    finally:
        check.close()
    assert row is not None and row[0] == "f" * 64


def test_name_drift_is_rejected_deterministically(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "name_drift.sqlite3"
    conn = open_database(path, standard_registry)
    conn.close()
    raw = sqlite3.connect(str(path), isolation_level=None)
    raw.execute(
        "UPDATE schema_migrations SET name = ?"
        " WHERE pack = 'timeline' AND version = 1",
        ("renamed_migration",),
    )
    raw.close()
    first_message: str | None = None
    for _ in range(2):
        with pytest.raises(MigrationNameDriftError) as excinfo:
            probe_database(path, standard_registry)
        message = str(excinfo.value)
        assert "name drift" in message
        if first_message is None:
            first_message = message
        else:
            assert message == first_message  # deterministic failure


def test_dependency_cycle_is_rejected() -> None:
    registry = (
        SchemaPackRegistry()
        .register_pack(_empty_pack_manifest("alpha", ["beta >= 1"]))
        .register_pack(_empty_pack_manifest("beta", ["alpha >= 1"]))
        .freeze()
    )
    with pytest.raises(MigrationCycleError) as excinfo:
        topological_migration_order(registry)
    assert "cycle" in str(excinfo.value)


def test_self_dependency_cycle_is_rejected() -> None:
    registry = (
        SchemaPackRegistry()
        .register_pack(_empty_pack_manifest("alpha", ["alpha >= 1"]))
        .freeze()
    )
    with pytest.raises(MigrationCycleError):
        topological_migration_order(registry)


def test_unregistered_dependency_is_rejected() -> None:
    registry = (
        SchemaPackRegistry()
        .register_pack(_empty_pack_manifest("alpha", ["ghost >= 1"]))
        .freeze()
    )
    with pytest.raises(MigrationError) as excinfo:
        topological_migration_order(registry)
    assert "unregistered pack" in str(excinfo.value)


def test_too_new_version_probe_is_byte_for_byte_nonmutating(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "too_new_version.sqlite3"
    conn = open_database(path, standard_registry)
    conn.close()
    raw = sqlite3.connect(str(path), isolation_level=None)
    raw.execute(
        "INSERT INTO schema_migrations"
        " (pack, version, name, checksum, applied_at)"
        " VALUES ('core', 2, 'future_core', ?, ?)",
        ("0" * 64, "2026-08-15T00:00:00+00:00"),
    )
    raw.close()
    before = _database_bytes(path)
    with pytest.raises(MigrationTooNewError) as excinfo:
        probe_database(path, standard_registry)
    assert "too new" in str(excinfo.value)
    _assert_database_unchanged(path, before)
    # The probe is read-only: the tampered row is still exactly as written.
    check = sqlite3.connect(
        f"file:{path}?mode=ro", uri=True, isolation_level=None
    )
    try:
        applied = read_schema_migrations(check)
    finally:
        check.close()
    assert any(row.version == 2 for row in applied)


def test_unregistered_pack_probe_is_byte_for_byte_nonmutating(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "ghost_pack.sqlite3"
    conn = open_database(path, standard_registry)
    conn.close()
    raw = sqlite3.connect(str(path), isolation_level=None)
    raw.execute(
        "INSERT INTO schema_migrations"
        " (pack, version, name, checksum, applied_at)"
        " VALUES ('ghost_pack', 1, 'ghost_initial', ?, ?)",
        ("1" * 64, "2026-08-15T00:00:00+00:00"),
    )
    raw.close()
    before = _database_bytes(path)
    with pytest.raises(MigrationTooNewError):
        probe_database(path, standard_registry)
    _assert_database_unchanged(path, before)


def test_too_new_schema_blocks_writable_open_before_any_mutation(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "too_new_open.sqlite3"
    conn = open_database(path, standard_registry)
    conn.close()
    raw = sqlite3.connect(str(path), isolation_level=None)
    raw.execute(
        "INSERT INTO schema_migrations"
        " (pack, version, name, checksum, applied_at)"
        " VALUES ('core', 2, 'future_core', ?, ?)",
        ("0" * 64, "2026-08-15T00:00:00+00:00"),
    )
    raw.close()
    before = _database_bytes(path)
    with pytest.raises(MigrationTooNewError):
        open_database(path, standard_registry)
    _assert_database_unchanged(path, before)


def test_read_only_open_never_applies_migrations(
    tmp_path,
    standard_registry,
) -> None:
    path = tmp_path / "empty_read_only.sqlite3"
    path.touch()  # an existing but completely empty database file
    before = _database_bytes(path)
    conn = open_database(path, standard_registry, read_only=True)
    try:
        # The read-only probe succeeded but applied zero migrations.
        assert _table_names(conn) == set()
    finally:
        conn.close()
    _assert_database_unchanged(path, before)
