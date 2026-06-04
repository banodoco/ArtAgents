from __future__ import annotations

import argparse
import os
import unittest
from unittest.mock import patch

from astrid.contracts.errors import AstridError
from astrid.core.cli_choices import StaticChoices
from astrid.core.orchestrator import cli as orchestrator_cli


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"missing subparser {name!r}")


class OrchestratorCliErrorEnvelopeTest(unittest.TestCase):
    def test_main_raises_astrid_error_for_registry_load_failure(self) -> None:
        with patch.object(orchestrator_cli, "load_default_registry", side_effect=ValueError("boom")):
            with self.assertRaises(AstridError) as excinfo:
                orchestrator_cli.main(["list"])
        self.assertEqual(str(excinfo.exception), "boom")

    def test_list_kind_uses_static_choices_wrapper(self) -> None:
        parser = orchestrator_cli.build_parser()
        list_parser = _subparser(parser, "list")
        kind_action = next(action for action in list_parser._actions if action.dest == "kind")

        self.assertIsInstance(kind_action.choices, StaticChoices)
        self.assertEqual(kind_action.choices.valid_options, ("built_in", "external"))

    def test_run_uses_gateway_resolved_project_without_rejecting_out(self) -> None:
        import types
        from pathlib import Path

        captured: dict[str, object] = {}

        def _capture(request, registry):
            captured["request"] = request
            return types.SimpleNamespace(
                planned_commands=(),
                command=(),
                errors=(),
                returncode=0,
            )

        args = argparse.Namespace(
            orchestrator_id="test.command",
            out=str(Path.cwd() / "tmp-orch-out"),
            project=None,
            input=[],
            brief=None,
            orchestrator_args=(),
            dry_run=False,
            python_exec=None,
            verbose=False,
        )

        with patch.dict(os.environ, {"ASTRID_GATEWAY_RESOLVED_PROJECT": "demo"}, clear=False), \
             patch.object(orchestrator_cli, "_require_qualified_id"), \
             patch("astrid.core.orchestrator.runner.run_orchestrator", side_effect=_capture):
            rc = orchestrator_cli._cmd_run(args, registry=object())

        request = captured["request"]
        self.assertEqual(rc, 0)
        self.assertEqual(request.project, "demo")
        self.assertTrue(request.project_was_auto_resolved)


if __name__ == "__main__":
    unittest.main()
