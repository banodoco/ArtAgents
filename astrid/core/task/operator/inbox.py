"""Transitional compatibility shim — the canonical inbox now lives at
``astrid.core.io.inbox``.

Import here works without deprecation noise so existing consumers don't
break during the transition.  New / updated code should import directly
from ``astrid.core.io.inbox`` (or ``astrid.core.io``).
"""

from __future__ import annotations

from astrid.core.io.inbox import (  # noqa: F401  — re-export
    CONSUMED_DIR_NAME,
    INBOX_DIR_NAME,
    REJECTED_DIR_NAME,
    InboxEntry,
    InboxValidationError,
    _compute_stale,
    _is_step_fully_superseded,
    _is_step_tombstoned,
    _latest_event_for_path,
    _move_to,
    _parse_entry,
    _parse_legacy_entry,
    _resolve_plan_step_path,
    consume_inbox_entry,
    inbox_dir,
    pending_count,
    scan_inbox,
)

__all__ = [
    "CONSUMED_DIR_NAME",
    "INBOX_DIR_NAME",
    "REJECTED_DIR_NAME",
    "InboxEntry",
    "InboxValidationError",
    "consume_inbox_entry",
    "inbox_dir",
    "pending_count",
    "scan_inbox",
]
