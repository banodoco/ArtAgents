"""Writer and unit-of-work tests (m1 plan step 6, T14).

Focused tests for the dedicated single-writer service built by plan step 6
and the kernel unit of work built by plan step 7 (same batch): FIFO
callback serialization, separate read-only reads, typed busy and exception
propagation, deterministic drain and shutdown, no connection or transaction
escape, and the deterministic inability of concurrent semantic callers to
obtain parallel write transactions.
The concurrency tests are deterministic by construction: one writer thread
owns one connection and one FIFO queue, so a callback that is still running
physically blocks every later callback. Tests use ``threading.Event``
handshakes plus the opt-in statement observer to prove that two units of
work are strictly serialized (begin/commit of the first before begin/commit
of the second) and that a second semantic caller cannot even begin its
transaction while the first is open.

Plan step 7's deeper unit-of-work surface is extended by T16 in the same
file: exactly one BEGIN IMMEDIATE and one COMMIT across a full typed
command (event append + receipt insert), ROLLBACK statement observation,
rejection of direct transaction control and nested transactions, the
unavailability of commit/rollback/connection access, deterministic opt-in
statement observation (kind, SQL, and parameters) that never leaks into
later submissions, the absence of any environment-controlled crash switch,
and the remaining typed operation boundaries (query lists, unknown stream
sequence allocation/CAS, zero-match projections).
"""

from __future__ import annotations

import ast
import inspect
import os
import shutil
import sqlite3
import subprocess
import sys
import threading

import pytest

from astrid.core.store import uow as uow_module
from astrid.core.store import writer as writer_module
from astrid.core.store.uow import UnitOfWork, UoWError
from astrid.core.store.writer import (
    DatabaseWriter,
    TransactionControlError,
    WriterBusyError,
    WriterError,
    WriterShutdownError,
    WriterSidecarError,
)

TS = "2026-08-15T00:00:00.000000+00:00"


def _insert_project(
    executor, project_id: str, slug: str | None = None, name: str | None = None
) -> None:
    """Insert a minimal valid projects row through any typed executor."""
    executor.execute(
        "INSERT INTO projects (id, slug, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (project_id, slug or project_id, name or project_id, TS, TS),
    )


def _insert_stream(executor, stream_id: str, project_id: str) -> None:
    """Insert a minimal valid event_streams row through any typed executor."""
    executor.execute(
        "INSERT INTO event_streams "
        "(id, project_id, stream_type, aggregate_id, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (stream_id, project_id, "core.project", project_id, TS),
    )


@pytest.fixture
def writer(tmp_path, core_registry):
    """A fresh writer over a kernel-only database at ``<tmp>/writer.sqlite3``."""
    db_path = tmp_path / "writer.sqlite3"
    w = DatabaseWriter(db_path, core_registry)
    try:
        yield w
    finally:
        w.close()


# ---------------------------------------------------------------------------
# FIFO callback serialization
# ---------------------------------------------------------------------------


def test_submit_executes_callbacks_in_fifo_order(writer: DatabaseWriter) -> None:
    order: list[int] = []
    for index in range(50):
        writer.submit(lambda session, i=index: order.append(i))
    assert order == list(range(50))


def test_fifo_serialization_blocks_later_callbacks_until_earlier_finishes(
    writer: DatabaseWriter,
) -> None:
    started = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    order: list[str] = []

    def first(session) -> None:
        order.append("first-begin")
        started.set()
        release.wait(10)
        order.append("first-end")

    def second(session) -> None:
        second_started.set()
        order.append("second")

    t1 = threading.Thread(target=lambda: writer.submit(first))
    t1.start()
    assert started.wait(10)
    t2 = threading.Thread(target=lambda: writer.submit(second))
    t2.start()
    # The single writer thread is inside `first`; `second` cannot start.
    assert second_started.wait(0.5) is False
    release.set()
    t1.join(10)
    t2.join(10)
    assert order == ["first-begin", "first-end", "second"]


# ---------------------------------------------------------------------------
# Separate read-only reads
# ---------------------------------------------------------------------------


def test_read_only_connection_reads_committed_data_and_rejects_writes(
    writer: DatabaseWriter,
) -> None:
    writer.submit(lambda session: _insert_project(session, "proj-1"))
    writer_connection_ids: list[int] = []
    writer.submit(lambda session: writer_connection_ids.append(id(session._connection)))

    with writer.read_only_connection() as read_conn:
        # The read-only connection is a different object, never the writer's.
        assert id(read_conn) != writer_connection_ids[0]
        row = read_conn.execute(
            "SELECT slug FROM projects WHERE id = 'proj-1'"
        ).fetchone()
        assert row[0] == "proj-1"
        with pytest.raises(sqlite3.OperationalError):
            read_conn.execute(
                "INSERT INTO projects (id, slug, name, created_at, updated_at) "
                "VALUES ('x', 'x', 'X', ?, ?)",
                (TS, TS),
            )

    # The writer still works after the read-only connection closes.
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM projects")
    )
    assert count[0] == 1


