"""M7 restore-startup, corruption, and schema refusal hardening."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.backup.operations import (
    RESTORE_JOURNAL_NAME,
    RESTORE_SWAP_BOUNDARIES,
    create_backup,
    recover_restore_staging,
)
from astrid.core.doctor import run_checks
from astrid.core.integrations.reigh.bridge_service import (
    BridgeTimelineNotFoundError,
)
from astrid.core.migrations.runner import MigrationTooNewError
from astrid.core.repositories.media import (
    EXTERNAL_LOCAL_REALM,
    MANAGED_LOCAL_REALM,
)
from astrid.core.store.uow import UnitOfWork
from astrid.packs import compose_standard_bridge
from tests.v10._m7_fixture import build_m7_fixture

_PNG_PREFIX = b"\x89PNG\r\n\x1a\n"


def _seed_project(root: Path, *, slug: str, payload: bytes) -> None:
    """Create a small editable project with one exact managed-media blob."""
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug=slug, name=slug.title(), idempotency_key=f"project-{slug}"
        )
        assert project.ok, project.error
        source = root / f"{slug}.png"
        source.write_bytes(_PNG_PREFIX + payload)
        media = app.media_service.import_file(
            project=slug, path=source, idempotency_key=f"media-{slug}"
        )
        assert media.ok, media.error


def _hash_tree(root: Path) -> str | None:
    """Hash relative names and bytes in one managed-media tree."""
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _state(root: Path) -> tuple[str | None, str | None]:
    """Capture exact database and managed-media hashes for old-or-new checks."""
    database = root / ".astrid" / "astrid.sqlite3"
    database_hash = (
        hashlib.sha256(database.read_bytes()).hexdigest()
        if database.is_file()
        else None
    )
    return database_hash, _hash_tree(root / ".astrid" / "media")


def _restore_child() -> str:
    """Return the small child program used for hard process death tests."""
    return (
        "import sys; "
        "from pathlib import Path; "
        "from astrid.core.backup.operations import restore_backup; "
        "restore_backup(Path(sys.argv[1]), projects_root=Path(sys.argv[2]))"
    )


def test_restore_kill_matrix_reopens_old_or_complete_editable_state(
    tmp_path: Path,
) -> None:
    """Every database/media move can be recovered before bridge writer open."""
    old_root = tmp_path / "old-project"
    replacement_root = tmp_path / "replacement-source"
    _seed_project(old_root, slug="old", payload=b"old-state")
    _seed_project(replacement_root, slug="new", payload=b"new-state")

    backup = tmp_path / "replacement-backup"
    create_backup(projects_root=replacement_root, dest_path=backup)
    old_state = _state(old_root)
    replacement_state = (
        hashlib.sha256((backup / "astrid.sqlite3").read_bytes()).hexdigest(),
        _hash_tree(backup / "media"),
    )
    assert old_state != replacement_state

    runtime_log = tmp_path / "restore-runtime.log"
    repo_root = Path(__file__).resolve().parents[2]
    for boundary in RESTORE_SWAP_BOUNDARIES:
        runtime_log.write_text("", encoding="utf-8")
        environment = os.environ.copy()
        environment["ASTRID_RESTORE_KILL_BOUNDARY"] = boundary
        environment["ASTRID_RESTORE_RUNTIME_LOG"] = str(runtime_log)
        environment["PYTHONPATH"] = str(repo_root)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                _restore_child(),
                str(backup),
                str(old_root),
            ],
            cwd=repo_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 78, completed.stderr
        records = [
            json.loads(line)
            for line in runtime_log.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert records and records[-1]["boundary"] == boundary

        # These are deliberately not journal names. Recovery must not scan
        # arbitrary files and infer a database/media pair from their bytes.
        staging_root = old_root / ".astrid" / ".restore-staging"
        noise = staging_root / "arbitrary"
        noise.mkdir(parents=True, exist_ok=True)
        (noise / "astrid.sqlite3").write_bytes(b"not semantic state")
        (staging_root / "unrelated.txt").write_text("ignore me", encoding="utf-8")

        composition = compose_standard_bridge(old_root)
        try:
            # The bridge read path works on the recovered pair: project
            # resolution succeeds (typed not-found for the missing timeline,
            # never an internal error) and the writer rows are readable.
            with pytest.raises(BridgeTimelineNotFoundError):
                composition.bridge.load_timeline("old", "old")
            with composition.writer.read_only_connection() as connection:
                assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        finally:
            composition.writer.close()

        recovered_state = _state(old_root)
        assert recovered_state in {old_state, replacement_state}
        assert not list(staging_root.glob(f"*/{RESTORE_JOURNAL_NAME}"))
        assert noise.exists()
        assert (staging_root / "unrelated.txt").exists()

        # A second read-before-write pass is a no-op and leaves the same exact
        # pair; this also exercises recovery after a fresh composition closed.
        assert recover_restore_staging(old_root) == 0
        assert _state(old_root) == recovered_state


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    """Capture all live bytes so rejected operations can prove no mutation."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name not in {"astrid.sqlite3-wal", "astrid.sqlite3-shm"}
    }


