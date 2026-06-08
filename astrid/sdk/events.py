"""Public event-stream read and subscribe endpoints.

These functions adapt SDK calls to the core task event infrastructure.
They resolve internal helpers through ``astrid.sdk`` so monkeypatch seams
applied to the package namespace are visible at call time.
"""

from __future__ import annotations

import sys
from pathlib import Path

from astrid.core.project.paths import validate_project_slug
from astrid.core.project.paths import run_dir as project_run_dir
from astrid.core.task.events import EVENTS_FILENAME

from .dto import EventStreamRecord
from .exceptions import (
    AstridSDKError,
    CapabilityInvocationError,
    _sdk_error_from_event_exception,
)


def _resolve_event_stream_run_dir(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
) -> Path:
    """Resolve the filesystem path for a run's event stream directory.

    This function is exposed on ``astrid.sdk`` so tests can monkeypatch it.
    The public endpoints (``read_events``, ``subscribe_events``) resolve it
    through ``astrid.sdk`` to respect those monkeypatches.
    """
    slug = validate_project_slug(project)
    run_path = project_run_dir(slug, run_id, root=projects_root)
    if not run_path.is_dir():
        raise FileNotFoundError(f"run {run_id!r} not found in project {slug!r}")
    events_path = run_path / EVENTS_FILENAME
    if not events_path.is_file():
        raise FileNotFoundError(
            f"run {run_id!r} in project {slug!r} has no {EVENTS_FILENAME}"
        )
    return run_path


def read_events(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    include_audit: bool = True,
    verify: bool = True,
) -> tuple[EventStreamRecord, ...]:
    """Return a verified read-only task/audit event snapshot for one run."""

    _sdk = sys.modules["astrid.sdk"]
    try:
        run_path = _sdk._resolve_event_stream_run_dir(project, run_id, projects_root=projects_root)
        return tuple(
            _sdk._read_task_event_stream(
                run_path,
                include_audit=include_audit,
                verify=verify,
            )
        )
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_event_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to read events for project {project!r} run {run_id!r}"
        ) from exc


def subscribe_events(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    include_audit: bool = True,
    verify: bool = True,
    follow: bool = False,
    poll_interval: float = 0.1,
    idle_polls: int | None = None,
):
    """Yield a verified read-only task/audit event stream for one run."""

    _sdk = sys.modules["astrid.sdk"]
    try:
        run_path = _sdk._resolve_event_stream_run_dir(project, run_id, projects_root=projects_root)
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_event_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to subscribe to events for project {project!r} run {run_id!r}"
        ) from exc

    def _iter():
        try:
            yield from _sdk._subscribe_task_event_stream(
                run_path,
                include_audit=include_audit,
                verify=verify,
                follow=follow,
                poll_interval=poll_interval,
                idle_polls=idle_polls,
            )
        except AstridSDKError:
            raise
        except Exception as exc:
            mapped = _sdk_error_from_event_exception(exc)
            if mapped is not None:
                raise mapped from exc
            raise CapabilityInvocationError(
                f"failed to subscribe to events for project {project!r} run {run_id!r}"
            ) from exc

    return _iter()


__all__ = [
    "_resolve_event_stream_run_dir",
    "read_events",
    "subscribe_events",
]
