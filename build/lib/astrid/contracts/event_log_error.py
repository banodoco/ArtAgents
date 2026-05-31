"""Shared EventLogError base for task and timeline event-log hierarchies."""

from __future__ import annotations


class EventLogError(RuntimeError):
    """Base for all event-log errors across task and timeline domains.

    Both ``astrid.core.task.events.EventLogError`` and
    ``astrid.core.timeline.eventlog.types.EventLogError`` re-export this class
    so ``except EventLogError`` catches errors from either family regardless of
    which import site was used.
    """
