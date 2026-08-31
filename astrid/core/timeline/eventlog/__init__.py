"""Pure event-log contracts used by the runtime materialization boundary.

Filesystem event-log backends and selectors are not product runtime APIs.
Offline migration code must import its reader directly; this package exports
only backend-neutral protocol and value types.
"""
from .projector import DisplayProjection, project_display
from .protocol import EventLogBackend
from .types import (
    AppendEventRequest,
    BackendName,
    EventLogError,
    EventLogHead,
    EventLogStaleVersionError,
    EventLogVerification,
    TimelineStreamRef,
    TimelineVersionConflict,
)

__all__ = [
    "AppendEventRequest",
    "BackendName",
    "EventLogBackend",
    "EventLogError",
    "EventLogHead",
    "EventLogStaleVersionError",
    "EventLogVerification",
    "DisplayProjection",
    "project_display",
    "TimelineVersionConflict",
    "TimelineStreamRef",
]
