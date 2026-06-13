"""Compatibility shim for the Release N task-fallback event transport path."""

from __future__ import annotations

from astrid.core import events as _events
from astrid.core.events import *  # noqa: F401,F403

EVENTS_FILENAME = _events.EVENTS_FILENAME
LEASE_FILENAME = _events.LEASE_FILENAME
append_event_to_locked_handle = _events.append_event_to_locked_handle
hash_prepended = _events.hash_prepended
_event_hash = _events._event_hash
_peek_tail_hash = _events._peek_tail_hash

__all__ = list(getattr(_events, "__all__", ())) + [
    "EVENTS_FILENAME",
    "LEASE_FILENAME",
    "append_event_to_locked_handle",
    "hash_prepended",
    "_event_hash",
    "_peek_tail_hash",
]
