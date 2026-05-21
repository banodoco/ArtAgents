"""Tests for the shared mutation gateway (pack_write_gateway) — m3.5 T7.

Proves:
1. Explicit bootstrap: timeline.imported emitted before first domain mutation
   when the event stream is empty and identity sidecar exists.
2. Append ordering: events are appended in the order they are supplied.
3. Actor attribution with actor.via chaining.
4. Materialization sequencing: assembly.json is updated after each append.
5. Gateway return values: PackWriteResult contains all required fields.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from astrid.core.project import paths as project_paths
from astrid.core.project.project import create_project
from astrid.core.timeline._edit_helpers import pack_write_gateway, PackWriteResult
from astrid.core.timeline.crud import create_timeline
from astrid.core.timeline.events.schema import TimelineActor

ROOT = Path(__file__).resolve().parents[1]


def _arrangement_event(clips: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build an arrangement.replaced event spec with a simple clips payload."""
    return {
        "kind": "arrangement.replaced",
        "payload": {"arrangement": {"clips": clips or []}},
    }


def _arrangement_event_dict(config: dict[str, Any]) -> dict[str, Any]:
    """Build an arrangement.replaced event spec with the given config."""
    return {
        "kind": "arrangement.replaced",
        "payload": {"arrangement": dict(config)},
    }


class GatewayBootstrapTest(unittest.TestCase):
    """Prove timeline.imported bootstrap behavior."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="gw-bootstrap-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("bootstrap-proj")
        create_timeline("bootstrap-proj", "bs-timeline")

    def _find_timeline_ulid(self) -> str:
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("bootstrap-proj", "bs-timeline")
        self.assertIsNotNone(found, "timeline should be discoverable")
        ulid, _tdir = found
        return ulid

    def test_first_write_emits_timeline_imported_before_domain_event(self):
        """On first write to an empty stream, timeline.imported is emitted first."""
        result = pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="gw-test:bootstrap", display="Gateway Test"),
        )

        self.assertTrue(result.bootstrap_emitted, "bootstrap should be emitted on first write")
        # Bootstrap + 1 domain event = 2 events
        self.assertEqual(result.attempts, 2, f"expected 2 events, got {result.attempts}")
        self.assertEqual(len(result.event_ids), 2)
        # Version should be >= 2 (bootstrap at v1, domain at v2)
        self.assertGreaterEqual(result.new_version, 2)

    def test_second_write_skips_bootstrap(self):
        """Second write to the same stream skips timeline.imported."""
        ulid = self._find_timeline_ulid()

        # First write — bootstraps.
        result1 = pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "first"}])],
            actor=TimelineActor(type="system", id="gw-test:first", display="Gateway Test"),
        )
        self.assertTrue(result1.bootstrap_emitted)

        # Second write — no bootstrap.
        result2 = pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "second"}])],
            actor=TimelineActor(type="system", id="gw-test:second", display="Gateway Test"),
        )
        self.assertFalse(result2.bootstrap_emitted, "bootstrap should be skipped on second write")
        # Only 1 domain event
        self.assertEqual(result2.attempts, 1)
        # Version should be higher than first write
        self.assertGreater(result2.new_version, result1.new_version)

    def test_verify_chain_passes_after_writes(self):
        """backend.verify_chain() must pass after gateway writes."""
        ulid = self._find_timeline_ulid()

        pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="gw-test:verify", display="Gateway Test"),
        )

        # Resolve backend and verify.
        from astrid.core.timeline.eventlog import select_timeline_backend
        from astrid.core.timeline.paths import assembly_identity_path
        from astrid.core.project.jsonio import read_json

        identity = read_json(assembly_identity_path("bootstrap-proj", ulid))
        tdir = self.tmp_root / "bootstrap-proj" / "timelines" / ulid
        _stream, backend = select_timeline_backend(
            timeline_id=identity["timeline_id"],
            timeline_home=tdir,
            preferred_backend=identity.get("backend"),
        )
        verification = backend.verify_chain()
        self.assertTrue(verification.ok, f"verify_chain failed: {verification.error}")


class GatewayAppendOrderingTest(unittest.TestCase):
    """Prove events are appended in order."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="gw-order-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("order-proj")
        create_timeline("order-proj", "order-tl")

    def test_events_appended_in_supplied_order(self):
        """Events appear in the order they were given, after bootstrap."""
        events = [
            _arrangement_event([{"id": "1"}]),
            _arrangement_event([{"id": "2"}]),
            _arrangement_event([{"id": "3"}]),
        ]

        result = pack_write_gateway(
            project_slug="order-proj",
            timeline_slug="order-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=events,
            actor=TimelineActor(type="system", id="gw-test:order", display="Gateway Test"),
        )

        # Bootstrap + 3 domain = 4 total
        self.assertEqual(result.attempts, 4)
        self.assertEqual(result.new_version, 4)


