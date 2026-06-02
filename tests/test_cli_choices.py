"""Focused tests for recoverable argparse choice helpers."""

from __future__ import annotations

import io
import sys
import unittest

from astrid.core.cli_choices import (
    AstridArgumentError,
    RecoverableArgumentParser,
    RegistryChoices,
    StaticChoices,
    add_choice_arg,
    add_kind_arg,
)
from astrid.core.pack import ElementKindDescriptor, ElementKindRegistry


class RegistryChoicesTests(unittest.TestCase):
    def test_registry_choices_is_live_against_registry_updates(self) -> None:
        registry = ElementKindRegistry()
        choices = RegistryChoices(catalog="transition", registry=registry)

        self.assertIn("cross-fade", choices)
        self.assertNotIn("wipe", choices)

        registry.register(
            ElementKindDescriptor(catalog="transition", id="wipe", aliases=("hard-cut",))
        )

        self.assertIn("wipe", choices)
        self.assertIn("hard-cut", choices)
        self.assertEqual(choices.valid_options[-1], "wipe")

    def test_static_choices_require_nonempty_values(self) -> None:
        with self.assertRaises(ValueError):
            StaticChoices(())

    def test_registry_choices_sequence_behavior(self) -> None:
        registry = ElementKindRegistry()
        choices = RegistryChoices(catalog="clip", registry=registry)
        self.assertGreater(len(choices), 0)
        self.assertEqual(choices[0], "video")
        self.assertIn("video", list(choices))
        self.assertIn("video", choices)
        self.assertNotIn("bogus", choices)

    def test_static_choices_sequence_behavior(self) -> None:
        choices = StaticChoices(("alpha", "beta", "gamma"), catalog="test")
        self.assertEqual(len(choices), 3)
        self.assertEqual(choices[1], "beta")
        self.assertIn("alpha", list(choices))
        self.assertEqual(choices.valid_options, ("alpha", "beta", "gamma"))
        self.assertEqual(choices.accepted_names, ("alpha", "beta", "gamma"))


