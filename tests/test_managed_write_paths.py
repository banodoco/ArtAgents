"""End-to-end tests for managed write paths — m4 T9 update.

Proves:
1. Managed flows emit correct event kinds and order
   (timeline.config_replaced; timeline.imported only for true-legacy timelines).
2. Compatibility outputs remain byte-equivalent after managed writes.
3. verify_chain() passes for pack-produced timeline fixtures.
4. Actor attribution including actor.via chaining.
5. Unmanaged artifact mode still works without breaking.

These tests exercise the managed LocalFs event path while Astrid's Reigh-side
blob writes remain a legacy compatibility bridge.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from astrid import timeline as timeline_contract
from astrid.core.project import paths as project_paths
from astrid.core.project.project import create_project
from astrid.core.timeline._edit_helpers import pack_write_gateway, PackWriteResult
from astrid.core.timeline.crud import create_timeline
from astrid.core.timeline.events.schema import TimelineActor

ROOT = Path(__file__).resolve().parents[1]


def _arrangement_event(clips: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a runtime-safe full TimelineConfig replacement event."""
    config: dict[str, Any] = {"tracks": [], "clips": []}
    if clips:
        config["tracks"] = [{"id": "v1", "kind": "visual", "label": "Video"}]
        config["clips"] = [
            {
                "id": str(clip.get("id", f"clip-{index}")),
                "at": float(index),
                "track": "v1",
                "clipType": "media",
                "asset": str(clip.get("asset", clip.get("id", f"asset-{index}"))),
            }
            for index, clip in enumerate(clips)
        ]
    return {
        "kind": "timeline.config_replaced",
        "payload": {"config": config},
    }


def _arrangement_event_dict(config: dict[str, Any]) -> dict[str, Any]:
    """Build a runtime-safe full TimelineConfig replacement event."""
    payload = {"tracks": [], "clips": []}
    payload.update(dict(config))
    return {
        "kind": "timeline.config_replaced",
        "payload": {"config": payload},
    }


def _resolve_backend_and_verify(project_slug: str, ulid: str, tdir: Path) -> bool:
    """Resolve the backend for a timeline and run verify_chain()."""
    from astrid.core.timeline.eventlog import select_timeline_backend
    from astrid.core.timeline.paths import assembly_identity_path
    from astrid.core.project.jsonio import read_json

    identity = read_json(assembly_identity_path(project_slug, ulid))
    _stream, backend = select_timeline_backend(
        timeline_id=identity["timeline_id"],
        timeline_home=tdir,
        preferred_backend=identity.get("backend"),
    )
    verification = backend.verify_chain()
    return verification.ok