# ---------------------------------------------------------------------------
# Busy and exception propagation
# ---------------------------------------------------------------------------


def test_writer_busy_error_is_typed_and_recovers_after_release(
    writer: DatabaseWriter, tmp_path
) -> None:
    external = sqlite3.connect(str(tmp_path / "writer.sqlite3"), isolation_level=None)
    try:
        external.execute("BEGIN IMMEDIATE")
        with pytest.raises(WriterBusyError):
            writer.submit(lambda session: _insert_project(session, "proj-busy"))
    finally:
        external.execute("ROLLBACK")
        external.close()

    # Once the external lock is released the writer works again.
    writer.submit(lambda session: _insert_project(session, "proj-ok"))
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM projects")
    )
    assert count[0] == 1


def test_callback_exception_propagates_unchanged(writer: DatabaseWriter) -> None:
    boom = ValueError("boom")
    with pytest.raises(ValueError) as excinfo:
        writer.submit(lambda session: (_ for _ in ()).throw(boom))
    assert excinfo.value is boom


def test_non_busy_sqlite_errors_propagate(writer: DatabaseWriter) -> None:
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        writer.submit(lambda session: session.execute("INSERT INTO missing (id) VALUES (1)"))


def test_sqlite_error_during_wal_replacement_is_typed_sidecar_failure(
    writer: DatabaseWriter, tmp_path
) -> None:
    """A SQLite error must not hide a simultaneous lost-WAL durability fault."""
    writer.submit(lambda session: _insert_project(session, "proj-before-race"))
    started = threading.Event()
    release = threading.Event()
    outcome: list[BaseException] = []

    def fail_after_replacement(_session) -> None:
        started.set()
        assert release.wait(10)
        raise sqlite3.OperationalError("synthetic disk I/O error")

    def submit() -> None:
        try:
            writer.submit(fail_after_replacement)
        except BaseException as exc:  # noqa: BLE001 - asserted below
            outcome.append(exc)

    thread = threading.Thread(target=submit)
    thread.start()
    try:
        assert started.wait(10)
        wal_path = tmp_path / "writer.sqlite3-wal"
        replacement = wal_path.with_suffix(".replacement")
        shutil.copyfile(wal_path, replacement)
        os.replace(replacement, wal_path)
    finally:
        release.set()
        thread.join(10)

    assert not thread.is_alive()
    assert len(outcome) == 1
    assert isinstance(outcome[0], WriterSidecarError)
    assert isinstance(outcome[0].__cause__, sqlite3.OperationalError)
    with pytest.raises(WriterSidecarError):
        writer.submit(lambda session: _insert_project(session, "proj-after-race"))


# ---------------------------------------------------------------------------
# Drain and shutdown behavior
# ---------------------------------------------------------------------------


def test_drain_waits_for_pending_work(writer: DatabaseWriter) -> None:
    started = threading.Event()
    release = threading.Event()
    finished: list[int] = []

    def slow(session) -> None:
        started.set()
        release.wait(10)
        finished.append(1)

    submitter = threading.Thread(target=lambda: writer.submit(slow))
    submitter.start()
    assert started.wait(10)

    drain_done = threading.Event()

    def drain_in_thread() -> None:
        writer.drain()
        drain_done.set()

    drainer = threading.Thread(target=drain_in_thread)
    drainer.start()
    # drain() must block while the pending callback is still running.
    assert drain_done.wait(0.5) is False
    release.set()
    submitter.join(10)
    assert drain_done.wait(10)
    assert finished == [1]


def test_close_drains_pending_work_and_is_idempotent(writer: DatabaseWriter) -> None:
    executed: list[int] = []
    for index in range(3):
        writer.submit(lambda session, i=index: executed.append(i))
    writer.close()
    assert executed == [0, 1, 2]
    assert writer.closed is True
    writer.close()  # idempotent: must not raise


def test_submit_after_close_raises_shutdown_error(writer: DatabaseWriter) -> None:
    writer.close()
    with pytest.raises(WriterShutdownError):
        writer.submit(lambda session: 1)


