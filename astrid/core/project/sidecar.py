"""Atomic sidecar helpers for task-run step directories."""

from __future__ import annotations

import errno
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_sidecar(path: str | Path, payload: Any) -> None:
    sidecar_path = Path(path)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    write_text_sidecar(sidecar_path, text)


def write_text_sidecar(path: str | Path, text: str) -> None:
    sidecar_path = Path(path)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{sidecar_path.name}.",
        suffix=".tmp",
        dir=sidecar_path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, sidecar_path)
        _fsync_dir(sidecar_path.parent)
    finally:
        tmp_path.unlink(missing_ok=True)


def _fsync_dir(path: Path) -> None:
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
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


__all__ = ["write_json_sidecar", "write_text_sidecar"]
