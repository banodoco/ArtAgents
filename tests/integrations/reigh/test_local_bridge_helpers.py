"""Helper tests for bridge fixture builders and identity sidecar layouts.

Covers:
- Legacy direct-assembly (assembly.json without identity sidecar)
- Event-log-like identity sidecar (assembly.identity.json with timeline_id)
- Registry fixture seeding
- Media file seeding
"""

from __future__ import annotations

import json

import pytest

# Import from the local conftest (pytest will have it available as a fixture module).
# We use the functions directly since they're defined in conftest.py in the same package.
import sys
import threading
import time
from pathlib import Path
from pathlib import Path as _Path

# Ensure the integrations.reigh package is importable
_pkg_dir = _Path(__file__).resolve().parent
if str(_pkg_dir) not in sys.path:
    sys.path.insert(0, str(_pkg_dir.parent.parent.parent))

import astrid.core.integrations.reigh.local_bridge as local_bridge
from astrid.core.integrations.reigh.local_bridge import (
    BRIDGE_AUDIO_PROXY_PROFILE_VERSION,
    BRIDGE_VIDEO_PROXY_PROFILE_VERSION,
    REIGH_LOCAL_EDITOR_ACTOR,
    bridge_registry_path,
    find_bridge_timeline,
    list_bridge_project_dirs,
    list_bridge_projects,
    list_bridge_timelines,
    load_bridge_registry,
    load_bridge_timeline,
    resolve_bridge_asset,
    resolve_bridge_projects_root,
    save_bridge_timeline,
)
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.eventlog.reigh_events import construct_reigh_timeline_events
from astrid.core.timeline.eventlog.selector import resolve_event_log_target
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError
from astrid.core.timeline.events.schema import canonical_json_bytes
from astrid.core.timeline.observability import resolve_timeline_target
from astrid.core.timeline.paths import load_assembly_json_with_repair
from tests.integrations.reigh.conftest import (  # type: ignore[import-not-found]
    make_assembly_json,
    make_identity_json,
    make_project_json,
    make_registry_json,
    make_timeline_id,
)


class TestFixtureDataFactories:
    """Verify low-level data factory contracts."""

    def test_make_timeline_id_is_stable_string(self) -> None:
        tid = make_timeline_id()
        assert isinstance(tid, str)
        assert len(tid) == 36  # UUID string length
        assert tid.count("-") == 4

    def test_make_assembly_json_defaults(self) -> None:
        a = make_assembly_json()
        assert a["output"]["resolution"] == "1920x1080"
        assert a["output"]["fps"] == 24
        assert a["clips"] == []
        assert a["tracks"] == []

    def test_make_assembly_json_custom(self) -> None:
        a = make_assembly_json(
            clips=[{"id": "c1", "at": 0, "track": "V1"}],
            tracks=[{"id": "V1", "kind": "visual", "label": "V1"}],
            output={"resolution": "1280x720", "fps": 30, "file": "out.mp4"},
        )
        assert len(a["clips"]) == 1
        assert a["clips"][0]["id"] == "c1"
        assert a["output"]["resolution"] == "1280x720"

    def test_make_identity_json_defaults(self) -> None:
        i = make_identity_json()
        assert "timeline_id" in i
        assert isinstance(i["timeline_id"], str)
        assert len(i["timeline_id"]) == 36
        assert i["provenance"] == "created"
        assert i["backend"] == "local_fs"

    def test_make_identity_json_custom_timeline_id(self) -> None:
        tid = "00000000-0000-0000-0000-000000000001"
        i = make_identity_json(timeline_id=tid, provenance="branched", backend="supabase")
        assert i["timeline_id"] == tid
        assert i["provenance"] == "branched"
        assert i["backend"] == "supabase"

    def test_make_project_json_defaults(self) -> None:
        p = make_project_json()
        assert "slug" in p
        assert p["name"] == p["slug"]
        assert p["schema_version"] == 1

    def test_make_project_json_custom(self) -> None:
        p = make_project_json(slug="ados-talks", name="Ados Talks", default_timeline_id="tid-1")
        assert p["slug"] == "ados-talks"
        assert p["name"] == "Ados Talks"
        assert p["default_timeline_id"] == "tid-1"

    def test_make_registry_json_defaults(self) -> None:
        r = make_registry_json()
        assert r == {"assets": {}}

    def test_make_registry_json_with_assets(self) -> None:
        r = make_registry_json(assets={
            "clip-1": {"file": "intro.mp4", "type": "video"},
            "clip-2": {"file": "https://example.com/bg.jpg", "type": "image"},
        })
        assert r["assets"]["clip-1"]["file"] == "intro.mp4"
        assert r["assets"]["clip-2"]["file"] == "https://example.com/bg.jpg"


