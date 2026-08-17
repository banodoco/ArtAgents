"""Deterministic authority-lint mutation fixtures (m1 plan step 22 / NSA-3).

Every rule of :mod:`scripts.reshape.authority_lint` is proven by a
representative mutation fixture that must fail exactly that rule, and each
documented exemption is proven by a fixture that must stay clean:

- **imports**: kernel-to-pack imports (every ``astrid/core`` file except the
  single composition exemption), pack-to-pack imports between the m1 schema
  packs, and the documented legacy rendering/builtin prefixes that stay
  legal in the kernel;
- **writer authority**: ``DatabaseWriter(`` / writable ``sqlite3.connect``
  outside the kernel store fails; ``mode=ro`` probes and the conformance
  kit's scratch writers stay legal;
- **legacy authorities**: supported v10 entry paths may never import the
  legacy file/JSONL/FSA/Supabase authorities, while legacy files *outside*
  those paths remain in-tree legally;
- **schema ownership**: kernel FKs to pack tables, cross-pack FKs,
  undeclared tables/indexes, forbidden schema, closed stream vocabulary,
  and pack convenience alias/default columns all fail;
- **exemptions**: only the gateway serve root may import the standard pack
  composition, and only legacy paths outside the supported v10 entries are
  exempt from the legacy-authority rule.

All fixtures are pure text under ``tmp_path``; no fixture touches the real
repository tree.
"""

from __future__ import annotations

from pathlib import Path

from scripts.reshape.authority_lint import (
    lint_import_boundaries,
    lint_legacy_authorities,
    lint_schema_ownership,
    lint_writer_authority,
    run_authority_lint,
)

# The real timeline schema-pack manifest shape (11 snake_case fields), used
# by every fixture that needs a declared pack table/vocabulary.
_TIMELINE_MANIFEST = """\
id: timeline
version: 1
depends_on:
  - core >= 1
migrations:
  - version: 1
    name: initial
    path: migrations/0001_initial.sql
    tables:
      - timelines
stream_types:
  - timeline.timeline
event_kinds:
  - timeline.created
  - timeline.saved
command_kinds:
  - timeline.create
  - timeline.save
repositories:
  - TimelineRepository
conformance:
  - replay
cli_mounts:
  timelines: timelines
bridge_mounts:
  - timelines
"""

_SHOTS_MANIFEST = """\
id: shots
version: 1
depends_on:
  - core >= 1
migrations:
  - version: 1
    name: initial
    path: migrations/0001_initial.sql
    tables:
      - shots
stream_types: []
event_kinds:
  - shot.item_added
command_kinds:
  - shot.add_item
repositories: []
conformance:
  - replay
cli_mounts:
  shots: timelines shots
bridge_mounts: []
"""


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _bootstrap(root: Path, *, with_shots: bool = False) -> None:
    """Minimal lint-scan root: core + packs with valid pack manifests."""
    _write(root, "astrid/core/__init__.py", "")
    _write(root, "astrid/packs/__init__.py", "")
    _write(root, "astrid/packs/timeline/__init__.py", "")
    _write(root, "astrid/packs/timeline/schema-pack.yaml", _TIMELINE_MANIFEST)
    _write(
        root,
        "astrid/packs/timeline/migrations/0001_initial.sql",
        "CREATE TABLE timelines (\n"
        "  id TEXT PRIMARY KEY,\n"
        "  project_id TEXT NOT NULL,\n"
        "  event_stream_id TEXT NOT NULL,\n"
        "  name TEXT NOT NULL,\n"
        "  document_json TEXT NOT NULL,\n"
        "  asset_registry_json TEXT NOT NULL,\n"
        "  created_at TEXT NOT NULL,\n"
        "  updated_at TEXT NOT NULL\n"
        ");\n",
    )
    if with_shots:
        _write(root, "astrid/packs/shots/__init__.py", "")
        _write(root, "astrid/packs/shots/schema-pack.yaml", _SHOTS_MANIFEST)
        _write(
            root,
            "astrid/packs/shots/migrations/0001_initial.sql",
            "CREATE TABLE shots (\n"
            "  id TEXT PRIMARY KEY,\n"
            "  project_id TEXT NOT NULL\n"
            ");\n",
        )


# ---------------------------------------------------------------------------
# Import boundaries
# ---------------------------------------------------------------------------


def test_kernel_to_pack_import_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/core/evil.py",
        "from astrid.packs.timeline.repository import TimelineRepository\n",
    )
    errors = lint_import_boundaries(tmp_path)
    assert any(
        "astrid/core/evil.py: kernel-to-pack import 'astrid.packs.timeline.repository'"
        in error
        for error in errors
    ), errors


