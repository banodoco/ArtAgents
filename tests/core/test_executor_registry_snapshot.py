"""Snapshot test for ExecutorRegistry post CapabilityRegistry migration.

Captures the full executor capability surface — register, get, list,
conflicts, as_mapping, validate_all, and override-store wiring — so
that any unintended drift is caught immediately.

The snapshot baseline is committed PRE-collapse (T3); T12 alone may
re-baseline the element snapshot, not this one.
"""

from __future__ import annotations

import json
import unittest

from astrid.core.execution.executor.registry import (
    ExecutorRegistry,
    ExecutorRegistryError,
)
from astrid.core.execution.executor.schema import (
    ExecutorDefinition,
    ExecutorValidationError,
    GraphMetadata,
)
from astrid.core.contracts.schema import CachePolicy, CommandSpec


def _make_executor(
    executor_id: str,
    *,
    kind: str = "built_in",
    priority: int = 30,
    **overrides,
) -> ExecutorDefinition:
    """Build a minimal, valid ExecutorDefinition for snapshot testing."""
    kwargs: dict = dict(
        id=executor_id,
        name=executor_id.split(".")[-1].replace("_", " ").title(),
        kind=kind,
        version="1.0.0",
        command=CommandSpec(argv=("echo", executor_id)),
        cache=CachePolicy(mode="none"),
        metadata={"priority": priority, "source": "pack", "source_pack": executor_id.split(".", 1)[0]},
    )
    kwargs.update(overrides)
    return ExecutorDefinition(**kwargs)


def _registry_as_dict(registry: ExecutorRegistry) -> dict:
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


