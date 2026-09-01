"""Public runtime event read and subscription endpoints.

The workspace runtime owns event storage and ordering.  This module converts
the generated client's event resources into Astrid's stable
``EventStreamRecord`` DTO without opening a local database or reading a
filesystem event projection.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from typing import Any, Iterator

from .dto import EventStreamRecord
from .exceptions import (
    AstridSDKError,
    CapabilityEventLogError,
    CapabilityInvocationError,
    CapabilityPreconditionError,
    CapabilityValidationError,
)

_PROJECT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validate_project_ref(project: str) -> str:
    if not isinstance(project, str) or not project.strip():
        raise CapabilityValidationError("project slug must be a non-empty string")
    if _PROJECT_REF.fullmatch(project) is None:
        raise CapabilityValidationError(f"invalid project slug: {project!r}")
    return project


def _runtime_error(result: Any) -> AstridSDKError:
    error = getattr(result, "error", None)
    code = str(getattr(error, "code", "runtime_error"))
    message = str(getattr(error, "message", "runtime event read failed"))
    if code in {"not_found", "validation_error"}:
        return CapabilityPreconditionError(message)
    return CapabilityInvocationError(message)


def _event_records(events: Any) -> tuple[EventStreamRecord, ...]:
    if not isinstance(events, (list, tuple)):
        raise CapabilityInvocationError("runtime event read returned an invalid event list")
    records: list[EventStreamRecord] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, Mapping):
            raise CapabilityEventLogError("runtime event read returned an invalid event resource")
        payload = event.get("payload")
        public_payload = dict(payload) if isinstance(payload, Mapping) else {}
        event_type = event.get("event_type")
        occurred_at = event.get("occurred_at")
        if isinstance(event_type, str):
            public_payload.setdefault("kind", event_type)
        if isinstance(occurred_at, str):
            public_payload.setdefault("ts", occurred_at)
        for key in (
            "event_id",
            "sequence",
            "cursor",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "occurred_at",
        ):
            if key in event:
                public_payload.setdefault(key, event[key])
        sequence = event.get("sequence", index)
        try:
            line = int(sequence)
        except (TypeError, ValueError) as exc:
            raise CapabilityEventLogError("runtime event sequence is invalid") from exc
        event_hash = public_payload.get("event_hash") or public_payload.get("hash")
        records.append(
            EventStreamRecord(
                # Runtime events replace the historical task event projection,
                # but ``task`` preserves the public DTO's source vocabulary.
                source="task",
                line=line,
                timestamp=occurred_at if isinstance(occurred_at, str) else None,
                kind=event_type if isinstance(event_type, str) else None,
                hash=event_hash if isinstance(event_hash, str) else None,
                payload=public_payload,
            )
        )
    return tuple(records)


def _read_runtime_events(client: Any, project: str, run_id: str) -> tuple[EventStreamRecord, ...]:
    runs = getattr(client, "runs", None)
    read = getattr(runs, "events", None)
    if not callable(read):
        raise CapabilityInvocationError("runtime client does not expose generated run events")
    result = read(project, run_id)
    if hasattr(result, "ok"):
        if not result.ok:
            raise _runtime_error(result)
        events = result.data
    else:
        events = result
    return _event_records(events)


def read_events(
    project: str,
    run_id: str,
    *,
    client: Any | None = None,
) -> tuple[EventStreamRecord, ...]:
    """Return the runtime event snapshot for one run.

    Runtime ordering and integrity are authoritative; no local storage path or
    verification options are accepted at this boundary.
    """
    slug = _validate_project_ref(project)
    if not isinstance(run_id, str) or not run_id.strip():
        raise CapabilityValidationError("run id must be a non-empty string")
    if client is None:
        raise CapabilityInvocationError(
            "explicit generated runtime client is required to read events"
        )
    return _read_runtime_events(client, slug, run_id)


def subscribe_events(
    project: str,
    run_id: str,
    *,
    follow: bool = False,
    poll_interval: float = 0.1,
    idle_polls: int | None = None,
    client: Any | None = None,
) -> Iterator[EventStreamRecord]:
    """Yield runtime events, optionally polling for newly appended events."""
    slug = _validate_project_ref(project)
    if not isinstance(run_id, str) or not run_id.strip():
        raise CapabilityValidationError("run id must be a non-empty string")

    def _iter(client: Any) -> Iterator[EventStreamRecord]:
        yielded = 0
        idle = 0
        while True:
            records = _read_runtime_events(client, slug, run_id)
            if yielded < len(records):
                yield from records[yielded:]
                yielded = len(records)
                idle = 0
                continue
            if not follow:
                return
            if idle_polls is not None and idle >= idle_polls:
                return
            idle += 1
            if poll_interval > 0:
                time.sleep(poll_interval)

    if client is None:
        raise CapabilityInvocationError(
            "explicit generated runtime client is required to subscribe to events"
        )
    return _iter(client)


__all__ = [
    "read_events",
    "subscribe_events",
]
