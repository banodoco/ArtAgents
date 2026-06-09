"""Shared atomic I/O helpers for text, bytes, and JSON writes.

All writers use sibling temporary files and ``os.replace()`` so that
readers never observe a partially-written file.
"""

from __future__ import annotations

import errno
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


class AtomicWriteError(OSError):
    """Raised when an atomic write cannot be completed."""


def _fsync_dir(path: Path) -> None:
    """Best-effort directory fsync to durably record the rename."""
    flags: int = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    fd: int | None = None
    try:
        fd = os.open(path, flags)
        os.fsync(fd)
    except OSError as exc:
        if exc.errno not in {errno.EINVAL, errno.ENOTSUP, errno.EBADF}:
            raise
    finally:
        if fd is not None:
            os.close(fd)


def _write_atomic(path: Path, write_func: Callable[[Path], None]) -> None:
    """Core atomic write: write to a sibling temp file, then ``os.replace``.

    ``write_func`` receives the temporary ``Path`` and should write
    the complete content there.  After ``write_func`` returns, the
    temporary file is fsync'd and atomically moved over *path*.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            # Give the caller the tmp_path; it can write via
            # handle or directly to the path – both work because
            # we hold the fd open exclusively.
            write_func(tmp_path)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_dir(path.parent)
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_atomic_binary(path: Path, write_func: Callable[[Path], None]) -> None:
    """Like :func:`_write_atomic` but opens the temp file in binary mode."""
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            write_func(tmp_path)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_dir(path.parent)
    finally:
        tmp_path.unlink(missing_ok=True)


# -- Public helpers -----------------------------------------------------------

def write_text_atomic(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Atomically write *text* to *path*."""

    def _write_text(tmp: Path) -> None:
        tmp.write_text(text, encoding=encoding)

    try:
        _write_atomic(Path(path), _write_text)
    except OSError as exc:
        raise AtomicWriteError(str(exc)) from exc


def write_bytes_atomic(path: str | Path, data: bytes) -> None:
    """Atomically write *data* to *path*."""

    def _write_bytes(tmp: Path) -> None:
        tmp.write_bytes(data)

    try:
        _write_atomic_binary(Path(path), _write_bytes)
    except OSError as exc:
        raise AtomicWriteError(str(exc)) from exc


def write_json_atomic(path: str | Path, payload: Any) -> None:
    """Atomically write *payload* as pretty-printed, sorted-key JSON."""

    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{json_path.name}.", suffix=".tmp", dir=json_path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, json_path)
        _fsync_dir(json_path.parent)
    except OSError as exc:
        raise AtomicWriteError(str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def read_json(path: str | Path) -> Any:
    """Read and parse a JSON file at *path*.

    Returns the decoded object.
    """
    json_path = Path(path)
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {json_path}: {exc.msg}") from exc
    except OSError as exc:
        raise AstridError(
            f"failed to read {json_path}: {exc}",
            recovery_command="check file permissions and disk health, then retry",
        ) from exc