# ---------------------------------------------------------------------------
# No connection or transaction escape
# ---------------------------------------------------------------------------


def test_writer_session_exposes_no_connection_or_transaction_escape(
    writer: DatabaseWriter,
) -> None:
    captured: dict[str, object] = {}

    def probe(session) -> None:
        captured["public"] = sorted(
            name for name in dir(session) if not name.startswith("_")
        )
        captured["has_connection"] = hasattr(session, "connection")
        captured["has_commit"] = hasattr(session, "commit")
        captured["has_rollback"] = hasattr(session, "rollback")

    writer.submit(probe)
    assert captured["public"] == ["execute", "in_transaction", "query", "query_one"]
    assert captured["has_connection"] is False
    assert captured["has_commit"] is False
    assert captured["has_rollback"] is False


def test_writer_session_rejects_transaction_control_statements(
    writer: DatabaseWriter,
) -> None:
    rejected: list[str] = []

    def probe(session) -> None:
        for sql in (
            "BEGIN IMMEDIATE",
            "  BEGIN",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT x",
            "RELEASE x",
        ):
            try:
                session.execute(sql)
            except TransactionControlError:
                rejected.append(sql)
        # Comments before the keyword are still rejected.
        try:
            session.execute("-- note\nBEGIN IMMEDIATE")
        except TransactionControlError:
            rejected.append("-- note\\nBEGIN IMMEDIATE")
        # Ordinary DML still works.
        _insert_project(session, "proj-tx")

    writer.submit(probe)
    assert rejected == [
        "BEGIN IMMEDIATE",
        "  BEGIN",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT x",
        "RELEASE x",
        "-- note\\nBEGIN IMMEDIATE",
    ]
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM projects")
    )
    assert count[0] == 1


def test_direct_transaction_transitions_reject_invalid_use(
    writer: DatabaseWriter,
) -> None:
    """Commit/rollback without an active transaction and double-begin fail.

    The writer session's transaction transitions are kernel-owned; even the
    private methods refuse invalid transitions with the typed
    TransactionControlError, so no callback can end or start a transaction
    it does not own.
    """

    def probe(session) -> None:
        with pytest.raises(TransactionControlError, match="no active transaction"):
            session._commit()
        with pytest.raises(TransactionControlError, match="no active transaction"):
            session._rollback()
        # A lone begin starts a transaction the callback cannot commit.
        session._begin_immediate()
        try:
            with pytest.raises(
                TransactionControlError, match="within a transaction"
            ):
                session._begin_immediate()
        finally:
            session._rollback()  # return the connection to a clean state
        assert session.in_transaction is False

    writer.submit(probe)
    # The writer still works normally afterwards.
    writer.submit(lambda session: _insert_project(session, "proj-tx2"))
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM projects")
    )
    assert count[0] == 1


# ---------------------------------------------------------------------------
# Unit of work envelope: exactly one BEGIN IMMEDIATE, commit, rollback
# ---------------------------------------------------------------------------


def test_uow_wraps_callback_in_exactly_one_begin_immediate(
    writer: DatabaseWriter,
) -> None:
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
    )
    result = uow.run(
        lambda u: (
            _insert_project(u, "proj-uow"),
            u.next_project_seq("proj-uow"),
        )
    )
    assert result[1] == 1
    kinds = [kind for kind, _ in observed]
    assert kinds == ["begin_immediate", "statement", "statement", "commit"]
    head = writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = 'proj-uow'"
        )
    )
    assert head[0] == 1


def test_uow_exactly_one_begin_and_one_commit_across_typed_command(
    writer: DatabaseWriter,
) -> None:
    """A full typed command still runs in exactly one BEGIN IMMEDIATE.

    Event append plus receipt insert plus projection update all execute
    inside the single transaction the unit of work owns: the observer sees
    exactly one ``begin_immediate`` at the front, exactly one ``commit`` at
    the end, and no rollback.
    """
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
    )
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-full"),
            _insert_stream(session, "stream-full", "proj-full"),
        )
    )
    uow.run(
        lambda u: (
            u.append_event(
                stream_id="stream-full",
                project_id="proj-full",
                event_id="ev-full",
                subject_type="core.project",
                subject_id="proj-full",
                changes_json="[]",
                kind="core.project.created",
                schema_version=1,
                idempotency_key="k-full",
                txn_id="txn-full",
                actor_kind="local",
                payload_json='{"data": {}}',
                created_at=TS,
            ),
            u.insert_receipt(
                project_id="proj-full",
                idempotency_key="k-full",
                request_hash="hash-full",
                command_kind="core.project.create",
                txn_id="txn-full",
                primary_stream_id="stream-full",
                resulting_stream_seq=1,
                first_project_seq=1,
                last_project_seq=1,
                event_ids_json='["ev-full"]',
                result_json='{"ok": true}',
                created_at=TS,
            ),
            u.update_projection(
                "projects", {"name": "Full"}, {"id": "proj-full"}
            ),
        )
    )
    kinds = [kind for kind, _ in observed]
    assert kinds.count("begin_immediate") == 1
    assert kinds.count("commit") == 1
    assert kinds.count("rollback") == 0
    assert kinds[0] == "begin_immediate"
    assert kinds[-1] == "commit"
    assert observed[0][1] == "BEGIN IMMEDIATE"
    assert observed[-1][1] == "COMMIT"


