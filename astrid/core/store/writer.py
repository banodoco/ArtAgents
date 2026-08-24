"""Dedicated single-writer SQLite service with FIFO submission.

(m1 plan step 6.) One writer thread owns exactly one writable ``sqlite3``
connection opened through :func:`astrid.core.store.database.open_database`.
Repository callers submit short synchronous command callbacks via
:meth:`DatabaseWriter.submit`; the writer thread executes them in FIFO order
and returns the result (or re-raises the callback's exception) to the
submitting caller. The owned connection never escapes the writer thread:
callbacks receive only a :class:`WriterSession` facade with typed query and
execute operations and no path back to the connection object.

Design rules kept here:

- One writer thread, one owned connection, one FIFO queue
  (``queue.Queue``, so submission order is execution order).
- ``submit()`` is synchronous: it blocks until the callback completes and
  surfaces the callback's exception unchanged, except that SQLite busy
  errors (``database is locked`` / ``database table is locked``) are
  translated to the typed :class:`WriterBusyError` so callers never depend
  on driver-specific messages.
- Submissions after :meth:`DatabaseWriter.close` raise the typed
  :class:`WriterShutdownError`.
- :meth:`DatabaseWriter.close` deterministically drains the queue, stops
  the writer thread, and closes the owned connection; the connection is
  touched only by the writer thread, including its final close.
- Read traffic never shares the write connection:
  :meth:`DatabaseWriter.read_only_connection` yields a separate read-only
  connection opened through the nonmutating read-only open path.

This module never imports the capability-pack loader or discovery
machinery and never hands the write connection (or any ``sqlite3``
connection) to callers. Transaction control (BEGIN/COMMIT/ROLLBACK) is
owned by the kernel unit of work (plan step 7), never by writer callers:
the session rejects transaction-control statements with the typed
:class:`TransactionControlError`, and callbacks that submit work from the
writer thread are rejected up front (they would deadlock the FIFO queue).
When a unit of work is active, an opt-in statement observer
(``on_statement`` on the unit of work) is notified after every SQL
statement boundary, including BEGIN IMMEDIATE/COMMIT/ROLLBACK, so tests
can observe the exact transaction shape without any environment switch.

Rows returned by the session are ``sqlite3.Row`` objects (the writer
connection uses ``row_factory = sqlite3.Row``), so callers may address
columns by name or position.
"""

from __future__ import annotations

import os
import queue
import sqlite3
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry
from astrid.core.store.database import open_database

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WriterError(RuntimeError):
    """Base error for the dedicated single-writer service."""


class WriterBusyError(WriterError):
    """Raised when a write callback hit the SQLite busy timeout.

    The configured ``busy_timeout`` bounds lock contention; when SQLite
    still reports a locked database after that bound, this typed error is
    raised to the submitting caller.
    """


class WriterShutdownError(WriterError):
    """Raised when work is submitted after the writer has been closed."""


class TransactionControlError(WriterError):
    """Raised when a caller attempts to control transactions directly.

    Transaction control (BEGIN IMMEDIATE / COMMIT / ROLLBACK / SAVEPOINT /
    RELEASE) is owned by the kernel unit of work. The writer session
    rejects such statements, and its private transaction methods raise
    this error on invalid transitions (begin-within-transaction, or
    commit/rollback with no active transaction).
    """


class WriterSidecarError(WriterError):
    """Raised when the WAL sidecar was replaced beneath the live writer.

    SQLite deletes ``-wal``/``-shm`` on the clean close of a writable
    connection. When a *foreign* process (CLI, doctor, backup, external
    tooling) opens the database read-write and closes cleanly while the
    long-lived serve writer sits idle between transactions, that close
    unlinks the very WAL file the writer connection has open. The writer
    then keeps committing into the orphaned inode: every COMMIT reports
    success, but no new reader can ever observe the rows — invisible
    divergence until restart.

    The writer therefore verifies the WAL's file identity before each
    submitted callback and fails closed with this typed error once the
    sidecar no longer backs its connection, converting the silent loss
    into a visible failure. Restarting the process reattaches a fresh
    writer to the current database files.
    """