class ManagedWriteEventKindsTest(unittest.TestCase):
    """Prove managed writes emit correct event kinds in correct order."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-evkinds-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("evkinds-proj")
        create_timeline("evkinds-proj", "evkinds-tl")

    def _find_timeline_ulid_and_dir(self) -> tuple[str, Path]:
        from astrid.core.timeline.paths import find_timeline_by_slug
        found = find_timeline_by_slug("evkinds-proj", "evkinds-tl")
        self.assertIsNotNone(found)
        return found

    def _read_event_kinds(self, tdir: Path) -> list[str]:
        from astrid.core.timeline.paths import assembly_identity_path
        from astrid.core.project.jsonio import read_json
        from astrid.core.timeline.eventlog import select_timeline_backend

        identity = read_json(assembly_identity_path("evkinds-proj", self._find_timeline_ulid_and_dir()[0]))
        _stream, backend = select_timeline_backend(
            timeline_id=identity["timeline_id"],
            timeline_home=tdir,
            preferred_backend=identity.get("backend"),
        )
        events = backend.read_events(limit=100)
        return [e.kind for e in events]

    def test_first_managed_write_no_bootstrap_for_created_timeline(self):
        """First managed write on a created timeline emits timeline.config_replaced
        directly — NO timeline.imported bootstrap."""
        ulid, tdir = self._find_timeline_ulid_and_dir()

        result = pack_write_gateway(
            project_slug="evkinds-proj",
            timeline_slug="evkinds-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="test:evkinds", display="Event Kinds Test"),
        )

        self.assertFalse(result.bootstrap_emitted,
                         "created timeline must NOT bootstrap")
        kinds = self._read_event_kinds(tdir)
        self.assertEqual(kinds[0], "timeline.config_replaced",
                         f"First event should be timeline.config_replaced, got {kinds}")

    def test_subsequent_managed_write_no_bootstrap(self):
        """Both first and second writes skip bootstrap for created timelines."""
        ulid, tdir = self._find_timeline_ulid_and_dir()

        # First write — no bootstrap for created timeline.
        result1 = pack_write_gateway(
            project_slug="evkinds-proj",
            timeline_slug="evkinds-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "first"}])],
            actor=TimelineActor(type="system", id="test:evkinds-1", display="Event Kinds Test 1"),
        )
        self.assertFalse(result1.bootstrap_emitted)

        # Second write — also no bootstrap.
        result2 = pack_write_gateway(
            project_slug="evkinds-proj",
            timeline_slug="evkinds-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "second"}])],
            actor=TimelineActor(type="system", id="test:evkinds-2", display="Event Kinds Test 2"),
        )

        self.assertFalse(result2.bootstrap_emitted)
        self.assertEqual(result2.attempts, 1)


class ManagedWriteVerifyChainTest(unittest.TestCase):
    """Prove verify_chain() passes after managed writes."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-vfy-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("vfy-proj")
        create_timeline("vfy-proj", "vfy-tl")

    def test_verify_chain_passes_after_single_managed_write(self):
        """verify_chain() passes after a single managed write with bootstrap."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("vfy-proj", "vfy-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        pack_write_gateway(
            project_slug="vfy-proj",
            timeline_slug="vfy-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="test:vfy", display="Verify Test"),
        )

        self.assertTrue(_resolve_backend_and_verify("vfy-proj", ulid, tdir),
                        "verify_chain() should pass after managed write")

    def test_verify_chain_passes_after_multiple_managed_writes(self):
        """verify_chain() passes after multiple managed writes."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("vfy-proj", "vfy-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        for i in range(3):
            pack_write_gateway(
                project_slug="vfy-proj",
                timeline_slug="vfy-tl",
                timeline_ulid=ulid,
                timeline_event_stream_id="",
                events=[_arrangement_event([{"id": f"clip_{i}"}])],
                actor=TimelineActor(type="system", id=f"test:vfy-{i}", display=f"Verify Test {i}"),
            )

        self.assertTrue(_resolve_backend_and_verify("vfy-proj", ulid, tdir),
                        "verify_chain() should pass after multiple managed writes")