def test_composition_exemption_is_the_only_kernel_to_pack_allowed(
    tmp_path: Path,
) -> None:
    _bootstrap(tmp_path)
    # The single documented application-composition exemption.
    _write(
        tmp_path,
        "astrid/core/gateway/dispatch.py",
        "from astrid.packs import register_standard_schema_packs\n",
    )
    # Any other kernel file importing a pack is a violation.
    _write(
        tmp_path,
        "astrid/core/not_exempt.py",
        "from astrid.packs import register_standard_schema_packs\n",
    )
    errors = lint_import_boundaries(tmp_path)
    assert not any(
        "astrid/core/gateway/dispatch.py" in error for error in errors
    ), errors
    assert any(
        "astrid/core/not_exempt.py: kernel-to-pack import 'astrid.packs'"
        in error
        for error in errors
    ), errors


def test_pack_to_pack_import_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path, with_shots=True)
    _write(
        tmp_path,
        "astrid/packs/timeline/evil.py",
        "from astrid.packs.shots.repository import ShotRepository\n",
    )
    errors = lint_import_boundaries(tmp_path)
    assert any(
        "astrid/packs/timeline/evil.py: pack-to-pack import "
        "'astrid.packs.shots.repository' from pack 'timeline'"
        in error
        for error in errors
    ), errors


def test_legacy_rendering_and_builtin_pack_imports_stay_legal_in_kernel(
    tmp_path: Path,
) -> None:
    """The m1-m6 legacy capability packs remain in-tree; kernel modules may
    keep importing the documented rendering/builtin prefixes."""
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/core/legacy_user.py",
        "from astrid.packs.rendering.something import render\n"
        "from astrid.packs.builtin.helpers import util\n",
    )
    errors = lint_import_boundaries(tmp_path)
    assert errors == [], errors


# ---------------------------------------------------------------------------
# Writer authority
# ---------------------------------------------------------------------------


def test_writer_construction_outside_kernel_store_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/core/evil_writer.py",
        "from astrid.core.store.writer import DatabaseWriter\n"
        "writer = DatabaseWriter('/tmp/x.sqlite3', None)\n",
    )
    _write(
        tmp_path,
        "astrid/packs/timeline/evil_writer.py",
        "import sqlite3\n"
        "conn = sqlite3.connect('/tmp/y.sqlite3')\n",
    )
    errors = lint_writer_authority(tmp_path)
    assert any(
        "astrid/core/evil_writer.py: SQLite writer construction outside the "
        "kernel store" in error
        for error in errors
    ), errors
    assert any(
        "astrid/packs/timeline/evil_writer.py: SQLite writer construction "
        "outside the kernel store" in error
        for error in errors
    ), errors


def test_read_only_probe_is_not_a_writer(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/core/reader.py",
        "import sqlite3\n"
        "conn = sqlite3.connect('file:db.sqlite3?mode=ro', uri=True)\n",
    )
    errors = lint_writer_authority(tmp_path)
    assert errors == [], errors


def test_conformance_kit_scratch_writer_is_exempt(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/core/conformance/kit.py",
        "from astrid.core.store.writer import DatabaseWriter\n"
        "writer = DatabaseWriter('/tmp/scratch.sqlite3', None)\n",
    )
    errors = lint_writer_authority(tmp_path)
    assert errors == [], errors


# ---------------------------------------------------------------------------
# Legacy authorities
# ---------------------------------------------------------------------------


def test_legacy_authority_in_supported_entry_path_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/bridge.py",
        "from astrid.core.timeline.eventlog import LocalFsBackend\n"
        "backend = LocalFsBackend(timeline_id='x', timeline_home=Path('.'))\n",
    )
    errors = lint_legacy_authorities(tmp_path)
    assert any(
        "astrid/packs/timeline/bridge.py: legacy authority marker "
        "'LocalFsBackend' in a supported v10 entry path" in error
        for error in errors
    ), errors


def test_legacy_files_outside_supported_paths_are_allowed(tmp_path: Path) -> None:
    """The m1-m6 legacy files stay in-tree; only the supported v10 entry
    paths are scanned for legacy authority markers."""
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/core/timeline/legacy_thing.py",
        "from astrid.core.timeline.eventlog import LocalFsBackend\n"
        "from astrid.core.timeline.eventlog.backends.supabase import client\n",
    )
    errors = lint_legacy_authorities(tmp_path)
    assert errors == [], errors


# ---------------------------------------------------------------------------
# Schema ownership
# ---------------------------------------------------------------------------


def test_kernel_fk_to_pack_table_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE events (\n"
        "  id TEXT PRIMARY KEY,\n"
        "  FOREIGN KEY (timeline_id) REFERENCES timelines (id)\n"
        ");\n",
    )
    errors = lint_schema_ownership(tmp_path)
    assert any(
        "astrid/packs/timeline/migrations/0002_bad.sql: kernel FK from "
        "events to pack table 'timelines'" in error
        for error in errors
    ), errors


