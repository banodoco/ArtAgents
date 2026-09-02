"""Exclusive-owner database lock (m4 plan step 4, task T5).

An OS-level exclusive advisory lock file held **beside the database** for the
process lifetime. The standard application composition acquires it before any
writable connection or writer queue can open; a second process that tries to
compose the same database fails closed with a typed
:class:`OwnerLockError` (surfaced by the application boundary as the SDK's
``unavailable`` contract) instead of opening a second writer queue that would
break the single-writer invariant.

This is the temporary exclusive-owner deviation (SD3-m4, decision artifact):
m4 permits exactly one process per database at a time — the serve process, or
a standalone SDK/CLI process when no long-running service owns the database.
The m6 closure (mutations routed through the serving process via loopback RPC,
or an exclusive service-owner protocol) removes this lock.

The lock is advisory and process-lifetime:

- It uses ``fcntl.flock`` (POSIX) with ``LOCK_EX | LOCK_NB``, so acquisition
  is non-blocking and fails closed when another process already holds the
  lock — before any second writable connection or writer queue can open.
- Two :class:`DatabaseOwnerLock` instances in the **same** process (each
  opening the lock file separately) also conflict, because ``flock`` locks
  are per open-file-description, not per process. This is exactly the
  single-owner semantics the composition needs.
- :meth:`DatabaseOwnerLock.release` (and ``close``) is idempotent and is the
  only way to drop the lock; the lock file itself is left in place (the
  authority is the ``flock``, never the file's existence), which avoids the
  unlink/recreate race a deleting-lock implementation would introduce.
This module has no dependency on the schema packs, the SDK, or the
capability-pack loader; it is a kernel store seam.
"""

from __future__ import annotations

import os
from pathlib import Path

from astrid.core.store.writer import WriterError

try:  # POSIX (the frozen m4 platform matrix is Linux CI).
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

try:  # pragma: no cover - Windows fallback, unused on the frozen matrix.
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore[assignment]

__all__ = ["DatabaseOwnerLock", "OwnerLockError", "database_lock_path"]


class OwnerLockError(WriterError):
    """Raised when the exclusive database owner lock cannot be acquired.

    Subclasses :class:`astrid.core.store.writer.WriterError` so it stays in
    the kernel writer error family; the application composition boundary
    translates it to the SDK's typed ``unavailable`` contract (SDK contract
    v10 section 2.2) before it can reach a caller, so a second-owner failure
    never leaks an OS or database error.
    """


def database_lock_path(database_path: str | Path) -> Path:
    """Return the lock file path that sits beside the database file."""
    path = Path(database_path)
    return path.with_name(path.name + ".lock")


class DatabaseOwnerLock:
    """A process-lifetime exclusive lock on one database path.

    Construction acquires the lock (fail-closed) or raises
    :class:`OwnerLockError`; :meth:`release` drops it. The object supports
    the context-manager protocol and an idempotent :meth:`close`.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._lock_path = database_lock_path(database_path)
        self._fd: int | None = None
        self._held = False
        self._acquire()

    # -- public surface -----------------------------------------------------

    @property
    def lock_path(self) -> Path:
        """The lock file path (read-only)."""
        return self._lock_path

    @property
    def held(self) -> bool:
        """Whether the exclusive lock is currently held by this instance."""
        return self._held

    def release(self) -> None:
        """Drop the exclusive lock (idempotent).

        After release the lock may be acquired by another process (or by a
        new :class:`DatabaseOwnerLock` instance). Releasing an already
        released lock is a no-op.
        """
        if not self._held:
            return
        fd = self._fd
        self._fd = None
        self._held = False
        if fd is None:
            return
        try:
            if fcntl is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
            elif msvcrt is not None:  # pragma: no cover - Windows
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                os.close(fd)
            else:  # pragma: no cover - no locking primitive available
                os.close(fd)
        except OSError:  # pragma: no cover - best-effort release
            pass

    def close(self) -> None:
        """Alias for :meth:`release` (idempotent lifecycle close)."""
        self.release()

    def __enter__(self) -> DatabaseOwnerLock:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    # -- private -------------------------------------------------------------

    def _acquire(self) -> None:
        """Acquire the exclusive lock, failing closed if it is held."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        except OSError as exc:
            raise OwnerLockError(
                "cannot open the database owner lock file"
            ) from exc
        self._fd = fd
        try:
            if fcntl is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise OwnerLockError(
                        "the database is already owned by another process"
                    ) from exc
            elif msvcrt is not None:  # pragma: no cover - Windows
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise OwnerLockError(
                        "the database is already owned by another process"
                    ) from exc
            else:  # pragma: no cover - no locking primitive available
                raise OwnerLockError(
                    "no OS file-locking primitive is available on this "
                    "platform"
                )
        except BaseException:
            os.close(fd)
            self._fd = None
            raise
        self._held = True
