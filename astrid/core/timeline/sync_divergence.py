"""Durable keep-both writers for sync divergence handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from astrid.core._shared.jsonio import ProjectJsonError, write_json_atomic
from astrid.core.timeline.eventlog.selector import EventLogTarget
from astrid.core.timeline.eventlog.supabase import SupabaseBackend
from astrid.core.timeline.eventlog.types import EventLogTransportError
from astrid.core.timeline.events.schema import TimelineEvent
from astrid.core.util.time import utc_now_milliseconds

from .sync_state import HeadSnapshot

_LOCAL_DIVERGENCE_PREFIX = "divergence-"


class TransferFailure(RuntimeError):
    """Raised when a transfer precondition fails before replay can proceed."""


@dataclass(frozen=True)
class LocalDivergenceArtifactRef:
    """Typed reference to a local keep-both artifact."""

    path: str
    timeline_id: str
    created_at: str
    kind: Literal["local_file"] = "local_file"

    def to_json_obj(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "path": self.path,
            "timeline_id": self.timeline_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SupabaseDivergenceArtifactRef:
    """Typed reference to a divergence_log row."""

    entry_id: str
    timeline_id: str
    spoke: str
    created_at: str
    kind: Literal["supabase_divergence_log"] = "supabase_divergence_log"

    def to_json_obj(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "entry_id": self.entry_id,
            "timeline_id": self.timeline_id,
            "spoke": self.spoke,
            "created_at": self.created_at,
        }


DivergenceArtifactRef = LocalDivergenceArtifactRef | SupabaseDivergenceArtifactRef


def write_keep_both_artifact(
    *,
    source: EventLogTarget,
    destination: EventLogTarget,
    source_head: HeadSnapshot,
    destination_head: HeadSnapshot,
    source_suffix: list[TimelineEvent],
    destination_suffix: list[TimelineEvent],
) -> DivergenceArtifactRef:
    """Durably preserve both suffixes before any LWW replay.

    Local destinations receive a JSON sidecar under the destination timeline
    home. Supabase destinations write a row to ``public.divergence_log``.
    """

    if destination.backend_name == "local_fs":
        return _write_local_divergence(
            source=source,
            destination=destination,
            source_head=source_head,
            destination_head=destination_head,
            source_suffix=source_suffix,
            destination_suffix=destination_suffix,
        )
    if destination.backend_name == "supabase":
        return _write_supabase_divergence(
            source=source,
            destination=destination,
            source_head=source_head,
            destination_head=destination_head,
            source_suffix=source_suffix,
            destination_suffix=destination_suffix,
        )
    raise TransferFailure(
        f"unsupported divergence destination backend {destination.backend_name!r}"
    )


def _write_local_divergence(
    *,
    source: EventLogTarget,
    destination: EventLogTarget,
    source_head: HeadSnapshot,
    destination_head: HeadSnapshot,
    source_suffix: list[TimelineEvent],
    destination_suffix: list[TimelineEvent],
) -> LocalDivergenceArtifactRef:
    if destination.timeline_home is None:
        raise TransferFailure("local divergence write requires a destination timeline home")

    created_at = utc_now_milliseconds()
    filename = f"{_LOCAL_DIVERGENCE_PREFIX}{_filename_stamp(created_at)}.json"
    path = Path(destination.timeline_home) / filename
    payload = {
        "schema_version": 1,
        "kind": "sync_divergence",
        "created_at": created_at,
        "timeline_id": destination.timeline_id,
        "source": _render_side(
            target=source,
            head=source_head,
            suffix=source_suffix,
        ),
        "destination": _render_side(
            target=destination,
            head=destination_head,
            suffix=destination_suffix,
        ),
    }
    try:
        write_json_atomic(path, payload)
    except (ProjectJsonError, OSError) as exc:
        raise TransferFailure(
            f"failed to persist keep-both artifact before replay: {path}: {exc}"
        ) from exc
    return LocalDivergenceArtifactRef(
        path=str(path),
        timeline_id=destination.timeline_id,
        created_at=created_at,
    )


def _write_supabase_divergence(
    *,
    source: EventLogTarget,
    destination: EventLogTarget,
    source_head: HeadSnapshot,
    destination_head: HeadSnapshot,
    source_suffix: list[TimelineEvent],
    destination_suffix: list[TimelineEvent],
) -> SupabaseDivergenceArtifactRef:
    if source.backend_name != "local_fs":
        raise TransferFailure(
            "Supabase divergence logging currently requires a local spoke source"
        )
    backend = destination.backend
    if not isinstance(backend, SupabaseBackend):
        raise TransferFailure("Supabase divergence destination requires a SupabaseBackend")

    try:
        row = backend.write_divergence(
            spoke="local",
            spoke_version=source_head.version,
            spoke_hash=source_head.last_hash,
            spoke_event_id=source_head.last_event_id,
            hub_version=destination_head.version,
            hub_hash=destination_head.last_hash,
            hub_event_id=destination_head.last_event_id,
            spoke_suffix=[event.to_json_obj() for event in source_suffix],
            hub_suffix=[event.to_json_obj() for event in destination_suffix],
            chosen_side="undecided",
            artifact_pointer=None,
        )
    except (EventLogTransportError, RuntimeError, ValueError) as exc:
        raise TransferFailure(
            "failed to persist keep-both artifact before replay: "
            f"Supabase divergence_log write failed: {exc}"
        ) from exc

    entry_id = row.get("id")
    created_at = row.get("created_at")
    timeline_id = row.get("timeline_id")
    spoke = row.get("spoke")
    if not isinstance(entry_id, str) or not entry_id:
        raise TransferFailure("Supabase divergence_log write did not return an id")
    if not isinstance(created_at, str) or not created_at:
        raise TransferFailure("Supabase divergence_log write did not return created_at")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise TransferFailure("Supabase divergence_log write did not return timeline_id")
    if not isinstance(spoke, str) or not spoke:
        raise TransferFailure("Supabase divergence_log write did not return spoke")
    return SupabaseDivergenceArtifactRef(
        entry_id=entry_id,
        timeline_id=timeline_id,
        spoke=spoke,
        created_at=created_at,
    )


def _render_side(
    *,
    target: EventLogTarget,
    head: HeadSnapshot,
    suffix: list[TimelineEvent],
) -> dict[str, object]:
    return {
        "backend": target.backend_name,
        "timeline_id": target.timeline_id,
        "timeline_home": str(target.timeline_home) if target.timeline_home is not None else None,
        "slug": target.slug,
        "head": head.to_json_obj(),
        "suffix": [event.to_json_obj() for event in suffix],
    }


def _filename_stamp(created_at: str) -> str:
    return (
        created_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("T", "-")
        .replace("Z", "Z")
    )
