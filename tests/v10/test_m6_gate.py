"""Sprint-6 gate test (m6 plan step 10 / task T15).

Proves every must/should done criterion of the m6 sprint plan against the
live tree, end to end:

- ``serve`` boots a clean project: ``compose_standard_bridge`` on a fresh
  ``tmp_path`` registers exactly the three in-tree schema packs and the
  local bridge HTTP server answers ``GET /health``;
- ``backup create`` -> destroy live data -> ``backup restore`` reopens with
  matching state: table count (20), event-stream heads, and pack migration
  state (core + timeline/shots/references) are byte-identical;
- ``doctor`` is clean (exit 0, every check ok) on a fresh project and on a
  restored project, and fails closed (exit 1, ``"ok": false``) when the
  database is deleted;
- exactly eight families appear in ``_top_level_commands()`` and in the
  executable help text;
- ``run_authority_lint`` over the live tree finds zero errors;
- the secret-sink test module from Phase 5 is referenced and present.
"""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from astrid.application import compose_standard_application
from astrid.core import doctor
from astrid.core.backup import create_backup, restore_backup
from astrid.core.gateway.dispatch import _top_level_commands
from astrid.core.gateway.help import _product_help_text
from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)
from astrid.packs import STANDARD_SCHEMA_PACKS, compose_standard_bridge
from scripts.reshape.authority_lint import run_authority_lint

EXPECTED_FAMILIES: frozenset[str] = frozenset(
    {"projects", "timelines", "media", "tasks", "runs", "serve", "doctor", "backup"}
)
"""The exactly-eight top-level families (five product + three operational)."""

EXPECTED_TABLE_COUNT = 20
"""The frozen v10 schema table count (core + timeline/shots/references)."""


def _destroy_live_data(root: Path) -> None:
    """Remove the live database and managed-media tree (simulate a loss)."""
    db_path = root / ".astrid" / "astrid.sqlite3"
    db_path.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    shutil.rmtree(root / ".astrid" / "media", ignore_errors=True)


def _seed_project_and_timeline(root: Path) -> None:
    """Create one project plus one timeline under *root*.

    Both services commit event-stream rows (``core.project`` and
    ``timeline.timeline`` streams with ``head_seq`` 1), so the gate can
    compare stream heads across the backup round trip.
    """
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        timeline = app.timelines_service.create(
            project="demo", slug="main", name="Main", idempotency_key="t1"
        )
        assert timeline.ok, timeline.error


def _capture_state(root: Path) -> dict[str, object]:
    """Read the database state the gate compares across backup/restore."""
    with compose_standard_application(projects_root=root) as app:
        with app.writer.read_only_connection() as conn:
            table_count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            stream_heads = conn.execute(
                "SELECT id, project_id, stream_type, head_seq"
                " FROM event_streams ORDER BY id"
            ).fetchall()
            migrations = conn.execute(
                "SELECT pack, version, name, checksum"
                " FROM schema_migrations ORDER BY pack"
            ).fetchall()
    return {
        "table_count": table_count,
        "stream_heads": [tuple(row) for row in stream_heads],
        "migrations": [tuple(row) for row in migrations],
    }