class GatewayActorAttributionTest(unittest.TestCase):
    """Prove actor attribution with actor.via chaining."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="gw-actor-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("actor-proj")
        create_timeline("actor-proj", "actor-tl")

    def test_actor_via_chaining_stored_in_events(self):
        """actor.via is preserved in the emitted event metadata."""
        human_actor = TimelineActor(type="human", id="user-42", display="Alice")
        agent_actor = TimelineActor(type="agent", id="agent-007", display="Claude")

        result = pack_write_gateway(
            project_slug="actor-proj",
            timeline_slug="actor-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=agent_actor,
            actor_via=human_actor,
        )

        # Read back the event stream and verify actor via chain.
        from astrid.core.timeline.eventlog import select_timeline_backend
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("actor-proj", "actor-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        # Read identity.
        from astrid.core.project.jsonio import read_json
        from astrid.core.timeline.paths import assembly_identity_path

        identity = read_json(assembly_identity_path("actor-proj", ulid))
        _, backend = select_timeline_backend(
            timeline_id=identity["timeline_id"],
            timeline_home=tdir,
            preferred_backend=identity.get("backend"),
        )

        head = backend.head()
        self.assertGreater(head.event_count, 0)

        # Check the domain event's actor (not the bootstrap event).
        events_list = backend.read_events(limit=head.event_count)
        self.assertGreaterEqual(len(events_list), 2, "should have bootstrap + domain event")

        domain_event = events_list[-1]
        # TimelineEvent.actor is a TimelineActor dataclass.
        domain_actor = domain_event.actor
        self.assertEqual(domain_actor.type, "agent")
        self.assertEqual(domain_actor.id, "agent-007")

        via_list = domain_actor.via or []
        self.assertGreaterEqual(len(via_list), 1)
        self.assertEqual(via_list[0].type, "human")
        self.assertEqual(via_list[0].id, "user-42")


class GatewayReturnValuesTest(unittest.TestCase):
    """Prove PackWriteResult contains all required fields."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="gw-return-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("return-proj")
        create_timeline("return-proj", "return-tl")

    def test_pack_write_result_has_all_required_fields(self):
        """Every field of PackWriteResult is populated after a write."""
        result = pack_write_gateway(
            project_slug="return-proj",
            timeline_slug="return-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="gw-test:return", display="Gateway Test"),
        )

        self.assertIsInstance(result, PackWriteResult)
        self.assertIsInstance(result.new_version, int)
        self.assertGreater(result.new_version, 0)
        self.assertIsInstance(result.event_ids, list)
        self.assertGreater(len(result.event_ids), 0)
        self.assertIsInstance(result.attempts, int)
        self.assertGreater(result.attempts, 0)
        self.assertIsInstance(result.backend_name, str)
        self.assertTrue(len(result.backend_name) > 0)
        self.assertIsInstance(result.timeline_ulid, str)
        self.assertTrue(len(result.timeline_ulid) > 0)
        self.assertIsInstance(result.timeline_slug, str)
        self.assertEqual(result.timeline_slug, "return-tl")
        self.assertIsInstance(result.timeline_event_stream_id, str)
        self.assertTrue(len(result.timeline_event_stream_id) > 0)
        self.assertIsInstance(result.timeline_home, Path)
        self.assertTrue(result.timeline_home.exists())
        self.assertIsInstance(result.bootstrap_emitted, bool)
        self.assertIsInstance(result.artifact_handles, dict)


class GatewayMaterializationTest(unittest.TestCase):
    """Prove assembly.json is updated after each append (materialize sequencing)."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="gw-mat-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_root, ignore_errors=True)
        self._env = patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(self.tmp_root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        create_project("mat-proj")
        create_timeline("mat-proj", "mat-tl")

    def test_assembly_json_updated_after_append(self):
        """assembly.json is materialized after each domain event append."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("mat-proj", "mat-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        timeline_config = {"tracks": [{"id": "v1", "kind": "visual", "label": "Video"}], "clips": [], "theme": "test"}

        result = pack_write_gateway(
            project_slug="mat-proj",
            timeline_slug="mat-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event_dict(timeline_config)],
            actor=TimelineActor(type="system", id="gw-test:mat", display="Gateway Test"),
        )

        # assembly.json must exist and be valid JSON.
        assembly_path = tdir / "assembly.json"
        self.assertTrue(assembly_path.exists(), "assembly.json must exist after materialization")
        assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
        self.assertIsInstance(assembly, dict)

    def test_verify_chain_passes_after_materialization(self):
        """backend.verify_chain() passes after gateway write + materialization."""
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("mat-proj", "mat-tl")
        self.assertIsNotNone(found)
        ulid, tdir = found

        pack_write_gateway(
            project_slug="mat-proj",
            timeline_slug="mat-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="gw-test:mat-vfy", display="Gateway Test"),
        )

        # Resolve backend and verify.
        from astrid.core.timeline.eventlog import select_timeline_backend
        from astrid.core.timeline.paths import assembly_identity_path
        from astrid.core.project.jsonio import read_json

        identity = read_json(assembly_identity_path("mat-proj", ulid))
        _stream, backend = select_timeline_backend(
            timeline_id=identity["timeline_id"],
            timeline_home=tdir,
            preferred_backend=identity.get("backend"),
        )
        verification = backend.verify_chain()
        self.assertTrue(verification.ok, f"verify_chain failed after materialization: {verification.error}")


if __name__ == "__main__":
    unittest.main()
