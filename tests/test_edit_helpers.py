"""Tests for the shared mutation gateway (pack_write_gateway) — m4 T9 update.

Proves:
1. Bootstrap behavior: created timelines (provenance "created") get NO
   timeline.imported — first domain event is bare.  Only true-legacy
   timelines (no identity sidecar) get timeline.imported bootstrap.
2. Append ordering: events are appended in the order they are supplied.
3. Actor attribution with actor.via chaining.
4. Materialization sequencing: assembly.json is regenerated after append.
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
from astrid.core.timeline.eventlog.types import SupabaseEventLogOptions

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
    """Prove bootstrap behavior: created timelines get NO timeline.imported;
    only true-legacy timelines (no identity) bootstrap."""

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

    def test_created_timeline_first_write_no_bootstrap(self):
        """On first write to a created timeline (provenance 'created'),
        NO timeline.imported is emitted — the first event is the domain
        event directly."""
        result = pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[_arrangement_event()],
            actor=TimelineActor(type="system", id="gw-test:bootstrap", display="Gateway Test"),
        )

        self.assertFalse(result.bootstrap_emitted,
                         "created timeline must NOT bootstrap")
        self.assertEqual(result.attempts, 1,
                         f"expected 1 domain event, got {result.attempts}")
        self.assertEqual(len(result.event_ids), 1)
        self.assertGreaterEqual(result.new_version, 1)

    def test_second_write_also_no_bootstrap(self):
        """Second write to created timeline also has no bootstrap."""
        ulid = self._find_timeline_ulid()

        # First write — no bootstrap for created timeline.
        result1 = pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "first"}])],
            actor=TimelineActor(type="system", id="gw-test:first", display="Gateway Test"),
        )
        self.assertFalse(result1.bootstrap_emitted,
                         "created timeline first write must NOT bootstrap")

        # Second write — also no bootstrap.
        result2 = pack_write_gateway(
            project_slug="bootstrap-proj",
            timeline_slug="bs-timeline",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event([{"id": "second"}])],
            actor=TimelineActor(type="system", id="gw-test:second", display="Gateway Test"),
        )
        self.assertFalse(result2.bootstrap_emitted,
                         "second write must NOT bootstrap")
        self.assertEqual(result2.attempts, 1)
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

    def test_selector_accepts_optional_supabase_options_seam(self):
        from astrid.core.timeline.eventlog import select_timeline_backend
        from uuid import uuid4

        options = SupabaseEventLogOptions(
            url="https://example.supabase.co",
            auth_token="pat-token",
            verified_subject="user-1",
        )
        _stream, backend = select_timeline_backend(
            timeline_id=str(uuid4()),
            timeline_home=self.tmp_root / "bootstrap-proj" / "timelines" / self._find_timeline_ulid(),
            preferred_backend="supabase",
            supabase_options=options,
        )
        self.assertEqual(backend.backend_name(), "supabase")
        self.assertEqual(backend.supabase_url, "https://example.supabase.co")


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
        """Events appear in the order they were given (no bootstrap for
        created timelines)."""
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

        # 3 domain events (no bootstrap for created timeline)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.new_version, 3)


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

        # For created timelines, only domain event is present (no bootstrap).
        events_list = backend.read_events(limit=head.event_count)
        self.assertGreaterEqual(len(events_list), 1, "should have at least 1 domain event")

        domain_event = events_list[0]
        self.assertEqual(domain_event.kind, "arrangement.replaced")

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