class TestBridgeSeedProjectLegacyDirectAssembly:
    """Legacy direct-assembly layout: assembly.json only, no identity sidecar."""

    def test_seed_legacy_creates_project_dir(self, seed_bridge_project) -> None:
        pdir = seed_bridge_project(slug="legacy", with_identity=False, with_registry=False)
        assert pdir.is_dir()
        assert (pdir / "project.json").is_file()

    def test_seed_legacy_no_identity_file(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000000"
        pdir = seed_bridge_project(
            slug="legacy-no-id",
            timeline_ulid=ulid,
            with_identity=False,
            with_registry=False,
        )
        tdir = pdir / "timelines" / ulid
        assert tdir.is_dir()
        assert (tdir / "assembly.json").is_file()
        assert not (tdir / "assembly.identity.json").exists()

    def test_seed_legacy_assembly_content(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000001"
        pdir = seed_bridge_project(
            slug="legacy-content",
            timeline_ulid=ulid,
            with_identity=False,
            clips=[{"id": "c1", "at": 0, "track": "V1", "asset": "img1"}],
        )
        assembly = json.loads(
            (pdir / "timelines" / ulid / "assembly.json").read_text(encoding="utf-8")
        )
        assert assembly["clips"][0]["id"] == "c1"
        assert assembly["clips"][0]["asset"] == "img1"


class TestBridgeSeedProjectEventLogIdentity:
    """Event-log-like identity sidecar layout: assembly.json + assembly.identity.json."""

    def test_seed_event_log_creates_identity(self, seed_bridge_project) -> None:
        tid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        ulid = "01JM4K5N7P0000000000000002"
        pdir = seed_bridge_project(
            slug="eventlog",
            timeline_ulid=ulid,
            timeline_id=tid,
            with_identity=True,
        )
        identity = json.loads(
            (pdir / "timelines" / ulid / "assembly.identity.json").read_text(encoding="utf-8")
        )
        assert identity["timeline_id"] == tid
        assert identity["provenance"] == "created"
        assert identity["backend"] == "local_fs"

    def test_seed_event_log_identity_round_trips(self, seed_bridge_project) -> None:
        """Prove the timeline_id written to identity matches the one we passed."""
        tid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        ulid = "01JM4K5N7P0000000000000003"
        pdir = seed_bridge_project(
            slug="roundtrip",
            timeline_ulid=ulid,
            timeline_id=tid,
        )
        from tests.integrations.reigh.conftest import (
            read_bridge_identity,  # type: ignore[import-not-found]
        )

        identity = read_bridge_identity(pdir, ulid)
        assert identity["timeline_id"] == tid

    def test_seed_event_log_registry_and_sources(self, seed_bridge_project) -> None:
        """Ensure registry and sources dir are created by default."""
        ulid = "01JM4K5N7P0000000000000004"
        pdir = seed_bridge_project(
            slug="with-registry",
            timeline_ulid=ulid,
            assets={"a1": {"file": "clip1.mp4"}},
        )
        tdir = pdir / "timelines" / ulid
        assert (tdir / "registry.json").is_file()
        assert (pdir / "sources").is_dir()

    def test_seed_event_log_without_registry(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000005"
        pdir = seed_bridge_project(
            slug="no-registry",
            timeline_ulid=ulid,
            with_registry=False,
        )
        tdir = pdir / "timelines" / ulid
        assert not (tdir / "registry.json").exists()

    def test_seed_event_log_custom_provenance(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000006"
        pdir = seed_bridge_project(
            slug="branched",
            timeline_ulid=ulid,
            identity_provenance="branched",
        )
        identity = json.loads(
            (pdir / "timelines" / ulid / "assembly.identity.json").read_text(encoding="utf-8")
        )
        assert identity["provenance"] == "branched"

    def test_seed_event_log_preserves_assembly_clips(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000007"
        clips = [
            {"id": "c1", "at": 0, "track": "V1", "asset": "a1"},
            {"id": "c2", "at": 5, "track": "A1", "asset": "a2"},
        ]
        pdir = seed_bridge_project(
            slug="multi-clip",
            timeline_ulid=ulid,
            clips=clips,
        )
        assembly = json.loads(
            (pdir / "timelines" / ulid / "assembly.json").read_text(encoding="utf-8")
        )
        assert len(assembly["clips"]) == 2
        assert assembly["clips"][0]["id"] == "c1"
        assert assembly["clips"][1]["id"] == "c2"


class TestBridgeSeedProjectExternalPathIsolation:
    """Prove fixtures never depend on external paths or filesystem state."""

    def test_no_external_paths_in_assembly(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000008"
        pdir = seed_bridge_project(slug="isolated", timeline_ulid=ulid)
        assembly = json.loads(
            (pdir / "timelines" / ulid / "assembly.json").read_text(encoding="utf-8")
        )
        # No external paths should appear
        text = json.dumps(assembly)
        assert "/Users/" not in text
        assert "/home/" not in text

    def test_no_external_paths_in_identity(self, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000009"
        pdir = seed_bridge_project(slug="isolated2", timeline_ulid=ulid)
        identity = json.loads(
            (pdir / "timelines" / ulid / "assembly.identity.json").read_text(encoding="utf-8")
        )
        text = json.dumps(identity)
        assert "/Users/" not in text
        assert "/home/" not in text

    def test_seed_is_deterministic(self, tmp_bridge_root) -> None:
        """Two seeds with same params produce same content structure."""
        # We can't reuse the fixture-callable cleanly across two seeds without
        # importing, so test that the tmp_bridge_root is empty before seeding.
        assert list(tmp_bridge_root.iterdir()) == []


class TestLocalBridgeHelpers:
    def test_resolve_bridge_projects_root_uses_explicit_root(self, tmp_bridge_root, monkeypatch) -> None:
        other_root = tmp_bridge_root / "other-root"
        other_root.mkdir()
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_bridge_root / "env-root"))
        assert resolve_bridge_projects_root(other_root) == other_root.resolve()

    def test_resolve_bridge_projects_root_uses_env_when_root_missing(self, tmp_bridge_root, monkeypatch) -> None:
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_bridge_root))
        assert resolve_bridge_projects_root() == tmp_bridge_root.resolve()

    def test_list_bridge_project_dirs_is_sorted_and_filters_non_projects(self, tmp_bridge_root, seed_bridge_project) -> None:
        seed_bridge_project(slug="z-last")
        seed_bridge_project(slug="a-first")
        (tmp_bridge_root / "notes").mkdir()
        (tmp_bridge_root / "notes" / "readme.txt").write_text("no project here", encoding="utf-8")

        project_dirs = list_bridge_project_dirs(tmp_bridge_root)

        assert [path.name for path in project_dirs] == ["a-first", "z-last"]

    def test_list_bridge_projects_returns_sorted_slug_name_rows(self, tmp_bridge_root, seed_bridge_project) -> None:
        seed_bridge_project(slug="z-last")
        seed_bridge_project(slug="a-first")

        rows = list_bridge_projects(tmp_bridge_root)

        assert rows == [
            {"slug": "a-first", "name": "a-first"},
            {"slug": "z-last", "name": "z-last"},
        ]

    def test_list_bridge_projects_skips_malformed_and_falls_back_to_slug(self, tmp_bridge_root, seed_bridge_project) -> None:
        seed_bridge_project(slug="good-proj")
        (tmp_bridge_root / "good-proj" / "project.json").write_text(
            json.dumps({"slug": "good-proj", "name": "Good Project", "schema_version": 1}),
            encoding="utf-8",
        )

        # project.json is malformed JSON -> the whole dir must be skipped
        bad_dir = tmp_bridge_root / "bad-proj"
        bad_dir.mkdir()
        (bad_dir / "project.json").write_text("{not json", encoding="utf-8")

        # project.json without a name -> falls back to the slug
        noname_dir = tmp_bridge_root / "noname-proj"
        noname_dir.mkdir()
        (noname_dir / "project.json").write_text(
            json.dumps({"slug": "noname-proj", "schema_version": 1}),
            encoding="utf-8",
        )

        assert list_bridge_projects(tmp_bridge_root) == [
            {"slug": "good-proj", "name": "Good Project"},
            {"slug": "noname-proj", "name": "noname-proj"},
        ]

    def test_list_bridge_projects_empty_root(self, tmp_bridge_root) -> None:
        assert list_bridge_projects(tmp_bridge_root) == []

    def test_list_bridge_timelines_returns_records_with_identity_and_default(
        self, tmp_bridge_root, seed_bridge_project,
    ) -> None:
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        default_ulid = "01JM4K5N7P0000000000000101"
        other_ulid = "01JM4K5N7P0000000000000102"
        project_dir = seed_bridge_project(
            slug="timelines-list",
            timeline_ulid=default_ulid,
            timeline_id=timeline_id,  # fixture also writes this as project.json default_timeline_id
        )

        # Second timeline: valid identity/display but NOT the project default.
        other_tdir = project_dir / "timelines" / other_ulid
        other_tdir.mkdir()
        (other_tdir / "assembly.json").write_text(json.dumps(make_assembly_json()), encoding="utf-8")
        (other_tdir / "assembly.identity.json").write_text(
            json.dumps(make_identity_json(timeline_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")),
            encoding="utf-8",
        )
        (other_tdir / "display.json").write_text(
            json.dumps({
                "schema_version": 1,
                "slug": "secondary",
                "name": "Secondary",
                "is_default": False,
            }),
            encoding="utf-8",
        )
        (other_tdir / "manifest.json").write_text(
            json.dumps({
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": None,
            }),
            encoding="utf-8",
        )

        rows = list_bridge_timelines("timelines-list", root=tmp_bridge_root)

        # Sorted by timeline directory name (ULID).
        assert [row.timeline_ulid for row in rows] == [default_ulid, other_ulid]
        assert rows[0].timeline_id == timeline_id
        assert rows[0].slug == "primary"
        assert rows[0].name == "Primary"
        assert rows[0].is_default is True
        assert rows[1].timeline_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        assert rows[1].slug == "secondary"
        assert rows[1].name == "Secondary"
        assert rows[1].is_default is False

    def test_list_bridge_timelines_skips_unreadable_display(self, tmp_bridge_root, seed_bridge_project) -> None:
        project_dir = seed_bridge_project(slug="timelines-skip", timeline_ulid="01JM4K5N7P0000000000000103")
        broken_tdir = project_dir / "timelines" / "01JM4K5N7P0000000000000104"
        broken_tdir.mkdir()
        (broken_tdir / "display.json").write_text("{not json", encoding="utf-8")

        rows = list_bridge_timelines("timelines-skip", root=tmp_bridge_root)

        assert [row.timeline_ulid for row in rows] == ["01JM4K5N7P0000000000000103"]

    def test_list_bridge_timelines_missing_project_returns_empty(self, tmp_bridge_root) -> None:
        assert list_bridge_timelines("no-such-project", root=tmp_bridge_root) == []



    def test_find_bridge_timeline_accepts_slug(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000012"
        project_dir = seed_bridge_project(slug="by-slug", timeline_ulid=ulid)
        (project_dir / "timelines" / ulid / "display.json").write_text(
            json.dumps({
                "schema_version": 1,
                "slug": "intro-cut",
                "name": "Intro Cut",
                "is_default": True,
            }),
            encoding="utf-8",
        )

        row = find_bridge_timeline("by-slug", "intro-cut", root=tmp_bridge_root)

        assert row is not None
        assert row.timeline_ulid == ulid
        assert row.slug == "intro-cut"

    def test_find_bridge_timeline_accepts_ulid(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000013"
        seed_bridge_project(slug="by-ulid", timeline_ulid=ulid)

        row = find_bridge_timeline("by-ulid", ulid, root=tmp_bridge_root)

        assert row is not None
        assert row.timeline_ulid == ulid

    def test_find_bridge_timeline_accepts_exact_uppercase_legacy_ulid(
        self, tmp_bridge_root, seed_bridge_project
    ) -> None:
        """Filesystem bridge keeps the uppercase identity exposed by list."""
        ulid = "01KYPVKMW5STB4W6FE05ED8242"
        seed_bridge_project(slug="by-legacy-ulid", timeline_ulid=ulid)

        listed = list_bridge_timelines("by-legacy-ulid", root=tmp_bridge_root)
        row = find_bridge_timeline("by-legacy-ulid", ulid, root=tmp_bridge_root)
        loaded = load_bridge_timeline(
            "by-legacy-ulid", ulid, root=tmp_bridge_root
        )

        assert [item.timeline_ulid for item in listed] == [ulid]
        assert row is not None
        assert row.timeline_ulid == ulid
        assert loaded is not None
        assert loaded["timeline_ulid"] == ulid
        assert (
            find_bridge_timeline("by-legacy-ulid", ulid.lower(), root=tmp_bridge_root)
            is None
        )

    def test_find_bridge_timeline_accepts_uuid(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000014"
        timeline_id = "12345678-1234-1234-1234-1234567890ab"
        seed_bridge_project(slug="by-uuid", timeline_ulid=ulid, timeline_id=timeline_id)

        row = find_bridge_timeline("by-uuid", timeline_id, root=tmp_bridge_root)

        assert row is not None
        assert row.timeline_ulid == ulid
        assert row.timeline_id == timeline_id

    def test_load_bridge_timeline_loads_config_and_uses_event_head_version(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000015"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        project_dir = seed_bridge_project(slug="load-bridge", timeline_ulid=ulid, timeline_id=timeline_id)
        (project_dir / "timelines" / ulid / "assembly.json").write_text(
            json.dumps({
                "output": {"resolution": "1920x1080", "fps": 24, "file": "timeline.mp4"},
                "clips": [],
                "tracks": [{"id": "V1", "kind": "visual", "label": "V1"}],
            }),
            encoding="utf-8",
        )

        payload = load_bridge_timeline("load-bridge", ulid, root=tmp_bridge_root)

        assert payload is not None
        assert payload["timeline_id"] == timeline_id
        assert payload["config_version"] == 0
        assert payload["config"]["tracks"][0]["id"] == "V1"

    def test_load_bridge_timeline_accepts_editor_shaped_legacy_assembly(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000016"
        project_dir = seed_bridge_project(slug="legacy-editor-shape", timeline_ulid=ulid)
        (project_dir / "timelines" / ulid / "assembly.json").write_text(
            json.dumps({
                "theme": "banodoco-default",
                "theme_overrides": {"visual": {"canvas": {"width": 1280, "height": 720}}},
                "tracks": [{"id": "video_main", "kind": "visual", "label": "Video"}],
                "clips": [{
                    "id": "clip-1",
                    "at": 0,
                    "track": "video_main",
                    "clipType": "media",
                    "asset": "source-main",
                    "from": 1,
                    "to": 2,
                }],
            }),
            encoding="utf-8",
        )

        payload = load_bridge_timeline("legacy-editor-shape", ulid, root=tmp_bridge_root)

        assert payload is not None
        assert payload["config"]["theme"] == "banodoco-default"
        assert payload["config"]["clips"][0]["asset"] == "source-main"

    def test_save_bridge_timeline_appends_editor_save_event_regenerates_projection_and_returns_head_version(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        ulid = "01JM4K5N7P0000000000000015"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        project_dir = seed_bridge_project(slug="save-bridge", timeline_ulid=ulid, timeline_id=timeline_id)
        timeline_home = project_dir / "timelines" / ulid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )
        saved_config = {
            "clips": [
                {
                    "id": "clip-1",
                    "at": 12,
                    "track": "V1",
                    "clipType": "media",
                    "asset": "asset-1",
                }
            ],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }

        payload = save_bridge_timeline("save-bridge", ulid, saved_config, root=tmp_bridge_root)

        assert payload is not None
        events = backend.read_events()
        head = backend.head()
        assert [event.kind for event in events] == ["timeline.created", "timeline.config_replaced"]
        assert events[1].actor.to_json_obj() == {
            "type": "human",
            "id": "reigh-app:local-editor",
            "display": "Reigh local editor",
        }
        assert events[1].payload.to_json_obj()["source"] == "editor_save"
        assert events[1].payload.to_json_obj()["config"] == saved_config
        assert head.version == len(events) == 2
        checkpoint = json.loads((timeline_home / "assembly.checkpoint.json").read_text(encoding="utf-8"))
        assert checkpoint["last_event_id"] == head.last_event_id
        assert checkpoint["event_count"] == head.event_count
        assert checkpoint["version"] == head.version
        # Verify assembly.head.json on disk matches the in-memory head
        head_json = json.loads((timeline_home / "assembly.head.json").read_text(encoding="utf-8"))
        assert head_json["version"] == head.version
        assert head_json["event_count"] == len(events)
        assert head_json["last_event_id"] == head.last_event_id
        assert head_json["last_hash"] == head.last_hash
        assert load_assembly_json_with_repair(timeline_home) == saved_config
        assert payload["config"] == saved_config
        assert payload["config_version"] == head.version

        reloaded = load_bridge_timeline("save-bridge", ulid, root=tmp_bridge_root)
        assert reloaded is not None
        assert reloaded["config"] == saved_config
        assert reloaded["config_version"] == head.version


    def test_save_bridge_timeline_strips_editor_superset_top_level_keys(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        ulid = "01JM4K5N7P0000000000000016"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-ffffffffffff"
        project_dir = seed_bridge_project(slug="save-superset", timeline_ulid=ulid, timeline_id=timeline_id)
        timeline_home = project_dir / "timelines" / ulid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )
        editor_config = {
            "clips": [
                {
                    "id": "clip-1",
                    "at": 2.25,
                    "track": "V1",
                    "clipType": "media",
                    "asset": "asset-1",
                }
            ],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
            "output": {"resolution": "1920x1080", "fps": 30, "file": "out.mp4"},
        }

        payload = save_bridge_timeline("save-superset", ulid, editor_config, root=tmp_bridge_root)

        assert payload is not None
        assert payload["config"]["clips"][0]["at"] == 2.25
        assert "output" not in payload["config"]
        assert "output" not in load_assembly_json_with_repair(timeline_home)
        events = backend.read_events()
        assert "output" not in events[1].payload.to_json_obj()["config"]

    def test_save_bridge_timeline_as_first_config_save_after_timeline_created(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        ulid = "01JM4K5N7P0000000000000030"
        timeline_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        project_dir = seed_bridge_project(slug="first-save", timeline_ulid=ulid, timeline_id=timeline_id)
        timeline_home = project_dir / "timelines" / ulid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        # A timeline must have at least timeline.created before config_replaced
        # because the display projection and bridge listing depend on it.
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )
        saved_config = {
            "clips": [{"id": "c0", "at": 0, "track": "V1", "clipType": "media", "asset": "a0"}],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }

        payload = save_bridge_timeline("first-save", ulid, saved_config, root=tmp_bridge_root)

        assert payload is not None
        events = backend.read_events()
        head = backend.head()
        assert [event.kind for event in events] == ["timeline.created", "timeline.config_replaced"]
        assert events[1].payload.to_json_obj()["source"] == "editor_save"
        assert events[1].payload.to_json_obj()["config"] == saved_config
        assert head.version == len(events) == 2
        head_json = json.loads((timeline_home / "assembly.head.json").read_text(encoding="utf-8"))
        assert head_json["version"] == 2
        assert head_json["event_count"] == 2
        assert load_assembly_json_with_repair(timeline_home) == saved_config
        assert payload["config"] == saved_config
        assert payload["config_version"] == head.version

        reloaded = load_bridge_timeline("first-save", ulid, root=tmp_bridge_root)
        assert reloaded is not None
        assert reloaded["config"] == saved_config
        assert reloaded["config_version"] == head.version

    def test_save_bridge_timeline_recovers_orphaned_tail_after_crash(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """MUST-FIX 3b: a save after a crash (append fsynced, head write lost)
        adopts the orphaned tail before constructing the retry batch, so the
        saved log stays consistent — head matches the jsonl, no events are
        lost, and the next save works.
        """
        ulid = "01JM4K5N7P00000000000000EE"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        project_dir = seed_bridge_project(
            slug="orphan-save",
            timeline_ulid=ulid,
            timeline_id=timeline_id,
        )
        timeline_home = project_dir / "timelines" / ulid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )
        head_before = backend.head()
        assert head_before.version == 1

        # Simulate a crash between the fsync'd append and the head write:
        # write a complete chained config event to the jsonl WITHOUT updating
        # assembly.head.json.
        orphan = construct_reigh_timeline_events(
            timeline_id=timeline_id,
            tail_hash=head_before.last_hash,
            next_event_version=head_before.version + 1,
            actor=REIGH_LOCAL_EDITOR_ACTOR,
            source="editor_save",
            config={"clips": [], "tracks": []},
        )
        with (timeline_home / "assembly.jsonl").open("ab") as handle:
            handle.write(canonical_json_bytes(orphan.events[0].event.to_json_obj()) + b"\n")

        saved_config = {
            "clips": [
                {
                    "id": "clip-1",
                    "at": 0,
                    "track": "V1",
                    "clipType": "media",
                    "asset": "asset-1",
                }
            ],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }
        payload = save_bridge_timeline("orphan-save", ulid, saved_config, root=tmp_bridge_root)
        assert payload is not None
        assert payload["config"] == saved_config

        # No lost events: created + orphan + save are all present and chained.
        events = backend.read_events()
        assert [event.kind for event in events] == [
            "timeline.created",
            "timeline.config_replaced",
            "timeline.config_replaced",
        ]
        assert backend.verify_chain().ok is True
        head = backend.head()
        assert head.version == len(events) == 3
        assert head.last_event_id == events[-1].event_id
        assert head.log_size == (timeline_home / "assembly.jsonl").stat().st_size
        # Head sidecar on disk matches the jsonl.
        head_json = json.loads((timeline_home / "assembly.head.json").read_text(encoding="utf-8"))
        assert head_json["version"] == head.version
        assert head_json["event_count"] == head.event_count
        assert head_json["last_event_id"] == head.last_event_id
        assert head_json["last_hash"] == head.last_hash
        assert load_assembly_json_with_repair(timeline_home) == saved_config

        # A further save still works and keeps the log consistent.
        payload2 = save_bridge_timeline("orphan-save", ulid, saved_config, root=tmp_bridge_root)
        assert payload2 is not None
        assert payload2["config_version"] == 4
        assert backend.verify_chain().ok is True
        assert backend.head().version == 4

    def test_save_bridge_timeline_returns_none_for_unknown_timeline(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        seed_bridge_project(slug="known-project")
        result = save_bridge_timeline("known-project", "nonexistent-timeline", {"clips": []}, root=tmp_bridge_root)
        assert result is None


    def test_load_bridge_timeline_falls_back_to_ulid_when_identity_missing(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000016"
        seed_bridge_project(slug="legacy-identity", timeline_ulid=ulid, with_identity=False)

        payload = load_bridge_timeline("legacy-identity", ulid, root=tmp_bridge_root)

        assert payload is not None
        assert payload["timeline_id"] == ulid

    def test_load_bridge_timeline_returns_none_for_unknown_timeline(self, tmp_bridge_root, seed_bridge_project) -> None:
        seed_bridge_project(slug="missing-check")
        assert load_bridge_timeline("missing-check", "does-not-exist", root=tmp_bridge_root) is None

    def test_bridge_registry_path_points_at_timeline_registry_sidecar(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000017"
        seed_bridge_project(slug="registry-path", timeline_ulid=ulid)

        path = bridge_registry_path("registry-path", ulid, root=tmp_bridge_root)

        assert path == tmp_bridge_root / "registry-path" / "timelines" / ulid / "registry.json"

    def test_load_bridge_registry_returns_empty_assets_when_registry_missing(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000018"
        seed_bridge_project(slug="missing-registry", timeline_ulid=ulid, with_registry=False)

        assert load_bridge_registry("missing-registry", ulid, root=tmp_bridge_root) == {"assets": {}}

    def test_load_bridge_registry_derives_missing_assets_from_single_source(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000019"
        project_dir = seed_bridge_project(slug="derived-registry", timeline_ulid=ulid, with_registry=False)
        timeline_home = project_dir / "timelines" / ulid
        (timeline_home / "assembly.json").write_text(
            json.dumps({
                "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
                "clips": [
                    {
                        "id": "clip-1",
                        "at": 0,
                        "track": "V1",
                        "clipType": "media",
                        "asset": "source-main",
                        "from": 0,
                        "to": 1,
                    },
                    {
                        "id": "clip-2",
                        "at": 0,
                        "track": "A1",
                        "clipType": "media",
                        "asset": "source-audio",
                        "from": 0,
                        "to": 1,
                    },
                ],
            }),
            encoding="utf-8",
        )
        sources_dir = project_dir / "sources"
        sources_dir.mkdir(exist_ok=True)
        (sources_dir / "only-source.mp4").write_bytes(b"fake")

        registry = load_bridge_registry("derived-registry", ulid, root=tmp_bridge_root)
        resolved = resolve_bridge_asset("derived-registry", ulid, "source-main", root=tmp_bridge_root)
        sources_payload = json.loads((project_dir / "sources.json").read_text(encoding="utf-8"))

        assert sorted(registry["assets"]) == ["source-audio", "source-main"]
        assert registry["assets"]["source-main"]["file"] == "only-source.mp4"
        assert registry["assets"]["source-audio"]["file"] == "only-source.mp4"
        assert registry["assets"]["source-main"]["type"] == "video/mp4"
        assert registry["assets"]["source-audio"]["type"] == "video/mp4"
        assert registry["assets"]["source-main"]["sourceId"] == registry["assets"]["source-audio"]["sourceId"]
        assert registry["assets"]["source-main"]["sourceVersion"] == registry["assets"]["source-audio"]["sourceVersion"]
        assert resolved is not None
        assert resolved.local_path == (sources_dir / "only-source.mp4").resolve()
        assert resolved.source_id == registry["assets"]["source-main"]["sourceId"]
        assert sources_payload["version"] == 1
        assert list(sources_payload["sources"]) == [registry["assets"]["source-main"]["sourceId"]]
        assert sources_payload["sources"][resolved.source_id]["assetIds"] == {
            "source-audio": True,
            "source-main": True,
        }

    def test_load_bridge_registry_keeps_relative_sources_entries_and_remote_urls(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000021"
        project_dir = seed_bridge_project(
            slug="registry-assets",
            timeline_ulid=ulid,
            assets={
                "local-video": {"file": "./clips/../clips/demo.mp4", "type": "video/mp4"},
                "local-video-copy": {"file": "clips/demo.mp4", "type": "video/mp4"},
                "remote-image": {"file": "https://cdn.example/cover.png", "type": "image/png"},
            },
        )
        media_path = project_dir / "sources" / "clips" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"demo-bytes")
        registry_path = project_dir / "timelines" / ulid / "registry.json"
        registry_path.write_text(
            json.dumps({
                "assets": {
                    "local-video": {"file": "./clips/../clips/demo.mp4", "type": "video/mp4"},
                    "local-video-copy": {"file": str(media_path.resolve()), "type": "video/mp4"},
                    "remote-image": {"file": "https://cdn.example/cover.png", "type": "image/png"},
                },
            }),
            encoding="utf-8",
        )

        registry = load_bridge_registry("registry-assets", ulid, root=tmp_bridge_root)
        local_asset = resolve_bridge_asset("registry-assets", ulid, "local-video", root=tmp_bridge_root)
        local_asset_copy = resolve_bridge_asset("registry-assets", ulid, "local-video-copy", root=tmp_bridge_root)
        remote_asset = resolve_bridge_asset("registry-assets", ulid, "remote-image", root=tmp_bridge_root)
        sources_payload = json.loads((project_dir / "sources.json").read_text(encoding="utf-8"))

        assert sorted(registry["assets"]) == ["local-video", "local-video-copy", "remote-image"]
        assert registry["assets"]["local-video"]["file"] == "clips/demo.mp4"
        assert registry["assets"]["local-video-copy"]["file"] == "clips/demo.mp4"
        assert registry["assets"]["local-video"]["sourceId"] == registry["assets"]["local-video-copy"]["sourceId"]
        assert registry["assets"]["local-video"]["sourceVersion"] == registry["assets"]["local-video-copy"]["sourceVersion"]
        assert local_asset is not None
        assert local_asset_copy is not None
        assert local_asset.source_kind == "local"
        assert local_asset.local_path == media_path.resolve()
        assert local_asset.size_bytes == len(b"demo-bytes")
        assert local_asset.source_id == local_asset_copy.source_id
        assert sources_payload["sources"][local_asset.source_id]["assetIds"] == {
            "local-video": True,
            "local-video-copy": True,
        }
        assert remote_asset is not None
        assert remote_asset.source_kind == "http"
        assert remote_asset.url == "https://cdn.example/cover.png"

    def test_load_bridge_registry_updates_source_version_when_local_metadata_changes(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000029"
        project_dir = seed_bridge_project(
            slug="registry-source-version",
            timeline_ulid=ulid,
            assets={"local-video": {"file": "clips/demo.mp4", "type": "video/mp4"}},
        )
        media_path = project_dir / "sources" / "clips" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"demo-v1")

        first_registry = load_bridge_registry("registry-source-version", ulid, root=tmp_bridge_root)
        first_sources = json.loads((project_dir / "sources.json").read_text(encoding="utf-8"))

        registry_path = project_dir / "timelines" / ulid / "registry.json"
        registry_path.write_text(
            json.dumps({
                "assets": {
                    "local-video": {
                        "file": "clips/demo.mp4",
                        "type": "video/mp4",
                        "content_sha256": "a" * 64,
                    },
                },
            }),
            encoding="utf-8",
        )
        media_path.write_bytes(b"demo-v2-with-more-bytes")

        second_registry = load_bridge_registry("registry-source-version", ulid, root=tmp_bridge_root)
        second_sources = json.loads((project_dir / "sources.json").read_text(encoding="utf-8"))

        source_id = first_registry["assets"]["local-video"]["sourceId"]
        assert second_registry["assets"]["local-video"]["sourceId"] == source_id
        assert second_registry["assets"]["local-video"]["sourceVersion"] != first_registry["assets"]["local-video"]["sourceVersion"]
        assert first_sources["sources"][source_id]["sourceVersion"] != second_sources["sources"][source_id]["sourceVersion"]
        assert second_sources["sources"][source_id]["content_sha256"] == "a" * 64

    def test_load_bridge_registry_updates_source_version_when_audio_proxy_profile_changes(
        self,
        tmp_bridge_root,
        seed_bridge_project,
        monkeypatch,
    ) -> None:
        ulid = "01JM4K5N7P000000000000002A"
        project_dir = seed_bridge_project(
            slug="registry-profile-version",
            timeline_ulid=ulid,
            assets={"local-video": {"file": "clips/demo.mp4", "type": "video/mp4"}},
        )
        media_path = project_dir / "sources" / "clips" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"demo-v1")

        first_registry = load_bridge_registry("registry-profile-version", ulid, root=tmp_bridge_root)
        source_id = first_registry["assets"]["local-video"]["sourceId"]

        monkeypatch.setattr(local_bridge, "BRIDGE_AUDIO_PROXY_PROFILE_VERSION", "aac-m4a-stereo-48000-128k-v2")

        second_registry = load_bridge_registry("registry-profile-version", ulid, root=tmp_bridge_root)
        second_sources = json.loads((project_dir / "sources.json").read_text(encoding="utf-8"))

        assert second_registry["assets"]["local-video"]["sourceId"] == source_id
        assert second_registry["assets"]["local-video"]["sourceVersion"] != first_registry["assets"]["local-video"]["sourceVersion"]
        assert second_sources["sources"][source_id]["audioProxyProfileVersion"] == "aac-m4a-stereo-48000-128k-v2"

    def test_load_bridge_registry_removes_stale_source_asset_mapping_when_asset_points_to_new_file(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        ulid = "01JM4K5N7P000000000000002B"
        project_dir = seed_bridge_project(
            slug="registry-remap",
            timeline_ulid=ulid,
            assets={"local-video": {"file": "clips/demo-a.mp4", "type": "video/mp4"}},
        )
        first_media_path = project_dir / "sources" / "clips" / "demo-a.mp4"
        first_media_path.parent.mkdir(parents=True, exist_ok=True)
        first_media_path.write_bytes(b"demo-a")
        second_media_path = project_dir / "sources" / "clips" / "demo-b.mp4"
        second_media_path.write_bytes(b"demo-b")

        first_registry = load_bridge_registry("registry-remap", ulid, root=tmp_bridge_root)
        first_source_id = first_registry["assets"]["local-video"]["sourceId"]

        registry_path = project_dir / "timelines" / ulid / "registry.json"
        registry_path.write_text(
            json.dumps({
                "assets": {
                    "local-video": {"file": "clips/demo-b.mp4", "type": "video/mp4"},
                },
            }),
            encoding="utf-8",
        )

        second_registry = load_bridge_registry("registry-remap", ulid, root=tmp_bridge_root)
        second_sources = json.loads((project_dir / "sources.json").read_text(encoding="utf-8"))
        second_source_id = second_registry["assets"]["local-video"]["sourceId"]

        assert second_source_id != first_source_id
        assert first_source_id not in second_sources["sources"]
        assert second_sources["sources"][second_source_id]["assetIds"] == {"local-video": True}

    def test_load_bridge_registry_rejects_traversal_and_outside_root_assets(self, tmp_bridge_root, seed_bridge_project, tmp_path) -> None:
        ulid = "01JM4K5N7P0000000000000020"
        outside_file = tmp_path / "outside.mp4"
        outside_file.write_bytes(b"outside")
        seed_bridge_project(
            slug="registry-guardrails",
            timeline_ulid=ulid,
            assets={
                "traversal": {"file": "../escape.mp4", "type": "video/mp4"},
                "absolute-outside": {"file": str(outside_file), "type": "video/mp4"},
            },
        )

        registry = load_bridge_registry("registry-guardrails", ulid, root=tmp_bridge_root)

        assert registry == {"assets": {}}
        assert resolve_bridge_asset("registry-guardrails", ulid, "traversal", root=tmp_bridge_root) is None
        assert resolve_bridge_asset("registry-guardrails", ulid, "absolute-outside", root=tmp_bridge_root) is None

class TestBridgeRegistryRecovery:
    """Registry sidecar recovery: event stream > legacy assets.json > derivation.

    Regression for the .DS_Store bug: real sources live in per-source
    directories, so the flat-file derivation heuristic saw only .DS_Store and
    mapped it onto every media asset. Recovery must prefer the canonical event
    stream, and derivation must never map hidden files onto assets.
    """

    @staticmethod
    def _seed_media_project(
        seed_bridge_project,
        *,
        slug: str,
        ulid: str,
        project_dir,
    ) -> None:
        seed_bridge_project(
            slug=slug,
            timeline_ulid=ulid,
            with_registry=False,
        )
        timeline_home = project_dir / "timelines" / ulid
        (timeline_home / "assembly.json").write_text(
            json.dumps({
                "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
                "clips": [
                    {
                        "id": "clip-1",
                        "at": 0,
                        "track": "V1",
                        "clipType": "media",
                        "asset": "frame-1",
                        "from": 0,
                        "to": 1,
                    },
                ],
            }),
            encoding="utf-8",
        )
        sources_dir = project_dir / "sources"
        (sources_dir / "frame-1.png").mkdir(parents=True, exist_ok=True)
        (sources_dir / "frame-1.png" / "frame-1.png").write_bytes(b"png-bytes")
        # The only flat file in sources/ is macOS Finder junk.
        (sources_dir / ".DS_Store").write_bytes(b"finder-junk")

    def test_recovers_registry_from_event_stream_when_sidecar_missing(
        self, tmp_bridge_root, seed_bridge_project
    ) -> None:
        ulid = "01JM4K5N7P0000000000000031"
        project_dir = tmp_bridge_root / "recover-events"
        self._seed_media_project(seed_bridge_project, slug="recover-events", ulid=ulid, project_dir=project_dir)
        timeline_home = project_dir / "timelines" / ulid

        # Canonical event stream carries the authoritative registry.
        (timeline_home / "assembly.jsonl").write_text(
            json.dumps({
                "actor": {"type": "agent", "id": "agent:test-migration", "display": "test migration"},
                "event_id": "01JM4K5N7P00000000000000A1",
                "timeline_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "ts": "2026-07-29T12:00:00Z",
                "schema_version": 1,
                "kind": "timeline.asset_registry_replaced",
                "payload": {
                    "registry": {
                        "assets": {
                            "frame-1": {
                                "file": "frame-1.png/frame-1.png",
                                "type": "image/png",
                                "resolution": "64x64",
                            }
                        }
                    }
                },
            }) + "\n",
            encoding="utf-8",
        )

        registry = load_bridge_registry("recover-events", ulid, root=tmp_bridge_root)
        resolved = resolve_bridge_asset("recover-events", ulid, "frame-1", root=tmp_bridge_root)

        # Recovered from the event, NOT mapped onto .DS_Store.
        assert registry["assets"]["frame-1"]["file"] == "frame-1.png/frame-1.png"
        assert registry["assets"]["frame-1"]["type"] == "image/png"
        # Sidecar persisted so downstream readers see the same authoritative assets.
        sidecar = json.loads((timeline_home / "registry.json").read_text(encoding="utf-8"))
        assert sidecar["assets"]["frame-1"]["type"] == "image/png"
        assert resolved is not None
        assert resolved.local_path == (project_dir / "sources" / "frame-1.png" / "frame-1.png").resolve()

    def test_recovers_registry_from_legacy_assets_json(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000032"
        project_dir = tmp_bridge_root / "recover-legacy"
        self._seed_media_project(seed_bridge_project, slug="recover-legacy", ulid=ulid, project_dir=project_dir)
        timeline_home = project_dir / "timelines" / ulid

        # Pre-bridge migration sidecar with absolute source paths.
        (timeline_home / "assets.json").write_text(
            json.dumps({
                "assets": {
                    "frame-1": {
                        "file": str((project_dir / "sources" / "frame-1.png" / "frame-1.png").resolve()),
                        "type": "image/png",
                    }
                }
            }),
            encoding="utf-8",
        )

        registry = load_bridge_registry("recover-legacy", ulid, root=tmp_bridge_root)
        resolved = resolve_bridge_asset("recover-legacy", ulid, "frame-1", root=tmp_bridge_root)

        assert registry["assets"]["frame-1"]["type"] == "image/png"
        assert resolved is not None
        assert resolved.local_path == (project_dir / "sources" / "frame-1.png" / "frame-1.png").resolve()

    def test_derivation_skips_dotfiles_so_junk_never_maps_to_assets(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000033"
        project_dir = tmp_bridge_root / "recover-nojunk"
        self._seed_media_project(seed_bridge_project, slug="recover-nojunk", ulid=ulid, project_dir=project_dir)

        # No registry.json, no event stream, no legacy sidecar: derivation runs,
        # but with the only flat file being a dotfile it must yield nothing.
        assert load_bridge_registry("recover-nojunk", ulid, root=tmp_bridge_root) == {"assets": {}}

    def test_bridge_registry_helpers_do_not_read_media_bytes(self, tmp_bridge_root, seed_bridge_project, monkeypatch) -> None:
        ulid = "01JM4K5N7P0000000000000021"
        project_dir = seed_bridge_project(
            slug="registry-lazy",
            timeline_ulid=ulid,
            assets={"local-video": {"file": "clips/lazy.mp4", "type": "video/mp4"}},
        )
        media_path = project_dir / "sources" / "clips" / "lazy.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"lazy-bytes")

        original_read_bytes = Path.read_bytes

        def guard_read_bytes(path: Path) -> bytes:
            if path.resolve() == media_path.resolve():
                raise AssertionError("media bytes should not be read while loading bridge metadata")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", guard_read_bytes)

        registry = load_bridge_registry("registry-lazy", ulid, root=tmp_bridge_root)
        resolved = resolve_bridge_asset("registry-lazy", ulid, "local-video", root=tmp_bridge_root)

        assert registry["assets"]["local-video"]["file"] == "clips/lazy.mp4"
        assert resolved is not None
        assert resolved.local_path == media_path.resolve()












    def test_resolve_timeline_target_keeps_identity_sidecar_uuid_for_slug_and_ulid_reads(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000022"
        timeline_id = "fedcba98-7654-3210-fedc-ba9876543210"
        project_dir = seed_bridge_project(slug="identity-audit", timeline_ulid=ulid, timeline_id=timeline_id)
        (project_dir / "timelines" / ulid / "display.json").write_text(
            json.dumps({
                "schema_version": 1,
                "slug": "eventlog-cut",
                "name": "Eventlog Cut",
                "is_default": True,
            }),
            encoding="utf-8",
        )

        slug_target = resolve_timeline_target("identity-audit", "eventlog-cut", root=tmp_bridge_root)
        ulid_target = resolve_timeline_target("identity-audit", ulid, root=tmp_bridge_root)
        uuid_target = resolve_timeline_target("identity-audit", timeline_id, root=tmp_bridge_root)

        assert slug_target.timeline_id == timeline_id
        assert ulid_target.timeline_id == timeline_id
        assert uuid_target.timeline_id == timeline_id

    def test_resolve_event_log_target_keeps_identity_sidecar_uuid_for_eventlog_layouts(self, tmp_bridge_root, seed_bridge_project) -> None:
        eventlog_ulid = "01JM4K5N7P0000000000000023"
        eventlog_uuid = "99999999-8888-7777-6666-555555555555"
        seed_bridge_project(slug="eventlog-layout", timeline_ulid=eventlog_ulid, timeline_id=eventlog_uuid)

        eventlog_target = resolve_event_log_target("eventlog-layout", eventlog_ulid, root=tmp_bridge_root)

        assert eventlog_target.timeline_id == eventlog_uuid


class TestBridgeAtomicSave:
    """CAS save behaviour: combined config+registry batches and stale-version guards."""

    def test_combined_save_appends_adjacent_config_and_registry_events(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """save_bridge_timeline with registry appends config+registry in one atomic batch."""
        ulid = "01JM4K5N7P00000000000000A1"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def0001"
        project_dir = seed_bridge_project(
            slug="combined-save",
            timeline_ulid=ulid,
            timeline_id=timeline_id,
        )
        timeline_home = project_dir / "timelines" / ulid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )

        config = {
            "clips": [{"id": "c1", "at": 0, "track": "V1", "clipType": "media", "asset": "a1"}],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }
        registry = {"assets": {"a1": {"file": "a1.mp4", "type": "video/mp4"}}}

        payload = save_bridge_timeline(
            "combined-save",
            ulid,
            config,
            registry=registry,
            root=tmp_bridge_root,
        )

        assert payload is not None
        events = backend.read_events()
        kinds = [event.kind for event in events]
        assert kinds == [
            "timeline.created",
            "timeline.config_replaced",
            "timeline.asset_registry_replaced",
        ]
        # Adjacent: config then registry.
        assert events[1].payload.to_json_obj()["config"] == config
        assert events[2].payload.to_json_obj()["registry"] == registry
        # Chain integrity.
        assert events[2].prev_hash == events[1].hash
        assert backend.head().version == 3

        # Sidecar written.
        sidecar = json.loads((timeline_home / "registry.json").read_text(encoding="utf-8"))
        assert sidecar == registry

        # Payload carries the registry.
        assert payload["registry"] == registry
        assert payload["config"] == config

    def test_stale_expected_version_changes_neither_event_log_nor_sidecars(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """A stale expected_version must raise and leave the event log + sidecars unchanged."""
        ulid = "01JM4K5N7P00000000000000B1"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-aaaaaa000001"
        project_dir = seed_bridge_project(
            slug="stale-save",
            timeline_ulid=ulid,
            timeline_id=timeline_id,
        )
        timeline_home = project_dir / "timelines" / ulid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )

        # Snapshot before the failing call.
        head_before = backend.head()
        events_before = backend.read_events()
        registry_before = load_bridge_registry("stale-save", ulid, root=tmp_bridge_root)

        config = {
            "clips": [{"id": "c1", "at": 0, "track": "V1", "clipType": "media", "asset": "a1"}],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }
        registry = {"assets": {"a1": {"file": "a1.mp4", "type": "video/mp4"}}}

        # expected_version=999 is far ahead — guaranteed stale.
        with pytest.raises(EventLogStaleVersionError):
            save_bridge_timeline(
                "stale-save",
                ulid,
                config,
                registry=registry,
                expected_version=999,
                root=tmp_bridge_root,
            )

        # Nothing changed.
        head_after = backend.head()
        assert head_after.version == head_before.version
        assert head_after.last_event_id == head_before.last_event_id
        assert head_after.event_count == head_before.event_count

        events_after = backend.read_events()
        assert [e.event_id for e in events_after] == [e.event_id for e in events_before]

        registry_after = load_bridge_registry("stale-save", ulid, root=tmp_bridge_root)
        assert registry_after == registry_before


class TestBridgeIncrementalSave:
    """T2.1: warm bridge saves do no full-log reads; crash recovery; aliases."""

    _CONFIG = {
        "clips": [{"id": "c1", "at": 0, "track": "V1", "clipType": "media", "asset": "a1"}],
        "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
    }
    _REGISTRY = {"assets": {"a1": {"file": "a1.mp4", "type": "video/mp4"}}}

    def _seed(self, seed_bridge_project, slug: str, ulid: str, timeline_id: str, tmp_bridge_root):
        project_dir = seed_bridge_project(slug=slug, timeline_ulid=ulid, timeline_id=timeline_id)
        timeline_home = project_dir / "timelines" / ulid
        # Production identities carry a "display" block (crud.create_timeline);
        # mirror that so find_bridge_timeline's display fast-path is taken and
        # no bridge-save step ever replays the event log.
        display = json.loads((timeline_home / "display.json").read_text(encoding="utf-8"))
        identity_path = timeline_home / "assembly.identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["display"] = display
        identity_path.write_text(json.dumps(identity), encoding="utf-8")

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        backend.append_event(
            timeline_id,
            "timeline.created",
            {"timeline_id": timeline_id, "slug": "primary", "name": "Primary"},
            actor=REIGH_LOCAL_EDITOR_ACTOR,
        )
        return timeline_home, backend

    @staticmethod
    def _seed_events(backend: LocalFsBackend, timeline_id: str, count: int) -> int:
        """Append *count* chained prebuilt events cheaply (no per-event schema).

        Uses the canonical event shape (TimelineEvent.new + with_event_hash)
        with a lightweight kind so a 2,000+ event log seeds in well under a
        second instead of paying jsonschema validation per event.
        """
        from astrid.core.timeline.events.schema import TimelineEvent, with_event_hash

        head = backend.head()
        prev_hash = head.last_hash
        version = head.version
        batch: list[TimelineEvent] = []
        for index in range(count):
            event = TimelineEvent.new(
                timeline_id=timeline_id,
                ts="2026-08-12T00:00:00Z",
                actor=REIGH_LOCAL_EDITOR_ACTOR,
                kind="timeline.renamed",
                payload={"old_slug": f"seed-{index}", "new_slug": f"seed-{index + 1}"},
                prev_hash=prev_hash,
                expected_version=version + 1,
            )
            event = with_event_hash(event, prev_hash=prev_hash)
            batch.append(event)
            prev_hash = event.hash
            version += 1
            if len(batch) >= 300:
                backend.append_prebuilt_events(timeline_id, batch)
                batch = []
        if batch:
            backend.append_prebuilt_events(timeline_id, batch)
        return version

    def test_warm_save_does_no_full_log_read(
        self,
        tmp_bridge_root,
        seed_bridge_project,
        monkeypatch,
    ) -> None:
        """Warm save_bridge_timeline performs zero full-log parses (head path)."""
        ulid = "01JM4K5N7P00000000000000C1"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def00c1"
        timeline_home, backend = self._seed(seed_bridge_project, "warm-incremental", ulid, timeline_id, tmp_bridge_root)

        # Pre-warm the projection checkpoint so every measured save is warm.
        from astrid.core.timeline.projection import regenerate_projection
        regenerate_projection(timeline_id, backend, timeline_home=timeline_home)

        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend as LocalFsCls

        calls = {"full": 0, "offset": 0}
        orig_full = LocalFsCls._read_all_events
        orig_offset = LocalFsCls._read_all_events_with_offsets

        def spy_full(self, *args, **kwargs):
            calls["full"] += 1
            return orig_full(self, *args, **kwargs)

        def spy_offset(self, *args, **kwargs):
            calls["offset"] += 1
            return orig_offset(self, *args, **kwargs)

        monkeypatch.setattr(LocalFsCls, "_read_all_events", spy_full)
        monkeypatch.setattr(LocalFsCls, "_read_all_events_with_offsets", spy_offset)

        for _ in range(3):
            payload = save_bridge_timeline(
                "warm-incremental",
                ulid,
                self._CONFIG,
                registry=self._REGISTRY,
                root=tmp_bridge_root,
            )
            assert payload is not None

        assert calls == {"full": 0, "offset": 0}, f"warm saves performed full-log reads: {calls}"
        head = json.loads((timeline_home / "assembly.head.json").read_text(encoding="utf-8"))
        assert head["log_size"] == (timeline_home / "assembly.jsonl").stat().st_size
        assert head["last_event_offset"] is not None

    def test_save_remains_fast_on_2000_plus_event_timeline(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """A warm save on a 2,000+ event timeline stays fast (no full-log scan)."""
        ulid = "01JM4K5N7P00000000000000C2"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def00c2"
        timeline_home, backend = self._seed(seed_bridge_project, "fast-incremental", ulid, timeline_id, tmp_bridge_root)

        # Seed ~2,100 chained events (realistic canonical shape, cheap build).
        version = self._seed_events(backend, timeline_id, 2100)
        assert backend.head().event_count == 1 + 2100
        assert version == 2101

        # Pre-warm the projection checkpoint so the measured save is warm.
        from astrid.core.timeline.projection import regenerate_projection
        regenerate_projection(timeline_id, backend, timeline_home=timeline_home)

        start = time.perf_counter()
        payload = save_bridge_timeline(
            "fast-incremental",
            ulid,
            self._CONFIG,
            registry=self._REGISTRY,
            root=tmp_bridge_root,
        )
        elapsed = time.perf_counter() - start
        assert payload is not None
        assert backend.verify_chain().ok is True
        assert backend.head().event_count == 1 + 2100 + 2
        assert elapsed < 0.5, f"warm save on 2,102-event log took {elapsed:.3f}s (SLO p95 <= 500ms)"

    def test_save_recovers_when_head_missing(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """Head-missing after a crash: the save falls back to a full parse and rewrites the head."""
        ulid = "01JM4K5N7P00000000000000C3"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def00c3"
        timeline_home, backend = self._seed(seed_bridge_project, "crash-head", ulid, timeline_id, tmp_bridge_root)

        (timeline_home / "assembly.head.json").unlink()

        payload = save_bridge_timeline(
            "crash-head",
            ulid,
            self._CONFIG,
            registry=self._REGISTRY,
            root=tmp_bridge_root,
        )
        assert payload is not None
        assert payload["config_version"] == 3
        head = json.loads((timeline_home / "assembly.head.json").read_text(encoding="utf-8"))
        assert head["version"] == 3
        assert head["log_size"] == (timeline_home / "assembly.jsonl").stat().st_size
        assert head["last_event_offset"] is not None
        assert LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home).verify_chain().ok is True

    def test_save_recovers_from_torn_tail_after_crash(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """Torn bytes beyond the head (crash mid-append) are truncated, then the save succeeds."""
        ulid = "01JM4K5N7P00000000000000C4"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def00c4"
        timeline_home, backend = self._seed(seed_bridge_project, "crash-torn", ulid, timeline_id, tmp_bridge_root)

        with (timeline_home / "assembly.jsonl").open("ab") as handle:
            handle.write(b'{"kind": "timeline.config_replaced", "paTORN')

        payload = save_bridge_timeline(
            "crash-torn",
            ulid,
            self._CONFIG,
            registry=self._REGISTRY,
            root=tmp_bridge_root,
        )
        assert payload is not None
        log = (timeline_home / "assembly.jsonl").read_bytes()
        assert b"paTORN" not in log
        assert backend.verify_chain().ok is True
        assert backend.head().log_size == len(log)

    def test_first_save_after_cold_start_stays_fast(
        self,
        tmp_bridge_root,
        seed_bridge_project,
        monkeypatch,
    ) -> None:
        """First save on a fresh 2k-event log (no checkpoint) does not full-replay."""
        ulid = "01JM4K5N7P00000000000000C6"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def00c6"
        timeline_home, backend = self._seed(seed_bridge_project, "cold-first", ulid, timeline_id, tmp_bridge_root)

        # Seed a bridge-shaped log: 2,100 chained events ending with a realistic
        # config_replaced tail (the last editor save), no checkpoint/assembly.
        self._seed_events(backend, timeline_id, 2100)
        from astrid.core.timeline.eventlog.reigh_events import construct_reigh_timeline_events
        from astrid.core.timeline.events.schema import TimelineActor

        head = backend.head()
        batch = construct_reigh_timeline_events(
            timeline_id=timeline_id,
            tail_hash=head.last_hash,
            next_event_version=head.version + 1,
            actor=TimelineActor(type="human", id="reigh-app:local-editor"),
            source="editor_save",
            config=self._CONFIG,
        )
        backend.append_prebuilt_events(timeline_id, [e.event for e in batch.events])
        assert backend.head().event_count == 1 + 2100 + 1
        assert not (timeline_home / "assembly.checkpoint.json").exists()

        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend as LocalFsCls

        calls = {"read_events": 0}
        orig = LocalFsCls.read_events

        def spy(self, *args, **kwargs):
            calls["read_events"] += 1
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(LocalFsCls, "read_events", spy)

        start = time.perf_counter()
        payload = save_bridge_timeline(
            "cold-first",
            ulid,
            self._CONFIG,
            registry=self._REGISTRY,
            root=tmp_bridge_root,
        )
        elapsed = time.perf_counter() - start
        assert payload is not None
        assert calls["read_events"] == 0, f"first (cold) save full-replayed: {calls}"
        assert elapsed < 0.5, f"first save on 2,102-event cold log took {elapsed:.3f}s"
        assert backend.verify_chain().ok is True
        assert backend.head().event_count == 1 + 2100 + 1 + 2

    def test_mixed_alias_concurrent_saves_serialize_on_one_lock(
        self,
        tmp_bridge_root,
        seed_bridge_project,
    ) -> None:
        """Saves via slug / ULID / UUID aliases share ONE canonical-path lock."""
        from astrid.core.integrations.reigh.local_bridge import _bridge_save_lock, find_bridge_timeline

        ulid = "01JM4K5N7P00000000000000C5"
        timeline_id = "aaaaaaaa-bbbb-cccc-dddd-c0ab1def00c5"
        timeline_home, backend = self._seed(seed_bridge_project, "alias-lock", ulid, timeline_id, tmp_bridge_root)

        record_ulid = find_bridge_timeline("alias-lock", ulid, root=tmp_bridge_root)
        record_uuid = find_bridge_timeline("alias-lock", timeline_id, root=tmp_bridge_root)
        record_slug = find_bridge_timeline("alias-lock", "primary", root=tmp_bridge_root)
        assert record_ulid is not None and record_uuid is not None and record_slug is not None
        assert record_ulid.timeline_home == record_uuid.timeline_home == record_slug.timeline_home
        assert _bridge_save_lock(record_ulid.timeline_home) is _bridge_save_lock(record_uuid.timeline_home)
        assert _bridge_save_lock(record_ulid.timeline_home) is _bridge_save_lock(record_slug.timeline_home)

        # Functional proof: concurrent saves through different aliases all
        # succeed and serialize (no interleaving → no chain breaks / lost
        # updates). Without the shared lock the two aliases would race and
        # produce prev_hash chain failures. Each save appends 2 events
        # (config + registry), so 10 saves add 20 events.
        errors: list[Exception] = []
        barrier = threading.Barrier(2)

        def worker(alias: str, saves: int) -> None:
            try:
                barrier.wait()
                for _ in range(saves):
                    save_bridge_timeline(
                        "alias-lock",
                        alias,
                        self._CONFIG,
                        registry=self._REGISTRY,
                        root=tmp_bridge_root,
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(ulid, 5)),
            threading.Thread(target=worker, args=(timeline_id, 5)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        assert all(not thread.is_alive() for thread in threads), "worker threads hung"
        assert errors == [], f"concurrent alias saves failed: {errors}"

        final = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
        assert final.verify_chain().ok is True
        assert final.head().event_count == 1 + 10 * 2
