"""Shared EventLogError base for the runtime-facing task event hierarchy."""

from __future__ import annotations


class EventLogError(RuntimeError):
    """Base for all event-log errors across task and timeline domains.

    Timeline storage errors are returned by the generated workspace client;
    Astrid no longer exposes a product-side timeline event-log hierarchy.
    """
