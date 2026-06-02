from __future__ import annotations

import argparse
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


if __name__ == "__main__":
    unittest.main()
