"""Local event-log selection for the Astrid timeline pack.

Astrid's product runtime has one event-log authority: the local filesystem
stream owned by the workspace runtime.  There is deliberately no backend
selector, credential lookup, or transport fallback for remote services.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .local_fs import LocalFsBackend
from .protocol import EventLogBackend
from .types import BackendName, TimelineStreamRef


def select_timeline_stream(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
) -> TimelineStreamRef:
    """Select the sole supported local event-log backend.

    A caller that names any other backend receives an explicit error; no
    environment or identity-sidecar value can silently switch transports.
    """
    if preferred_backend is not None and preferred_backend.strip().lower() not in {
        "",
        "local_fs",
    }:
        raise ValueError("only the local_fs timeline backend is supported")
    return TimelineStreamRef(
        backend="local_fs",
        timeline_id=timeline_id,
        home=Path(timeline_home) if timeline_home is not None else None,
        source="timeline_home" if timeline_home is not None else "default_local",
    )


def build_timeline_backend(stream: TimelineStreamRef) -> EventLogBackend:
    """Construct the local backend for a resolved stream."""
    if stream.backend != "local_fs":
        raise ValueError("only the local_fs timeline backend is supported")
    if stream.home is None:
        raise ValueError("local_fs timeline stream requires a timeline home")
    return LocalFsBackend(timeline_id=stream.timeline_id, timeline_home=stream.home)


def select_timeline_backend(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
) -> tuple[TimelineStreamRef, EventLogBackend]:
    stream = select_timeline_stream(
        timeline_id=timeline_id,
        timeline_home=timeline_home,
        preferred_backend=preferred_backend,
    )
    return stream, build_timeline_backend(stream)


@dataclass(frozen=True)
class EventLogTarget:
    """A resolved local timeline target."""

    backend_name: BackendName
    timeline_id: str
    timeline_ulid: str | None
    timeline_home: Path
    slug: str | None
    backend: EventLogBackend
    source: str = "local"


def resolve_event_log_target(
    project_slug: str,
    slug_or_id: str,
    *,
    root: str | Path | None = None,
    preferred_backend: str | None = None,
) -> EventLogTarget:
    """Resolve a local timeline and bind it to its local event stream."""
    from astrid.core.timeline.observability import resolve_timeline_target

    target = resolve_timeline_target(project_slug, slug_or_id, root=root)
    stream, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=preferred_backend or target.backend,
    )
    return EventLogTarget(
        backend_name=stream.backend,
        timeline_id=target.timeline_id,
        timeline_ulid=target.timeline_ulid,
        timeline_home=target.timeline_home,
        slug=target.slug,
        backend=backend,
    )


__all__ = [
    "EventLogTarget",
    "build_timeline_backend",
    "resolve_event_log_target",
    "select_timeline_backend",
    "select_timeline_stream",
]