def _doctor_statuses(root: Path) -> dict[str, tuple[str, str]]:
    return {
        check.name: (check.status, check.detail)
        for check in run_checks(projects_root=root)
    }


def _insert_future_migration(database: Path, *, pack: str) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO schema_migrations "
            "(pack, version, name, checksum, applied_at) VALUES (?, ?, ?, ?, ?)",
            (pack, 999, "future", "0" * 64, "2026-08-20T00:00:00+00:00"),
        )


def test_corruption_matrix_has_stable_public_failures_and_is_read_only(
    tmp_path: Path,
) -> None:
    """Missing/mutated media and bad SQLite state fail closed without writes."""
    missing_root = tmp_path / "missing-media"
    missing = build_m7_fixture(missing_root)
    external = missing_root / "fixture-input" / "external-source.png"
    external.unlink()
    before_missing = _tree_snapshot(missing_root)
    missing_codes = []
    with compose_standard_application(missing_root) as app:
        for ordinal in range(2):
            result = app.media_service.verify(
                "m7-representative",
                "m7-media-external-source",
                realm=EXTERNAL_LOCAL_REALM,
                idempotency_key=f"m7-missing-media-verify-{ordinal}",
            )
            assert not result.ok
            assert result.error is not None
            missing_codes.append(result.error.code)
    assert missing_codes == ["internal_error", "internal_error"]
    assert _tree_snapshot(missing_root) == before_missing

    mutated_root = tmp_path / "mutated-media"
    mutated = build_m7_fixture(mutated_root)
    managed_digest = mutated.snapshot["bytes"]["managed-source"]["sha256"]
    managed = (
        mutated_root
        / ".astrid"
        / "media"
        / "sha256"
        / managed_digest[:2]
        / managed_digest[2:4]
        / managed_digest
    )
    assert managed.is_file()
    original = managed.read_bytes()
    managed.write_bytes(bytes([original[0] ^ 0xFF]) + original[1:])
    before_mutated = _tree_snapshot(mutated_root)
    mutated_codes = []
    with compose_standard_application(mutated_root) as app:
        for ordinal in range(2):
            result = app.media_service.verify(
                "m7-representative",
                "m7-media-managed-source",
                realm=MANAGED_LOCAL_REALM,
                idempotency_key=f"m7-mutated-media-verify-{ordinal}",
            )
            assert not result.ok
            assert result.error is not None
            mutated_codes.append(result.error.code)
    # The public SDK taxonomy deliberately bounds an unmapped integrity
    # exception to internal_error; repeated rejects must not drift or write.
    assert mutated_codes == ["internal_error", "internal_error"]
    assert _tree_snapshot(mutated_root) == before_mutated

    corrupt_root = tmp_path / "corrupt-sqlite"
    build_m7_fixture(corrupt_root)
    database = corrupt_root / ".astrid" / "astrid.sqlite3"
    corrupted = bytearray(database.read_bytes())
    page_size = int.from_bytes(corrupted[16:18], "big") or 4096
    assert len(corrupted) > page_size
    with sqlite3.connect(database) as connection:
        root_page = int(
            connection.execute(
                "SELECT rootpage FROM sqlite_master WHERE name = 'events'"
            ).fetchone()[0]
        )
    page_offset = (root_page - 1) * page_size
    assert page_offset + 8 < len(corrupted)
    corrupted[page_offset + 3] = 0xFF
    database.write_bytes(corrupted)
    before_corrupt = _tree_snapshot(corrupt_root)
    statuses = _doctor_statuses(corrupt_root)
    assert set(statuses) == {
        "python_version",
        "data_paths",
        "media_paths",
        "sqlite_quick_check",
        "fk_integrity",
        "schema_versions",
    }
    assert statuses["sqlite_quick_check"][0] == "fail"
    assert statuses["fk_integrity"][0] == "fail"
    assert _doctor_statuses(corrupt_root) == statuses
    assert _tree_snapshot(corrupt_root) == before_corrupt

    fk_root = tmp_path / "foreign-key"
    build_m7_fixture(fk_root)
    fk_database = fk_root / ".astrid" / "astrid.sqlite3"
    with sqlite3.connect(fk_database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO media_locations "
            "(id, media_id, realm, locator, verified_at, created_at) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (
                "m7-invalid-location",
                "m7-no-such-media",
                EXTERNAL_LOCAL_REALM,
                str(fk_root / "missing.png"),
                "2026-08-20T00:00:00+00:00",
            ),
        )
    before_fk = _tree_snapshot(fk_root)
    fk_statuses = _doctor_statuses(fk_root)
    assert fk_statuses["fk_integrity"][0] == "fail"
    assert "foreign key violation" in fk_statuses["fk_integrity"][1]
    assert _doctor_statuses(fk_root) == fk_statuses
    assert _tree_snapshot(fk_root) == before_fk


