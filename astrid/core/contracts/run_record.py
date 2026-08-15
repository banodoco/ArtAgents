"""Run-record path/load helpers for contracts (neutral leaf; no project imports).

This leaf exists to break the ``contracts <-> project`` import cycle: the
timeline-visualize preflight in :mod:`astrid.core.contracts.timeline_visualize`
needs to resolve and read a run record without importing
:mod:`astrid.core.project.run` (which imports contracts). The helpers here are
deliberately validation-free — the preflight caller field-validates every value
it uses. The validated public API stays in ``astrid.core.project.run``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.foundation import project_paths as paths
from astrid.core.foundation.atomic_io import read_json


def resolve_record_path(
    value: str | Path,
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> Path:
    """Resolve a run-record path against a project root when it is relative."""

    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (paths.project_dir(project_slug, root=root) / path).resolve()


def load_run_record_unvalidated(
    project_slug: str,
    run_id: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Load a run record as raw JSON without schema validation.

    Fail-closed: missing/malformed files raise via :func:`read_json` (the
    preflight caller treats any exception as "not a valid visualization
    manifest").
    """

    return read_json(paths.run_json_path(project_slug, run_id, root=root))


__all__ = ["resolve_record_path", "load_run_record_unvalidated"]
