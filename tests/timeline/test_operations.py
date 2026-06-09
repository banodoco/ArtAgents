"""Tests for timeline recovery operations (T5)."""

from __future__ import annotations

import pytest
from pathlib import Path
from uuid import uuid4

from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.operations import (
    RecoveryResult,
    recover_to_event,
    recover_to_snapshot,
)
from astrid.core.timeline.projection import ProjectionError

_ACTOR = TimelineActor(type="agent", id="recovery-test")


def _raw_config(label: str = "Video") -> dict:
    return {
        "tracks": [{"id": "v1", "kind": "visual", "label": label}],
        "clips": [],
    }


class TestRecoverToEvent:
    """Tests for recover_to_event()."""

    def test_recover_to_event_verifies_chain_and_appends(
        self, tmp_path: Path, monkeypatch
    ):
        """Recover to an anchor event: chain verified, timeline.recovered appended."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000001"
        home.mkdir(parents=True)

        # Set up identity
        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000001",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        # Mock resolution
        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=home,
                slug="test-tl",
                backend_name_display="local_fs",
            ),
        )

        result = recover_to_event(
            "test-project",
            "test-tl",
            e1.event_id,
            _ACTOR,
            "test recovery",
        )

        assert isinstance(result, RecoveryResult)
        assert result.anchor_event_id == e1.event_id
        assert result.anchor_type == "event"
        assert result.reason == "test recovery"
        # A new timeline.recovered event was appended
        assert result.new_event_id is not None
        assert result.new_version == 2  # 1 existing + 1 recovery
        assert "clip_count" in result.projected_head_summary
        assert len(result.regenerated_artifact_paths) >= 2

        # Verify the recovery event exists
        events = backend.read_events()
        assert len(events) == 2
        assert events[-1].kind == "timeline.recovered"
        assert events[-1].payload.projected_state_summary == _raw_config()

    def test_recover_to_event_refuses_broken_chain(
        self, tmp_path: Path, monkeypatch
    ):
        """Recovery refused when verify_chain() fails."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000002"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000002",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        # Mock resolution
        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000002",
                timeline_home=home,
                slug="test-tl2",
                backend_name_display="local_fs",
            ),
        )

        # Tamper with the event to break chain verification
        events_path = home / "assembly.jsonl"
        # Append a second event with wrong prev_hash to break the chain
        with open(events_path, "a") as f:
            f.write(
                '{"event_id":"01J0000000000000000000000Y","timeline_id":"'
                + timeline_id
                + '","ts":"2026-05-21T00:00:00Z","actor":{"type":"agent","id":"x"},'
                + '"prev_hash":"wrong-hash","hash":"also-wrong","kind":"clip.added",'
                + '"payload":{"clip_id":"bad","kind":"visual","track_id":"visual","asset_id":"x"},'
                + '"schema_version":2}\n'
            )

        with pytest.raises(ProjectionError, match="recovery refused"):
            recover_to_event(
                "test-project",
                "test-tl2",
                e1.event_id,
                _ACTOR,
                "should fail",
            )

    def test_recover_to_event_unknown_event_id(
        self, tmp_path: Path, monkeypatch
    ):
        """Recover to an event that doesn't exist raises ProjectionError."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000003"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000003",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000003",
                timeline_home=home,
                slug="test-tl3",
                backend_name_display="local_fs",
            ),
        )

        with pytest.raises(ProjectionError, match="not found"):
            recover_to_event(
                "test-project",
                "test-tl3",
                "01JJJJJJJJJJJJJJJJJJJJJJJJ",  # nonexistent
                _ACTOR,
                "should fail",
            )


class TestRecoverToSnapshot:
    """Tests for recover_to_snapshot()."""

    def test_recover_to_snapshot_validates_metadata(
        self, tmp_path: Path, monkeypatch
    ):
        """Snapshot recovery validates metadata and appends timeline.recovered."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000004"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000004",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000004",
                timeline_home=home,
                slug="test-tl4",
                backend_name_display="local_fs",
            ),
        )

        result = recover_to_snapshot(
            "test-project",
            "test-tl4",
            snapshot_metadata={
                "timeline_id": timeline_id,
                "last_event_id": e1.event_id,
                "last_hash": e1.hash,
                "version": 1,
                "event_count": 1,
            },
            snapshot_assembly=_raw_config(),
            actor=_ACTOR,
            reason="snapshot recovery test",
        )

        assert isinstance(result, RecoveryResult)
        assert result.anchor_type == "snapshot"
        assert result.anchor_event_id == e1.event_id
        assert result.new_version == 2

        events = backend.read_events()
        assert events[-1].kind == "timeline.recovered"
        assert events[-1].payload.projected_state_summary == _raw_config()

    def test_recover_to_snapshot_mismatched_identity(
        self, tmp_path: Path, monkeypatch
    ):
        """Snapshot with mismatched timeline_id raises ValueError."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000005"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000005",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000005",
                timeline_home=home,
                slug="test-tl5",
                backend_name_display="local_fs",
            ),
        )

        with pytest.raises(ValueError, match="does not match"):
            recover_to_snapshot(
                "test-project",
                "test-tl5",
                snapshot_metadata={
                    "timeline_id": str(uuid4()),  # Different
                    "last_event_id": e1.event_id,
                    "last_hash": e1.hash,
                    "version": 1,
                },
                snapshot_assembly=_raw_config(),
                actor=_ACTOR,
                reason="should fail",
            )

    def test_recover_to_snapshot_hash_mismatch(
        self, tmp_path: Path, monkeypatch
    ):
        """Snapshot with wrong hash raises ProjectionError."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000006"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000006",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000006",
                timeline_home=home,
                slug="test-tl6",
                backend_name_display="local_fs",
            ),
        )

        with pytest.raises(ProjectionError, match="snapshot hash"):
            recover_to_snapshot(
                "test-project",
                "test-tl6",
                snapshot_metadata={
                    "timeline_id": timeline_id,
                    "last_event_id": e1.event_id,
                    "last_hash": "wrong-hash-12345",
                    "version": 1,
                },
                snapshot_assembly=_raw_config(),
                actor=_ACTOR,
                reason="should fail",
            )

    def test_recover_to_snapshot_refuses_broken_chain(
        self, tmp_path: Path, monkeypatch
    ):
        """Snapshot recovery refused when verify_chain() fails."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000007"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000007",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000007",
                timeline_home=home,
                slug="test-tl7",
                backend_name_display="local_fs",
            ),
        )

        # Break the chain by appending a malformed event
        events_path = home / "assembly.jsonl"
        # Corrupt: write a second event with wrong prev_hash to break chain
        with open(events_path, "a") as f:
            # Write a valid-looking event but with a wrong prev_hash
            f.write(
                '{"event_id":"01J0000000000000000000000X","timeline_id":"'
                + timeline_id
                + '","ts":"2026-05-21T00:00:00Z","actor":{"type":"agent","id":"x"},'
                + '"prev_hash":"wrong-hash","hash":"also-wrong","kind":"clip.added",'
                + '"payload":{"clip_id":"bad","kind":"visual","track_id":"visual","asset_id":"x"},'
                + '"schema_version":2}\n'
            )

        with pytest.raises(ProjectionError, match="recovery refused"):
            recover_to_snapshot(
                "test-project",
                "test-tl7",
                snapshot_metadata={
                    "timeline_id": timeline_id,
                    "last_event_id": e1.event_id,
                    "last_hash": e1.hash,
                    "version": 1,
                },
                snapshot_assembly=_raw_config(),
                actor=_ACTOR,
                reason="should fail",
            )

    def test_recover_to_snapshot_rejects_unrelated_valid_config(
        self, tmp_path: Path, monkeypatch
    ):
        """Snapshot config must match the replayed anchor projection."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000008"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000008",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id,
            "timeline.config_replaced",
            {"config": _raw_config("Video")},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000008",
                timeline_home=home,
                slug="test-tl8",
                backend_name_display="local_fs",
            ),
        )

        with pytest.raises(ProjectionError, match="snapshot TimelineConfig digest"):
            recover_to_snapshot(
                "test-project",
                "test-tl8",
                snapshot_metadata={
                    "timeline_id": timeline_id,
                    "last_event_id": e1.event_id,
                    "last_hash": e1.hash,
                    "version": 1,
                },
                snapshot_assembly=_raw_config("Unrelated"),
                actor=_ACTOR,
                reason="should fail",
            )

        assert [event.kind for event in backend.read_events()] == ["timeline.config_replaced"]

    @pytest.mark.parametrize(
        "snapshot_assembly",
        [
            {},
            {"schema_version": 1, "assembly": {"tracks": [], "clips": []}},
            {"tracks": [], "clips": [], "pool": {"entries": []}},
            {"tracks": [], "clips": [], "arrangement": {"clips": []}},
            {"clips": [{"id": "old", "kind": "visual", "track_id": "visual", "asset_id": "a1"}], "tracks": []},
        ],
    )
    def test_recover_to_snapshot_rejects_wrapper_and_legacy_configs(
        self, tmp_path: Path, monkeypatch, snapshot_assembly: dict
    ):
        """Snapshot recovery refuses non-raw runtime container shapes."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "timelines" / "01J00000000000000000000009"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000009",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
        e1 = backend.append_event(
            timeline_id,
            "timeline.config_replaced",
            {"config": _raw_config()},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000009",
                timeline_home=home,
                slug="test-tl9",
                backend_name_display="local_fs",
            ),
        )

        with pytest.raises(ProjectionError, match="valid raw TimelineConfig"):
            recover_to_snapshot(
                "test-project",
                "test-tl9",
                snapshot_metadata={
                    "timeline_id": timeline_id,
                    "last_event_id": e1.event_id,
                    "last_hash": e1.hash,
                    "version": 1,
                },
                snapshot_assembly=snapshot_assembly,
                actor=_ACTOR,
                reason="should fail",
            )

        assert [event.kind for event in backend.read_events()] == ["timeline.config_replaced"]
