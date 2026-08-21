from __future__ import annotations

import tempfile
import unittest

from astrid.core.pack.alias_resolver import AliasResolver
from astrid.core.contracts.schema import CommandSpec
from astrid.core.execution.executor.install import ExecutorInstallPlan, ExecutorInstallResult
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.schema import ExecutorDefinition
from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.pack.override import OverrideStore


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
    def test_executor_registry_get_resolves_alias_and_applies_override_by_canonical_id(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_shots", "editorial.shots")
        with tempfile.TemporaryDirectory() as tmp:
            override_store = OverrideStore(project_root=tmp)
            override_store.set_override("executor", "editorial.shots", "local.shots")
            registry = ExecutorRegistry(alias_resolver=resolver, override_store=override_store)
            registry.register(_executor_definition("editorial.shots", name="Shots"))
            registry.register(_executor_definition("local.shots", name="Local Shots"))

            result = registry.get("builtin.legacy_shots")

        self.assertEqual(result.id, "local.shots")
        self.assertEqual(result.name, "Local Shots")
        self.assertNotIn("override_target", result.metadata)

    def test_executor_registry_get_reports_missing_alias_target(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_shots", "builtin.missing")
        registry = ExecutorRegistry(alias_resolver=resolver)

        with self.assertRaisesRegex(
            KeyError,
            r"alias 'builtin\.legacy_shots' points to missing executor 'builtin\.missing'",
        ):
            registry.get("builtin.legacy_shots")

    def test_orchestrator_registry_get_resolves_alias_and_applies_override_by_canonical_id(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_hype", "video_editing.hype")
        with tempfile.TemporaryDirectory() as tmp:
            override_store = OverrideStore(project_root=tmp)
            override_store.set_override("orchestrator", "video_editing.hype", "local.hype")
            registry = OrchestratorRegistry(alias_resolver=resolver, override_store=override_store)
            registry.register(_orchestrator_definition("video_editing.hype", name="Hype"))
            registry.register(_orchestrator_definition("local.hype", name="Local Hype"))

            result = registry.get("builtin.legacy_hype")

        self.assertEqual(result.id, "local.hype")
        self.assertEqual(result.name, "Local Hype")
        self.assertNotIn("override_target", result.metadata)

    def test_orchestrator_registry_get_reports_missing_alias_target(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_hype", "builtin.missing")
        registry = OrchestratorRegistry(alias_resolver=resolver)

        with self.assertRaisesRegex(
            KeyError,
            r"alias 'builtin\.legacy_hype' points to missing orchestrator 'builtin\.missing'",
        ):
            registry.get("builtin.legacy_hype")

    def test_registry_lookup_resolves_aliases(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_demo", "builtin.demo")
        registry = ExecutorRegistry(alias_resolver=resolver)
        registry.register(_executor_definition("builtin.demo"))

        executor = registry.get("builtin.legacy_demo")
        assert executor.id == "builtin.demo"
        assert resolver.is_alias("builtin.legacy_demo")
        assert resolver.resolve("builtin.legacy_demo") == "builtin.demo"

    def test_orchestrator_registry_lookup_resolves_aliases(self) -> None:
        """Orchestrator lookup resolves aliases through the registry.

        The ``orchestrators`` CLI verb (``orchestrators_cli``) was retired with
        the legacy runtime; alias resolution now lives in the
        ``OrchestratorRegistry`` itself — the same lookup path the retired CLI
        exercised.
        """
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_demo", "builtin.demo")
        registry = OrchestratorRegistry(
            alias_resolver=resolver,
            executor_registry=ExecutorRegistry(),
        )
        registry.register(_orchestrator_definition("builtin.demo"))

        orchestrator = registry.get("builtin.legacy_demo")
        assert orchestrator.id == "builtin.demo"
        assert resolver.is_alias("builtin.legacy_demo")
        assert resolver.resolve("builtin.legacy_demo") == "builtin.demo"


if __name__ == "__main__":
    unittest.main()
