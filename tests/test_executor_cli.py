"""Tests for executor UUID mode and handoff metadata — m3.5 T15.

Proves:
1. UUID mode skips non-producing runs successfully (returns 0 when
   hype.timeline.json is absent).
2. Timeline-producing UUID runs emit handoff metadata without calling
   SupabaseDataProvider.save_timeline().
3. _emit_uuid_handoff_metadata produces valid JSON with all required fields.
4. _push_run_to_supabase is fully removed (no remaining references).
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from astrid.contracts.errors import AstridError
from astrid.core.cli_choices import StaticChoices
from tests.helpers.cli_runner import run_cli

ROOT = Path(__file__).resolve().parents[1]


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"missing subparser {name!r}")


class ExecutorUUIDHandoffTest(unittest.TestCase):
    """Prove UUID-mode handoff metadata emission."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="exec-uuid-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_emit_uuid_handoff_metadata_skip_when_no_timeline(self):
        """Non-producing runs: hype.timeline.json absent → returns 0, logs to stderr."""
        from astrid.core.executor.cli import _emit_uuid_handoff_metadata

        out_dir = self.tmp_dir / "empty-out"
        out_dir.mkdir(parents=True, exist_ok=True)

        # No hype.timeline.json in out_dir.
        rc = _emit_uuid_handoff_metadata(
            project_id="00000000-0000-0000-0000-000000000001",
            timeline_id="00000000-0000-0000-0000-000000000002",
            out_dir=out_dir,
        )
        self.assertEqual(rc, 0, "non-producing UUID runs should return 0")

    def test_emit_uuid_handoff_metadata_produces_valid_json(self):
        """Timeline-producing UUID runs emit valid bridge JSON."""
        from astrid.core.executor.cli import _emit_uuid_handoff_metadata

        out_dir = self.tmp_dir / "producing-out"
        out_dir.mkdir(parents=True, exist_ok=True)
        timeline_path = out_dir / "hype.timeline.json"
        timeline_path.write_text('{"theme":"test","clips":[]}', encoding="utf-8")

        result = run_cli(
            lambda _: _emit_uuid_handoff_metadata(
                project_id="11111111-1111-1111-1111-111111111111",
                timeline_id="22222222-2222-2222-2222-222222222222",
                out_dir=out_dir,
            ),
            [],
        )

        rc = result.exit_code
        self.assertEqual(rc, 0)
        output = result.stdout.strip()
        handoff = json.loads(output)

        # Verify required fields.
        self.assertEqual(handoff["bridge"], "executor-uuid-mode")
        self.assertEqual(handoff["schema_version"], 1)
        self.assertEqual(handoff["project_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(handoff["timeline_id"], "22222222-2222-2222-2222-222222222222")
        self.assertIn("out_dir", handoff)
        self.assertIn("timeline_path", handoff)
        self.assertIn("note", handoff)
        self.assertIn("m6", handoff["note"].lower())
        self.assertIn("replay", handoff["note"].lower())
        self.assertIn("emitted_at", handoff)

    def test_push_run_to_supabase_is_removed(self):
        """_push_run_to_supabase must not exist in cli.py."""
        from astrid.core.executor import cli as executor_cli

        self.assertFalse(
            hasattr(executor_cli, "_push_run_to_supabase"),
            "_push_run_to_supabase must be removed from executor/cli.py",
        )

    def test_no_supabase_save_timeline_call_in_uuid_path(self):
        """UUID-mode execution path must not call SupabaseDataProvider.save_timeline()."""
        import astrid.core.executor.cli as cli_mod

        source = Path(cli_mod.__file__).read_text(encoding="utf-8")
        # Check for actual calls to .save_timeline(), not just mentions in
        # help text, comments, or docstrings.
        lines = source.splitlines()
        in_docstring = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Track triple-quoted docstrings (simple state machine).
            if stripped.startswith('"""') or stripped.endswith('"""'):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # Skip comments.
            if stripped.startswith("#"):
                continue
            if ".save_timeline(" in stripped:
                self.fail(
                    f"SupabaseDataProvider.save_timeline() call found at line {i}: {stripped}"
                )

    def test_project_uuid_or_none_rejects_slugs(self):
        """_project_uuid_or_none returns None for non-UUID values like slugs."""
        from astrid.core.executor.cli import _project_uuid_or_none

        self.assertIsNone(_project_uuid_or_none(None))
        self.assertIsNone(_project_uuid_or_none(""))
        self.assertIsNone(_project_uuid_or_none("my-slug"))
        self.assertIsNone(_project_uuid_or_none("not-a-uuid"))

        # Valid UUIDs.
        self.assertEqual(
            _project_uuid_or_none("12345678-1234-1234-1234-123456789abc"),
            "12345678-1234-1234-1234-123456789abc",
        )

    def test_main_raises_astrid_error_for_registry_load_failure(self):
        from unittest.mock import patch
        import astrid.core.executor.cli as executor_cli

        with patch.object(executor_cli, "load_default_registry", side_effect=ValueError("boom")):
            with self.assertRaises(AstridError) as excinfo:
                executor_cli.main(["list"])
        self.assertEqual(str(excinfo.exception), "boom")

    def test_list_kind_uses_static_choices_wrapper(self):
        import astrid.core.executor.cli as executor_cli

        parser = executor_cli.build_parser()
        list_parser = _subparser(parser, "list")
        kind_action = next(action for action in list_parser._actions if action.dest == "kind")

        self.assertIsInstance(kind_action.choices, StaticChoices)
        self.assertEqual(kind_action.choices.valid_options, ("built_in", "external"))


if __name__ == "__main__":
    unittest.main()


class ExecutorRunStdioRoutingTest(unittest.TestCase):
    """T1: executor run routes command echo to stderr; --json suppresses it."""

    def _make_run_parser(self):
        import astrid.core.executor.cli as cli_mod
        return cli_mod

    def test_run_subparser_has_json_flag(self):
        """run subparser must accept --json flag."""
        import astrid.core.executor.cli as cli_mod
        import inspect
        src = inspect.getsource(cli_mod)
        self.assertIn('run_parser.add_argument(\"--json\"', src)

    def _run_cmd_run(self, command, payload, use_json):
        import io, sys
        from unittest.mock import MagicMock, patch
        import astrid.core.executor.cli as cli_mod
        import astrid.core.executor.runner as runner_mod

        fake_result = MagicMock()
        fake_result.missing_binaries = []
        fake_result.skipped = False
        fake_result.command = command
        fake_result.payload = payload
        fake_result.returncode = 0

        fake_args = MagicMock()
        fake_args.executor_id = "some.executor"
        fake_args.project = None
        fake_args.dry_run = False
        fake_args.json = use_json

        fake_registry = MagicMock()

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(runner_mod, "run_executor", return_value=fake_result), \
             patch("astrid.core.executor.cli._reject_run_passthrough"), \
             patch("astrid.core.executor.cli._require_qualified_id"), \
             patch("astrid.core.executor.cli._project_uuid_or_none", return_value=None), \
             patch("astrid.core.executor.cli._executor_needs_out", return_value=False), \
             patch("astrid.core.executor.cli._run_inputs", return_value={}), \
             patch.object(sys, "stdout", stdout_buf), \
             patch.object(sys, "stderr", stderr_buf):
            cli_mod._cmd_run(fake_args, fake_registry)

        return stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_run_command_echo_goes_to_stderr(self):
        """result.command echo must land on stderr, not stdout."""
        stdout, stderr = self._run_cmd_run(command=["echo", "hello"], payload=None, use_json=False)
        self.assertNotIn("echo hello", stdout)
        self.assertIn("echo hello", stderr)

    def test_run_json_flag_suppresses_command_echo(self):
        """--json flag must suppress the command echo entirely (no stderr echo)."""
        from unittest.mock import MagicMock
        stdout, stderr = self._run_cmd_run(
            command=["echo", "hello"], payload=MagicMock(), use_json=True
        )
        self.assertNotIn("echo hello", stdout)
        self.assertNotIn("echo hello", stderr)


import subprocess


class ExecutorLsListAliasTest(unittest.TestCase):
    """T3: executors ls and executors list resolve to the same handler."""

    def test_ls_and_list_same_handler(self):
        """Both ls and list resolve to _cmd_list in the executor CLI."""
        import sys
        r_ls = subprocess.run(
            [sys.executable, "-m", "astrid", "executors", "ls", "--help"],
            capture_output=True, text=True
        )
        r_list = subprocess.run(
            [sys.executable, "-m", "astrid", "executors", "list", "--help"],
            capture_output=True, text=True
        )
        # Both verbs must show help with --json option (same handler).
        self.assertIn("--json", r_ls.stdout + r_ls.stderr,
                      "executors ls --help should mention --json")
        self.assertIn("--json", r_list.stdout + r_list.stderr,
                      "executors list --help should mention --json")
        # Both produce identical output (same handler registered).
        self.assertEqual(r_ls.stdout, r_list.stdout,
                         "executors ls and list must resolve to the same handler")