def _start_server(composition) -> tuple[object, threading.Thread, str]:
    """Start a bridge HTTP server over the serve composition, mirroring the
    gateway serve composition root (m4 plan step 21): bridge, writer, and
    database path are constructor-injected."""
    server = create_local_bridge_server(
        projects_root=composition.projects_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    return server, thread, f"http://{host}:{port}"


def _stop_server(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# serve boots a clean project end to end
# ---------------------------------------------------------------------------


def test_serve_boots_clean_project_end_to_end(tmp_path: Path) -> None:
    composition = compose_standard_bridge(tmp_path)
    try:
        # Exactly the three in-tree schema packs are registered.
        assert STANDARD_SCHEMA_PACKS == ("timeline", "shots", "references")
        assert set(STANDARD_SCHEMA_PACKS) <= set(composition.registry.packs)
        assert "core" in composition.registry.packs
        assert composition.database_path.is_file()

        server, thread, base = _start_server(composition)
        try:
            with urlopen(f"{base}/health", timeout=10) as response:  # noqa: S310
                assert response.status == 200
                body = json.loads(response.read().decode("utf-8"))
            assert body["ok"] is True
            assert Path(body["projects_root"]) == tmp_path
        finally:
            _stop_server(server, thread)
    finally:
        composition.close()


# ---------------------------------------------------------------------------
# backup create -> destroy -> restore -> reopen with matching state
# ---------------------------------------------------------------------------


def test_backup_destroy_restore_reopens_with_matching_state(tmp_path: Path) -> None:
    _seed_project_and_timeline(tmp_path)
    before = _capture_state(tmp_path)
    assert before["table_count"] == EXPECTED_TABLE_COUNT
    assert len(before["stream_heads"]) >= 2  # project stream + timeline stream

    dest = tmp_path / "backup"
    result = create_backup(projects_root=tmp_path, dest_path=dest)
    assert (dest / "astrid.sqlite3").is_file()
    assert (dest / "backup.json").is_file()

    _destroy_live_data(tmp_path)
    assert not (tmp_path / ".astrid" / "astrid.sqlite3").exists()

    restored = restore_backup(dest, projects_root=tmp_path)
    assert restored.database_path == tmp_path / ".astrid" / "astrid.sqlite3"
    assert restored.database_path.is_file()

    after = _capture_state(tmp_path)
    assert after["table_count"] == EXPECTED_TABLE_COUNT
    assert after["stream_heads"] == before["stream_heads"]
    assert after["migrations"] == before["migrations"]


# ---------------------------------------------------------------------------
# doctor: clean on fresh and restored projects; fail-closed on deleted DB
# ---------------------------------------------------------------------------


def _doctor_json(projects_root: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    code = doctor.main(["--projects-root", str(projects_root), "--json"])
    payload = json.loads(capsys.readouterr().out)
    return code, payload


def test_doctor_is_clean_on_fresh_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_project_and_timeline(tmp_path)
    code, payload = _doctor_json(tmp_path, capsys)
    assert code == 0
    assert payload["ok"] is True
    assert all(check["status"] == "ok" for check in payload["checks"])


def test_doctor_is_clean_on_restored_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_project_and_timeline(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)
    _destroy_live_data(tmp_path)
    restore_backup(dest, projects_root=tmp_path)

    code, payload = _doctor_json(tmp_path, capsys)
    assert code == 0
    assert payload["ok"] is True
    assert all(check["status"] == "ok" for check in payload["checks"])


def test_doctor_fails_closed_on_deleted_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_project_and_timeline(tmp_path)
    db_path = tmp_path / ".astrid" / "astrid.sqlite3"
    assert db_path.is_file()
    _destroy_live_data(tmp_path)
    assert not db_path.exists()

    code, payload = _doctor_json(tmp_path, capsys)
    assert code == 1
    assert payload["ok"] is False
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert any(check["name"] == "sqlite_quick_check" for check in failed)
    assert any(check["name"] == "fk_integrity" for check in failed)
    assert any(check["name"] == "schema_versions" for check in failed)


# ---------------------------------------------------------------------------
# Exactly eight families in _top_level_commands() and help text
# ---------------------------------------------------------------------------


def test_exactly_eight_families_in_commands_and_help() -> None:
    assert _top_level_commands() == EXPECTED_FAMILIES
    assert len(EXPECTED_FAMILIES) == 8

    text = _product_help_text()
    assert "exactly eight families" in text
    for family in sorted(EXPECTED_FAMILIES):
        assert family in text, f"help text omits family {family!r}"


# ---------------------------------------------------------------------------
# Live-tree authority lint
# ---------------------------------------------------------------------------


def test_live_tree_authority_lint_is_clean() -> None:
    report = run_authority_lint()
    assert report.ok, report.errors


# ---------------------------------------------------------------------------
# Phase 5 secret-sink module is referenced
# ---------------------------------------------------------------------------


def test_secret_sink_module_is_referenced() -> None:
    """The Phase 5 secret-sink tests are part of the m6 gate surface."""
    import tests.v10.test_m6_secret_sink as secret_sink

    for test_name in (
        "test_backup_media_copy_excludes_env_and_secret_bearing_paths",
        "test_backup_directory_never_contains_sentinel_secret_value",
        "test_build_child_subprocess_env_excludes_provider_and_account_cloud_vars",
    ):
        assert callable(getattr(secret_sink, test_name)), test_name