def test_uow_rolls_back_on_callback_exception(writer: DatabaseWriter) -> None:
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
    )
    with pytest.raises(RuntimeError, match="abort"):
        uow.run(
            lambda u: (
                _insert_project(u, "proj-rollback"),
                (_ for _ in ()).throw(RuntimeError("abort")),
            )
        )
    kinds = [kind for kind, _ in observed]
    assert kinds == ["begin_immediate", "statement", "rollback"]
    row = writer.submit(
        lambda session: session.query_one(
            "SELECT id FROM projects WHERE id = 'proj-rollback'"
        )
    )
    assert row is None


def test_uow_rollback_observes_rollback_statement_and_reverts_all_state(
    writer: DatabaseWriter,
) -> None:
    """Rollback is observed as a real ROLLBACK statement and reverts all rows.

    Event append and receipt insert inside the failed callback leave zero
    events, zero receipts, and unchanged project and stream heads — the
    whole typed command is atomic.
    """
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
    )
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-rb2"),
            _insert_stream(session, "stream-rb2", "proj-rb2"),
        )
    )
    with pytest.raises(RuntimeError, match="abort"):
        uow.run(
            lambda u: (
                u.append_event(
                    stream_id="stream-rb2",
                    project_id="proj-rb2",
                    event_id="ev-rb2",
                    subject_type="core.project",
                    subject_id="proj-rb2",
                    changes_json="[]",
                    kind="core.project.created",
                    schema_version=1,
                    idempotency_key="k-rb2",
                    txn_id="txn-rb2",
                    actor_kind="local",
                    payload_json='{"data": {}}',
                    created_at=TS,
                ),
                u.insert_receipt(
                    project_id="proj-rb2",
                    idempotency_key="k-rb2",
                    request_hash="hash-rb2",
                    command_kind="core.project.create",
                    txn_id="txn-rb2",
                    primary_stream_id="stream-rb2",
                    resulting_stream_seq=1,
                    first_project_seq=1,
                    last_project_seq=1,
                    event_ids_json='["ev-rb2"]',
                    result_json='{"ok": true}',
                    created_at=TS,
                ),
                (_ for _ in ()).throw(RuntimeError("abort")),
            )
        )
    assert observed[-1] == ("rollback", "ROLLBACK")
    event_count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM events")
    )
    receipt_count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM command_receipts")
    )
    project_head = writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = 'proj-rb2'"
        )
    )
    stream_head = writer.submit(
        lambda session: session.query_one(
            "SELECT head_seq FROM event_streams WHERE id = 'stream-rb2'"
        )
    )
    assert event_count[0] == 0
    assert receipt_count[0] == 0
    assert project_head[0] == 0
    assert stream_head[0] == 0


def test_statement_observer_receives_kind_sql_and_parameters(
    writer: DatabaseWriter,
) -> None:
    """The opt-in observer sees exact (kind, sql, parameters) triples."""
    observed: list[tuple[str, str, tuple]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql, params))
    )
    uow.run(
        lambda u: u.execute(
            "INSERT INTO projects (id, slug, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("proj-obs", "proj-obs", "Observed", TS, TS),
        )
    )
    assert observed[0][0] == "begin_immediate"
    statement = observed[1]
    assert statement[0] == "statement"
    assert "INSERT INTO projects" in statement[1]
    assert statement[2] == ("proj-obs", "proj-obs", "Observed", TS, TS)
    assert observed[-1][0] == "commit"


def test_statement_observation_does_not_leak_after_run(writer: DatabaseWriter) -> None:
    """The observer is opt-in per unit of work and never leaks sideways.

    After a run with an observer completes, a later plain submission (even
    one that executes SQL) produces no observation events.
    """
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
    )
    uow.run(lambda u: _insert_project(u, "proj-ob1"))
    assert observed, "observer must fire during the observed run"
    observed.clear()
    writer.submit(lambda session: _insert_project(session, "proj-ob2"))
    assert observed == []


