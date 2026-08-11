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
    load_bridge_registry,
    load_bridge_timeline,
    resolve_bridge_asset,
    resolve_bridge_projects_root,
    save_bridge_timeline,
)
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.eventlog.selector import resolve_event_log_target
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError
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