@pytest.mark.parametrize("pack", ["core", "timeline"])
def test_too_new_core_and_pack_migrations_refuse_before_writer_use(
    tmp_path: Path, pack: str
) -> None:
    """Future migration rows fail in doctor and before bridge writer open."""
    root = tmp_path / f"future-{pack}"
    build_m7_fixture(root)
    database = root / ".astrid" / "astrid.sqlite3"
    _insert_future_migration(database, pack=pack)
    statuses = _doctor_statuses(root)
    before = _tree_snapshot(root)
    assert statuses["schema_versions"][0] == "fail"
    assert "too new" in statuses["schema_versions"][1] or "not registered" in statuses["schema_versions"][1]

    refusal_messages = []
    for _ in range(2):
        with pytest.raises(MigrationTooNewError) as caught:
            compose_standard_bridge(root)
        refusal_messages.append(str(caught.value))
    assert refusal_messages[0] == refusal_messages[1]
    assert _tree_snapshot(root) == before


def _stage(root: Path, txn_id: str, name: str, content: bytes) -> Path:
    """Create one deterministic staging directory for the GC matrix."""
    directory = root / ".astrid" / "media" / ".staging" / txn_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return path


def test_startup_gc_keeps_live_attempts_and_only_removes_orphans(
    tmp_path: Path,
) -> None:
    """Startup fencing protects live staging and leaves managed bytes intact."""
    fixture = build_m7_fixture(tmp_path / "gc")
    database = fixture.root / ".astrid" / "astrid.sqlite3"
    live_txn = "ab" * 16
    terminal_txn = "cd" * 16
    orphan_txn = "ef" * 16
    live_path = _stage(fixture.root, live_txn, "live.bin", b"live-attempt")
    terminal_path = _stage(
        fixture.root, terminal_txn, "terminal.bin", b"terminal-attempt"
    )
    orphan_path = _stage(fixture.root, orphan_txn, "orphan.bin", b"orphan")
    arbitrary = fixture.root / ".astrid" / "media" / ".staging" / "not-a-txn"
    arbitrary.mkdir(parents=True)
    (arbitrary / "keep.txt").write_bytes(b"non-semantic entry")
    managed_before = _hash_tree(fixture.root / ".astrid" / "media" / "sha256")

    with sqlite3.connect(database) as connection:
        task_id = fixture.spec["runs"]["fanout"]["children"][0]["id"]
        for ordinal, (attempt_id, txn_id, status) in enumerate(
            (
                ("m7-live-attempt", live_txn, "running"),
                ("m7-terminal-attempt", terminal_txn, "failed"),
            ),
            start=1,
        ):
            connection.execute(
                "INSERT INTO execution_attempts "
                "(id, task_id, attempt_no, executor_id, status, status_version, "
                "lease_id, lease_expires_at, heartbeat_counter, last_heartbeat_at, "
                "progress_json, error_json, created_at, updated_at, finished_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, 0, NULL, ?, '{}', ?, ?, NULL)",
                (
                    attempt_id,
                    task_id,
                    ordinal,
                    "m7-test-executor",
                    status,
                    f"lease-{attempt_id}",
                    "2026-08-20T01:00:00+00:00",
                    json.dumps({"staging_txn_id": txn_id}),
                    "2026-08-20T00:00:00+00:00",
                    "2026-08-20T00:00:00+00:00",
                ),
            )

    composition = compose_standard_bridge(fixture.root)
    try:
        with composition.writer.read_only_connection() as connection:
            assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    finally:
        composition.writer.close()

    assert live_path.exists()
    assert not terminal_path.exists()
    assert not orphan_path.exists()
    assert (arbitrary / "keep.txt").exists()
    assert _hash_tree(fixture.root / ".astrid" / "media" / "sha256") == managed_before