class RecoverableArgumentParserTests(unittest.TestCase):
    def test_add_kind_arg_attaches_registry_choices_object(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        action = add_kind_arg(parser, "--kind", catalog="transition", default="cross-fade")

        self.assertIsInstance(action.choices, RegistryChoices)
        self.assertEqual(action.choices.catalog, "transition")
        self.assertIn("cross-fade", parser.format_help())

    def test_add_choice_arg_attaches_static_choices_object(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid projects")
        action = add_choice_arg(
            parser, "--kind", values=("video", "audio"), catalog="project-source"
        )

        self.assertIsInstance(action.choices, StaticChoices)
        self.assertEqual(action.choices.valid_options, ("video", "audio"))
        self.assertIn("video", parser.format_help())

    # ── invalid choice → AstridArgumentError (no SystemExit, no stderr) ──────

    def test_invalid_registry_choice_raises_astrid_argument_error(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", required=True)

        with self.assertRaises(AstridArgumentError) as excinfo:
            parser.parse_args(["--kind", "dissolve"])

        exc = excinfo.exception
        self.assertEqual(exc.argument_name, "--kind")
        self.assertEqual(exc.invalid_value, "dissolve")
        self.assertEqual(exc.catalog, "transition")
        self.assertIn("cross-fade", exc.valid_options)
        self.assertIn("invalid choice", str(exc))

    def test_invalid_static_choice_raises_astrid_argument_error(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid projects")
        add_choice_arg(
            parser,
            "--kind",
            values=("video", "audio"),
            catalog="project-source",
            required=True,
        )

        with self.assertRaises(AstridArgumentError) as excinfo:
            parser.parse_args(["--kind", "text"])

        exc = excinfo.exception
        self.assertEqual(exc.argument_name, "--kind")
        self.assertEqual(exc.invalid_value, "text")
        self.assertEqual(exc.valid_options, ("video", "audio"))
        self.assertEqual(exc.catalog, "project-source")

    def test_invalid_registry_choice_suppresses_raw_stderr(self) -> None:
        """Prove no raw argparse stderr is written when AstridArgumentError is raised."""
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", required=True)

        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            with self.assertRaises(AstridArgumentError):
                parser.parse_args(["--kind", "dissolve"])
        finally:
            sys.stderr = old_stderr

        self.assertEqual(captured.getvalue(), "")

    # ── crossfade-specific recovery metadata ─────────────────────────────────

    def test_crossfade_typo_produces_structured_recovery_metadata(self) -> None:
        """When only ``cross-fade`` is canonical (no ``crossfade`` alias),
        passing ``--kind crossfade`` must raise AstridArgumentError whose
        valid_options include ``cross-fade``.

        Uses a fresh registry with only the canonical id, simulating a
        scenario where the alias hasn't been registered.
        """
        # Use a custom catalog so the built-in transition descriptors
        # (which include the crossfade alias) do not interfere.
        registry = ElementKindRegistry()
        registry.register(
            ElementKindDescriptor(catalog="test-effect", id="cross-fade")
        )
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(
            parser,
            "--kind",
            catalog="test-effect",
            registry=registry,
            required=True,
        )

        with self.assertRaises(AstridArgumentError) as excinfo:
            parser.parse_args(["--kind", "crossfade"])

        exc = excinfo.exception
        self.assertEqual(exc.argument_name, "--kind")
        self.assertEqual(exc.invalid_value, "crossfade")
        self.assertEqual(exc.catalog, "test-effect")
        self.assertIn("cross-fade", exc.valid_options)
        self.assertNotIn("crossfade", exc.valid_options)
        self.assertIn("cross-fade", str(exc))
        self.assertIn("invalid choice", str(exc))

    def test_recovery_metadata_contains_all_fields_for_automated_recovery(self) -> None:
        """AstridArgumentError carries every field a recovery command needs."""
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="clip", required=True)

        with self.assertRaises(AstridArgumentError) as excinfo:
            parser.parse_args(["--kind", "bogus"])

        exc = excinfo.exception
        # All metadata fields are non-None/non-empty for automated recovery
        self.assertIsInstance(exc.message, str)
        self.assertGreater(len(exc.message), 0)
        self.assertIsInstance(exc.argument_name, str)
        self.assertGreater(len(exc.argument_name), 0)
        self.assertIsInstance(exc.invalid_value, str)
        self.assertGreater(len(exc.invalid_value), 0)
        self.assertIsInstance(exc.valid_options, tuple)
        self.assertGreater(len(exc.valid_options), 0)
        self.assertIsInstance(exc.catalog, str)
        self.assertGreater(len(exc.catalog), 0)

    # ── help behaviour ───────────────────────────────────────────────────────

    def test_help_flag_produces_system_exit_zero(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", default="cross-fade")

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args(["--help"])

        self.assertEqual(excinfo.exception.code, 0)

    def test_help_output_includes_valid_options(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", default="cross-fade")

        help_text = parser.format_help()
        self.assertIn("--kind", help_text)
        self.assertIn("cross-fade", help_text)

    def test_help_flag_on_required_arg_still_shows_help(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", required=True)

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args(["--help"])

        self.assertEqual(excinfo.exception.code, 0)

    # ── default behaviour ────────────────────────────────────────────────────

    def test_default_value_is_used_when_argument_not_provided(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", default="cross-fade")

        ns = parser.parse_args([])
        self.assertEqual(ns.kind, "cross-fade")

    def test_default_value_does_not_trigger_astrid_argument_error(self) -> None:
        """The default value 'cross-fade' is valid so no error is raised."""
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", default="cross-fade")

        # Should parse without error
        ns = parser.parse_args([])
        self.assertEqual(ns.kind, "cross-fade")

    # ── required behaviour ───────────────────────────────────────────────────

    def test_required_missing_argument_still_produces_system_exit(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", required=True)

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args([])

        self.assertEqual(excinfo.exception.code, 2)

    def test_required_with_valid_value_parses_correctly(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", required=True)

        ns = parser.parse_args(["--kind", "cross-fade"])
        self.assertEqual(ns.kind, "cross-fade")

    # ── non-recoverable errors ───────────────────────────────────────────────

    def test_non_recoverable_parse_errors_still_use_system_exit(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition", required=True)

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args([])

        self.assertEqual(excinfo.exception.code, 2)

    def test_unrecognized_arguments_still_produce_system_exit(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        add_kind_arg(parser, "--kind", catalog="transition")

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args(["--bogus", "value"])

        self.assertEqual(excinfo.exception.code, 2)

    # ── add_kind_arg / add_choice_arg refuse explicit choices ─────────────────

    def test_add_kind_arg_refuses_explicit_choices(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid timelines")
        with self.assertRaises(TypeError):
            add_kind_arg(parser, "--kind", catalog="transition", choices=["a"])

    def test_add_choice_arg_refuses_explicit_choices(self) -> None:
        parser = RecoverableArgumentParser(prog="astrid projects")
        with self.assertRaises(TypeError):
            add_choice_arg(parser, "--kind", values=("x",), choices=["a"])

    # ── interoperability with plain argparse ──────────────────────────────────

    def test_plain_argument_parser_still_uses_system_exit_for_choices(self) -> None:
        import argparse

        parser = argparse.ArgumentParser(prog="astrid timelines")
        parser.add_argument("--kind", choices=("video", "audio"), required=True)

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args(["--kind", "text"])

        self.assertEqual(excinfo.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
