"""Snapshot test for OrchestratorRegistry post CapabilityRegistry migration.

Captures the full orchestrator capability surface — register, get, list,
conflicts, as_mapping, validate_all, and override-store wiring — so
that any unintended drift is caught immediately.

The snapshot baseline is committed PRE-collapse (T4); T12 alone may
re-baseline the element snapshot, not this one.
"""

from __future__ import annotations

import json
import unittest

from astrid.core.execution.orchestrator.registry import (
    OrchestratorRegistry,
    OrchestratorRegistryError,
)
from astrid.core.execution.orchestrator.schema import (
    OrchestratorDefinition,
    OrchestratorValidationError,
    RuntimeSpec,
)
from astrid.core.contracts.schema import CommandSpec, Port


def _make_orchestrator(
    orchestrator_id: str,
    *,
    kind: str = "built_in",
    priority: int = 30,
    **overrides,
) -> OrchestratorDefinition:
    """Build a minimal, valid OrchestratorDefinition for snapshot testing."""
    kwargs: dict = dict(
        id=orchestrator_id,
        name=orchestrator_id.split(".")[-1].replace("_", " ").title(),
        kind=kind,
        version="1.0.0",
        runtime=RuntimeSpec(kind="command", command=CommandSpec(argv=("echo", orchestrator_id))),
        metadata={"priority": priority, "source": "pack", "source_pack": orchestrator_id.split(".", 1)[0]},
    )
    kwargs.update(overrides)
    return OrchestratorDefinition(**kwargs)


def _registry_as_dict(registry: OrchestratorRegistry) -> dict:
    """Serialize the registry's public surface for snapshot comparison."""
    return {
        "list": [
            {
                "id": d.id,
                "name": d.name,
                "kind": d.kind,
                "version": d.version,
                "metadata": dict(d.metadata),
            }
            for d in registry.list()
        ],
        "list_built_in": [
            d.id for d in registry.list(kind="built_in")
        ],
        "list_external": [
            d.id for d in registry.list(kind="external")
        ],
        "conflicts": [
            {
                "key": c.key,
                "winner_id": c.winner.id,
                "shadowed_ids": [s.id for s in c.shadowed],
            }
            for c in registry.conflicts()
        ],
        "as_mapping_keys": sorted(registry.as_mapping().keys()),
    }


