"""Deterministic JSON IO helpers for project state.

Delegates to the shared atomic-I/O primitives in
:mod:`astrid.core.util.atomic_io` while preserving the
existing ``ProjectJsonError`` exception and import paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.util.atomic_io import read_json as _atomic_read_json
from astrid.core.util.atomic_io import write_json_atomic as _atomic_write_json


class ProjectJsonError(AstridError):
    """Raised when project JSON cannot be read or written."""


def read_json(path: str | Path) -> Any:
    """Read and parse a JSON file at *path*.

    Wraps lower-level errors in :class:`ProjectJsonError`.
    """
    try:
        return _atomic_read_json(path)
    except FileNotFoundError:
        raise
    except ValueError as exc:
        raise ProjectJsonError(str(exc)) from exc
    except OSError as exc:
        raise ProjectJsonError(f"failed to read {path}: {exc}") from exc


def write_json_atomic(path: str | Path, payload: Any) -> None:
    """Atomically write *payload* as JSON to *path*.

    Delegates to :func:`astrid.core.util.atomic_io.write_json_atomic`.
    """
    try:
        _atomic_write_json(path, payload)
    except OSError as exc:
        raise ProjectJsonError(f"failed to write {path}: {exc}") from exc
