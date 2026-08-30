"""Library-surface tests for the surviving pack CLI module (astrid.core.pack.cli).

Proves:
1. packs_cli main/build_parser/cmd_new still work as library functions
2. inspect output surfaces pack permissions and v1 trust metadata
3. agent-index entry assembly carries permissions/trust
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core.cli_choices import StaticChoices
from astrid.core.pack import cli as packs_cli
from astrid.core.pack.validate import extract_trust_summary
from astrid.core.pack.agent_index import _assemble_pack_entry
from astrid.core.pack.store import InstallRecord


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXAMPLES_MINIMAL = _REPO_ROOT / "examples" / "packs" / "minimal"


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"missing subparser {name!r}")


def _chdir_context(path: Path):
    """Context manager to temporarily change CWD. Returns the original CWD."""
    return _ChdirContext(path)


class _ChdirContext:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._original: str | None = None

    def __enter__(self) -> Path:
        self._original = os.getcwd()
        os.chdir(str(self._path))
        return self._path

    def __exit__(self, *args: object) -> None:
        if self._original is not None:
            os.chdir(self._original)


class ScratchPackFixture:
    """Provides a temporary directory that gets cleaned up after the test."""

    def __init__(self, test_case: unittest.TestCase) -> None:
        self._test_case = test_case
        self._tmp: str | None = None
        self._path: Path | None = None

    def __enter__(self) -> Path:
        self._tmp = tempfile.mkdtemp(prefix="test-packs-cli-")
        self._path = Path(self._tmp)
        return self._path

    def __exit__(self, *args: object) -> None:
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)


class TestScaffoldFixture(unittest.TestCase):
    """Fixture that builds a temp pack via scaffolds, validates it, and checks created file list."""

    EXPECTED_PACK_FILES = {
        "pack.yaml",
        "skill/SKILL.md",
    }
    EXPECTED_PACK_DIRS = {
        "executors",
        "orchestrators",
        "elements",
    }
    EXPECTED_EXECUTOR_FILES = {
        "executor.yaml",
        "run.py",
        "STAGE.md",
    }
    EXPECTED_ORCHESTRATOR_FILES = {
        "orchestrator.yaml",
        "run.py",
        "STAGE.md",
    }

    def _scaffold_pack_in(self, tmp: Path, pack_id: str) -> Path:
        """Scaffold a pack and return its root."""
        with _chdir_context(tmp):
            rc = packs_cli.cmd_new([pack_id])
            if rc != 0:
                raise RuntimeError(f"cmd_new({pack_id}) failed with {rc}")
        return tmp / pack_id

    def test_scaffolded_pack_has_expected_file_list(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack_in(tmp, "test_pack")

            # Check expected files exist
            for fname in self.EXPECTED_PACK_FILES:
                path = pack_dir / fname
                self.assertTrue(
                    path.is_file(),
                    f"Expected {fname} to exist in scaffolded pack",
                )

            # Check expected directories exist
            for dname in self.EXPECTED_PACK_DIRS:
                path = pack_dir / dname
                self.assertTrue(
                    path.is_dir(),
                    f"Expected {dname}/ directory to exist in scaffolded pack",
                )

class TestCLIBackwardCompat(unittest.TestCase):
    """Ensure the CLI modules' internal APIs don't break."""

    def test_packs_cli_main_importable(self) -> None:
        self.assertTrue(callable(packs_cli.main))

    def test_packs_cli_build_parser_works(self) -> None:
        parser = packs_cli.build_parser()
        self.assertIsNotNone(parser)

        # Parse validate
        args = parser.parse_args(["validate", str(_EXAMPLES_MINIMAL)])
        self.assertEqual(args.command, "validate")

        # Parse new
        args = parser.parse_args(["new", "test_pack"])
        self.assertEqual(args.command, "new")
        self.assertEqual(args.pack_id, "test_pack")

    def test_packs_cli_filter_enum_args_use_static_choices_wrappers(self) -> None:
        parser = packs_cli.build_parser()
        list_parser = _subparser(parser, "list")
        status_parser = _subparser(parser, "status")

        for subparser in (list_parser, status_parser):
            for dest in ("status", "visibility"):
                action = next(option for option in subparser._actions if option.dest == dest)
                self.assertIsInstance(action.choices, StaticChoices)

    def test_packs_cli_main_validate_returns_zero(self) -> None:
        exit_code = packs_cli.main(["validate", str(_EXAMPLES_MINIMAL)])
        self.assertEqual(exit_code, 0)

    def test_packs_cli_main_new_rejects_bad_id(self) -> None:
        exit_code = packs_cli.main(["new", "BAD"])
        self.assertNotEqual(exit_code, 0)


class TestInspectPermissionsAndTrust(unittest.TestCase):
    """T10: Verify inspect output surfaces pack permissions and v1 trust metadata
    with disclosure-only/no-sandbox wording."""

    def setUp(self) -> None:
        self._gen_root = _REPO_ROOT / "astrid" / "packs" / "generation"
        self._trust = extract_trust_summary(str(self._gen_root))
        self._manifest = {
            "id": "generation",
            "name": "Astrid Generation",
            "version": "1.0.0",
            "description": "Test pack",
            "agent": {"purpose": "Generate images and videos"},
        }
        self._record = InstallRecord(
            pack_id="generation",
            name="Astrid Generation",
            version="1.0.0",
            schema_version=1,
            source_path=str(self._gen_root),
            installed_at="2025-01-01T00:00:00Z",
            revision="generation",
            install_root=str(self._gen_root),
        )

    # ── _build_full_inspect JSON structure ──────────────────────────

    def test_full_inspect_json_has_permissions(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        self.assertIn("permissions", data)
        self.assertIsInstance(data["permissions"], list)
        self.assertGreater(len(data["permissions"]), 0)
        for p in data["permissions"]:
            self.assertIsInstance(p, dict)
            self.assertIn("id", p)
            self.assertIn("reason", p)

    def test_full_inspect_json_has_permission_ids(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        self.assertIn("permission_ids", data)
        self.assertIsInstance(data["permission_ids"], list)
        self.assertGreater(len(data["permission_ids"]), 0)
        for pid in data["permission_ids"]:
            self.assertIsInstance(pid, str)

    def test_full_inspect_json_has_trust_block(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        self.assertIn("trust", data)
        trust = data["trust"]
        self.assertIsInstance(trust, dict)
        self.assertEqual(trust.get("sandbox"), "none")
        self.assertEqual(trust.get("runs_with_user_process_permissions"), True)
        self.assertEqual(trust.get("permission_enforcement"), "disclosure_only")

    def test_full_inspect_json_permission_ids_match_permissions(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        perm_ids = {p["id"] for p in data["permissions"]}
        list_ids = set(data["permission_ids"])
        self.assertEqual(perm_ids, list_ids)

    # ── _print_full_inspect plain-text output ────────────────────────

    def test_full_inspect_plain_has_permissions_section(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_full_inspect(data)
        out = buf.getvalue()
        self.assertIn("Permissions:", out)
        self.assertIn("subprocess", out)

    def test_full_inspect_plain_has_permission_ids_line(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_full_inspect(data)
        out = buf.getvalue()
        self.assertIn("Permission IDs:", out)
        self.assertIn("subprocess", out)

    def test_full_inspect_plain_has_trust_section(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_full_inspect(data)
        out = buf.getvalue()
        self.assertIn("Trust:", out)
        self.assertIn("sandbox: none", out)
        self.assertIn("runs_with_user_process_permissions: True", out)
        self.assertIn("permission_enforcement: disclosure_only", out)

    def test_full_inspect_plain_has_disclosure_only_notice(self) -> None:
        data = packs_cli._build_full_inspect(self._record, self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_full_inspect(data)
        out = buf.getvalue()
        self.assertIn("disclosure-only", out)
        self.assertIn("No sandboxing", out)

    def test_full_inspect_plain_empty_permissions(self) -> None:
        empty_trust = dict(self._trust, permissions=[], permission_ids=[])
        data = packs_cli._build_full_inspect(self._record, self._manifest, empty_trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_full_inspect(data)
        out = buf.getvalue()
        self.assertNotIn("Permissions:", out)

    # ── _build_agent_view JSON structure ─────────────────────────────

    def test_agent_view_json_has_permissions(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        self.assertIn("permissions", view)
        self.assertIsInstance(view["permissions"], list)
        self.assertGreater(len(view["permissions"]), 0)
        for p in view["permissions"]:
            self.assertIsInstance(p, dict)
            self.assertIn("id", p)
            self.assertIn("reason", p)

    def test_agent_view_json_has_permission_ids(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        self.assertIn("permission_ids", view)
        self.assertIsInstance(view["permission_ids"], list)
        self.assertGreater(len(view["permission_ids"]), 0)

    def test_agent_view_json_has_trust_block(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        self.assertIn("trust", view)
        trust = view["trust"]
        self.assertIsInstance(trust, dict)
        self.assertEqual(trust.get("sandbox"), "none")
        self.assertEqual(trust.get("runs_with_user_process_permissions"), True)
        self.assertEqual(trust.get("permission_enforcement"), "disclosure_only")

    def test_agent_view_json_permission_ids_match_permissions(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        perm_ids = {p["id"] for p in view["permissions"]}
        list_ids = set(view["permission_ids"])
        self.assertEqual(perm_ids, list_ids)

    # ── _print_agent_view plain-text output ──────────────────────────

    def test_agent_view_plain_has_permissions_section(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_agent_view(view)
        out = buf.getvalue()
        self.assertIn("Permissions:", out)
        self.assertIn("subprocess", out)

    def test_agent_view_plain_has_permission_ids_line(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_agent_view(view)
        out = buf.getvalue()
        self.assertIn("Permission IDs:", out)

    def test_agent_view_plain_has_trust_section(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_agent_view(view)
        out = buf.getvalue()
        self.assertIn("Trust:", out)
        self.assertIn("sandbox: none", out)
        self.assertIn("permission_enforcement: disclosure_only", out)

    def test_agent_view_plain_has_disclosure_only_notice(self) -> None:
        view = packs_cli._build_agent_view(self._manifest, self._trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_agent_view(view)
        out = buf.getvalue()
        self.assertIn("disclosure-only", out)
        self.assertIn("No sandboxing", out)

    def test_agent_view_plain_empty_permissions(self) -> None:
        empty_trust = dict(self._trust, permissions=[], permission_ids=[])
        view = packs_cli._build_agent_view(self._manifest, empty_trust)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packs_cli._print_agent_view(view)
        out = buf.getvalue()
        self.assertNotIn("Permissions:", out)


class TestAgentIndexPermissionsAndTrust(unittest.TestCase):
    """T10: Verify agent-index output surfaces pack permissions and v1 trust
    metadata."""

    def setUp(self) -> None:
        self._gen_root = _REPO_ROOT / "astrid" / "packs" / "generation"
        self._trust = extract_trust_summary(str(self._gen_root))
        self._manifest = {
            "id": "generation",
            "name": "Astrid Generation",
            "version": "1.0.0",
            "description": "Test pack",
            "agent": {"purpose": "Generate images and videos"},
        }

    def test_assemble_pack_entry_has_permissions(self) -> None:
        entry = _assemble_pack_entry(self._gen_root, "generation", self._manifest, self._trust)
        self.assertIn("permissions", entry)
        self.assertIsInstance(entry["permissions"], list)
        self.assertGreater(len(entry["permissions"]), 0)
        for p in entry["permissions"]:
            self.assertIsInstance(p, dict)
            self.assertIn("id", p)
            self.assertIn("reason", p)

    def test_assemble_pack_entry_has_permission_ids(self) -> None:
        entry = _assemble_pack_entry(self._gen_root, "generation", self._manifest, self._trust)
        self.assertIn("permission_ids", entry)
        self.assertIsInstance(entry["permission_ids"], list)
        self.assertGreater(len(entry["permission_ids"]), 0)

    def test_assemble_pack_entry_has_trust_block(self) -> None:
        entry = _assemble_pack_entry(self._gen_root, "generation", self._manifest, self._trust)
        self.assertIn("trust", entry)
        trust = entry["trust"]
        self.assertIsInstance(trust, dict)
        self.assertEqual(trust.get("sandbox"), "none")
        self.assertEqual(trust.get("runs_with_user_process_permissions"), True)
        self.assertEqual(trust.get("permission_enforcement"), "disclosure_only")

    def test_assemble_pack_entry_permission_ids_match_permissions(self) -> None:
        entry = _assemble_pack_entry(self._gen_root, "generation", self._manifest, self._trust)
        perm_ids = {p["id"] for p in entry["permissions"]}
        list_ids = set(entry["permission_ids"])
        self.assertEqual(perm_ids, list_ids)

    def test_assemble_pack_entry_empty_permissions_still_has_trust(self) -> None:
        empty_trust = dict(self._trust, permissions=[], permission_ids=[])
        entry = _assemble_pack_entry(self._gen_root, "generation", self._manifest, empty_trust)
        self.assertEqual(entry.get("permissions"), [])
        self.assertEqual(entry.get("permission_ids"), [])
        self.assertIn("trust", entry)
        self.assertEqual(entry["trust"]["sandbox"], "none")


class TestAgentIndexAndInspectWiring(unittest.TestCase):
    """The surviving agent-index and manifest inspect surfaces are importable."""

    def test_extract_trust_summary_bound_in_cli_module(self) -> None:
        # The installed-inspect path calls extract_trust_summary; it must be
        # importable from the cli module (was previously unbound -> NameError).
        self.assertTrue(callable(packs_cli.extract_trust_summary))


if __name__ == "__main__":
    unittest.main()