class OrchestratorRegistrySnapshotTests(unittest.TestCase):
    """Full-surface snapshot of the migrated OrchestratorRegistry."""

    def test_register_accepts_dict_and_validates(self):
        """register() still accepts dict-or-definition (SD2)."""
        registry = OrchestratorRegistry()
        # dict input
        result = registry.register({
            "id": "test.dict_orch",
            "name": "Dict Orch",
            "kind": "built_in",
            "version": "1.0.0",
            "runtime": {"kind": "command", "command": {"argv": ["echo", "hello"]}},
            "metadata": {"source": "pack", "source_pack": "test"},
        })
        self.assertIsInstance(result, OrchestratorDefinition)
        self.assertEqual(result.id, "test.dict_orch")
        # OrchestratorDefinition input
        defn = _make_orchestrator("test.defn_orch", kind="external")
        result2 = registry.register(defn)
        self.assertIs(result2, defn)

    def test_register_rejects_invalid_input(self):
        """register() validates before inserting."""
        registry = OrchestratorRegistry()
        with self.assertRaises(OrchestratorValidationError):
            registry.register({"id": "test.bad", "name": "Bad"})  # missing required fields

    def test_snapshot_empty_registry(self):
        """Empty registry produces the expected empty-surface snapshot."""
        registry = OrchestratorRegistry()
        snapshot = _registry_as_dict(registry)
        self.assertEqual(snapshot["list"], [])
        self.assertEqual(snapshot["conflicts"], [])
        self.assertEqual(snapshot["as_mapping_keys"], [])

    def test_snapshot_single_orchestrator(self):
        """One orchestrator — no conflicts, basic surface correct."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("video_editing.hype", priority=30))
        snapshot = _registry_as_dict(registry)

        self.assertEqual(len(snapshot["list"]), 1)
        self.assertEqual(snapshot["list"][0]["id"], "video_editing.hype")
        self.assertEqual(snapshot["list_built_in"], ["video_editing.hype"])
        self.assertEqual(snapshot["list_external"], [])
        self.assertEqual(snapshot["conflicts"], [])
        self.assertEqual(snapshot["as_mapping_keys"], ["video_editing.hype"])

    def test_snapshot_multi_orchestrator_with_kind_filtering(self):
        """Multiple orchestrators across kinds — list() filtering works."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("video_editing.hype", kind="built_in", priority=30))
        registry.register(_make_orchestrator("video_editing.vary", kind="built_in", priority=30))
        registry.register(_make_orchestrator("external.upload", kind="external", priority=20))
        snapshot = _registry_as_dict(registry)

        self.assertEqual(len(snapshot["list"]), 3)
        self.assertEqual(snapshot["list_built_in"], ["video_editing.hype", "video_editing.vary"])
        self.assertEqual(snapshot["list_external"], ["external.upload"])
        self.assertEqual(snapshot["conflicts"], [])

    def test_snapshot_with_conflicts(self):
        """Two definitions for the same id — conflicts() reports the shadowed one."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("video_editing.hype", version="1.0.0", priority=30))
        registry.register(_make_orchestrator("video_editing.hype", version="2.0.0", priority=10))
        snapshot = _registry_as_dict(registry)

        # Winner is the higher-priority (lower number)
        self.assertEqual(len(snapshot["list"]), 1)
        self.assertEqual(snapshot["list"][0]["version"], "2.0.0")

        self.assertEqual(len(snapshot["conflicts"]), 1)
        self.assertEqual(snapshot["conflicts"][0]["key"], "video_editing.hype")
        self.assertEqual(snapshot["conflicts"][0]["winner_id"], "video_editing.hype")
        self.assertEqual(len(snapshot["conflicts"][0]["shadowed_ids"]), 1)
        self.assertEqual(snapshot["conflicts"][0]["shadowed_ids"][0], "video_editing.hype")

    def test_get_resolves_winner(self):
        """get() returns highest-priority definition."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("video_editing.hype", version="1.0.0", priority=30))
        registry.register(_make_orchestrator("video_editing.hype", version="2.0.0", priority=10))

        winner = registry.get("video_editing.hype")
        self.assertEqual(winner.version, "2.0.0")
        self.assertEqual(winner.metadata["priority"], 10)

    def test_get_unknown_raises_keyerror(self):
        """get() raises KeyError for unknown ids."""
        registry = OrchestratorRegistry()
        with self.assertRaises(KeyError):
            registry.get("nonexistent.orch")

    def test_list_invalid_kind_raises(self):
        """list() raises for invalid kind values."""
        registry = OrchestratorRegistry()
        with self.assertRaises(OrchestratorRegistryError):
            registry.list(kind="bogus")

    def test_as_mapping_returns_winners(self):
        """as_mapping() returns the winning definition for each id."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("a.orch", priority=30))
        registry.register(_make_orchestrator("a.orch", priority=10))
        registry.register(_make_orchestrator("b.orch", priority=20))

        mp = registry.as_mapping()
        self.assertEqual(mp["a.orch"].metadata["priority"], 10)
        self.assertEqual(mp["b.orch"].metadata["priority"], 20)

    def test_validate_all_passes_on_clean_registry(self):
        """validate_all() succeeds when there are no issues."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("a.orch", priority=30))
        registry.register(_make_orchestrator("b.orch", priority=20))
        result = registry.validate_all()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_validate_all_detects_missing_child_orchestrator(self):
        """validate_all() raises when child_orchestrators references an unknown orchestrator."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator(
            "a.orch",
            priority=30,
            child_orchestrators=("unknown.orch",),
        ))
        with self.assertRaises(OrchestratorRegistryError):
            registry.validate_all()

    def test_validate_all_detects_self_reference(self):
        """validate_all() raises when orchestrator references itself as child."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator(
            "a.orch",
            priority=30,
            child_orchestrators=("a.orch",),
        ))
        with self.assertRaises(OrchestratorRegistryError):
            registry.validate_all()

    def test_conflicts_empty_when_no_overlap(self):
        """conflicts() returns empty when no ids share keys."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("a.orch", priority=30))
        registry.register(_make_orchestrator("b.orch", priority=20))
        self.assertEqual(registry.conflicts(), ())

    def test_to_json_serializes(self):
        """to_json() produces valid JSON."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("test.orch", priority=30))
        json_str = registry.to_json()
        data = json.loads(json_str)
        self.assertIn("orchestrators", data)
        self.assertEqual(len(data["orchestrators"]), 1)
        self.assertEqual(data["orchestrators"][0]["id"], "test.orch")

    def test_to_dict_respects_kind_filter(self):
        """to_dict() filters by kind when requested."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("a.orch", kind="built_in", priority=30))
        registry.register(_make_orchestrator("b.orch", kind="external", priority=20))
        data = registry.to_dict(kind="built_in")
        self.assertEqual(len(data["orchestrators"]), 1)
        self.assertEqual(data["orchestrators"][0]["id"], "a.orch")

    def test_iter_all_yields_all_including_shadowed(self):
        """_iter_all() yields both winner and shadowed definitions."""
        registry = OrchestratorRegistry()
        registry.register(_make_orchestrator("a.orch", version="1.0.0", priority=30))
        registry.register(_make_orchestrator("a.orch", version="2.0.0", priority=10))
        all_defs = list(registry._iter_all())
        self.assertEqual(len(all_defs), 2)
        versions = {d.version for d in all_defs}
        self.assertEqual(versions, {"1.0.0", "2.0.0"})

    def test_child_output_artifact_types_empty_for_unknown_id(self):
        """child_output_artifact_types() returns empty dict for unknown id."""
        registry = OrchestratorRegistry()
        self.assertEqual(registry.child_output_artifact_types("nonexistent.orch"), {})


if __name__ == "__main__":
    unittest.main()