def _event_chain_snapshot(root: Path, project_id: str) -> dict[str, object]:
    """Return projection/receipt facts used to classify old-or-complete state."""
    with compose_standard_application(projects_root=root) as app:
        with app.writer.read_only_connection() as connection:
            timeline = connection.execute(
                "SELECT document_json, asset_registry_json FROM timelines "
                "WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            counts = {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
                        (project_id,),
                    ).fetchone()[0]
                )
                for table in ("events", "command_receipts", "event_streams")
            }
            receipt = connection.execute(
                "SELECT idempotency_key, first_project_seq, last_project_seq "
                "FROM command_receipts WHERE project_id = ? "
                "AND idempotency_key = 'm7-uow-crash-save'",
                (project_id,),
            ).fetchone()
            stream_ids = [
                str(row[0])
                for row in connection.execute(
                    "SELECT id FROM event_streams WHERE project_id = ? ORDER BY id",
                    (project_id,),
                ).fetchall()
            ]
        summaries = []
        for stream_id in stream_ids:
            summary = app.events.verify_stream(app.writer, stream_id)
            summaries.append((stream_id, summary.event_count, summary.head_hash))
        return {
            "timeline": tuple(timeline) if timeline is not None else None,
            "counts": tuple(sorted(counts.items())),
            "receipt": tuple(receipt) if receipt is not None else None,
            "chains": tuple(summaries),
        }


def _timeline_save_child() -> str:
    """Child process that exits at one observed UoW statement boundary."""
    return """import json
import os
import sys
from pathlib import Path

from astrid.application import compose_standard_application
from astrid.core.store.uow import UnitOfWork

root = Path(sys.argv[1])
log = Path(sys.argv[2])
target = int(sys.argv[3])
project_id = sys.argv[4]
seen = {"n": 0}


def observe(kind, sql, params):
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"boundary": seen["n"], "kind": kind, "sql": sql}) + "\\n")
        handle.flush()
    if seen["n"] == target:
        os._exit(78)
    seen["n"] += 1


with compose_standard_application(projects_root=root) as app:
    UnitOfWork(app.writer, on_statement=observe).run(
        lambda u: app.timelines.save(
            u,
            project_id=project_id,
            ref="main",
            config={"fps": 24, "resolution": [1920, 1080], "fixture_state": "crash-complete"},
            registry={"assets": {}},
            expected_version=2,
            idempotency_key="m7-uow-crash-save",
            created_at="2026-08-20T00:00:00.000000+00:00",
        )
    )
"""


