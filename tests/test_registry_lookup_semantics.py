from __future__ import annotations

import unittest

from astrid.core.contracts.schema import CommandSpec
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.schema import ExecutorDefinition
from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec


def _executor_definition(executor_id: str, *, name: str = "Demo") -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        name=name,
        kind="built_in",
        version="1.0.0",
        metadata={"source": "pack", "source_pack": executor_id.split(".", 1)[0]},
    )


def _orchestrator_definition(orchestrator_id: str, *, name: str = "Demo") -> OrchestratorDefinition:
    return OrchestratorDefinition(
        id=orchestrator_id,
        name=name,
        kind="built_in",
        version="1.0.0",
        runtime=RuntimeSpec(kind="command", command=CommandSpec(argv=("echo", "ok"))),
        metadata={"source": "pack", "source_pack": orchestrator_id.split(".", 1)[0]},
    )


class RegistryLookupSemanticsTest(unittest.TestCase):
    def test_executor_registry_lookup_requires_canonical_id(self) -> None:
        registry = ExecutorRegistry()
        registry.register(_executor_definition("builtin.demo"))

        executor = registry.get("builtin.demo")
        assert executor.id == "builtin.demo"
        with self.assertRaises(KeyError):
            registry.get("builtin.legacy_demo")

    def test_orchestrator_registry_lookup_requires_canonical_id(self) -> None:
        registry = OrchestratorRegistry(executor_registry=ExecutorRegistry())
        registry.register(_orchestrator_definition("builtin.demo"))

        orchestrator = registry.get("builtin.demo")
        assert orchestrator.id == "builtin.demo"
        with self.assertRaises(KeyError):
            registry.get("builtin.legacy_demo")


if __name__ == "__main__":
    unittest.main()