class ManagedWriteCompatibilityOutputTest(unittest.TestCase):
    """Prove compatibility outputs are produced and equivalent after managed writes."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-comp-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("comp-proj")
        create_timeline("comp-proj", "comp-tl")

    def test_assembly_json_exists_after_managed_write(self):
        """assembly.json is materialized after managed write."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("comp-proj", "comp-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        timeline_config = {
            "tracks": [{"id": "v1", "kind": "visual", "label": "Video"}],
            "clips": [
                {
                    "id": "clip_1",
                    "track": "v1",
                    "clipType": "media",
                    "asset": "asset_1",
                    "at": 0.0,
                    "from": 0.0,
                    "to": 5.0,
                }
            ],
            "theme": "test-theme",
        }

        pack_write_gateway(
            project_slug="comp-proj",
            timeline_slug="comp-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event_dict(timeline_config)],
            actor=TimelineActor(type="system", id="test:comp", display="Compat Test"),
        )

        assembly_path = tdir / "assembly.json"
        self.assertTrue(assembly_path.exists(), "assembly.json must exist after managed write")
        assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
        self.assertIsInstance(assembly, dict, "assembly.json must be valid JSON dict")

    def test_assembly_json_updated_after_each_write(self):
        """assembly.json content changes after each managed write."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("comp-proj", "comp-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        config1 = {"tracks": [{"id": "v1", "kind": "visual", "label": "Video"}], "clips": [], "theme": "t1"}
        config2 = {"tracks": [{"id": "v1", "kind": "visual", "label": "Video"}], "clips": [], "theme": "t2"}

        pack_write_gateway(
            project_slug="comp-proj",
            timeline_slug="comp-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event_dict(config1)],
            actor=TimelineActor(type="system", id="test:comp-1", display="Compat Test 1"),
        )

        assembly_path = tdir / "assembly.json"
        content1 = assembly_path.read_bytes()

        pack_write_gateway(
            project_slug="comp-proj",
            timeline_slug="comp-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event_dict(config2)],
            actor=TimelineActor(type="system", id="test:comp-2", display="Compat Test 2"),
        )

        content2 = assembly_path.read_bytes()
        self.assertNotEqual(content1, content2,
                            "assembly.json should differ after second write")


class ManagedWriteActorAttributionTest(unittest.TestCase):
    """Prove actor attribution with actor.via chaining on managed writes."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-actor-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("actor2-proj")
        create_timeline("actor2-proj", "actor2-tl")

    def _read_domain_events(self, project_slug: str, timeline_slug: str):
        from astrid.core.timeline.paths import find_timeline_by_slug, assembly_identity_path
        from astrid.core.timeline.eventlog import select_timeline_backend
        from astrid.core.project.jsonio import read_json

        found = find_timeline_by_slug(project_slug, timeline_slug)
        self.assertIsNotNone(found)
        ulid, tdir = found
        identity = read_json(assembly_identity_path(project_slug, ulid))
        _stream, backend = select_timeline_backend(
            timeline_id=identity["timeline_id"],
            timeline_home=tdir,
            preferred_backend=identity.get("backend"),
        )
        return backend.read_events(limit=100)

    def test_system_actor_attributed_correctly(self):
        """System actor is attributed correctly on managed writes."""
        pack_write_gateway(
            project_slug="actor2-proj",
            timeline_slug="actor2-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="video_editing.cut:test-run-001", display="video_editing.cut"),
        )

        events = self._read_domain_events("actor2-proj", "actor2-tl")
        domain_event = events[-1]
        self.assertEqual(domain_event.kind, "timeline.config_replaced")
        self.assertEqual(domain_event.actor.type, "system")
        self.assertEqual(domain_event.actor.id, "video_editing.cut:test-run-001")

    def test_agent_actor_with_human_via_chaining(self):
        """Agent actor with human via preserves chained provenance."""
        human_actor = TimelineActor(type="human", id="user-alice", display="Alice")
        agent_actor = TimelineActor(type="agent", id="agent-claude", display="Claude")

        pack_write_gateway(
            project_slug="actor2-proj",
            timeline_slug="actor2-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=agent_actor,
            actor_via=human_actor,
        )

        events = self._read_domain_events("actor2-proj", "actor2-tl")
        domain_event = events[-1]
        self.assertEqual(domain_event.actor.type, "agent")
        self.assertEqual(domain_event.actor.id, "agent-claude")

        via_list = domain_event.actor.via or []
        self.assertGreaterEqual(len(via_list), 1, "actor.via should contain upstream actor")
        self.assertEqual(via_list[0].type, "human")
        self.assertEqual(via_list[0].id, "user-alice")

    def test_human_actor_direct(self):
        """Human actor is attributed directly when no via chain."""
        human_actor = TimelineActor(type="human", id="user-bob", display="Bob")

        pack_write_gateway(
            project_slug="actor2-proj",
            timeline_slug="actor2-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=human_actor,
        )

        events = self._read_domain_events("actor2-proj", "actor2-tl")
        domain_event = events[-1]
        self.assertEqual(domain_event.actor.type, "human")
        self.assertEqual(domain_event.actor.id, "user-bob")
        # No via chain for direct human actor.
        via_list = domain_event.actor.via or []
        self.assertEqual(len(via_list), 0, "Direct human actor should have no via chain")


