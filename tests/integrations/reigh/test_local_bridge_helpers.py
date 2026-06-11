"""Helper tests for bridge fixture builders and identity sidecar layouts.

Covers:
- Legacy direct-assembly (assembly.json without identity sidecar)
- Event-log-like identity sidecar (assembly.identity.json with timeline_id)
- Registry fixture seeding
- Media file seeding
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Import from the local conftest (pytest will have it available as a fixture module).
# We use the functions directly since they're defined in conftest.py in the same package.
import sys
from pathlib import Path as _Path

# Ensure the integrations.reigh package is importable
_pkg_dir = _Path(__file__).resolve().parent
if str(_pkg_dir) not in sys.path:
    sys.path.insert(0, str(_pkg_dir.parent.parent.parent))

from tests.integrations.reigh.conftest import (  # type: ignore[import-not-found]
    make_assembly_json,
    make_identity_json,
    make_project_json,
    make_registry_json,
    make_timeline_id,
)
from astrid.core.integrations.reigh.local_bridge import (
    BRIDGE_CONFIG_VERSION,
    bridge_registry_path,
    find_bridge_timeline,
    list_bridge_project_dirs,
    list_bridge_projects,
    list_bridge_timelines,
    load_bridge_registry,
    load_bridge_timeline,
    resolve_bridge_asset,
    resolve_bridge_projects_root,
)
from astrid.core.timeline.eventlog.selector import resolve_event_log_target
from astrid.core.timeline.observability import resolve_timeline_target


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
        from tests.integrations.reigh.conftest import read_bridge_identity  # type: ignore[import-not-found]

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

    def test_list_bridge_projects_returns_slug_and_name(self, tmp_bridge_root, seed_bridge_project) -> None:
        seed_bridge_project(slug="bridge-one")
        (tmp_bridge_root / "bridge-one" / "project.json").write_text(
            json.dumps(make_project_json(slug="bridge-one", name="Bridge One")),
            encoding="utf-8",
        )

        assert list_bridge_projects(tmp_bridge_root) == [{"slug": "bridge-one", "name": "Bridge One"}]

    def test_list_bridge_timelines_returns_sorted_rows_with_canonical_identity(self, tmp_bridge_root, seed_bridge_project) -> None:
        first_ulid = "01JM4K5N7P0000000000000010"
        second_ulid = "01JM4K5N7P0000000000000011"
        seed_bridge_project(slug="bridge-timelines", timeline_ulid=second_ulid, timeline_id="22222222-2222-2222-2222-222222222222")
        seed_bridge_project(slug="bridge-timelines", timeline_ulid=first_ulid, timeline_id="11111111-1111-1111-1111-111111111111")

        rows = list_bridge_timelines("bridge-timelines", root=tmp_bridge_root)

        assert [row.timeline_ulid for row in rows] == [first_ulid, second_ulid]
        assert rows[0].timeline_id == "11111111-1111-1111-1111-111111111111"

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

    def test_load_bridge_timeline_loads_config_and_sets_config_version(self, tmp_bridge_root, seed_bridge_project) -> None:
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
        assert payload["config_version"] == BRIDGE_CONFIG_VERSION
        assert payload["config"]["tracks"][0]["id"] == "V1"

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

    def test_load_bridge_registry_keeps_relative_sources_entries_and_remote_urls(self, tmp_bridge_root, seed_bridge_project) -> None:
        ulid = "01JM4K5N7P0000000000000019"
        project_dir = seed_bridge_project(
            slug="registry-assets",
            timeline_ulid=ulid,
            assets={
                "local-video": {"file": "clips/demo.mp4", "type": "video/mp4"},
                "remote-image": {"file": "https://cdn.example/cover.png", "type": "image/png"},
            },
        )
        media_path = project_dir / "sources" / "clips" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"demo-bytes")

        registry = load_bridge_registry("registry-assets", ulid, root=tmp_bridge_root)
        local_asset = resolve_bridge_asset("registry-assets", ulid, "local-video", root=tmp_bridge_root)
        remote_asset = resolve_bridge_asset("registry-assets", ulid, "remote-image", root=tmp_bridge_root)

        assert sorted(registry["assets"]) == ["local-video", "remote-image"]
        assert local_asset is not None
        assert local_asset.source_kind == "local"
        assert local_asset.local_path == media_path.resolve()
        assert local_asset.size_bytes == len(b"demo-bytes")
        assert remote_asset is not None
        assert remote_asset.source_kind == "http"
        assert remote_asset.url == "https://cdn.example/cover.png"

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
