"""Read-only unified task/audit event stream helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.audit.graph import load_ledger
from astrid.audit.transport import verify_ledger_path

from .events import EVENTS_FILENAME, EventLogError, read_events, verify_chain


@dataclass(frozen=True)
class EventStreamRecord:
    """One read-side record from the task event log or legacy audit ledger."""

    source: str
    line: int
    timestamp: str | None
    kind: str | None
    hash: str | None
    payload: dict[str, Any]


def read_event_stream(
    run_dir: str | Path,
    *,
    include_audit: bool = True,
    verify: bool = True,
) -> list[EventStreamRecord]:
    """Return task and optional audit records without mutating on-disk state."""

    run_path = Path(run_dir)
    events_path = run_path / EVENTS_FILENAME
    ledger_path = run_path / "audit" / "ledger.jsonl"

    if verify:
        ok, line_idx, reason = verify_chain(events_path)
        if not ok:
            location = (
                f"event log line {line_idx + 1}: " if line_idx is not None and line_idx >= 0 else ""
            )
            raise EventLogError(f"task event verification failed: {location}{reason}")
        if include_audit and ledger_path.exists():
            ok, line_number, reason = verify_ledger_path(ledger_path)
            if not ok:
                location = f"audit ledger line {line_number}: " if line_number is not None else ""
                raise EventLogError(f"audit ledger verification failed: {location}{reason}")

    records: list[EventStreamRecord] = []
    for line_number, event in enumerate(read_events(events_path), start=1):
        records.append(
            EventStreamRecord(
                source="task",
                line=line_number,
                timestamp=_optional_str(event.get("ts")),
                kind=_optional_str(event.get("kind")),
                hash=_optional_str(event.get("hash")),
                payload=event,
            )
        )

    if include_audit and ledger_path.exists():
        for record in load_ledger(run_path):
            line_number = record.get("_ledger_line")
            records.append(
                EventStreamRecord(
                    source="audit",
                    line=line_number if isinstance(line_number, int) else -1,
                    timestamp=_optional_str(record.get("created_at")) or _optional_str(record.get("ts")),
                    kind=_optional_str(record.get("event")) or _optional_str(record.get("kind")),
                    hash=_optional_str(record.get("hash")),
                    payload=record,
                )
            )
    return records


def subscribe_event_stream(
    run_dir: str | Path,
    *,
    include_audit: bool = True,
    verify: bool = True,
    follow: bool = False,
    poll_interval: float = 0.1,
    idle_polls: int | None = None,
):
    """Yield task and optional audit records as a synchronous iterator."""

    yielded = 0
    idle = 0
    while True:
        records = read_event_stream(run_dir, include_audit=include_audit, verify=verify)
        if yielded < len(records):
            for record in records[yielded:]:
                yield record
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


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
