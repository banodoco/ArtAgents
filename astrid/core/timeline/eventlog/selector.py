"""Backend selection helpers for timeline event streams."""

from __future__ import annotations

from pathlib import Path

from .local_fs import LocalFsBackend
from .protocol import EventLogBackend
from .supabase import SupabaseBackend
from .types import SupabaseEventLogOptions, TimelineStreamRef


def select_timeline_stream(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
    supabase_options: SupabaseEventLogOptions | None = None,
) -> TimelineStreamRef:
    backend = (preferred_backend or "").strip().lower()
    if backend == "supabase":
        return TimelineStreamRef(
            backend="supabase",
            timeline_id=timeline_id,
            home=None,
            source="preferred_backend",
            supabase_options=supabase_options,
        )
    if timeline_home is not None:
        return TimelineStreamRef(
            backend="local_fs",
            timeline_id=timeline_id,
            home=Path(timeline_home),
            source="timeline_home",
            supabase_options=supabase_options,
        )
    return TimelineStreamRef(
        backend="local_fs",
        timeline_id=timeline_id,
        home=None,
        source="default_local",
        supabase_options=supabase_options,
    )


def build_timeline_backend(stream: TimelineStreamRef) -> EventLogBackend:
    if stream.backend == "supabase":
        options = stream.supabase_options
        return SupabaseBackend(
            timeline_id=stream.timeline_id,
            supabase_url=options.url if options is not None else None,
            auth_token=options.auth_token if options is not None else None,
            enabled=options is not None,
        )
    if stream.home is None:
        raise ValueError("local_fs timeline stream requires a timeline home")
    return LocalFsBackend(timeline_id=stream.timeline_id, timeline_home=stream.home)


def select_timeline_backend(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
    supabase_options: SupabaseEventLogOptions | None = None,
) -> tuple[TimelineStreamRef, EventLogBackend]:
    stream = select_timeline_stream(
        timeline_id=timeline_id,
        timeline_home=timeline_home,
        preferred_backend=preferred_backend,
        supabase_options=supabase_options,
    )
    return stream, build_timeline_backend(stream)