def test_nested_uow_from_inside_callback_is_rejected(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    nested = UnitOfWork(writer)
    with pytest.raises(WriterError, match="writer thread"):
        uow.run(lambda u: nested.run(lambda inner: 1))


def test_uow_rejects_active_transaction_from_inside_callback(
    writer: DatabaseWriter,
) -> None:
    """The unit of work refuses to run while a transaction is already active.

    Exercises the UoW-level nesting guard directly: even if a callback
    somehow reached the private execute path with a transaction already
    open, the typed UoWError is raised and the outer transaction is
    unaffected.
    """
    uow = UnitOfWork(writer)

    def probe(session) -> None:
        session._begin_immediate()  # simulate an already-open transaction
        try:
            with pytest.raises(UoWError, match="nested unit of work"):
                uow._execute(session, lambda inner: "inner")
        finally:
            session._rollback()

    writer.submit(probe)


def test_rejected_nested_uow_leaves_outer_transaction_intact(
    writer: DatabaseWriter,
) -> None:
    """A rejected nested run does not corrupt the outer unit of work.

    The outer callback continues, commits normally, and the observer still
    records exactly one begin/commit pair for the whole command.
    """
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
    )
    nested = UnitOfWork(writer)

    def outer(u: UnitOfWork) -> str:
        _insert_project(u, "proj-outer")
        with pytest.raises(WriterError, match="writer thread"):
            nested.run(lambda inner: 1)
        _insert_project(u, "proj-outer2")
        return "outer-done"

    assert uow.run(outer) == "outer-done"
    kinds = [kind for kind, _ in observed]
    assert kinds == ["begin_immediate", "statement", "statement", "commit"]
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM projects")
    )
    assert count[0] == 2


def test_uow_typed_operations_require_active_run(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    with pytest.raises(UoWError, match="not active"):
        uow.query("SELECT 1")
    with pytest.raises(UoWError, match="not active"):
        uow.next_project_seq("proj-x")
    with pytest.raises(UoWError, match="not active"):
        uow.update_projection("projects", {"name": "x"}, {"id": "proj-x"})


def test_uow_exposes_only_typed_operations(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    public = sorted(name for name in dir(uow) if not name.startswith("_"))
    assert public == [
        "append_event",
        "cas_stream_head",
        "execute",
        "find_receipt",
        "insert_receipt",
        "next_project_seq",
        "next_stream_seq",
        "query",
        "query_one",
        "run",
        "update_projection",
    ]
    assert not hasattr(uow, "session")
    assert not hasattr(uow, "connection")


# ---------------------------------------------------------------------------
# Typed unit-of-work operations
# ---------------------------------------------------------------------------


def test_uow_sequence_allocation_is_gap_free(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    writer.submit(lambda session: _insert_project(session, "proj-seq"))
    seqs = uow.run(
        lambda u: (u.next_project_seq("proj-seq"), u.next_project_seq("proj-seq"))
    )
    assert seqs == (1, 2)
    head = writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = 'proj-seq'"
        )
    )
    assert head[0] == 2


def test_uow_sequence_allocation_rejects_unknown_project(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    with pytest.raises(UoWError, match="unknown project"):
        uow.run(lambda u: u.next_project_seq("missing"))


def test_uow_stream_sequence_allocation_rejects_unknown_stream(
    writer: DatabaseWriter,
) -> None:
    uow = UnitOfWork(writer)
    writer.submit(lambda session: _insert_project(session, "proj-sseq"))
    with pytest.raises(UoWError, match="unknown stream"):
        uow.run(lambda u: u.next_stream_seq("missing-stream"))


def test_uow_query_and_execute_typed_paths(writer: DatabaseWriter) -> None:
    """``query`` returns every row and ``execute`` returns a usable cursor."""
    uow = UnitOfWork(writer)
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-q1", name="Alpha"),
            _insert_project(session, "proj-q2", name="Beta"),
        )
    )
    rows = uow.run(
        lambda u: u.query(
            "SELECT id, name FROM projects ORDER BY id"
        )
    )
    assert [(row["id"], row["name"]) for row in rows] == [
        ("proj-q1", "Alpha"),
        ("proj-q2", "Beta"),
    ]
    cursor = uow.run(
        lambda u: u.execute(
            "UPDATE projects SET name = ? WHERE id = ?",
            ("Gamma", "proj-q1"),
        )
    )
    assert cursor.rowcount == 1
    renamed = uow.run(lambda u: u.query_one(
        "SELECT name FROM projects WHERE id = 'proj-q1'"
    ))
    assert renamed[0] == "Gamma"