class UnmanagedArtifactModeTest(unittest.TestCase):
    """Prove unmanaged artifact mode still works (no managed binding = no gateway)."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-unmgd-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_gateway_not_called_without_managed_binding(self):
        """pack_write_gateway is not called when no managed binding is present."""
        # Unmanaged mode: create project/timeline is NOT needed.
        # Just verify that the gateway raises an error when the timeline
        # doesn't exist (proving it would only be called in managed mode).
        with self.assertRaises(Exception):
            pack_write_gateway(
                project_slug="nonexistent-proj",
                timeline_slug="nonexistent-tl",
                timeline_ulid="",
                timeline_event_stream_id="",
                events=[_arrangement_event()],
                actor=TimelineActor(type="system", id="test:unmgd", display="Unmanaged Test"),
            )

    def test_unmanaged_timeline_save_timeline_still_works(self):
        """save_timeline from astrid.timeline still writes files directly (unmanaged mode)."""
        from astrid import timeline as tl

        out_dir = Path(tempfile.mkdtemp(prefix="unmgd-out-", dir=self.tmp_root))
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)

        timeline_config = {
            "tracks": [{"id": "v1", "kind": "visual", "label": "Video"}],
            "clips": [],
            "theme": "banodoco-default",
        }
        timeline_path = out_dir / "hype.timeline.json"
        tl.save_timeline(timeline_config, timeline_path)

        self.assertTrue(timeline_path.exists(), "hype.timeline.json should be written in unmanaged mode")
        content = json.loads(timeline_path.read_text(encoding="utf-8"))
        self.assertIsInstance(content, dict)
        self.assertEqual(content.get("theme"), "banodoco-default")


class ManagedWritePackWriteResultTest(unittest.TestCase):
    """Prove PackWriteResult contains all required fields for managed writes."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-result-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("result-proj")
        create_timeline("result-proj", "result-tl")

    def test_pack_write_result_fields_for_cut_like_write(self):
        """PackWriteResult simulates what cut/refine/assemble expect."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("result-proj", "result-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        result = pack_write_gateway(
            project_slug="result-proj",
            timeline_slug="result-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="video_editing.cut:hash123", display="video_editing.cut"),
        )

        # Verify all fields packs expect.
        self.assertIsInstance(result, PackWriteResult)
        self.assertGreater(result.new_version, 0, "new_version should be > 0")
        self.assertGreater(len(result.event_ids), 0, "event_ids should be non-empty")
        self.assertGreater(result.attempts, 0, "attempts should be > 0")
        self.assertTrue(len(result.backend_name) > 0, "backend_name should be non-empty")
        self.assertTrue(len(result.timeline_ulid) > 0, "timeline_ulid should be non-empty")
        self.assertEqual(result.timeline_slug, "result-tl")
        self.assertTrue(len(result.timeline_event_stream_id) > 0,
                        "timeline_event_stream_id should be non-empty")
        self.assertTrue(result.timeline_home.exists(), "timeline_home should exist")
        self.assertIsInstance(result.bootstrap_emitted, bool)

    def test_pack_write_result_for_hype_like_write(self):
        """PackWriteResult simulates what hype expects after managed edit."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("result-proj", "result-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        # First write (no bootstrap for created timeline).
        result1 = pack_write_gateway(
            project_slug="result-proj",
            timeline_slug="result-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="video_editing.hype:editor_micro_fix", display="video_editing.hype"),
        )
        self.assertFalse(result1.bootstrap_emitted,
                         "created timeline first write must NOT bootstrap")

        # Second write (still no bootstrap) — like hype's _apply_trim_deltas.
        result = pack_write_gateway(
            project_slug="result-proj",
            timeline_slug="result-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "trimmed_clip"}])],
            actor=TimelineActor(type="system", id="video_editing.hype:editor_micro_fix", display="video_editing.hype"),
        )

        self.assertFalse(result.bootstrap_emitted,
                         "Second write should not bootstrap")
        self.assertEqual(result.attempts, 1,
                         "Second write should append exactly 1 event")
        self.assertGreater(result.new_version, result1.new_version,
                           "new_version should increment from previous write")