class ExecutorRegistrySnapshotTests(unittest.TestCase):
    """Full-surface snapshot of the migrated ExecutorRegistry."""

    def test_register_accepts_dict_and_validates(self):
        """register() still accepts dict-or-definition (SD2)."""
        registry = ExecutorRegistry()
        # dict input
        result = registry.register({
            "id": "test.dict_exec",
            "name": "Dict Exec",
            "kind": "built_in",
            "version": "1.0.0",
            "command": {"argv": ["echo", "hello"]},
            "cache": {"mode": "none"},
            "metadata": {"source": "pack", "source_pack": "test"},
        })
        self.assertIsInstance(result, ExecutorDefinition)
        self.assertEqual(result.id, "test.dict_exec")
        # ExecutorDefinition input
        defn = _make_executor("test.defn_exec", kind="external")
        result2 = registry.register(defn)
        self.assertIs(result2, defn)

    def test_register_rejects_invalid_input(self):
        """register() validates before inserting."""
        registry = ExecutorRegistry()
        with self.assertRaises(ExecutorValidationError):
            registry.register({"id": "test.bad", "name": "Bad"})  # missing required fields

    def test_snapshot_empty_registry(self):
        """Empty registry produces the expected empty-surface snapshot."""
        registry = ExecutorRegistry()
        snapshot = _registry_as_dict(registry)
        self.assertEqual(snapshot["list"], [])
        self.assertEqual(snapshot["conflicts"], [])
        self.assertEqual(snapshot["as_mapping_keys"], [])

    def test_snapshot_single_executor(self):
        """One executor — no conflicts, basic surface correct."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("editorial.shots", priority=30))
        snapshot = _registry_as_dict(registry)

        self.assertEqual(len(snapshot["list"]), 1)
        self.assertEqual(snapshot["list"][0]["id"], "editorial.shots")
        self.assertEqual(snapshot["list_built_in"], ["editorial.shots"])
        self.assertEqual(snapshot["list_external"], [])
        self.assertEqual(snapshot["conflicts"], [])
        self.assertEqual(snapshot["as_mapping_keys"], ["editorial.shots"])

    def test_snapshot_multi_executor_with_kind_filtering(self):
        """Multiple executors across kinds — list() filtering works."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("editorial.shots", kind="built_in", priority=30))
        registry.register(_make_executor("editorial.render", kind="built_in", priority=30))
        registry.register(_make_executor("external.upload", kind="external", priority=20))
        snapshot = _registry_as_dict(registry)

        self.assertEqual(len(snapshot["list"]), 3)
        self.assertEqual(snapshot["list_built_in"], ["editorial.render", "editorial.shots"])
        self.assertEqual(snapshot["list_external"], ["external.upload"])
        self.assertEqual(snapshot["conflicts"], [])

    def test_snapshot_with_conflicts(self):
        """Two definitions for the same id — conflicts() reports the shadowed one."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("editorial.shots", version="1.0.0", priority=30))
        registry.register(_make_executor("editorial.shots", version="2.0.0", priority=10))
        snapshot = _registry_as_dict(registry)

        # Winner is the higher-priority (lower number)
        self.assertEqual(len(snapshot["list"]), 1)
        self.assertEqual(snapshot["list"][0]["version"], "2.0.0")

        self.assertEqual(len(snapshot["conflicts"]), 1)
        self.assertEqual(snapshot["conflicts"][0]["key"], "editorial.shots")
        self.assertEqual(snapshot["conflicts"][0]["winner_id"], "editorial.shots")
        self.assertEqual(len(snapshot["conflicts"][0]["shadowed_ids"]), 1)
        self.assertEqual(snapshot["conflicts"][0]["shadowed_ids"][0], "editorial.shots")

    def test_get_resolves_winner(self):
        """get() returns highest-priority definition."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("editorial.shots", version="1.0.0", priority=30))
        registry.register(_make_executor("editorial.shots", version="2.0.0", priority=10))

        winner = registry.get("editorial.shots")
        self.assertEqual(winner.version, "2.0.0")
        self.assertEqual(winner.metadata["priority"], 10)

    def test_get_unknown_raises_keyerror(self):
        """get() raises KeyError for unknown ids."""
        registry = ExecutorRegistry()
        with self.assertRaises(KeyError):
            registry.get("nonexistent.exec")

    def test_list_invalid_kind_raises(self):
        """list() raises for invalid kind values."""
        registry = ExecutorRegistry()
        with self.assertRaises(ExecutorRegistryError):
            registry.list(kind="bogus")

    def test_as_mapping_returns_winners(self):
        """as_mapping() returns the winning definition for each id."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("a.exec", priority=30))
        registry.register(_make_executor("a.exec", priority=10))
        registry.register(_make_executor("b.exec", priority=20))

        mp = registry.as_mapping()
        self.assertEqual(mp["a.exec"].metadata["priority"], 10)
        self.assertEqual(mp["b.exec"].metadata["priority"], 20)

    def test_validate_all_passes_on_clean_registry(self):
        """validate_all() succeeds when graph references are consistent."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("a.exec", priority=30))
        registry.register(_make_executor("b.exec", priority=20))
        result = registry.validate_all()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_validate_all_detects_missing_dependency(self):
        """validate_all() raises when graph references an unknown executor."""
        registry = ExecutorRegistry()
        registry.register(_make_executor(
            "a.exec",
            graph=GraphMetadata(depends_on=("unknown.exec",)),
            priority=30,
        ))
        with self.assertRaises(ExecutorRegistryError):
            registry.validate_all()

    def test_validate_all_detects_self_dependency(self):
        """validate_all() raises when executor depends on itself."""
        registry = ExecutorRegistry()
        registry.register(_make_executor(
            "a.exec",
            graph=GraphMetadata(depends_on=("a.exec",)),
            priority=30,
        ))
        with self.assertRaises(ExecutorRegistryError):
            registry.validate_all()

    def test_conflicts_empty_when_no_overlap(self):
        """conflicts() returns empty when no ids share keys."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("a.exec", priority=30))
        registry.register(_make_executor("b.exec", priority=20))
        self.assertEqual(registry.conflicts(), ())

    def test_to_json_serializes(self):
        """to_json() produces valid JSON."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("test.exec", priority=30))
        json_str = registry.to_json()
        data = json.loads(json_str)
        self.assertIn("executors", data)
        self.assertEqual(len(data["executors"]), 1)
        self.assertEqual(data["executors"][0]["id"], "test.exec")

    def test_to_dict_respects_kind_filter(self):
        """to_dict() filters by kind when requested."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("a.exec", kind="built_in", priority=30))
        registry.register(_make_executor("b.exec", kind="external", priority=20))
        data = registry.to_dict(kind="built_in")
        self.assertEqual(len(data["executors"]), 1)
        self.assertEqual(data["executors"][0]["id"], "a.exec")

    def test_iter_all_yields_all_including_shadowed(self):
        """_iter_all() yields both winner and shadowed definitions."""
        registry = ExecutorRegistry()
        registry.register(_make_executor("a.exec", version="1.0.0", priority=30))
        registry.register(_make_executor("a.exec", version="2.0.0", priority=10))
        all_defs = list(registry._iter_all())
        self.assertEqual(len(all_defs), 2)
        versions = {d.version for d in all_defs}
        self.assertEqual(versions, {"1.0.0", "2.0.0"})


if __name__ == "__main__":
    unittest.main()
