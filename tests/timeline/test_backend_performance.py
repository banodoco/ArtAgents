"""Lightweight performance smoke tests for timeline eventlog backends (T11).

Covers:
- Projection over a representative event sequence
- Event reads (bulk read)
- Repeated CAS contention

All tests use only tmp_path and in-memory events — no Supabase credentials
or external dependencies. Thresholds are deliberately loose and deterministic
so they pass reliably on CI. Marked as `performance-smoke`, not benchmark.
"""

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core.project.jsonio import write_json_atomic
from astrid.core.util.time import utc_now_iso
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent
from astrid.core.timeline.projection import project_to_assembly

pytestmark = pytest.mark.performance_smoke

_ACTOR = TimelineActor(type="agent", id="perf:smoke-test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_backend(tmp_path: Path) -> LocalFsBackend:
    timeline_id = str(uuid4())
    home = tmp_path / "timeline_home"
    home.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        home / "assembly.identity.json",
        {
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": "01JP0000000000000000000000",
            "backend": "local_fs",
            "provenance": "imported",
            "created_at": "2026-05-21T00:00:00Z",
        },
    )
    return LocalFsBackend(timeline_id=timeline_id, timeline_home=home)


def _generate_clip_events(count: int, timeline_id: str) -> list[TimelineEvent]:
    """Generate *count* synthetic clip.added events."""
    events: list[TimelineEvent] = []
    for i in range(count):
        event = TimelineEvent.new(
            timeline_id=timeline_id,
            ts=utc_now_iso(),
            actor=_ACTOR,
            kind="clip.added",
            payload={
                "clip_id": f"clip-{i:05d}",
                "kind": "visual",
                "track_id": "visual",
                "asset_id": f"asset-{i:05d}",
                "position": None,
            },
        )
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Projection smoke
# ---------------------------------------------------------------------------


def test_projection_over_representative_sequence(tmp_path: Path):
    """Projection finishes within a generous budget for ~200 events."""
    backend = _build_backend(tmp_path)
    events = _generate_clip_events(200, backend.timeline_id)

    # Append all events
    for event in events:
        backend.append_event(
            backend.timeline_id,
            event.kind,
            event.payload.to_json_obj() if hasattr(event.payload, 'to_json_obj') else dict(event.payload),
            actor=event.actor,
        )

    stored = backend.read_events()
    assert len(stored) == 200

    start = time.monotonic()
    assembly = project_to_assembly(stored)
    elapsed = time.monotonic() - start

    # Projection over 200 events should complete well under 2 seconds
    assert elapsed < 2.0, f"projection took {elapsed:.3f}s, threshold 2.0s"
    assert len(assembly.get("clips", [])) == 200


# ---------------------------------------------------------------------------
# Event read smoke
# ---------------------------------------------------------------------------


def test_event_reads_bulk(tmp_path: Path):
    """Reading 500 events completes within a generous budget."""
    backend = _build_backend(tmp_path)
    events = _generate_clip_events(500, backend.timeline_id)

    for event in events:
        backend.append_event(
            backend.timeline_id,
            event.kind,
            event.payload.to_json_obj() if hasattr(event.payload, 'to_json_obj') else dict(event.payload),
            actor=event.actor,
        )

    start = time.monotonic()
    stored = backend.read_events()
    elapsed = time.monotonic() - start

    assert len(stored) == 500
    # Reading 500 events from a JSONL file should finish well under 1 second
    assert elapsed < 1.0, f"reading 500 events took {elapsed:.3f}s, threshold 1.0s"


# ---------------------------------------------------------------------------
# CAS contention smoke
# ---------------------------------------------------------------------------


def test_repeated_cas_contention(tmp_path: Path):
    """Repeated CAS contention does not degrade or corrupt the event stream."""
    # Append events one at a time with expected_version,
    # and verify that contention is handled correctly (no corruption).
    timeline_id = str(uuid4())
    home = tmp_path / "cas_home"
    home.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        home / "assembly.identity.json",
        {
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": "01JC0000000000000000000000",
            "backend": "local_fs",
            "provenance": "imported",
            "created_at": "2026-05-21T00:00:00Z",
        },
    )
    be = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)

    # Append 100 events, each with correct expected_version
    # This simulates repeated CAS operations
    count = 100
    start = time.monotonic()
    for i in range(count):
        current_version = be.head().version
        be.append_event(
            timeline_id,
            "clip.added",
            {"clip_id": f"cas-clip-{i:05d}", "kind": "visual", "track_id": "visual", "asset_id": f"a-{i:05d}", "position": None},
            actor=_ACTOR,
            expected_version=current_version,
        )
    elapsed = time.monotonic() - start

    # Verify all events were stored
    stored = be.read_events()
    assert len(stored) == count

    # Verify chain integrity
    verification = be.verify_chain()
    assert verification.ok is True

    # CAS with correct version should be reasonably fast
    # 100 events with CAS and fsync each is I/O bound, so we allow up to 10s
    assert elapsed < 10.0, f"100 CAS appends took {elapsed:.3f}s, threshold 10.0s"


def test_cas_contention_with_stale_versions(tmp_path: Path):
    """Stale-version CAS rejections are fast and do not mutate state."""
    timeline_id = str(uuid4())
    home = tmp_path / "stale_home"
    home.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        home / "assembly.identity.json",
        {
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": "01JS0000000000000000000000",
            "backend": "local_fs",
            "provenance": "imported",
            "created_at": "2026-05-21T00:00:00Z",
        },
    )
    be = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)

    # Append one event to set version to 1
    be.append_event(
        timeline_id,
        "clip.added",
        {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": None},
        actor=_ACTOR,
    )

    # Repeated stale-version attempts should all fail quickly without mutation
    count = 50
    start = time.monotonic()
    for _ in range(count):
        try:
            be.append_event(
                timeline_id,
                "clip.added",
                {"clip_id": "cX", "kind": "visual", "track_id": "visual", "asset_id": "aX", "position": None},
                actor=_ACTOR,
                expected_version=0,  # stale: current is 1
            )
            pytest.fail("Expected EventLogStaleVersionError")
        except EventLogStaleVersionError:
            pass
    elapsed = time.monotonic() - start

    # 50 stale-version rejections should complete well under 5 seconds
    assert elapsed < 5.0, f"50 stale CAS rejections took {elapsed:.3f}s, threshold 5.0s"

    # State must be unchanged — still exactly 1 event
    stored = be.read_events()
    assert len(stored) == 1
    assert stored[0].kind == "clip.added"
    assert stored[0].payload.clip_id == "c1"

    head = be.head()
    assert head.version == 1
    assert head.event_count == 1
