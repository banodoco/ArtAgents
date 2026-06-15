"""Tests for durable keep-both divergence writers."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.timeline.eventlog import EventLogTarget, LocalFsBackend, SupabaseBackend
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.sync_divergence import (
    LocalDivergenceArtifactRef,
    SupabaseDivergenceArtifactRef,
    TransferFailure,
    write_keep_both_artifact,
)
from astrid.core.timeline.sync_state import HeadSnapshot

_ACTOR = TimelineActor(type="agent", id="sync-divergence-test")


def _local_target(tmp_path: Path, name: str) -> EventLogTarget:
    timeline_id = str(uuid4())
    home = tmp_path / name
    home.mkdir()
    write_json_atomic(
        home / "assembly.identity.json",
        {
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": f"01J0000000000000000000000{name[-1]}",
            "backend": "local_fs",
            "provenance": "imported",
            "created_at": "2026-05-21T00:00:00Z",
        },
    )
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
    return EventLogTarget(
        backend_name="local_fs",
        timeline_id=timeline_id,
        timeline_ulid=f"01J0000000000000000000000{name[-1]}",
        timeline_home=home,
        slug=name,
        backend=backend,
        source="local",
    )


class TestLocalKeepBothWriter:
    # ------------------------------------------------------------------
    # Existing tests
    # ------------------------------------------------------------------

    def test_writes_local_divergence_file_before_return(self, tmp_path: Path):
        source = _local_target(tmp_path, "source1")
        destination = _local_target(tmp_path, "dest2")

        source_event = source.backend.append_event(
            source.timeline_id,
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        destination_event = destination.backend.append_event(
            destination.timeline_id,
            "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[source_event],
            destination_suffix=[destination_event],
        )

        assert isinstance(artifact, LocalDivergenceArtifactRef)
        path = Path(artifact.path)
        assert path.exists()
        payload = json.loads(path.read_text())
        assert payload["kind"] == "sync_divergence"
        assert payload["timeline_id"] == destination.timeline_id
        assert payload["source"]["head"]["last_hash"] == source_event.hash
        assert payload["destination"]["head"]["last_hash"] == destination_event.hash
        assert payload["source"]["suffix"][0]["kind"] == "clip.added"
        assert payload["destination"]["suffix"][0]["kind"] == "theme.set"

    def test_raises_transfer_failure_on_local_write_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        source = _local_target(tmp_path, "source3")
        destination = _local_target(tmp_path, "dest4")

        def _boom(path: Path, payload: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(
            "astrid.core.timeline.sync_divergence.write_json_atomic",
            _boom,
        )

        with pytest.raises(TransferFailure, match="failed to persist keep-both artifact"):
            write_keep_both_artifact(
                source=source,
                destination=destination,
                source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                source_suffix=[],
                destination_suffix=[],
            )

    # ------------------------------------------------------------------
    # Full payload shape
    # ------------------------------------------------------------------

    _CLIP_PAYLOAD = {"clip_id": "c9", "kind": "visual", "track_id": "visual", "asset_id": "a9"}

    def test_payload_includes_full_top_level_shape(self, tmp_path: Path):
        """Verify schema_version, kind, created_at, and timeline_id in payload."""
        source = _local_target(tmp_path, "srca")
        destination = _local_target(tmp_path, "dsta")

        source_event = source.backend.append_event(
            source.timeline_id,
            "clip.added",
            self._CLIP_PAYLOAD,
            actor=_ACTOR,
        )
        dest_event = destination.backend.append_event(
            destination.timeline_id,
            "theme.set",
            {"theme_id": "ocean"},
            actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[source_event],
            destination_suffix=[dest_event],
        )

        payload = json.loads(Path(artifact.path).read_text())
        assert payload["schema_version"] == 1
        assert payload["kind"] == "sync_divergence"
        assert isinstance(payload["created_at"], str)
        assert len(payload["created_at"]) > 0
        assert payload["timeline_id"] == destination.timeline_id

    def test_payload_includes_full_head_metadata(self, tmp_path: Path):
        """Verify head snapshots include version, last_hash, and last_event_id."""
        source = _local_target(tmp_path, "srcb")
        destination = _local_target(tmp_path, "dstb")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "dusk"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        payload = json.loads(Path(artifact.path).read_text())

        src_head = payload["source"]["head"]
        assert src_head["version"] == 1
        assert src_head["last_hash"] == se.hash
        assert src_head["last_event_id"] == se.event_id

        dst_head = payload["destination"]["head"]
        assert dst_head["version"] == 1
        assert dst_head["last_hash"] == de.hash
        assert dst_head["last_event_id"] == de.event_id

    def test_payload_includes_empty_head_metadata(self, tmp_path: Path):
        """Verify head snapshots for empty streams (version=0, hashes null)."""
        source = _local_target(tmp_path, "srcc")
        destination = _local_target(tmp_path, "dstc")

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            source_suffix=[],
            destination_suffix=[],
        )

        payload = json.loads(Path(artifact.path).read_text())
        assert payload["source"]["head"]["version"] == 0
        assert payload["source"]["head"]["last_hash"] is None
        assert payload["source"]["head"]["last_event_id"] is None
        assert payload["destination"]["head"]["version"] == 0
        assert payload["destination"]["head"]["last_hash"] is None
        assert payload["destination"]["head"]["last_event_id"] is None

    def test_payload_includes_side_rendering_fields(self, tmp_path: Path):
        """Verify each side includes backend, timeline_id, timeline_home, slug."""
        source = _local_target(tmp_path, "srcd")
        destination = _local_target(tmp_path, "dstd")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "midnight"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        payload = json.loads(Path(artifact.path).read_text())

        for side_key, target in [("source", source), ("destination", destination)]:
            side = payload[side_key]
            assert side["backend"] == "local_fs"
            assert side["timeline_id"] == target.timeline_id
            assert side["timeline_home"] == str(target.timeline_home)
            assert side["slug"] == target.slug

    # ------------------------------------------------------------------
    # Suffix preservation
    # ------------------------------------------------------------------

    def test_preserves_full_suffix_event_details(self, tmp_path: Path):
        """Verify each suffix event preserves event_id, hash, ts, kind, actor, prev_hash."""
        source = _local_target(tmp_path, "srce")
        destination = _local_target(tmp_path, "dste")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c42", "kind": "visual", "track_id": "visual", "asset_id": "a42"}, actor=_ACTOR,
        )
        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "aurora"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        payload = json.loads(Path(artifact.path).read_text())

        src_ev = payload["source"]["suffix"][0]
        assert src_ev["event_id"] == se.event_id
        assert src_ev["hash"] == se.hash
        assert src_ev["ts"] == se.ts
        assert src_ev["kind"] == "clip.added"
        assert src_ev["prev_hash"] is None  # first event in stream
        assert src_ev["actor"]["type"] == "agent"
        assert src_ev["actor"]["id"] == "sync-divergence-test"

        dst_ev = payload["destination"]["suffix"][0]
        assert dst_ev["event_id"] == de.event_id
        assert dst_ev["hash"] == de.hash
        assert dst_ev["ts"] == de.ts
        assert dst_ev["kind"] == "theme.set"
        assert dst_ev["actor"]["type"] == "agent"

    def test_multiple_events_in_suffix(self, tmp_path: Path):
        """Verify both side suffixes can carry multiple events."""
        source = _local_target(tmp_path, "srcf")
        destination = _local_target(tmp_path, "dstf")

        se1 = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        se2 = source.backend.append_event(
            source.timeline_id, "clip.moved",
            {"clip_id": "c1", "position": {"mode": "index", "index": 0}}, actor=_ACTOR,
        )
        de1 = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "sunset"}, actor=_ACTOR,
        )
        de2 = destination.backend.append_event(
            destination.timeline_id, "config.set",
            {"fps": 60}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se1, se2],
            destination_suffix=[de1, de2],
        )

        payload = json.loads(Path(artifact.path).read_text())
        assert len(payload["source"]["suffix"]) == 2
        assert payload["source"]["suffix"][0]["event_id"] == se1.event_id
        assert payload["source"]["suffix"][1]["event_id"] == se2.event_id
        assert payload["source"]["suffix"][1]["prev_hash"] == se1.hash
        assert len(payload["destination"]["suffix"]) == 2
        assert payload["destination"]["suffix"][0]["event_id"] == de1.event_id
        assert payload["destination"]["suffix"][1]["event_id"] == de2.event_id

    def test_empty_suffix_arrays(self, tmp_path: Path):
        """Verify both sides can have empty suffix arrays."""
        source = _local_target(tmp_path, "srcg")
        destination = _local_target(tmp_path, "dstg")

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            source_suffix=[],
            destination_suffix=[],
        )

        payload = json.loads(Path(artifact.path).read_text())
        assert payload["source"]["suffix"] == []
        assert payload["destination"]["suffix"] == []

    def test_source_only_suffix_preserved(self, tmp_path: Path):
        """Verify source suffix is preserved even when destination suffix is empty."""
        source = _local_target(tmp_path, "srch")
        destination = _local_target(tmp_path, "dsth")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            source_suffix=[se],
            destination_suffix=[],
        )

        payload = json.loads(Path(artifact.path).read_text())
        assert len(payload["source"]["suffix"]) == 1
        assert payload["source"]["suffix"][0]["event_id"] == se.event_id
        assert payload["destination"]["suffix"] == []

    def test_destination_only_suffix_preserved(self, tmp_path: Path):
        """Verify destination suffix is preserved even when source suffix is empty."""
        source = _local_target(tmp_path, "srci")
        destination = _local_target(tmp_path, "dsti")

        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "dawn"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[],
            destination_suffix=[de],
        )

        payload = json.loads(Path(artifact.path).read_text())
        assert payload["source"]["suffix"] == []
        assert len(payload["destination"]["suffix"]) == 1
        assert payload["destination"]["suffix"][0]["event_id"] == de.event_id

    # ------------------------------------------------------------------
    # Artifact reference
    # ------------------------------------------------------------------

    def test_artifact_ref_includes_all_fields(self, tmp_path: Path):
        """Verify LocalDivergenceArtifactRef has path, timeline_id, kind, created_at."""
        source = _local_target(tmp_path, "srcj")
        destination = _local_target(tmp_path, "dstj")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "storm"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        assert isinstance(artifact, LocalDivergenceArtifactRef)
        assert artifact.kind == "local_file"
        assert artifact.timeline_id == destination.timeline_id
        assert isinstance(artifact.path, str)
        assert len(artifact.path) > 0
        assert isinstance(artifact.created_at, str)
        assert len(artifact.created_at) > 0

        ref_json = artifact.to_json_obj()
        assert ref_json == {
            "kind": "local_file",
            "path": artifact.path,
            "timeline_id": artifact.timeline_id,
            "created_at": artifact.created_at,
        }

    def test_artifact_ref_path_points_to_existing_file(self, tmp_path: Path):
        """Verify the artifact ref path is an actual existing file."""
        source = _local_target(tmp_path, "srck")
        destination = _local_target(tmp_path, "dstk")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "fog"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        path = Path(artifact.path)
        assert path.exists()
        assert path.is_file()
        # The file should be inside the destination timeline home
        assert str(destination.timeline_home) in str(path)

    # ------------------------------------------------------------------
    # Filename convention
    # ------------------------------------------------------------------

    def test_filename_follows_divergence_timestamp_convention(self, tmp_path: Path):
        """Verify the divergence file is named divergence-{stamp}.json."""
        source = _local_target(tmp_path, "srcl")
        destination = _local_target(tmp_path, "dstl")

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        de = destination.backend.append_event(
            destination.timeline_id, "theme.set",
            {"theme_id": "mist"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        filename = Path(artifact.path).name
        assert filename.startswith("divergence-")
        assert filename.endswith(".json")
        # Timestamp stamp should not contain colons, dashes, or dots (sanitized)
        stamp = filename[len("divergence-"):-len(".json")]
        assert ":" not in stamp
        assert "." not in stamp
        assert "-" in stamp  # ISO date portion: YYYYMMDD-HHMMSS...

    # ------------------------------------------------------------------
    # Failure paths (beyond write error)
    # ------------------------------------------------------------------

    def test_raises_when_timeline_home_is_none(self, tmp_path: Path):
        """Local divergence write requires destination.timeline_home."""
        source = _local_target(tmp_path, "srcm")
        # Create a target with no timeline_home
        dest_id = str(uuid4())
        dest_backend = LocalFsBackend(timeline_id=dest_id, timeline_home=tmp_path / "dstm")
        destination = EventLogTarget(
            backend_name="local_fs",
            timeline_id=dest_id,
            timeline_ulid=None,
            timeline_home=None,  # explicitly None
            slug="no-home",
            backend=dest_backend,
            source="local",
        )

        with pytest.raises(TransferFailure, match="requires a destination timeline home"):
            write_keep_both_artifact(
                source=source,
                destination=destination,
                source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                source_suffix=[],
                destination_suffix=[],
            )


class TestSupabaseKeepBothWriter:
    # ------------------------------------------------------------------
    # Existing tests
    # ------------------------------------------------------------------

    def test_writes_supabase_divergence_log_before_return(
        self, tmp_path: Path, fake_supabase_transport
    ):
        source = _local_target(tmp_path, "source5")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        source_event = source.backend.append_event(
            source.timeline_id,
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        destination_event = fake_supabase_transport.append_event(
            timeline_id=destination.timeline_id,
            kind="theme.set",
            payload={"theme_id": "light"},
            actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[source_event],
            destination_suffix=[destination_event],
        )

        assert isinstance(artifact, SupabaseDivergenceArtifactRef)
        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == artifact.entry_id
        assert row["timeline_id"] == destination.timeline_id
        assert row["spoke"] == "local"
        assert row["spoke_suffix"][0]["kind"] == "clip.added"
        assert row["hub_suffix"][0]["kind"] == "theme.set"

    def test_raises_transfer_failure_on_supabase_write_error(
        self, tmp_path: Path, fake_supabase_transport, monkeypatch: pytest.MonkeyPatch
    ):
        source = _local_target(tmp_path, "source6")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        def _boom(**kwargs: object) -> dict[str, object]:
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(fake_supabase_transport, "write_divergence", _boom)

        with pytest.raises(TransferFailure, match="Supabase divergence_log write failed"):
            write_keep_both_artifact(
                source=source,
                destination=destination,
                source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                source_suffix=[],
                destination_suffix=[],
            )

    # ------------------------------------------------------------------
    # Full head/provenance metadata
    # ------------------------------------------------------------------

    def test_divergence_row_includes_full_spoke_and_hub_metadata(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Verify spoke/hub version, hash, and event_id are all stored."""
        source = _local_target(tmp_path, "srcn")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c-z", "kind": "visual", "track_id": "visual", "asset_id": "a-z"}, actor=_ACTOR,
        )
        de = fake_supabase_transport.append_event(
            timeline_id=destination.timeline_id,
            kind="theme.set", payload={"theme_id": "ember"},
            actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        assert len(rows) == 1
        row = rows[0]

        # Spoke (local source) metadata
        assert row["spoke_version"] == 1
        assert row["spoke_hash"] == se.hash
        assert row["spoke_event_id"] == se.event_id

        # Hub (Supabase destination) metadata
        assert row["hub_version"] == 1
        assert row["hub_hash"] == de.hash
        assert row["hub_event_id"] == de.event_id

        # Provenance fields
        assert row["timeline_id"] == destination.timeline_id
        assert row["spoke"] == "local"
        assert row["chosen_side"] == "undecided"
        assert row["artifact_pointer"] is None
        assert isinstance(row["created_at"], str)
        assert len(row["created_at"]) > 0
        assert row["resolved_at"] is None  # undecided → not resolved yet

    def test_divergence_row_with_empty_heads(self, tmp_path: Path, fake_supabase_transport):
        """Verify spoke/hub metadata when both heads are empty (version 0)."""
        source = _local_target(tmp_path, "srco")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            source_suffix=[],
            destination_suffix=[],
        )

        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        row = rows[0]
        assert row["spoke_version"] == 0
        assert row["spoke_hash"] is None
        assert row["spoke_event_id"] is None
        assert row["hub_version"] == 0
        assert row["hub_hash"] is None
        assert row["hub_event_id"] is None

    # ------------------------------------------------------------------
    # Suffix preservation
    # ------------------------------------------------------------------

    def test_preserves_full_suffix_event_details_in_divergence_row(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Verify each suffix event in the divergence row has event_id, hash, ts, kind."""
        source = _local_target(tmp_path, "srcp")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "cx", "kind": "visual", "track_id": "visual", "asset_id": "ax"}, actor=_ACTOR,
        )
        de = fake_supabase_transport.append_event(
            timeline_id=destination.timeline_id,
            kind="theme.set", payload={"theme_id": "cinder"},
            actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        row = rows[0]

        spoke_ev = row["spoke_suffix"][0]
        assert spoke_ev["event_id"] == se.event_id
        assert spoke_ev["hash"] == se.hash
        assert spoke_ev["ts"] == se.ts
        assert spoke_ev["kind"] == "clip.added"
        assert spoke_ev["actor"]["type"] == "agent"

        hub_ev = row["hub_suffix"][0]
        assert hub_ev["event_id"] == de.event_id
        assert hub_ev["hash"] == de.hash
        assert hub_ev["ts"] == de.ts
        assert hub_ev["kind"] == "theme.set"

    def test_multiple_events_in_divergence_suffix(self, tmp_path: Path, fake_supabase_transport):
        """Verify both spoke_suffix and hub_suffix can carry multiple events."""
        source = _local_target(tmp_path, "srcq")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        se1 = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        se2 = source.backend.append_event(
            source.timeline_id, "clip.moved",
            {"clip_id": "c1", "position": {"mode": "index", "index": 0}}, actor=_ACTOR,
        )
        de1 = fake_supabase_transport.append_event(
            timeline_id=destination.timeline_id,
            kind="theme.set", payload={"theme_id": "ash"}, actor=_ACTOR,
        )
        de2 = fake_supabase_transport.append_event(
            timeline_id=destination.timeline_id,
            kind="config.set", payload={"fps": 30}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se1, se2],
            destination_suffix=[de1, de2],
        )

        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        row = rows[0]
        assert len(row["spoke_suffix"]) == 2
        assert row["spoke_suffix"][0]["event_id"] == se1.event_id
        assert row["spoke_suffix"][1]["event_id"] == se2.event_id
        assert len(row["hub_suffix"]) == 2
        assert row["hub_suffix"][0]["event_id"] == de1.event_id
        assert row["hub_suffix"][1]["event_id"] == de2.event_id

    def test_empty_suffix_in_divergence_row(self, tmp_path: Path, fake_supabase_transport):
        """Verify both suffix arrays can be empty."""
        source = _local_target(tmp_path, "srcr")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            source_suffix=[],
            destination_suffix=[],
        )

        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        row = rows[0]
        assert row["spoke_suffix"] == []
        assert row["hub_suffix"] == []

    # ------------------------------------------------------------------
    # Artifact reference
    # ------------------------------------------------------------------

    def test_artifact_ref_includes_all_fields_supabase(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Verify SupabaseDivergenceArtifactRef has entry_id, timeline_id, spoke, kind, created_at."""
        source = _local_target(tmp_path, "srcs")
        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        se = source.backend.append_event(
            source.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=_ACTOR,
        )
        de = fake_supabase_transport.append_event(
            timeline_id=destination.timeline_id,
            kind="theme.set", payload={"theme_id": "ember"}, actor=_ACTOR,
        )

        artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=HeadSnapshot.from_eventlog_head(source.backend.head()),
            destination_head=HeadSnapshot.from_eventlog_head(destination.backend.head()),
            source_suffix=[se],
            destination_suffix=[de],
        )

        assert isinstance(artifact, SupabaseDivergenceArtifactRef)
        assert artifact.kind == "supabase_divergence_log"
        assert artifact.timeline_id == destination.timeline_id
        assert artifact.spoke == "local"
        assert isinstance(artifact.entry_id, str)
        assert len(artifact.entry_id) > 0
        assert isinstance(artifact.created_at, str)
        assert len(artifact.created_at) > 0

        ref_json = artifact.to_json_obj()
        assert ref_json == {
            "kind": "supabase_divergence_log",
            "entry_id": artifact.entry_id,
            "timeline_id": artifact.timeline_id,
            "spoke": artifact.spoke,
            "created_at": artifact.created_at,
        }

        # entry_id must match what's stored
        rows = fake_supabase_transport.read_divergence_log(timeline_id=destination.timeline_id)
        assert rows[0]["id"] == artifact.entry_id

    # ------------------------------------------------------------------
    # Failure paths
    # ------------------------------------------------------------------

    def test_raises_when_destination_backend_is_not_supabase(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Supabase divergence write requires a SupabaseBackend."""
        source = _local_target(tmp_path, "srct")
        # destination is local_fs, not supabase — but backend_name is set to "supabase"
        dest_backend = LocalFsBackend(
            timeline_id=str(uuid4()),
            timeline_home=tmp_path / "dstt",
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=dest_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=dest_backend,
            source="remote",
        )

        with pytest.raises(TransferFailure, match="requires a SupabaseBackend"):
            write_keep_both_artifact(
                source=source,
                destination=destination,
                source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                source_suffix=[],
                destination_suffix=[],
            )

    def test_raises_when_source_is_not_local_fs(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Supabase divergence currently requires a local_fs source."""
        # Create a supabase-backed "source"
        source_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        source = EventLogTarget(
            backend_name="supabase",
            timeline_id=source_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=source_backend,
            source="remote",
        )

        destination_backend = SupabaseBackend(
            timeline_id=str(uuid4()),
            transport=fake_supabase_transport,
            enabled=True,
        )
        destination = EventLogTarget(
            backend_name="supabase",
            timeline_id=destination_backend.timeline_id,
            timeline_ulid=None,
            timeline_home=None,
            slug=None,
            backend=destination_backend,
            source="remote",
        )

        with pytest.raises(TransferFailure, match="requires a local spoke source"):
            write_keep_both_artifact(
                source=source,
                destination=destination,
                source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                source_suffix=[],
                destination_suffix=[],
            )

    def test_raises_for_unsupported_destination_backend(self, tmp_path: Path):
        """write_keep_both_artifact raises for unknown backend names."""
        source = _local_target(tmp_path, "srcu")

        # Create a target with an unsupported backend_name
        dest_id = str(uuid4())
        dest_backend = LocalFsBackend(timeline_id=dest_id, timeline_home=tmp_path / "dstu")
        destination = EventLogTarget(
            backend_name="unknown_backend",
            timeline_id=dest_id,
            timeline_ulid=None,
            timeline_home=tmp_path / "dstu",
            slug="bad",
            backend=dest_backend,
            source="local",
        )

        with pytest.raises(TransferFailure, match="unsupported divergence destination backend"):
            write_keep_both_artifact(
                source=source,
                destination=destination,
                source_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                destination_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
                source_suffix=[],
                destination_suffix=[],
            )