# Statements that would seize or release transaction control. Any SQL
# whose first keyword is one of these is rejected on the writer session.
_TRANSACTION_CONTROL_KEYWORDS: frozenset[str] = frozenset(
    {"begin", "commit", "end", "rollback", "savepoint", "release"}
)


def _first_statement_keyword(sql: str) -> str | None:
    """Return the lowercased first keyword of ``sql``, skipping comments."""
    text = sql
    while True:
        text = text.lstrip()
        if text.startswith("--"):
            newline = text.find("\n")
            if newline == -1:
                return None
            text = text[newline + 1 :]
            continue
        if text.startswith("/*"):
            close = text.find("*/")
            if close == -1:
                return None
            text = text[close + 2 :]
            continue
        break
    if not text:
        return None
    return text.split(None, 1)[0].lower()


class _Sentinel:
    """Unique marker used to stop the writer thread (never a work item)."""


_SENTINEL = _Sentinel()


# ---------------------------------------------------------------------------
# Non-escaping session facade
# ---------------------------------------------------------------------------


class WriterSession:
    """Typed, non-escaping facade over the writer's owned connection.

    Exposes exactly the query/execute operations callbacks need. There is
    deliberately no public attribute that yields the underlying
    ``sqlite3.Connection``: the connection is owned by the writer thread and
    transaction control is owned by the kernel unit of work (plan step 7).
    Transaction-control statements (BEGIN/COMMIT/ROLLBACK/SAVEPOINT/
    RELEASE) are rejected with :class:`TransactionControlError`.

    Rows are ``sqlite3.Row`` objects (the writer connection uses
    ``row_factory = sqlite3.Row``).
    """

    __slots__ = (
        "_connection",
        "_in_transaction",
        "_statement_observer",
    )

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._in_transaction = False
        self._statement_observer: Callable[[str, str, tuple[Any, ...]], None] | None = None

    # -- public typed operations ----------------------------------------

    def execute(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> sqlite3.Cursor:
        """Execute one statement on the writer's connection.

        The connection runs in autocommit (``isolation_level=None``); the
        unit of work owns explicit transaction boundaries. Returns the
        cursor so callers can read ``lastrowid``/``rowcount``.
        """
        self._check_transaction_control(sql)
        cursor = self._connection.execute(sql, parameters)
        self._notify("statement", sql, parameters)
        return cursor

    def query(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        """Execute one read statement and return every row."""
        self._check_transaction_control(sql)
        rows = self._connection.execute(sql, parameters).fetchall()
        self._notify("statement", sql, parameters)
        return rows

    def query_one(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> sqlite3.Row | None:
        """Execute one read statement and return its first row or ``None``."""
        self._check_transaction_control(sql)
        row = self._connection.execute(sql, parameters).fetchone()
        self._notify("statement", sql, parameters)
        return row

    @property
    def in_transaction(self) -> bool:
        """Whether a BEGIN IMMEDIATE unit of work is active on this session.

        Read-only observation for the unit of work's nesting guard; there
        is no public way to start or end a transaction from a callback.
        """
        return self._in_transaction

    # -- private transaction control (kernel unit of work only) ---------

    def _begin_immediate(self) -> None:
        """Begin exactly one ``BEGIN IMMEDIATE`` transaction (UoW only)."""
        if self._in_transaction:
            raise TransactionControlError(
                "cannot begin a transaction within a transaction"
            )
        self._connection.execute("BEGIN IMMEDIATE")
        self._in_transaction = True
        self._notify("begin_immediate", "BEGIN IMMEDIATE", ())

    def _commit(self) -> None:
        """Commit the active transaction (UoW only)."""
        if not self._in_transaction:
            raise TransactionControlError("no active transaction to commit")
        self._connection.execute("COMMIT")
        self._in_transaction = False
        self._notify("commit", "COMMIT", ())

    def _rollback(self) -> None:
        """Roll back the active transaction (UoW only)."""
        if not self._in_transaction:
            raise TransactionControlError("no active transaction to roll back")
        self._connection.execute("ROLLBACK")
        self._in_transaction = False
        self._notify("rollback", "ROLLBACK", ())

    # -- private statement observation -----------------------------------

    def _set_statement_observer(
        self, observer: Callable[[str, str, tuple[Any, ...]], None]
    ) -> None:
        """Opt-in statement observer installed by the unit of work."""
        self._statement_observer = observer

    def _clear_statement_observer(self) -> None:
        self._statement_observer = None

    def _notify(
        self, kind: str, sql: str, parameters: Sequence[Any]
    ) -> None:
        observer = self._statement_observer
        if observer is not None:
            observer(kind, sql, tuple(parameters))

    # -- private helpers --------------------------------------------------

    def _check_transaction_control(self, sql: str) -> None:
        keyword = _first_statement_keyword(sql)
        if keyword in _TRANSACTION_CONTROL_KEYWORDS:
            raise TransactionControlError(
                "transaction control is kernel-owned: "
                f"{keyword.upper()} is not allowed on the writer session"
            )


# ---------------------------------------------------------------------------
# Work items
# ---------------------------------------------------------------------------


@dataclass
class _WorkItem:
    """One submitted callback plus its completion state.

    ``done`` is set exactly once by the writer thread, so ``submit()`` can
    block synchronously and then read ``result``/``error`` without races.
    """

    callback: Callable[[WriterSession], Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None


# ---------------------------------------------------------------------------
# The writer service
# ---------------------------------------------------------------------------


class DatabaseWriter:
    """Dedicated writer thread with one owned SQLite connection.

    Usage::

        writer = DatabaseWriter(path, registry)
        result = writer.submit(lambda session: session.query_one(
            "SELECT slug FROM projects WHERE id = ?", (project_id,)
        ))
        with writer.read_only_connection() as read_conn:
            ...
        writer.close()

    The writable connection is opened (and pending migrations applied) at
    construction time, so construction fails fast on incompatible schemas.
    ``close()`` must be called from outside the writer thread.
    """

    def __init__(
        self, path: str | Path, registry: FrozenSchemaPackRegistry
    ) -> None:
        self._path = Path(path)
        self._registry = registry
        self._connection: sqlite3.Connection | None = None
        self._queue: queue.Queue[Any] = queue.Queue()
        self._closed = False
        self._submit_lock = threading.Lock()
        self._idle = threading.Condition()
        self._pending = 0
        self._started = threading.Event()
        self._startup_error: BaseException | None = None
        # WAL sidecar guard: (st_dev, st_ino) of the ``-wal`` file backing
        # the owned connection as of the last completed callback; ``None``
        # while no WAL has been observed yet. Touched only on the writer
        # thread.
        self._wal_identity: tuple[int, int] | None = None
        self._sidecar_fault_reported = False
        self._thread = threading.Thread(
            target=self._run,
            name="astrid-sqlite-writer",
            daemon=True,
        )
        self._thread.start()
        # The writer thread creates the owned connection, so construction
        # fails fast (e.g. on a too-new schema) with the same typed
        # incompatibility errors a direct writable open would raise.
        self._started.wait()
        if self._startup_error is not None:
            self._thread.join()
            raise self._startup_error

    # -- submission --------------------------------------------------------

    def submit(self, callback: Callable[[WriterSession], Any]) -> Any:
        """Submit a synchronous write callback and block until it completes.

        The callback runs on the writer thread and receives a
        :class:`WriterSession`. Returns the callback's return value and
        re-raises the callback's exception (SQLite busy errors translated to
        :class:`WriterBusyError`). Raises :class:`WriterShutdownError` when
        the writer has been closed.
        """
        if not callable(callback):
            raise TypeError("writer callback must be callable")
        if threading.current_thread() is self._thread:
            # The writer thread executes callbacks itself; submitting from it
            # would enqueue work the writer can never process and deadlock on
            # item.done.wait(). Reject up front with a typed error instead.
            raise WriterError(
                "cannot submit work from the writer thread (deadlock)"
            )
        with self._submit_lock:
            if self._closed:
                raise WriterShutdownError(
                    "cannot submit to a closed sqlite writer"
                )
            if not self._thread.is_alive():
                raise WriterShutdownError(
                    "sqlite writer thread is not running"
                )
            item = _WorkItem(callback)
            with self._idle:
                self._pending += 1
            self._queue.put(item)
        item.done.wait()
        if item.error is not None:
            raise item.error
        return item.result

    # -- lifecycle ---------------------------------------------------------

    def drain(self) -> None:
        """Block until every already-submitted callback has completed.

        New submissions remain accepted; this waits only for work that has
        been admitted so far (deterministic drain).
        """
        with self._idle:
            while self._pending > 0:
                self._idle.wait()

    def close(self) -> None:
        """Drain pending work, stop the writer thread, and close the connection.

        Deterministic and idempotent: queued callbacks are still executed,
        the thread exits on a sentinel, and the owned connection is closed
        by the writer thread itself. Must be called from outside the writer
        thread.
        """
        with self._submit_lock:
            if self._closed:
                return
            self._closed = True
            self._queue.put(_SENTINEL)
        self._thread.join()

    @property
    def closed(self) -> bool:
        """Whether ``close()`` has been called."""
        return self._closed

    def __enter__(self) -> DatabaseWriter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- separate read-only reads ------------------------------------------

    @contextmanager
    def read_only_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a separate read-only connection for transaction-free reads.

        The connection is opened through the nonmutating read-only open path
        (:func:`astrid.core.store.database.open_database` with
        ``read_only=True``), performs the same incompatibility probe as a
        writable open, and never shares the writer's connection. Writing
        through it fails at the SQLite level.
        """
        conn = open_database(self._path, self._registry, read_only=True)
        try:
            yield conn
        finally:
            conn.close()

    def _wal_sidecar_identity(self) -> tuple[int, int] | None:
        """Return ``(st_dev, st_ino)`` of the ``-wal`` file, or ``None``."""
        try:
            stat = os.stat(f"{self._path}-wal")
        except OSError:
            return None
        return (stat.st_dev, stat.st_ino)

    # -- writer thread -----------------------------------------------------

    def _run(self) -> None:
        """Writer thread loop: open the owned connection, FIFO execution."""
        try:
            self._connection = open_database(self._path, self._registry)
        except BaseException as exc:  # noqa: BLE001 - surfaced to constructor
            self._startup_error = exc
            self._started.set()
            return
        # Typed rows: every row the session returns is addressable by name
        # and position. The connection stays owned by this thread.
        self._connection.row_factory = sqlite3.Row
        self._started.set()
        self._wal_identity = self._wal_sidecar_identity()
        try:
            while True:
                item = self._queue.get()
                if item is _SENTINEL:
                    self._queue.task_done()
                    break
                try:
                    # Sidecar guard: between callbacks the writer holds no
                    # locks, so a foreign writable close can unlink the WAL.
                    # A changed or missing file past the first observation
                    # means this connection no longer backs durable state:
                    # commits would keep landing in a WAL nobody can read,
                    # so every later submission fails the same way.
                    identity = self._wal_sidecar_identity()
                    if identity != self._wal_identity:
                        if not self._sidecar_fault_reported:
                            self._sidecar_fault_reported = True
                            print(
                                "astrid-sqlite-writer: database WAL was "
                                f"replaced beneath the live writer "
                                f"(observed {self._wal_identity}, now "
                                f"{identity}); writes fail closed until "
                                f"restart",
                                file=sys.stderr,
                            )
                        raise WriterSidecarError(
                            "the database WAL was replaced beneath the live "
                            "writer (a foreign process closed a writable "
                            "connection); writes cannot be durable — restart "
                            "astrid serve"
                        )
                    session = WriterSession(self._connection)
                    item.result = item.callback(session)
                    self._wal_identity = self._wal_sidecar_identity()
                except sqlite3.OperationalError as exc:
                    if "locked" in str(exc).lower():
                        item.error = WriterBusyError(
                            f"sqlite writer busy: {exc}"
                        )
                    else:
                        item.error = exc
                except BaseException as exc:  # noqa: BLE001 - propagate to caller
                    item.error = exc
                finally:
                    with self._idle:
                        self._pending -= 1
                        if self._pending == 0:
                            self._idle.notify_all()
                    self._queue.task_done()
                    item.done.set()
        finally:
            self._connection.close()


__all__ = [
    "DatabaseWriter",
    "TransactionControlError",
    "WriterBusyError",
    "WriterSidecarError",
    "WriterSession",
    "WriterShutdownError",
]