def test_cross_pack_fk_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path, with_shots=True)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE timelines (\n"
        "  id TEXT PRIMARY KEY,\n"
        "  FOREIGN KEY (shot_id) REFERENCES shots (id)\n"
        ");\n",
    )
    errors = lint_schema_ownership(tmp_path)
    assert any(
        "astrid/packs/timeline/migrations/0002_bad.sql: cross-pack FK from "
        "timelines to 'shots' (pack 'shots')" in error
        for error in errors
    ), errors


def test_undeclared_table_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE mystery_table (id TEXT PRIMARY KEY);\n",
    )
    errors = lint_schema_ownership(tmp_path)
    assert any(
        "astrid/packs/timeline/migrations/0002_bad.sql: undeclared table "
        "'mystery_table'" in error
        for error in errors
    ), errors


def test_forbidden_schema_table_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE sessions (id TEXT PRIMARY KEY);\n",
    )
    errors = lint_schema_ownership(tmp_path)
    assert any(
        "astrid/packs/timeline/migrations/0002_bad.sql: forbidden table "
        "'sessions' violates the no-dormant-platform invariant" in error
        for error in errors
    ), errors


def test_undeclared_kernel_index_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE projects (id TEXT PRIMARY KEY);\n"
        "CREATE INDEX rogue_idx ON projects (slug);\n",
    )
    errors = lint_schema_ownership(tmp_path)
    assert any(
        "astrid/packs/timeline/migrations/0002_bad.sql: undeclared kernel "
        "index 'rogue_idx'" in error
        for error in errors
    ), errors


def test_undeclared_stream_type_in_sql_fails(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE events (id TEXT PRIMARY KEY);\n"
        "INSERT INTO event_streams (id, stream_type) "
        "VALUES ('s1', 'core.nonexistent');\n",
    )
    errors = lint_schema_ownership(tmp_path)
    assert any(
        "astrid/packs/timeline/migrations/0002_bad.sql: stream type "
        "'core.nonexistent' is not declared by the composed registry"
        in error
        for error in errors
    ), errors


def test_pack_convenience_alias_default_columns_fail(tmp_path: Path) -> None:
    """Projected alias/default state may never become pack write columns
    (SD1): slug, ULID, default, and hash columns on a pack-owned table."""
    _bootstrap(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE timelines (\n"
        "  id TEXT PRIMARY KEY,\n"
        "  slug TEXT,\n"
        "  timeline_ulid TEXT,\n"
        "  is_default INTEGER,\n"
        "  event_hash TEXT,\n"
        "  previous_event_hash TEXT\n"
        ");\n",
    )
    errors = lint_schema_ownership(tmp_path)
    for column in (
        "slug",
        "timeline_ulid",
        "is_default",
        "event_hash",
        "previous_event_hash",
    ):
        assert any(
            f"convenience column timelines.{column} projects alias/default "
            "state as write authority" in error
            for error in errors
        ), (column, errors)


# ---------------------------------------------------------------------------
# Whole-lint clean baseline and exemption proof
# ---------------------------------------------------------------------------


def test_clean_fixture_passes_the_whole_authority_lint(tmp_path: Path) -> None:
    """A fixture with only the declared schema pack and no mutations is ok."""
    _bootstrap(tmp_path)
    report = run_authority_lint(tmp_path)
    assert report.ok, report.errors


def test_mutation_fixture_fails_the_whole_authority_lint(
    tmp_path: Path,
) -> None:
    """One representative mutation per rule family, combined, is caught by
    the combined lint (import, writer, legacy, and schema errors together)."""
    _bootstrap(tmp_path, with_shots=True)
    _write(
        tmp_path,
        "astrid/core/evil.py",
        "from astrid.packs.timeline.repository import TimelineRepository\n",
    )
    _write(
        tmp_path,
        "astrid/core/evil_writer.py",
        "from astrid.core.store.writer import DatabaseWriter\n"
        "writer = DatabaseWriter('/tmp/x.sqlite3', None)\n",
    )
    _write(
        tmp_path,
        "astrid/packs/timeline/bridge.py",
        "from astrid.core.timeline.eventlog import LocalFsBackend\n",
    )
    _write(
        tmp_path,
        "astrid/packs/timeline/migrations/0002_bad.sql",
        "CREATE TABLE events (\n"
        "  id TEXT PRIMARY KEY,\n"
        "  FOREIGN KEY (timeline_id) REFERENCES timelines (id)\n"
        ");\n"
        "CREATE TABLE sessions (id TEXT PRIMARY KEY);\n",
    )
    report = run_authority_lint(tmp_path)
    assert not report.ok
    joined = "\n".join(report.errors)
    assert "kernel-to-pack import" in joined
    assert "SQLite writer construction outside the kernel store" in joined
    assert "legacy authority marker 'LocalFsBackend'" in joined
    assert "kernel FK from events to pack table 'timelines'" in joined
    assert "forbidden table 'sessions'" in joined
