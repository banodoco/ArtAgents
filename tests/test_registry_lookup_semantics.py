from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from astrid.core.pack.alias_resolver import AliasResolver
from astrid.core.contracts.schema import CommandSpec
from astrid.core.execution.executor import cli as executors_cli
from astrid.core.execution.executor.install import ExecutorInstallPlan, ExecutorInstallResult
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.schema import ExecutorDefinition
from astrid.core.execution.orchestrator import cli as orchestrators_cli
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

    def test_executor_cli_paths_use_registry_lookup_for_aliases(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_demo", "builtin.demo")
        registry = ExecutorRegistry(alias_resolver=resolver)
        registry.register(_executor_definition("builtin.demo"))

        inspect_stdout = io.StringIO()
        with contextlib.redirect_stdout(inspect_stdout):
            rc = executors_cli._cmd_inspect(
                argparse.Namespace(
                    executor_id="builtin.legacy_demo",
                    json=True,
                    pack=None,
                    show_overrides=False,
                ),
                registry,
            )
        self.assertEqual(rc, 0)
        inspect_payload = json.loads(inspect_stdout.getvalue())
        self.assertEqual(inspect_payload["id"], "builtin.demo")
        self.assertEqual(
            inspect_payload["_capability"]["aliases"][0]["alias"],
            "builtin.legacy_demo",
        )

        validate_stdout = io.StringIO()
        with contextlib.redirect_stdout(validate_stdout):
            rc = executors_cli._cmd_validate(
                argparse.Namespace(
                    executor_id="builtin.legacy_demo",
                    check_binaries=False,
                ),
                registry,
            )
        self.assertEqual(rc, 0)
        self.assertIn("builtin.legacy_demo: ok", validate_stdout.getvalue())

        install_result = ExecutorInstallResult(
            plan=ExecutorInstallPlan(
                executor_id="builtin.demo",
                kind="built_in",
                environment_path=None,
                python_path=None,
                noop_reason="built-in executors use the host Python environment",
            ),
            dry_run=True,
            returncode=0,
        )
        with patch("astrid.core.execution.executor.install.install_executor", return_value=install_result) as install_mock:
            install_stdout = io.StringIO()
            with contextlib.redirect_stdout(install_stdout):
                rc = executors_cli._cmd_install(
                    argparse.Namespace(
                        executor_id="builtin.legacy_demo",
                        dry_run=True,
                    ),
                    registry,
                )
        self.assertEqual(rc, 0)
        installed_executor = install_mock.call_args.args[0]
        self.assertEqual(installed_executor.id, "builtin.demo")
        self.assertIn("builtin.demo: no install needed", install_stdout.getvalue())

    def test_orchestrator_cli_paths_use_registry_lookup_for_aliases(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("builtin.legacy_demo", "builtin.demo")
        registry = OrchestratorRegistry(
            alias_resolver=resolver,
            executor_registry=ExecutorRegistry(),
        )
        registry.register(_orchestrator_definition("builtin.demo"))

        inspect_stdout = io.StringIO()
        with contextlib.redirect_stdout(inspect_stdout):
            rc = orchestrators_cli._cmd_inspect(
                argparse.Namespace(
                    orchestrator_id="builtin.legacy_demo",
                    json=True,
                    pack=None,
                    show_overrides=False,
                ),
                registry,
            )
        self.assertEqual(rc, 0)
        inspect_payload = json.loads(inspect_stdout.getvalue())
        self.assertEqual(inspect_payload["id"], "builtin.demo")
        self.assertEqual(
            inspect_payload["_capability"]["aliases"][0]["alias"],
            "builtin.legacy_demo",
        )

        validate_stdout = io.StringIO()
        with contextlib.redirect_stdout(validate_stdout):
            rc = orchestrators_cli._cmd_validate(
                argparse.Namespace(orchestrator_id="builtin.legacy_demo"),
                registry,
            )
        self.assertEqual(rc, 0)
        self.assertIn("builtin.legacy_demo: ok", validate_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
