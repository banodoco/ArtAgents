"""Backend selection helpers for timeline event streams."""

from __future__ import annotations

from pathlib import Path

from .types import TimelineStreamRef


def select_timeline_stream(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
) -> TimelineStreamRef:
    backend = (preferred_backend or "").strip().lower()
    if backend == "supabase":
        return TimelineStreamRef(
            backend="supabase",
            timeline_id=timeline_id,
            home=None,
            source="preferred_backend",
        )
    if timeline_home is not None:
        return TimelineStreamRef(
            backend="local_fs",
            timeline_id=timeline_id,
            home=Path(timeline_home),
            source="timeline_home",
        )
    return TimelineStreamRef(
        backend="local_fs",
        timeline_id=timeline_id,
        home=None,
        source="default_local",
    )
