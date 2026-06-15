"""Tests for sync_state.py — HeadSnapshot, SyncBookmark, IO helpers, and classifier.

Covers:
- Dataclass serialization shape (HeadSnapshot, SyncBookmark)
- Local sync_bookmark.json read/write via tmp_path
- Corrupt/missing sidecar handling
- Backend head snapshot extraction
- Ancestry validation
- All six classifier states
- Bootstrap-safe missing bookmark
- Incompatible non-empty unrelated heads
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core.timeline.sync_state import (
    SYNC_BOOKMARK_FILENAME,
    HeadSnapshot,
    SyncBookmark,
    SyncStateError,
    classify_sync_state,
    compare_head_to_bookmark,
    head_snapshot_from_backend,
    is_missing_bookmark_bootstrap_safe,
    read_local_sync_bookmark,
    sync_bookmark_path,
    validate_bookmark_matches_timeline,
    write_local_sync_bookmark,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(version: int, last_hash: str | None, last_event_id: str | None) -> HeadSnapshot:
    return HeadSnapshot(version=version, last_hash=last_hash, last_event_id=last_event_id)


EMPTY = _snap(0, None, None)
V1_HEAD = _snap(1, "aaa", "evt-1")
V2_HEAD = _snap(2, "bbb", "evt-2")
V3_HEAD = _snap(3, "ccc", "evt-3")
V1_ALT = _snap(1, "zzz", "evt-alt")  # same version, different hash (divergent)


def _bookmark(
    *,
    timeline_id: str = "tid-1",
    spoke: str = "local",
    spoke_version: int = 0,
    spoke_hash: str | None = None,
    spoke_event_id: str | None = None,
    hub_version: int = 0,
    hub_hash: str | None = None,
    hub_event_id: str | None = None,
    synced_at: str = "2026-06-12T00:00:00Z",
) -> SyncBookmark:
    return SyncBookmark(
        timeline_id=timeline_id,
        spoke=spoke,  # type: ignore[arg-type]
        spoke_version=spoke_version,
        spoke_hash=spoke_hash,
        spoke_event_id=spoke_event_id,
        hub_version=hub_version,
        hub_hash=hub_hash,
        hub_event_id=hub_event_id,
        synced_at=synced_at,
    )


# ---------------------------------------------------------------------------
# HeadSnapshot
# ---------------------------------------------------------------------------

class TestHeadSnapshot:
    """Tests for HeadSnapshot dataclass creation, validation, serialization."""

    # -- valid shapes -------------------------------------------------------

    def test_empty_head(self) -> None:
        h = _snap(0, None, None)
        assert h.version == 0
        assert h.last_hash is None
        assert h.last_event_id is None
        assert h.is_empty is True

    def test_non_empty_head(self) -> None:
        h = _snap(3, "abc123", "evt-42")
        assert h.version == 3
        assert h.last_hash == "abc123"
        assert h.last_event_id == "evt-42"
        assert h.is_empty is False

    # -- validation ---------------------------------------------------------

    def test_negative_version_raises(self) -> None:
        with pytest.raises(SyncStateError, match="version must be >= 0"):
            _snap(-1, None, None)

    def test_empty_head_with_hash_raises(self) -> None:
        with pytest.raises(SyncStateError, match="empty heads must not carry"):
            _snap(0, "aaa", None)

    def test_empty_head_with_event_id_raises(self) -> None:
        with pytest.raises(SyncStateError, match="empty heads must not carry"):
            _snap(0, None, "evt-1")

    def test_non_empty_head_missing_hash_raises(self) -> None:
        with pytest.raises(SyncStateError, match="non-empty heads must include last_hash"):
            _snap(1, None, "evt-1")

    def test_non_empty_head_missing_event_id_raises(self) -> None:
        with pytest.raises(SyncStateError, match="non-empty heads must include last_hash"):
            _snap(1, "aaa", None)

    def test_non_empty_head_empty_hash_raises(self) -> None:
        with pytest.raises(SyncStateError, match="non-empty heads must include last_hash"):
            _snap(1, "", "evt-1")

    def test_non_empty_head_empty_event_id_raises(self) -> None:
        with pytest.raises(SyncStateError, match="non-empty heads must include last_hash"):
            _snap(1, "aaa", "")

    # -- serialization ------------------------------------------------------

    def test_to_json_obj_empty(self) -> None:
        obj = EMPTY.to_json_obj()
        assert obj == {"version": 0, "last_hash": None, "last_event_id": None}

    def test_to_json_obj_non_empty(self) -> None:
        obj = V1_HEAD.to_json_obj()
        assert obj == {"version": 1, "last_hash": "aaa", "last_event_id": "evt-1"}

    def test_from_dict_empty(self) -> None:
        h = HeadSnapshot.from_dict({"version": 0, "last_hash": None, "last_event_id": None})
        assert h == EMPTY

    def test_from_dict_non_empty(self) -> None:
        h = HeadSnapshot.from_dict({"version": 2, "last_hash": "bbb", "last_event_id": "evt-2"})
        assert h == V2_HEAD

    def test_from_dict_bad_type(self) -> None:
        with pytest.raises(SyncStateError, match="must be a JSON object"):
            HeadSnapshot.from_dict("not-a-dict")

    def test_from_dict_version_not_int(self) -> None:
        with pytest.raises(SyncStateError, match="version must be an integer"):
            HeadSnapshot.from_dict({"version": "1", "last_hash": None, "last_event_id": None})

    def test_from_dict_hash_not_string(self) -> None:
        with pytest.raises(SyncStateError, match="last_hash must be a string or null"):
            HeadSnapshot.from_dict({"version": 1, "last_hash": 123, "last_event_id": "evt-1"})

    def test_from_dict_event_id_not_string(self) -> None:
        with pytest.raises(SyncStateError, match="last_event_id must be a string or null"):
            HeadSnapshot.from_dict({"version": 1, "last_hash": "aaa", "last_event_id": 456})

    def test_roundtrip_json(self) -> None:
        h = V3_HEAD
        reloaded = HeadSnapshot.from_dict(h.to_json_obj())
        assert reloaded == h


# ---------------------------------------------------------------------------
# SyncBookmark
# ---------------------------------------------------------------------------

class TestSyncBookmark:
    """Tests for SyncBookmark dataclass creation, validation, serialization."""

    # -- valid shapes -------------------------------------------------------

    def test_empty_bookmark(self) -> None:
        bm = _bookmark()
        assert bm.timeline_id == "tid-1"
        assert bm.spoke == "local"
        assert bm.spoke_version == 0
        assert bm.spoke_hash is None
        assert bm.spoke_event_id is None
        assert bm.hub_version == 0
        assert bm.hub_hash is None
        assert bm.hub_event_id is None
        assert bm.synced_at == "2026-06-12T00:00:00Z"

    def test_non_empty_bookmark(self) -> None:
        bm = _bookmark(
            spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
            hub_version=2, hub_hash="bbb", hub_event_id="evt-2",
        )
        assert bm.spoke_version == 1
        assert bm.spoke_hash == "aaa"
        assert bm.hub_version == 2
        assert bm.hub_hash == "bbb"

    def test_app_spoke(self) -> None:
        bm = _bookmark(spoke="app")
        assert bm.spoke == "app"

    # -- spoke_head / hub_head ---------------------------------------------

    def test_spoke_head(self) -> None:
        bm = _bookmark(spoke_version=3, spoke_hash="ccc", spoke_event_id="evt-3")
        head = bm.spoke_head()
        assert head == _snap(3, "ccc", "evt-3")

    def test_hub_head(self) -> None:
        bm = _bookmark(hub_version=5, hub_hash="eee", hub_event_id="evt-5")
        head = bm.hub_head()
        assert head == _snap(5, "eee", "evt-5")

    # -- validation: timeline_id -------------------------------------------

    def test_empty_timeline_id_raises(self) -> None:
        with pytest.raises(SyncStateError, match="timeline_id must be non-empty"):
            _bookmark(timeline_id="")

    # -- validation: spoke -------------------------------------------------

    def test_invalid_spoke_raises(self) -> None:
        with pytest.raises(SyncStateError, match="spoke must be"):
            _bookmark(spoke="remote")  # type: ignore[arg-type]

    # -- validation: synced_at ---------------------------------------------

    def test_empty_synced_at_raises(self) -> None:
        with pytest.raises(SyncStateError, match="synced_at must be non-empty"):
            _bookmark(synced_at="")

    # -- validation: side constraints (delegated to _validate_bookmark_side)

    def test_negative_spoke_version_raises(self) -> None:
        with pytest.raises(SyncStateError, match="spoke_version must be >= 0"):
            _bookmark(spoke_version=-1)

    def test_spoke_version_zero_with_hash_raises(self) -> None:
        with pytest.raises(SyncStateError, match="spoke_hash.*must be null"):
            _bookmark(spoke_version=0, spoke_hash="aaa")

    def test_spoke_version_non_zero_without_hash_raises(self) -> None:
        with pytest.raises(SyncStateError, match="spoke_hash.*required"):
            _bookmark(spoke_version=1, spoke_hash=None, spoke_event_id="evt-1")

    def test_hub_version_non_zero_without_hash_raises(self) -> None:
        with pytest.raises(SyncStateError, match="hub_hash.*required"):
            _bookmark(hub_version=1, hub_hash=None, hub_event_id="evt-1")

    # -- serialization -----------------------------------------------------

    def test_to_json_obj_empty(self) -> None:
        bm = _bookmark()
        obj = bm.to_json_obj()
        assert obj == {
            "timeline_id": "tid-1",
            "spoke": "local",
            "spoke_version": 0,
            "spoke_hash": None,
            "spoke_event_id": None,
            "hub_version": 0,
            "hub_hash": None,
            "hub_event_id": None,
            "synced_at": "2026-06-12T00:00:00Z",
        }

    def test_to_json_obj_non_empty(self) -> None:
        bm = _bookmark(
            spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
            hub_version=2, hub_hash="bbb", hub_event_id="evt-2",
        )
        obj = bm.to_json_obj()
        assert obj["spoke_version"] == 1
        assert obj["spoke_hash"] == "aaa"
        assert obj["hub_version"] == 2

    def test_from_dict_empty(self) -> None:
        bm = SyncBookmark.from_dict({
            "timeline_id": "tid-1",
            "spoke": "local",
            "spoke_version": 0,
            "spoke_hash": None,
            "spoke_event_id": None,
            "hub_version": 0,
            "hub_hash": None,
            "hub_event_id": None,
            "synced_at": "2026-06-12T00:00:00Z",
        })
        assert bm.timeline_id == "tid-1"
        assert bm.spoke_version == 0

    def test_from_dict_non_empty(self) -> None:
        bm = SyncBookmark.from_dict({
            "timeline_id": "tid-2",
            "spoke": "app",
            "spoke_version": 3,
            "spoke_hash": "ccc",
            "spoke_event_id": "evt-3",
            "hub_version": 4,
            "hub_hash": "ddd",
            "hub_event_id": "evt-4",
            "synced_at": "2026-06-12T12:00:00Z",
        })
        assert bm.timeline_id == "tid-2"
        assert bm.spoke == "app"
        assert bm.spoke_version == 3
        assert bm.hub_version == 4

    def test_from_dict_bad_type(self) -> None:
        with pytest.raises(SyncStateError, match="must be a JSON object"):
            SyncBookmark.from_dict([])

    def test_from_dict_missing_timeline_id(self) -> None:
        with pytest.raises(SyncStateError, match="timeline_id must be a string"):
            SyncBookmark.from_dict({"spoke": "local", "spoke_version": 0, "hub_version": 0, "synced_at": "x"})

    def test_from_dict_bad_version_type(self) -> None:
        with pytest.raises(SyncStateError, match="spoke_version must be an integer"):
            SyncBookmark.from_dict({
                "timeline_id": "tid",
                "spoke": "local",
                "spoke_version": "not-an-int",
                "hub_version": 0,
                "synced_at": "x",
            })

    def test_roundtrip_json(self) -> None:
        bm = _bookmark(
            spoke_version=2, spoke_hash="bbb", spoke_event_id="evt-2",
            hub_version=3, hub_hash="ccc", hub_event_id="evt-3",
        )
        reloaded = SyncBookmark.from_dict(bm.to_json_obj())
        assert reloaded == bm

    def test_from_heads(self) -> None:
        bm = SyncBookmark.from_heads(
            timeline_id="tid-3",
            spoke="app",
            spoke_head=V1_HEAD,
            hub_head=V2_HEAD,
            synced_at="2026-06-12T10:00:00Z",
        )
        assert bm.timeline_id == "tid-3"
        assert bm.spoke == "app"
        assert bm.spoke_version == 1
        assert bm.spoke_hash == "aaa"
        assert bm.hub_version == 2
        assert bm.hub_hash == "bbb"
        assert bm.synced_at == "2026-06-12T10:00:00Z"

    def test_from_heads_auto_synced_at(self) -> None:
        bm = SyncBookmark.from_heads(
            timeline_id="tid-4",
            spoke="local",
            spoke_head=EMPTY,
            hub_head=EMPTY,
        )
        assert bm.synced_at  # auto-generated, non-empty


# ---------------------------------------------------------------------------
# Local sidecar read / write
# ---------------------------------------------------------------------------

class TestLocalSidecarIO:
    """Tests for read_local_sync_bookmark / write_local_sync_bookmark."""

    def test_read_missing_returns_none(self, tmp_path: Path) -> None:
        home = tmp_path / "no-bookmark"
        home.mkdir()
        result = read_local_sync_bookmark(home)
        assert result is None

    def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        home = tmp_path / "with-bookmark"
        home.mkdir()
        bm = _bookmark(
            timeline_id=str(uuid4()),
            spoke="local",
            spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
            hub_version=2, hub_hash="bbb", hub_event_id="evt-2",
        )
        path = write_local_sync_bookmark(home, bm)
        assert path.name == SYNC_BOOKMARK_FILENAME
        assert path.exists()

        reloaded = read_local_sync_bookmark(home)
        assert reloaded is not None
        assert reloaded == bm

    def test_write_overwrites_existing(self, tmp_path: Path) -> None:
        home = tmp_path / "overwrite"
        home.mkdir()
        bm1 = _bookmark(timeline_id="tid-old", spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1")
        bm2 = _bookmark(timeline_id="tid-new", spoke_version=2, spoke_hash="bbb", spoke_event_id="evt-2")
        write_local_sync_bookmark(home, bm1)
        write_local_sync_bookmark(home, bm2)
        reloaded = read_local_sync_bookmark(home)
        assert reloaded is not None
        assert reloaded.timeline_id == "tid-new"

    def test_read_corrupt_json_raises(self, tmp_path: Path) -> None:
        home = tmp_path / "corrupt"
        home.mkdir()
        sidecar = sync_bookmark_path(home)
        sidecar.write_text("{this is not json")
        with pytest.raises(SyncStateError, match="failed to read"):
            read_local_sync_bookmark(home)

    def test_read_valid_json_wrong_shape_raises(self, tmp_path: Path) -> None:
        home = tmp_path / "wrong-shape"
        home.mkdir()
        sidecar = sync_bookmark_path(home)
        sidecar.write_text(json.dumps({"not_a_bookmark": True}))
        with pytest.raises(SyncStateError, match="timeline_id must be a string"):
            read_local_sync_bookmark(home)

    def test_sync_bookmark_path_returns_expected_filename(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        p = sync_bookmark_path(home)
        assert p == home / SYNC_BOOKMARK_FILENAME


# ---------------------------------------------------------------------------
# Backend head snapshot extraction
# ---------------------------------------------------------------------------

class TestHeadSnapshotFromBackend:
    """Tests for head_snapshot_from_backend using LocalFsBackend."""

    def test_empty_backend(self, tmp_path: Path) -> None:
        tid = str(uuid4())
        home = tmp_path / "empty_be"
        home.mkdir()
        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001",
             "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        be = LocalFsBackend(timeline_id=tid, timeline_home=home)
        snap = head_snapshot_from_backend(be)
        assert snap == EMPTY

    def test_non_empty_backend(self, tmp_path: Path) -> None:
        tid = str(uuid4())
        home = tmp_path / "nonempty_be"
        home.mkdir()
        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000002",
             "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema import TimelineActor
        be = LocalFsBackend(timeline_id=tid, timeline_home=home)
        be.append_event(tid, "track.created", {"track_id": "V1"}, actor=TimelineActor(type="agent", id="test"))
        snap = head_snapshot_from_backend(be)
        assert snap.version == 1
        assert snap.last_hash is not None
        assert snap.last_event_id is not None


# ---------------------------------------------------------------------------
# Ancestry / bookmark validation
# ---------------------------------------------------------------------------

class TestAncestryValidation:
    """Tests for validate_bookmark_matches_timeline."""

    def test_matching_timeline_id_passes(self) -> None:
        bm = _bookmark(timeline_id="tid-match")
        # Should not raise
        validate_bookmark_matches_timeline(bm, timeline_id="tid-match")

    def test_mismatched_timeline_id_raises(self) -> None:
        bm = _bookmark(timeline_id="tid-A")
        with pytest.raises(SyncStateError, match="does not match"):
            validate_bookmark_matches_timeline(bm, timeline_id="tid-B")


# ---------------------------------------------------------------------------
# compare_head_to_bookmark
# ---------------------------------------------------------------------------

class TestCompareHeadToBookmark:
    """Tests for compare_head_to_bookmark relation helper."""

    def test_matches(self) -> None:
        assert compare_head_to_bookmark(V1_HEAD, V1_HEAD) == "matches"

    def test_empty_matches_empty(self) -> None:
        assert compare_head_to_bookmark(EMPTY, EMPTY) == "matches"

    def test_advanced(self) -> None:
        assert compare_head_to_bookmark(V2_HEAD, V1_HEAD) == "advanced"

    def test_behind(self) -> None:
        assert compare_head_to_bookmark(V1_HEAD, V2_HEAD) == "behind"

    def test_conflict_same_version_different_hash(self) -> None:
        assert compare_head_to_bookmark(V1_ALT, V1_HEAD) == "conflict"

    def test_conflict_same_version_different_event_id(self) -> None:
        alt = _snap(1, "aaa", "evt-different")
        assert compare_head_to_bookmark(alt, V1_HEAD) == "conflict"


# ---------------------------------------------------------------------------
# Bootstrap safety
# ---------------------------------------------------------------------------

class TestIsMissingBookmarkBootstrapSafe:
    """Tests for is_missing_bookmark_bootstrap_safe."""

    def test_source_empty_is_safe(self) -> None:
        assert is_missing_bookmark_bootstrap_safe(
            source_head=EMPTY, destination_head=V1_HEAD,
        ) is True

    def test_destination_empty_is_safe(self) -> None:
        assert is_missing_bookmark_bootstrap_safe(
            source_head=V1_HEAD, destination_head=EMPTY,
        ) is True

    def test_both_empty_is_safe(self) -> None:
        assert is_missing_bookmark_bootstrap_safe(
            source_head=EMPTY, destination_head=EMPTY,
        ) is True

    def test_source_known_safe_flag(self) -> None:
        # Both non-empty but source_known_safe=True
        assert is_missing_bookmark_bootstrap_safe(
            source_head=V1_HEAD, destination_head=V2_HEAD,
            source_known_safe=True,
        ) is True

    def test_destination_known_safe_flag(self) -> None:
        assert is_missing_bookmark_bootstrap_safe(
            source_head=V1_HEAD, destination_head=V2_HEAD,
            destination_known_safe=True,
        ) is True

    def test_both_non_empty_no_flags_unsafe(self) -> None:
        assert is_missing_bookmark_bootstrap_safe(
            source_head=V1_HEAD, destination_head=V2_HEAD,
        ) is False


# ---------------------------------------------------------------------------
# Classifier — all six states + edge cases
# ---------------------------------------------------------------------------

class TestClassifySyncState:
    """Tests for classify_sync_state covering all six states."""

    # -- bookmark_missing ---------------------------------------------------

    def test_bookmark_missing_empty_destination(self) -> None:
        # Source has data, destination is empty — safe to bootstrap
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=EMPTY,
            bookmark=None,
        )
        assert result == "bookmark_missing"

    def test_bookmark_missing_empty_source(self) -> None:
        result = classify_sync_state(
            source_head=EMPTY,
            destination_head=V1_HEAD,
            bookmark=None,
        )
        assert result == "bookmark_missing"

    def test_bookmark_missing_both_empty(self) -> None:
        result = classify_sync_state(
            source_head=EMPTY,
            destination_head=EMPTY,
            bookmark=None,
        )
        assert result == "bookmark_missing"

    def test_bookmark_missing_known_safe(self) -> None:
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V2_HEAD,
            bookmark=None,
            source_known_safe=True,
        )
        assert result == "bookmark_missing"

    # -- bookmark_incompatible (unsafe bootstrap) --------------------------

    def test_bookmark_incompatible_non_empty_unsafe(self) -> None:
        # Both sides non-empty, no safe flags → incompatible
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V2_HEAD,
            bookmark=None,
        )
        assert result == "bookmark_incompatible"

    def test_bookmark_incompatible_stale_spoke(self) -> None:
        # Bookmark says spoke is at v1, but source is at v2 → spoke behind bookmark → incompatible
        bm = _bookmark(spoke_version=2, spoke_hash="bbb", spoke_event_id="evt-2",
                        hub_version=1, hub_hash="aaa", hub_event_id="evt-1")
        result = classify_sync_state(
            source_head=V1_HEAD,      # source is behind bookmarked spoke (v1 < v2)
            destination_head=V1_HEAD,  # destination matches bookmarked hub
            bookmark=bm,
        )
        assert result == "bookmark_incompatible"

    def test_bookmark_incompatible_stale_hub(self) -> None:
        # Bookmark says hub at v2, but actual destination is at v1 → behind
        bm = _bookmark(spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
                        hub_version=2, hub_hash="bbb", hub_event_id="evt-2")
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V1_HEAD,  # destination is behind bookmarked hub
            bookmark=bm,
        )
        assert result == "bookmark_incompatible"

    def test_bookmark_incompatible_conflict_spoke(self) -> None:
        # Bookmark says spoke at v1 with hash "aaa", actual source at v1 with hash "zzz"
        bm = _bookmark(spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
                        hub_version=1, hub_hash="aaa", hub_event_id="evt-1")
        result = classify_sync_state(
            source_head=V1_ALT,       # same version, different hash → conflict
            destination_head=V1_HEAD,
            bookmark=bm,
        )
        assert result == "bookmark_incompatible"

    def test_bookmark_timeline_id_mismatch_raises(self) -> None:
        bm = _bookmark(timeline_id="tid-wrong")
        with pytest.raises(SyncStateError, match="does not match"):
            classify_sync_state(
                source_head=V1_HEAD,
                destination_head=V1_HEAD,
                bookmark=bm,
                expected_timeline_id="tid-correct",
            )

    # -- up_to_date ---------------------------------------------------------

    def test_up_to_date(self) -> None:
        bm = _bookmark(spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
                        hub_version=1, hub_hash="aaa", hub_event_id="evt-1")
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V1_HEAD,
            bookmark=bm,
        )
        assert result == "up_to_date"

    def test_up_to_date_both_empty(self) -> None:
        bm = _bookmark()
        result = classify_sync_state(
            source_head=EMPTY,
            destination_head=EMPTY,
            bookmark=bm,
        )
        assert result == "up_to_date"

    # -- source_only --------------------------------------------------------

    def test_source_only(self) -> None:
        # Spoke advanced from v1 → v2, hub still at v1
        bm = _bookmark(spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
                        hub_version=1, hub_hash="aaa", hub_event_id="evt-1")
        result = classify_sync_state(
            source_head=V2_HEAD,
            destination_head=V1_HEAD,
            bookmark=bm,
        )
        assert result == "source_only"

    # -- destination_only ---------------------------------------------------

    def test_destination_only(self) -> None:
        bm = _bookmark(spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
                        hub_version=1, hub_hash="aaa", hub_event_id="evt-1")
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V2_HEAD,
            bookmark=bm,
        )
        assert result == "destination_only"

    # -- both_advanced ------------------------------------------------------

    def test_both_advanced(self) -> None:
        bm = _bookmark(spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
                        hub_version=1, hub_hash="aaa", hub_event_id="evt-1")
        result = classify_sync_state(
            source_head=V2_HEAD,
            destination_head=V3_HEAD,
            bookmark=bm,
        )
        assert result == "both_advanced"

    # -- edge: no expected_timeline_id skips validation --------------------

    def test_no_timeline_id_check_when_none(self) -> None:
        # Without expected_timeline_id, the bookmark's timeline_id is not validated.
        # Use a matching bookmark so the state resolves cleanly.
        bm = _bookmark(
            timeline_id="tid-any",
            spoke_version=1, spoke_hash="aaa", spoke_event_id="evt-1",
            hub_version=1, hub_hash="aaa", hub_event_id="evt-1",
        )
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V1_HEAD,
            bookmark=bm,
        )
        assert result == "up_to_date"


# ---------------------------------------------------------------------------
# Incompatible non-empty unrelated heads
# ---------------------------------------------------------------------------

class TestIncompatibleNonEmptyUnrelatedHeads:
    """Covers the 'incompatible non-empty unrelated heads' scenario from the plan."""

    def test_unrelated_non_empty_heads_no_bookmark_unsafe(self) -> None:
        """Two non-empty diverged chains with no bookmark and no safe flags."""
        result = classify_sync_state(
            source_head=V3_HEAD,
            destination_head=V2_HEAD,
            bookmark=None,
        )
        assert result == "bookmark_incompatible"

    def test_unrelated_non_empty_same_version_different_hash_no_bookmark(self) -> None:
        result = classify_sync_state(
            source_head=V1_HEAD,
            destination_head=V1_ALT,
            bookmark=None,
        )
        assert result == "bookmark_incompatible"

    def test_unrelated_behind_bookmark(self) -> None:
        """Bookmark expects v3 but actual heads are behind → incompatible."""
        bm = _bookmark(spoke_version=3, spoke_hash="ccc", spoke_event_id="evt-3",
                        hub_version=3, hub_hash="ccc", hub_event_id="evt-3")
        result = classify_sync_state(
            source_head=V2_HEAD,
            destination_head=V1_HEAD,
            bookmark=bm,
        )
        assert result == "bookmark_incompatible"