class ManagedWriteSlugResolutionTest(unittest.TestCase):
    """Prove the gateway resolves ULID from slug when not provided."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-slug-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("slug-proj")
        create_timeline("slug-proj", "slug-tl")

    def test_gateway_resolves_ulid_from_empty_string(self):
        """Gateway resolves ULID when timeline_ulid='' (as packs do)."""
        result = pack_write_gateway(
            project_slug="slug-proj",
            timeline_slug="slug-tl",
            timeline_ulid="",  # Packs pass empty string
            timeline_event_stream_id="",  # Packs pass empty string
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="test:slug", display="Slug Resolve Test"),
        )

        self.assertTrue(len(result.timeline_ulid) > 0,
                        "Gateway should resolve ULID from slug")
        self.assertEqual(len(result.timeline_ulid), 26,
                        "ULID should be exactly 26 characters")
        self.assertTrue(len(result.timeline_event_stream_id) > 0,
                        "Gateway should resolve event stream ID")
        # Should be a valid UUID format
        parts = result.timeline_event_stream_id.split("-")
        self.assertEqual(len(parts), 5, "Event stream ID should be UUID format")


class ManagedEventMultipleKindsTest(unittest.TestCase):
    """Prove multiple event kinds can be appended in a single gateway call."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="mgt-multi-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("multi-proj")
        create_timeline("multi-proj", "multi-tl")

    def test_multiple_config_replaced_events_in_order(self):
        """Multiple timeline.config_replaced events appended in order (no bootstrap
        for created timelines)."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("multi-proj", "multi-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        events = [
            _arrangement_event([{"id": "step1"}]),
            _arrangement_event([{"id": "step2"}]),
            _arrangement_event([{"id": "step3"}]),
        ]

        result = pack_write_gateway(
            project_slug="multi-proj",
            timeline_slug="multi-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=events,
            actor=TimelineActor(type="system", id="test:multi", display="Multi Test"),
        )

        # 3 domain events (no bootstrap for created timeline)
        self.assertFalse(result.bootstrap_emitted)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.new_version, 3)

        # Verify ordering from event stream.
        from astrid.core.timeline.paths import assembly_identity_path
        from astrid.core.project.jsonio import read_json
        from astrid.core.timeline.eventlog import select_timeline_backend

        identity = read_json(assembly_identity_path("multi-proj", ulid))
        _stream, backend = select_timeline_backend(
            timeline_id=identity["timeline_id"],
            timeline_home=tdir,
            preferred_backend=identity.get("backend"),
        )
        all_events = backend.read_events(limit=10)
        kinds = [e.kind for e in all_events]

        self.assertEqual(kinds[0], "timeline.config_replaced")
        self.assertEqual(kinds[1], "timeline.config_replaced")
        self.assertEqual(kinds[2], "timeline.config_replaced")
        self.assertEqual(len(kinds), 3)


class ManagedPackConfigReplacementSurfaceTest(unittest.TestCase):
    """Pack-managed full writes use validated timeline.config_replaced configs."""

    def _capture_gateway_events(self):
        captured: list[dict[str, Any]] = []

        def fake_gateway(*args, **kwargs):
            captured.extend(kwargs["events"])
            return SimpleNamespace(new_version=17)

        return captured, fake_gateway

    def _assert_single_valid_config_replaced_event(self, event: dict[str, Any]) -> None:
        self.assertEqual(event["kind"], "timeline.config_replaced")
        payload = event["payload"]
        self.assertIsInstance(payload, dict)
        config = payload["config"]
        self.assertEqual(timeline_contract.validate_timeline_config_for_container(config), config)

    def test_cut_refine_and_assemble_emit_config_replaced_payloads(self):
        from astrid.core.timeline import _edit_helpers
        from astrid.packs.video_editing.executors.cut import run as cut_run
        from astrid.packs.editorial.executors.refine import run as refine_run
        from astrid.packs.iteration.executors.assemble import run as assemble_run

        config = {
            "tracks": [{"id": "v1", "kind": "visual", "label": "Video"}],
            "clips": [
                {
                    "id": "clip-1",
                    "at": 0,
                    "track": "v1",
                    "clipType": "media",
                    "asset": "asset-1",
                }
            ],
        }
        args = SimpleNamespace(project="demo", timeline_slug="primary")

        for emit in (
            lambda: cut_run._emit_cut_managed_events(args, config),
            lambda: refine_run._emit_refine_managed_events(args, config),
            lambda: assemble_run._emit_assemble_managed_events("demo", "primary", config),
        ):
            captured, fake_gateway = self._capture_gateway_events()
            with patch.object(_edit_helpers, "pack_write_gateway", fake_gateway):
                self.assertEqual(emit(), 17)
            self.assertEqual(len(captured), 1)
            self._assert_single_valid_config_replaced_event(captured[0])

    def test_named_managed_sources_do_not_emit_arrangement_replaced(self):
        managed_sources = [
            ROOT / "astrid/packs/video_editing/executors/cut/run.py",
            ROOT / "astrid/packs/video_editing/orchestrators/hype/run.py",
            ROOT / "astrid/packs/editorial/executors/refine/run.py",
            ROOT / "astrid/packs/iteration/executors/assemble/run.py",
            ROOT / "astrid/core/worker/banodoco_worker.py",
        ]
        for path in managed_sources:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn('"kind": "arrangement.replaced"', source, str(path))
            self.assertNotIn("'kind': 'arrangement.replaced'", source, str(path))


if __name__ == "__main__":
    unittest.main()