def test_uow_stream_cas_succeeds_and_fails_without_mutation(
    writer: DatabaseWriter,
) -> None:
    uow = UnitOfWork(writer)
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-cas"),
            _insert_stream(session, "stream-cas", "proj-cas"),
        )
    )
    assert uow.run(lambda u: u.cas_stream_head("stream-cas", 0, 1)) is True
    assert uow.run(lambda u: u.cas_stream_head("stream-cas", 0, 5)) is False
    head = writer.submit(
        lambda session: session.query_one(
            "SELECT head_seq FROM event_streams WHERE id = 'stream-cas'"
        )
    )
    assert head[0] == 1


def test_uow_stream_cas_unknown_stream_returns_false(
    writer: DatabaseWriter,
) -> None:
    """CAS on a missing stream fails without mutation, never raises."""
    uow = UnitOfWork(writer)
    writer.submit(lambda session: _insert_project(session, "proj-cas2"))
    assert uow.run(lambda u: u.cas_stream_head("missing-stream", 0, 1)) is False
    missing = writer.submit(
        lambda session: session.query_one(
            "SELECT id FROM event_streams WHERE id = 'missing-stream'"
        )
    )
    assert missing is None


def test_uow_update_projection_zero_match_returns_zero(
    writer: DatabaseWriter,
) -> None:
    """A projection update with no matching row reports zero changes."""
    uow = UnitOfWork(writer)
    writer.submit(lambda session: _insert_project(session, "proj-nomatch"))
    changed = uow.run(
        lambda u: u.update_projection(
            "projects", {"name": "X"}, {"id": "no-such-project"}
        )
    )
    assert changed == 0
    name = writer.submit(
        lambda session: session.query_one(
            "SELECT name FROM projects WHERE id = 'proj-nomatch'"
        )
    )
    assert name[0] == "proj-nomatch"


def test_uow_append_event_advances_heads_atomically(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-ev"),
            _insert_stream(session, "stream-ev", "proj-ev"),
        )
    )
    seqs = uow.run(
        lambda u: u.append_event(
            stream_id="stream-ev",
            project_id="proj-ev",
            event_id="ev-1",
            subject_type="core.project",
            subject_id="proj-ev",
            changes_json="[]",
            kind="core.project.created",
            schema_version=1,
            idempotency_key="k-ev-1",
            txn_id="txn-1",
            actor_kind="local",
            payload_json='{"data": {}}',
            created_at=TS,
        )
    )
    assert seqs == (1, 1)
    row = writer.submit(
        lambda session: session.query_one(
            "SELECT project_seq, seq, kind FROM events WHERE event_id = 'ev-1'"
        )
    )
    assert (row[0], row[1], row[2]) == (1, 1, "core.project.created")
    project_head = writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = 'proj-ev'"
        )
    )
    stream_head = writer.submit(
        lambda session: session.query_one(
            "SELECT head_seq FROM event_streams WHERE id = 'stream-ev'"
        )
    )
    assert project_head[0] == 1
    assert stream_head[0] == 1


def test_uow_append_event_rolls_back_event_and_heads(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-ev2"),
            _insert_stream(session, "stream-ev2", "proj-ev2"),
        )
    )
    with pytest.raises(RuntimeError, match="abort"):
        uow.run(
            lambda u: (
                u.append_event(
                    stream_id="stream-ev2",
                    project_id="proj-ev2",
                    event_id="ev-2",
                    subject_type="core.project",
                    subject_id="proj-ev2",
                    changes_json="[]",
                    kind="core.project.created",
                    schema_version=1,
                    idempotency_key="k-ev-2",
                    txn_id="txn-2",
                    actor_kind="local",
                    payload_json='{"data": {}}',
                    created_at=TS,
                ),
                (_ for _ in ()).throw(RuntimeError("abort")),
            )
        )
    event_count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM events")
    )
    assert event_count[0] == 0
    project_head = writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = 'proj-ev2'"
        )
    )
    stream_head = writer.submit(
        lambda session: session.query_one(
            "SELECT head_seq FROM event_streams WHERE id = 'stream-ev2'"
        )
    )
    assert project_head[0] == 0
    assert stream_head[0] == 0


