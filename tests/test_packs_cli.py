"""CLI tests for packs validate, packs new, executors new, and orchestrators new.

Proves:
1. packs validate examples/packs/minimal exits 0
2. A deliberately broken pack fixture fails with file-specific error and non-zero exit
3. packs new + executors new + orchestrators new creates a pack that passes validate
4. Scaffolds reject invalid ids, missing targets, and overwrites
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from astrid.packs import cli as packs_cli
from astrid.packs.validate import validate_pack


_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_MINIMAL = _REPO_ROOT / "examples" / "packs" / "minimal"
_EXAMPLE_PACKS = {
    "minimal": _EXAMPLES_MINIMAL,
    "file_summarizer": _REPO_ROOT / "examples" / "packs" / "file_summarizer",
    "text_digest": _REPO_ROOT / "examples" / "packs" / "text_digest",
    "text_review": _REPO_ROOT / "examples" / "packs" / "text_review",
}


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


def _astrid_env() -> dict:
    """Return an environment dict with PYTHONPATH set so astrid is importable."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    repo = str(_REPO_ROOT)
    env["PYTHONPATH"] = f"{repo}{os.pathsep}{existing}" if existing else repo
    return env


def _run_packs(*args: str, cwd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run a packs subcommand in the given CWD with astrid importable."""
    return subprocess.run(
        [sys.executable, "-m", "astrid", "packs", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_astrid_env(),
        check=check,
    )


def _run_executors(*args: str, cwd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run an executors subcommand in the given CWD with astrid importable."""
    return subprocess.run(
        [sys.executable, "-m", "astrid", "executors", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_astrid_env(),
        check=check,
    )


def _run_orchestrators(*args: str, cwd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run an orchestrators subcommand in the given CWD with astrid importable."""
    return subprocess.run(
        [sys.executable, "-m", "astrid", "orchestrators", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_astrid_env(),
        check=check,
    )


class TestPacksValidateCLI(unittest.TestCase):
    """Prove: packs validate examples/packs/minimal exits 0."""

    def test_validate_minimal_example_exits_zero(self) -> None:
        self.assertTrue(
            _EXAMPLES_MINIMAL.is_dir(),
            f"examples/packs/minimal must exist at {_EXAMPLES_MINIMAL}",
        )
        result = _run_packs("validate", str(_EXAMPLES_MINIMAL), cwd=str(_REPO_ROOT))
        self.assertEqual(
            result.returncode, 0,
            f"validate should exit 0 but got {result.returncode}; stderr: {result.stderr!r}",
        )
        self.assertIn("valid:", result.stdout)

    def test_validate_minimal_example_with_warnings_flag_exits_zero(self) -> None:
        result = _run_packs(
            "validate", str(_EXAMPLES_MINIMAL), "--warnings",
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0)

    def test_validate_examples_only_packs_by_explicit_path(self) -> None:
        for pack_id, pack_root in _EXAMPLE_PACKS.items():
            with self.subTest(pack_id=pack_id):
                self.assertTrue(pack_root.is_dir(), f"example pack missing: {pack_root}")
                result = _run_packs("validate", str(pack_root), cwd=str(_REPO_ROOT))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("valid:", result.stdout)

    def test_packs_list_inspect_and_status_subcommands(self) -> None:
        list_result = _run_packs("list", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(list_result.returncode, 0, list_result.stderr)
        listed = json.loads(list_result.stdout)
        self.assertIn("groups", listed)
        self.assertIn("builtin", {pack["id"] for pack in listed["packs"]})
        builtin = next(pack for pack in listed["packs"] if pack["id"] == "builtin")
        self.assertIn("content", builtin)
        self.assertIn("agent", builtin)
        self.assertEqual(builtin["status"], "deprecated")
        self.assertEqual(builtin["visibility"], "visible")
        self.assertEqual(builtin["taxonomy"]["domain"], "system")
        self.assertEqual(builtin["origin"], "builtin")
        self.assertTrue(any(group["value"] == "system" for group in listed["groups"]))

        inspect_result = _run_packs("inspect", "builtin", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
        inspected = json.loads(inspect_result.stdout)
        self.assertEqual(inspected["id"], "builtin")
        self.assertEqual(inspected["taxonomy"]["domain"], "system")
        self.assertEqual(inspected["origin"], "builtin")

        status_result = _run_packs("status", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        status = json.loads(status_result.stdout)
        self.assertIn("groups", status)
        self.assertIn("validation", status["packs"][0])
        self.assertTrue(all("taxonomy" in pack for pack in status["packs"]))

    def test_packs_taxonomy_plain_text_and_filters(self) -> None:
        list_result = _run_packs("list", "--domain", "system", cwd=str(_REPO_ROOT))
        self.assertEqual(list_result.returncode, 0, list_result.stderr)
        self.assertIn("taxonomy: domain=system", list_result.stdout)
        self.assertIn("builtin\t", list_result.stdout)
        self.assertNotIn("external\t", list_result.stdout)

        status_result = _run_packs("status", "--domain", "system", cwd=str(_REPO_ROOT))
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        self.assertIn("taxonomy: domain=system", status_result.stdout)
        self.assertIn("builtin\tdeprecated\tvisible", status_result.stdout)

        inspect_result = _run_packs("inspect", "builtin", cwd=str(_REPO_ROOT))
        self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
        self.assertIn("taxonomy:", inspect_result.stdout)
        self.assertIn("  origin: builtin", inspect_result.stdout)
        self.assertIn("  domain: system", inspect_result.stdout)

    def test_category_filter_remains_metadata_only(self) -> None:
        domain_result = _run_packs("list", "--domain", "system", cwd=str(_REPO_ROOT))
        self.assertEqual(domain_result.returncode, 0, domain_result.stderr)
        self.assertIn("builtin\t", domain_result.stdout)

        category_result = _run_packs("list", "--category", "system", cwd=str(_REPO_ROOT))
        self.assertEqual(category_result.returncode, 0, category_result.stderr)
        self.assertEqual(category_result.stdout.strip(), "")

    def test_validate_defaults_to_current_directory(self) -> None:
        """When no path is given, validate defaults to '.'."""
        with ScratchPackFixture(self) as tmp:
            self._write_minimal_valid_pack(tmp)
            result = _run_packs("validate", cwd=str(tmp))
            self.assertEqual(
                result.returncode, 0,
                f"validate should exit 0; stderr: {result.stderr!r}",
            )
            self.assertIn("valid:", result.stdout)

    def test_validate_nonexistent_path_exits_nonzero(self) -> None:
        result = _run_packs(
            "validate", "/nonexistent/path/12345",
            cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_validate_non_directory_exits_nonzero(self) -> None:
        with ScratchPackFixture(self) as tmp:
            some_file = tmp / "not_a_dir.txt"
            some_file.write_text("hello")
            result = _run_packs("validate", str(some_file), cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)

    def _write_minimal_valid_pack(self, root: Path) -> None:
        (root / "pack.yaml").write_text(
            textwrap.dedent("""\
                schema_version: 1
                id: test_pack
                name: Test Pack
                version: 0.1.0
                description: A test pack.
                content:
                  executors: executors
                  orchestrators: orchestrators
                agent:
                  purpose: Testing
            """),
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text("# Test Pack\n\nAgent guide.\n")
        (root / "README.md").write_text("# Test Pack\n\nUser docs.\n")
        (root / "STAGE.md").write_text("## Purpose\n\nTesting.\n")
        (root / "executors").mkdir(parents=True, exist_ok=True)
        (root / "orchestrators").mkdir(parents=True, exist_ok=True)


class TestPacksValidateBrokenPack(unittest.TestCase):
    """Prove: a deliberately broken pack fixture fails with file-specific error and non-zero exit."""

    def test_broken_pack_missing_schema_version_reports_file_specific_error(self) -> None:
        with ScratchPackFixture(self) as tmp:
            (tmp / "pack.yaml").write_text(
                "id: broken_pack\nname: Broken\nversion: 0.1.0\nagent:\n  purpose: Test\n",
                encoding="utf-8",
            )
            (tmp / "AGENTS.md").write_text("# Broken\n")
            (tmp / "README.md").write_text("# Broken\n")
            result = _run_packs("validate", str(tmp), cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pack.yaml", result.stderr)
            self.assertIn("schema_version", result.stderr.lower())

    def test_broken_pack_invalid_yaml_reports_file_specific_error(self) -> None:
        with ScratchPackFixture(self) as tmp:
            (tmp / "pack.yaml").write_text(
                "schema_version: 1\nid: broken\n  name: Bad Indent\n",
                encoding="utf-8",
            )
            result = _run_packs("validate", str(tmp), cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pack.yaml", result.stderr)
            self.assertIn("YAML", result.stderr)

    def test_broken_pack_missing_entrypoint_file_reports_error(self) -> None:
        with ScratchPackFixture(self) as tmp:
            (tmp / "pack.yaml").write_text(
                textwrap.dedent("""\
                    schema_version: 1
                    id: broken
                    name: Broken
                    version: 0.1.0
                    agent:
                      purpose: Test
                    content:
                      executors: executors
                """),
                encoding="utf-8",
            )
            (tmp / "AGENTS.md").write_text("# Broken\n")
            (tmp / "README.md").write_text("# Broken\n")
            (tmp / "STAGE.md").write_text("## Purpose\n\nBroken.\n")
            (tmp / "executors").mkdir(parents=True)
            exec_dir = tmp / "executors" / "no_run"
            exec_dir.mkdir(parents=True)
            (exec_dir / "executor.yaml").write_text(
                textwrap.dedent("""\
                    schema_version: 1
                    id: broken.no_run
                    name: No Run
                    version: 0.1.0
                    runtime:
                      type: python-cli
                      entrypoint: run.py
                """),
                encoding="utf-8",
            )
            (exec_dir / "STAGE.md").write_text("# No Run\n")
            result = _run_packs("validate", str(tmp), cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("executors/no_run", result.stderr)
            self.assertIn("entrypoint", result.stderr.lower())

class TestScaffoldAndValidateRoundTrip(unittest.TestCase):
    """Prove: packs new + executors new + orchestrators new creates a valid pack."""

    def test_full_scaffold_round_trip_via_subprocess(self) -> None:
        with ScratchPackFixture(self) as tmp:
            cwd = str(tmp)

            # 1. packs new — creates in CWD
            result = _run_packs("new", "my_pack", cwd=cwd)
            self.assertEqual(
                result.returncode, 0,
                f"packs new failed: stderr={result.stderr!r}",
            )
            pack_root = tmp / "my_pack"
            self.assertTrue(pack_root.is_dir(), f"Expected {pack_root} to exist")
            self.assertTrue((pack_root / "pack.yaml").is_file())
            self.assertTrue((pack_root / "AGENTS.md").is_file())
            self.assertTrue((pack_root / "README.md").is_file())
            self.assertTrue((pack_root / "STAGE.md").is_file())
            self.assertTrue((pack_root / "executors").is_dir())
            self.assertTrue((pack_root / "orchestrators").is_dir())
            self.assertTrue((pack_root / "elements").is_dir())

            # 2. executors new (must be run from the pack root to find pack.yaml)
            result = _run_executors(
                "new", "my_pack.ingest_assets",
                cwd=str(pack_root),
            )
            self.assertEqual(
                result.returncode, 0,
                f"executors new failed: stderr={result.stderr!r}",
            )
            exec_dir = pack_root / "executors" / "ingest_assets"
            self.assertTrue(exec_dir.is_dir())
            self.assertTrue((exec_dir / "executor.yaml").is_file())
            self.assertTrue((exec_dir / "run.py").is_file())
            self.assertTrue((exec_dir / "STAGE.md").is_file())

            # 3. orchestrators new
            result = _run_orchestrators(
                "new", "my_pack.make_trailer",
                cwd=str(pack_root),
            )
            self.assertEqual(
                result.returncode, 0,
                f"orchestrators new failed: stderr={result.stderr!r}",
            )
            orch_dir = pack_root / "orchestrators" / "make_trailer"
            self.assertTrue(orch_dir.is_dir())
            self.assertTrue((orch_dir / "orchestrator.yaml").is_file())
            self.assertTrue((orch_dir / "run.py").is_file())
            self.assertTrue((orch_dir / "STAGE.md").is_file())

            # 4. Validate the fully scaffolded pack
            errors, warnings = validate_pack(pack_root)
            self.assertEqual(
                errors, [],
                f"Scaffolded pack should have zero validation errors, got: {errors}",
            )

            # 5. CLI validate subprocess also exits 0
            result = _run_packs("validate", str(pack_root), cwd=str(pack_root))
            self.assertEqual(
                result.returncode, 0,
                f"CLI validate should exit 0; stderr: {result.stderr!r}",
            )
            self.assertIn("valid:", result.stdout)

    def test_packs_new_scaffold_includes_taxonomy_fields(self) -> None:
        with ScratchPackFixture(self) as tmp:
            result = _run_packs("new", "taxonomy_pack", cwd=str(tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = (tmp / "taxonomy_pack" / "pack.yaml").read_text(encoding="utf-8")
            self.assertIn("origin: external", manifest)
            self.assertIn("install_tier: core", manifest)
            self.assertIn("pack_type: capability", manifest)
            self.assertIn("domain: system", manifest)
            self.assertIn("stability: stable", manifest)
            self.assertIn("support: core", manifest)

    def test_scaffold_pack_then_add_executor_and_orchestrator_programmatic(self) -> None:
        """Use the CLI modules directly (not subprocess) to test the internal API."""
        with ScratchPackFixture(self) as tmp:
            # cmd_new uses Path.cwd() to determine target, so chdir into tmp
            with _chdir_context(tmp):
                rc = packs_cli.cmd_new(["test_pack"])
                self.assertEqual(
                    rc, 0,
                    f"cmd_new should return 0, got {rc}",
                )

            pack_dir = tmp / "test_pack"
            self.assertTrue(pack_dir.is_dir(), f"Expected {pack_dir} to exist")

            # Scaffold executor and orchestrator from pack_dir
            result = _run_executors("new", "test_pack.my_exec", cwd=str(pack_dir))
            self.assertEqual(result.returncode, 0, f"executors new: {result.stderr}")

            result = _run_orchestrators("new", "test_pack.my_orch", cwd=str(pack_dir))
            self.assertEqual(result.returncode, 0, f"orchestrators new: {result.stderr}")

            # Validate the result
            errors, warnings = validate_pack(pack_dir)
            self.assertEqual(errors, [], f"Scaffolded pack should validate cleanly: {errors}")


class TestScaffoldRejections(unittest.TestCase):
    """Prove: scaffolds reject invalid ids, missing targets, and overwrites."""

    def _scaffold_pack(self, tmp: Path, pack_id: str) -> Path:
        """Scaffold a pack in tmp and return the pack root directory."""
        with _chdir_context(tmp):
            rc = packs_cli.cmd_new([pack_id])
            if rc != 0:
                raise RuntimeError(f"cmd_new({pack_id}) failed with exit code {rc}")
        return tmp / pack_id

    def test_packs_new_rejects_invalid_id(self) -> None:
        with ScratchPackFixture(self) as tmp:
            result = _run_packs("new", "Invalid-Id", cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid pack id", result.stderr.lower())

    def test_packs_new_rejects_id_with_special_chars(self) -> None:
        with ScratchPackFixture(self) as tmp:
            for bad_id in ("123abc", "my_pack!", "UPPERCASE", "dot.name"):
                with self.subTest(bad_id=bad_id):
                    result = _run_packs("new", bad_id, cwd=str(tmp))
                    self.assertNotEqual(result.returncode, 0)

    def test_packs_new_rejects_existing_directory(self) -> None:
        with ScratchPackFixture(self) as tmp:
            existing = tmp / "my_pack"
            existing.mkdir()
            result = _run_packs("new", "my_pack", cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr.lower())

    def test_executors_new_rejects_invalid_qualified_id(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack(tmp, "my_pack")
            result = _run_executors("new", "bad-id", cwd=str(pack_dir))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be", result.stderr.lower())

    def test_executors_new_rejects_missing_pack(self) -> None:
        with ScratchPackFixture(self) as tmp:
            result = _run_executors("new", "nonexistent.my_exec", cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pack.yaml not found", result.stderr)

    def test_executors_new_rejects_pack_id_mismatch(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack(tmp, "my_pack")
            result = _run_executors("new", "other_pack.my_exec", cwd=str(pack_dir))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pack id mismatch", result.stderr.lower())

    def test_executors_new_rejects_overwrite(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack(tmp, "my_pack")

            # First scaffold succeeds
            result = _run_executors("new", "my_pack.my_exec", cwd=str(pack_dir))
            self.assertEqual(result.returncode, 0)

            # Second scaffold to same target fails
            result = _run_executors("new", "my_pack.my_exec", cwd=str(pack_dir))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr.lower())

    def test_orchestrators_new_rejects_invalid_qualified_id(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack(tmp, "my_pack")
            result = _run_orchestrators("new", "bad-id", cwd=str(pack_dir))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be", result.stderr.lower())

    def test_orchestrators_new_rejects_missing_pack(self) -> None:
        with ScratchPackFixture(self) as tmp:
            result = _run_orchestrators("new", "nonexistent.my_orch", cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pack.yaml not found", result.stderr)

    def test_orchestrators_new_rejects_overwrite(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack(tmp, "my_pack")

            # First scaffold succeeds
            result = _run_orchestrators("new", "my_pack.my_orch", cwd=str(pack_dir))
            self.assertEqual(result.returncode, 0)

            # Second scaffold fails
            result = _run_orchestrators("new", "my_pack.my_orch", cwd=str(pack_dir))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr.lower())


class TestScaffoldFixture(unittest.TestCase):
    """Fixture that builds a temp pack via scaffolds, validates it, and checks created file list."""

    EXPECTED_PACK_FILES = {
        "pack.yaml",
        "AGENTS.md",
        "README.md",
        "STAGE.md",
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

    def test_scaffold_add_executor_then_add_orchestrator_and_validate(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack_in(tmp, "test_pack")

            # Add executor
            result = _run_executors("new", "test_pack.my_exec", cwd=str(pack_dir))
            self.assertEqual(result.returncode, 0, f"executors new: {result.stderr}")

            # Add orchestrator
            result = _run_orchestrators("new", "test_pack.my_orch", cwd=str(pack_dir))
            self.assertEqual(result.returncode, 0, f"orchestrators new: {result.stderr}")

            # Check executor files
            exec_dir = pack_dir / "executors" / "my_exec"
            for fname in self.EXPECTED_EXECUTOR_FILES:
                path = exec_dir / fname
                self.assertTrue(
                    path.is_file(),
                    f"Expected {fname} in executors/my_exec/",
                )

            # Check orchestrator files
            orch_dir = pack_dir / "orchestrators" / "my_orch"
            for fname in self.EXPECTED_ORCHESTRATOR_FILES:
                path = orch_dir / fname
                self.assertTrue(
                    path.is_file(),
                    f"Expected {fname} in orchestrators/my_orch/",
                )

            # Validate
            errors, warnings = validate_pack(pack_dir)
            self.assertEqual(
                errors, [],
                f"Validation should pass; got errors: {errors}",
            )

    def test_scaffold_creates_valid_pack_without_manual_edits(self) -> None:
        """The scaffold round-trip must produce a valid pack zero-touch."""
        with ScratchPackFixture(self) as tmp:
            pack_dir = self._scaffold_pack_in(tmp, "test_pack")

            _run_executors("new", "test_pack.ingest", cwd=str(pack_dir), check=True)
            _run_orchestrators("new", "test_pack.assemble", cwd=str(pack_dir), check=True)

            # No manual edits — just validate
            errors, warnings = validate_pack(pack_dir)
            self.assertEqual(
                errors, [],
                f"Zero-touch scaffolded pack should validate cleanly: {errors}",
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

    def test_packs_cli_main_validate_returns_zero(self) -> None:
        exit_code = packs_cli.main(["validate", str(_EXAMPLES_MINIMAL)])
        self.assertEqual(exit_code, 0)

    def test_packs_cli_main_new_rejects_bad_id(self) -> None:
        exit_code = packs_cli.main(["new", "BAD"])
        self.assertNotEqual(exit_code, 0)


class TestTaxonomyHiddenPackBehavior(unittest.TestCase):
    """Prove: example-only packs are absent from runtime discovery, even with
    --show-hidden, but remain valid when addressed by explicit example paths."""

    _EXAMPLES_ONLY_PACK_IDS = {
        "clip_tools",
        "video_tools",
        "file_summarizer",
        "text_digest",
        "text_review",
    }

    def test_default_discovery_excludes_text_review(self) -> None:
        result = _run_packs("list", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertTrue(self._EXAMPLES_ONLY_PACK_IDS.isdisjoint(pack_ids))

    def test_show_hidden_excludes_examples_only_packs(self) -> None:
        result = _run_packs("list", "--json", "--show-hidden", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertTrue(self._EXAMPLES_ONLY_PACK_IDS.isdisjoint(pack_ids))

    def test_status_default_excludes_text_review(self) -> None:
        result = _run_packs("status", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in status["packs"]}
        self.assertTrue(self._EXAMPLES_ONLY_PACK_IDS.isdisjoint(pack_ids))

    def test_status_show_hidden_excludes_examples_only_packs(self) -> None:
        result = _run_packs("status", "--json", "--show-hidden", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in status["packs"]}
        self.assertTrue(self._EXAMPLES_ONLY_PACK_IDS.isdisjoint(pack_ids))

    def test_inspect_text_review_fails_because_it_is_example_only(self) -> None:
        result = _run_packs("inspect", "text_review", "--json", cwd=str(_REPO_ROOT))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown pack 'text_review'", result.stderr)

    def test_visible_packs_present_in_default_discovery(self) -> None:
        result = _run_packs("list", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        for visible_id in ("builtin", "external", "iteration", "media", "upload"):
            self.assertIn(visible_id, pack_ids, f"{visible_id} must be in default discovery")


class TestTaxonomyAllFilters(unittest.TestCase):
    """Prove: all six taxonomy filter flags work independently."""

    def test_domain_filter_includes_only_matching(self) -> None:
        result = _run_packs("list", "--json", "--domain", "system", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertIn("builtin", pack_ids)
        self.assertNotIn("external", pack_ids)
        self.assertNotIn("media", pack_ids)

    def test_origin_filter_includes_only_matching(self) -> None:
        result = _run_packs("list", "--json", "--origin", "builtin", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertIn("builtin", pack_ids)
        self.assertIn("external", pack_ids)
        self.assertIn("media", pack_ids)

    def test_install_tier_filter_includes_only_matching(self) -> None:
        result = _run_packs("list", "--json", "--install-tier", "core", "--show-hidden", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertIn("builtin", pack_ids)
        self.assertIn("external", pack_ids)
        # Example-only packs are not runtime-discovered even with --show-hidden.
        self.assertNotIn("text_review", pack_ids)

    def test_pack_type_filter_includes_only_matching(self) -> None:
        result = _run_packs("list", "--json", "--pack-type", "capability", "--show-hidden", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertIn("builtin", pack_ids)
        self.assertIn("external", pack_ids)

    def test_stability_filter_includes_only_matching(self) -> None:
        result = _run_packs("list", "--json", "--stability", "stable", "--show-hidden", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertIn("builtin", pack_ids)
        self.assertIn("external", pack_ids)

    def test_support_filter_includes_only_matching(self) -> None:
        result = _run_packs("list", "--json", "--support", "core", "--show-hidden", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertIn("builtin", pack_ids)
        self.assertIn("external", pack_ids)
        # Example-only packs are not runtime-discovered even with --show-hidden.
        self.assertNotIn("text_review", pack_ids)

    def test_combined_filters(self) -> None:
        result = _run_packs("list", "--json", "--domain", "system", "--origin", "builtin", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        pack_ids = {pack["id"] for pack in listed["packs"]}
        self.assertEqual(pack_ids, {"builtin"})


class TestTaxonomyGroupingAndOutput(unittest.TestCase):
    """Prove: JSON output has groups, plain-text output has taxonomy headings."""

    def test_list_json_has_groups_and_packs(self) -> None:
        result = _run_packs("list", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(result.stdout)
        self.assertIn("packs", listed)
        self.assertIn("groups", listed)
        self.assertIsInstance(listed["packs"], list)
        self.assertIsInstance(listed["groups"], list)
        for group in listed["groups"]:
            self.assertIn("group_by", group)
            self.assertEqual(group["group_by"], "domain")
            self.assertIn("value", group)
            self.assertIn("packs", group)
            self.assertIsInstance(group["packs"], list)

    def test_status_json_has_groups_and_validation(self) -> None:
        result = _run_packs("status", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertIn("packs", status)
        self.assertIn("groups", status)
        for pack in status["packs"]:
            self.assertIn("taxonomy", pack)
            self.assertIn("validation", pack)

    def test_list_plain_text_grouped_by_domain(self) -> None:
        result = _run_packs("list", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("taxonomy: domain=", result.stdout)

    def test_status_plain_text_grouped_by_domain(self) -> None:
        result = _run_packs("status", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("taxonomy: domain=", result.stdout)

    def test_inspect_json_has_taxonomy(self) -> None:
        result = _run_packs("inspect", "builtin", "--json", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        inspected = json.loads(result.stdout)
        self.assertIn("taxonomy", inspected)
        self.assertEqual(inspected["taxonomy"]["domain"], "system")
        self.assertEqual(inspected["taxonomy"]["origin"], "builtin")

    def test_inspect_plain_text_has_taxonomy_block(self) -> None:
        result = _run_packs("inspect", "builtin", cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("taxonomy:", result.stdout)
        self.assertIn("domain:", result.stdout)


class TaxonomyEnumValidationTest(unittest.TestCase):
    """T4: pack.json taxonomy enum constraints reject typo'd values."""

    def test_typo_origin_rejected(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = tmp / "typo_pack"
            pack_dir.mkdir()
            (pack_dir / "pack.yaml").write_text(
                "schema_version: 1\nid: typo.pack\nname: Typo Pack\nversion: 0.1.0\n"
                "origin: typo_value\n",
                encoding="utf-8",
            )
            result = _run_packs("validate", str(pack_dir), cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0, "typo'd origin should fail validation")

    def test_typo_domain_rejected(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = tmp / "typo_domain"
            pack_dir.mkdir()
            (pack_dir / "pack.yaml").write_text(
                "schema_version: 1\nid: typo.domain\nname: Typo Domain\nversion: 0.1.0\n"
                "domain: notadomain\n",
                encoding="utf-8",
            )
            result = _run_packs("validate", str(pack_dir), cwd=str(tmp))
            self.assertNotEqual(result.returncode, 0, "typo'd domain should fail validation")

    def test_valid_taxonomy_passes(self) -> None:
        with ScratchPackFixture(self) as tmp:
            pack_dir = tmp / "good_pack"
            pack_dir.mkdir()
            (pack_dir / "pack.yaml").write_text(
                "schema_version: 1\nid: good_pack\nname: Good Pack\nversion: 0.1.0\n"
                "origin: builtin\ninstall_tier: core\npack_type: capability\n"
                "domain: media\nstability: stable\nsupport: core\n",
                encoding="utf-8",
            )
            result = _run_packs("validate", str(pack_dir), cwd=str(tmp))
            self.assertEqual(result.returncode, 0, f"valid taxonomy pack should pass: {result.stderr}")


class PacksLsListAliasTest(unittest.TestCase):
    """T3: packs ls and packs list resolve to the same handler."""

    def test_packs_ls_same_as_list(self) -> None:
        result_ls = _run_packs("ls", cwd=str(_REPO_ROOT))
        result_list = _run_packs("list", cwd=str(_REPO_ROOT))
        self.assertEqual(result_ls.returncode, result_list.returncode)
        self.assertEqual(result_ls.stdout, result_list.stdout)


class NounGroupLsListParityTest(unittest.TestCase):
    """T3: every noun group has both ls and list resolving to the same handler."""

    def _run_astrid(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "astrid", *args],
            capture_output=True, text=True,
        )

    def _assert_ls_list_parity(self, noun: str, expect_option: str = "") -> None:
        r_ls = self._run_astrid(noun, "ls", "--help")
        r_list = self._run_astrid(noun, "list", "--help")
        # Both must emit help text (presence of "options:" or "-h" is sufficient).
        self.assertIn("-h", r_ls.stdout + r_ls.stderr,
                      f"{noun} ls should emit help")
        self.assertIn("-h", r_list.stdout + r_list.stderr,
                      f"{noun} list should emit help")
        # Both must resolve to the same handler (same help content).
        self.assertEqual(r_ls.stdout, r_list.stdout,
                         f"{noun} ls and list should produce identical help output")
        if expect_option:
            self.assertIn(expect_option, r_ls.stdout + r_ls.stderr)

    def test_executors_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("executors", "--json")

    def test_orchestrators_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("orchestrators")

    def test_elements_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("elements")

    def test_models_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("models")

    def test_packs_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("packs")

    def test_sessions_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("sessions")

    def test_timelines_ls_and_list_help(self) -> None:
        self._assert_ls_list_parity("timelines")


if __name__ == "__main__":
    unittest.main()