def test_uow_statement_boundaries_reopen_old_or_complete_with_receipts(
    tmp_path: Path,
) -> None:
    """Every injected statement crash leaves no partial timeline projection."""
    template = build_m7_fixture(tmp_path / "uow-template")
    project_id = str(template.spec["project"]["id"])
    baseline = _event_chain_snapshot(template.root, project_id)
    repo_root = Path(__file__).resolve().parents[2]

    # Learn the complete observer trace once; each boundary is then exercised
    # in a fresh copy and retains the child log as first-class evidence.
    trace_log = tmp_path / "uow-trace.log"
    trace_root = tmp_path / "uow-trace-root"
    shutil.copytree(template.root, trace_root)
    trace_env = {**os.environ, "PYTHONPATH": str(repo_root)}
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _timeline_save_child(),
            str(trace_root),
            str(trace_log),
            "-1",
            project_id,
        ],
        cwd=repo_root,
        env=trace_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    trace = [json.loads(line) for line in trace_log.read_text(encoding="utf-8").splitlines()]
    assert trace and trace[-1]["kind"] == "commit"

    for boundary in range(len(trace)):
        crash_root = tmp_path / f"uow-crash-{boundary}"
        shutil.copytree(template.root, crash_root)
        log = tmp_path / f"uow-crash-{boundary}.log"
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                _timeline_save_child(),
                str(crash_root),
                str(log),
                str(boundary),
                project_id,
            ],
            cwd=repo_root,
            env=trace_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert child.returncode == 78, child.stderr
        records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert records and records[-1]["boundary"] == boundary

        after = _event_chain_snapshot(crash_root, project_id)
        if after == baseline:
            continue
        # A post-commit kill is accepted only as one complete command: the
        # receipt, event, projection, and every stream hash chain are present.
        assert after["receipt"] is not None
        assert after["timeline"] is not None
        assert "crash-complete" in str(after["timeline"])
        assert after["counts"] != baseline["counts"]
        assert all(summary[2] for summary in after["chains"])


def _migration_child() -> str:
    """Child process that hard-deads during one migration SQL statement."""
    return """import os
import sqlite3
import sys
from pathlib import Path

from astrid.core.store.writer import DatabaseWriter
from astrid.packs import build_standard_registry

database = Path(sys.argv[1])
log = Path(sys.argv[2])
needle = sys.argv[3]
real_connect = sqlite3.connect


class CrashConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        if needle in sql:
            with log.open("a", encoding="utf-8") as handle:
                handle.write(sql + "\\n")
                handle.flush()
            os._exit(78)
        return super().execute(sql, parameters)


def connect(*args, **kwargs):
    kwargs["factory"] = CrashConnection
    return real_connect(*args, **kwargs)


sqlite3.connect = connect
DatabaseWriter(database, build_standard_registry())
"""


def test_migration_statement_crashes_reopen_as_complete_schema(
    tmp_path: Path,
) -> None:
    """A hard-dead migration never leaves a partially applied catalog."""
    repo_root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "PYTHONPATH": str(repo_root)}
    for ordinal, needle in enumerate(("CREATE TABLE projects", "INSERT INTO schema_migrations")):
        root = tmp_path / f"migration-crash-{ordinal}"
        root.mkdir()
        database = root / ".astrid" / "astrid.sqlite3"
        database.parent.mkdir(parents=True)
        log = root / "migration-child.log"
        child = subprocess.run(
            [sys.executable, "-c", _migration_child(), str(database), str(log), needle],
            cwd=repo_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert child.returncode == 78, child.stderr
        assert needle in log.read_text(encoding="utf-8")

        composition = compose_standard_bridge(root)
        try:
            with composition.writer.read_only_connection() as connection:
                migrations = connection.execute(
                    "SELECT pack, version FROM schema_migrations ORDER BY pack, version"
                ).fetchall()
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            assert len(migrations) == 5
            assert {"projects", "events", "timelines", "shots", "project_references"} <= tables
        finally:
            composition.writer.close()