def test_uow_update_projection_and_receipt_operations(writer: DatabaseWriter) -> None:
    uow = UnitOfWork(writer)
    writer.submit(lambda session: _insert_project(session, "proj-r"))
    changed = uow.run(
        lambda u: u.update_projection("projects", {"name": "Renamed"}, {"id": "proj-r"})
    )
    assert changed == 1
    name = writer.submit(
        lambda session: session.query_one(
            "SELECT name FROM projects WHERE id = 'proj-r'"
        )
    )
    assert name[0] == "Renamed"

    assert uow.run(lambda u: u.find_receipt("proj-r", "k-r")) is None
    uow.run(
        lambda u: u.insert_receipt(
            project_id="proj-r",
            idempotency_key="k-r",
            request_hash="hash-1",
            command_kind="core.project.create",
            txn_id="txn-r",
            primary_stream_id=None,
            resulting_stream_seq=None,
            first_project_seq=1,
            last_project_seq=1,
            event_ids_json="[]",
            result_json='{"ok": true}',
            created_at=TS,
        )
    )
    receipt = uow.run(lambda u: u.find_receipt("proj-r", "k-r"))
    assert receipt is not None
    assert receipt["request_hash"] == "hash-1"
    assert receipt["command_kind"] == "core.project.create"


def test_uow_update_projection_rejects_invalid_identifiers(
    writer: DatabaseWriter,
) -> None:
    uow = UnitOfWork(writer)
    with pytest.raises(UoWError, match="invalid SQL identifier"):
        uow.run(
            lambda u: u.update_projection(
                "projects; DROP TABLE events", {"name": "x"}, {"id": "proj-r"}
            )
        )


# ---------------------------------------------------------------------------
# Concurrent semantic callers never obtain parallel write transactions
# ---------------------------------------------------------------------------


def test_concurrent_semantic_callers_never_get_parallel_write_transactions(
    writer: DatabaseWriter,
) -> None:
    markers: list[tuple[str, str]] = []
    uow = UnitOfWork(
        writer, on_statement=lambda kind, sql, params: markers.append((kind, sql))
    )
    started = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    results: dict[str, str] = {}

    def first(u: UnitOfWork) -> str:
        markers.append(("cb1", "begin"))
        started.set()
        release.wait(10)
        _insert_project(u, "proj-c1")
        markers.append(("cb1", "end"))
        return "first"

    def second(u: UnitOfWork) -> str:
        second_started.set()
        _insert_project(u, "proj-c2")
        return "second"

    t1 = threading.Thread(target=lambda: results.update(t1=uow.run(first)))
    t1.start()
    assert started.wait(10)
    t2 = threading.Thread(target=lambda: results.update(t2=uow.run(second)))
    t2.start()
    # While the first transaction is still open, the second semantic caller
    # must not even begin its callback, let alone its transaction: the one
    # writer thread is inside `first`.
    assert second_started.wait(0.5) is False
    release.set()
    t1.join(10)
    t2.join(10)
    assert results == {"t1": "first", "t2": "second"}

    # Transaction boundaries are strictly serialized: begin+commit of the
    # first unit of work, then begin+commit of the second. Never parallel.
    transaction_events = [
        kind for kind, _ in markers if kind in ("begin_immediate", "commit", "rollback")
    ]
    assert transaction_events == [
        "begin_immediate",
        "commit",
        "begin_immediate",
        "commit",
    ]

    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM projects")
    )
    assert count[0] == 2


def test_concurrent_uow_increments_are_serialized_without_lost_updates(
    writer: DatabaseWriter,
) -> None:
    uow = UnitOfWork(writer)
    writer.submit(lambda session: _insert_project(session, "counter", name="0"))
    errors: list[BaseException] = []

    def increment(u: UnitOfWork) -> None:
        row = u.query_one("SELECT name FROM projects WHERE id = 'counter'")
        u.update_projection(
            "projects", {"name": str(int(row[0]) + 1)}, {"id": "counter"}
        )

    def worker() -> None:
        try:
            for _ in range(10):
                uow.run(increment)
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert not errors
    final = writer.submit(
        lambda session: session.query_one(
            "SELECT name FROM projects WHERE id = 'counter'"
        )
    )
    assert final[0] == "60"


# ---------------------------------------------------------------------------
# No environment-triggered production crash switches (T16)
# ---------------------------------------------------------------------------


