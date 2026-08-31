"""Runtime snapshot projection tests.

The live snapshot API accepts already-materialized runtime events.  It does
not acquire event logs or registry files from a project directory.
"""

from __future__ import annotations

import pytest

pytest.importorskip("banodoco_timeline_schema")

from astrid.core.timeline.snapshot import (
    SnapshotIntegrityError,
    snapshot_from_runtime,
    verify_frozen,
)

TIMELINE_ID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"


def test_empty_runtime_materialization_is_deterministic_and_verifiable() -> None:
    snapshot = snapshot_from_runtime(
        timeline_id=TIMELINE_ID,
        timeline_ulid=TIMELINE_ULID,
        slug="main",
        project_slug="demo",
        events=[],
    )
    assert snapshot.assembly == {"clips": [], "tracks": []}
    assert snapshot.registry == {"assets": {}}
    assert snapshot.head_version == 0
    assert verify_frozen(snapshot) == list(snapshot.diagnostics)


def test_runtime_snapshot_rejects_noncanonical_identity() -> None:
    with pytest.raises(SnapshotIntegrityError, match="timeline_ulid"):
        snapshot_from_runtime(
            timeline_id=TIMELINE_ID,
            timeline_ulid=TIMELINE_ULID.lower(),
            slug="main",
            project_slug="demo",
            events=[],
        )


def test_runtime_snapshot_never_accepts_a_path_as_event_input() -> None:
    with pytest.raises(SnapshotIntegrityError, match="event 1 is schema-invalid"):
        snapshot_from_runtime(
            timeline_id=TIMELINE_ID,
            timeline_ulid=TIMELINE_ULID,
            slug="main",
            project_slug="demo",
            events=["assembly.jsonl"],  # type: ignore[list-item]
        )
