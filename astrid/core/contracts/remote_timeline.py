"""Structural contract for listing remote (Supabase/Reigh) timelines.

``astrid.core.timeline.migration`` needs to discover remote timeline rows to
build migration candidates, but the concrete transport lives in the higher
``astrid.core.integrations.reigh`` tier. Depending on it directly would invert
the layering (timeline → integrations). Instead, timeline depends only on this
``RemoteTimelineLister`` Protocol and the caller injects the concrete reigh
implementation, whose ``list_timelines`` / ``timeline_has_events`` functions
satisfy this structural shape.
"""

from __future__ import annotations

from typing import Any, Protocol


class RemoteTimelineLister(Protocol):
    """Transport seam for discovering remote timelines during migration."""

    def list_timelines(
        self,
        *,
        supabase_url: str,
        auth: Any,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return ``public.timelines`` rows (each with ``id``/``project_id``)."""
        ...

    def timeline_has_events(
        self,
        *,
        supabase_url: str,
        auth: Any,
        timeline_id: str,
    ) -> bool:
        """Return whether ``public.timeline_events`` has rows for the timeline."""
        ...


__all__ = ["RemoteTimelineLister"]