def test_no_environment_controlled_crash_switches_in_kernel_store(
    writer: DatabaseWriter,
) -> None:
    """The writer/UoW kernel has no environment-controlled crash behavior.

    Static scan: neither the writer nor the unit-of-work module reads the
    process environment (no ``environ``/``getenv``), so no environment
    variable can flip production behavior. Behavioral check: plausible
    crash-switch variables set in the environment leave a normal unit of
    work completely unchanged — it still commits exactly once.
    """
    source = inspect.getsource(uow_module) + inspect.getsource(writer_module)
    # Scan executable code only (docstrings may mention the word
    # "environment"): no os.environ attribute access, no environ/getenv
    # name, no ASTRID_-prefixed string literal anywhere.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv"):
            raise AssertionError(f"kernel store reads the environment: {node.attr}")
        if isinstance(node, ast.Name) and node.id in ("environ", "getenv"):
            raise AssertionError(f"kernel store reads the environment: {node.id}")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "ASTRID_" in node.value
        ):
            raise AssertionError("kernel store contains an ASTRID_ switch")

    monkeypatch = pytest.MonkeyPatch()
    for name in (
        "ASTRID_CRASH_AFTER_STATEMENT",
        "ASTRID_STATEMENT_CRASH",
        "ASTRID_UOW_CRASH",
    ):
        monkeypatch.setenv(name, "1")
    try:
        observed: list[tuple[str, str]] = []
        uow = UnitOfWork(
            writer, on_statement=lambda kind, sql, params: observed.append((kind, sql))
        )
        result = uow.run(
            lambda u: (
                _insert_project(u, "proj-env"),
                u.next_project_seq("proj-env"),
            )
        )
        assert result[1] == 1
        kinds = [kind for kind, _ in observed]
        assert kinds == ["begin_immediate", "statement", "statement", "commit"]
    finally:
        monkeypatch.undo()
    head = writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = 'proj-env'"
        )
    )
    assert head[0] == 1


def test_writer_fails_closed_when_wal_replaced_beneath_it(
    writer: DatabaseWriter, tmp_path
) -> None:
    """A foreign writable close unlinks the WAL; later writes must fail.

    Regression (phase-b): a foreign process (CLI, doctor, backup, external
    tooling) opening the database read-write and closing cleanly while the
    long-lived writer sits idle deletes ``-wal``/``-shm`` out from under the
    writer's connection. The writer used to keep committing into the
    orphaned inode: every COMMIT reported success while no reader could ever
    observe the rows — the serve HTTP save path returned ``200`` with an
    incremented ``config_version`` but wrote nothing durable. The writer now
    verifies the WAL identity before each callback and raises the typed
    :class:`WriterSidecarError` instead of lying.
    """
    writer.submit(
        lambda session: _insert_project(session, "proj-sidecar")
    )
    db_path = str(tmp_path / "writer.sqlite3")
    # The bridge's read path churns separate read-only connections
    # (``open_database(read_only=True)`` probe + ``mode=ro`` open/close).
    with writer.read_only_connection() as read_conn:
        read_conn.execute("SELECT COUNT(*) FROM projects").fetchone()
    # A foreign process (CLI, doctor, backup, external tooling) then opens
    # the database read-write and closes cleanly. SQLite builds differ on
    # whether that close unlinks a WAL while another connection is open, so
    # explicitly remove the sidecar after exercising the foreign-open path.
    foreign_code = (
        "import sqlite3; "
        f"c = sqlite3.connect({db_path!r}); "
        "c.execute('SELECT COUNT(*) FROM projects').fetchone(); "
        "c.close()"
    )
    subprocess.run(
        [sys.executable, "-c", foreign_code], check=True, timeout=60
    )
    wal_path = db_path + "-wal"
    assert os.path.exists(wal_path)
    replacement_path = wal_path + ".replacement"
    shutil.copyfile(wal_path, replacement_path)
    os.replace(replacement_path, wal_path)
    assert os.path.exists(wal_path)

    # The next submission must fail closed instead of committing into the
    # orphaned inode.
    with pytest.raises(WriterSidecarError):
        writer.submit(
            lambda session: _insert_project(session, "proj-after-poison")
        )
    # Fail closed means fail durably: no partial rows from the poisoned
    # attempt, and every later submission fails the same way.
    with pytest.raises(WriterSidecarError):
        writer.submit(
            lambda session: session.query_one(
                "SELECT 1 FROM projects WHERE id LIKE 'proj-after-poison%'"
            )
        )
    # Every later submission keeps failing closed.
    with pytest.raises(WriterSidecarError):
        writer.submit(lambda session: _insert_project(session, "proj-again"))
    # And nothing from the poisoned window reached durable state: verified
    # through a separate read-only connection, never the poisoned writer.
    external = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        count = external.execute(
            "SELECT COUNT(*) FROM projects WHERE id LIKE 'proj-after%'"
        ).fetchone()[0]
    finally:
        external.close()
    assert count == 0
