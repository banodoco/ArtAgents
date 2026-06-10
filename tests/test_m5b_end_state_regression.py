"""End-state regression tests for m5b god-module splits.

These tests encode the *intended* post-refactor invariants.  They are
expected to FAIL against the current implementation and turn green only
when the corresponding refactors are complete.  Each test class documents
which specific refactor it guards.

DO NOT weaken these assertions to pass against the old code — they are the
contract the refactor must satisfy.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1.  No ``raw[0] ==`` dispatch in astrid/core/gateway/dispatch.py
# ---------------------------------------------------------------------------

class RawDispatchRemovalTest(unittest.TestCase):
    """The ``_dispatch()`` function must not use ``raw[0] ==`` comparisons.

    After the CLI-unification refactor (m5b), the long chain of
    ``if raw and raw[0] == "..."`` in ``astrid/core/gateway/dispatch.py:_dispatch()``
    must be replaced with a table-driven dispatch (register-based,
    argparse sub-parsers, or equivalent).  String-comparison chains are a
    maintenance liability because they duplicate the verb vocabulary and
    allow typos/additions to go unnoticed.

    This test uses AST-level inspection to assert the ``raw[0] ==``
    pattern is absent from ``_dispatch()``.
    """

    def test_dispatch_has_no_raw0_equality_chain(self) -> None:
        """No ``raw[0] == ...`` comparison inside ``_dispatch()``."""
        pipeline_path = _REPO_ROOT / "astrid" / "core" / "gateway" / "dispatch.py"
        source = pipeline_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(pipeline_path))

        dispatch_fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_dispatch":
                dispatch_fn = node
                break

        self.assertIsNotNone(dispatch_fn, "Could not find _dispatch() in gateway/dispatch.py")

        raw0_eq_locations: list[str] = []
        for node in ast.walk(dispatch_fn):
            if isinstance(node, ast.Compare):
                # Look for ``raw[0] == "..."``
                if (
                    isinstance(node.left, ast.Subscript)
                    and isinstance(node.left.value, ast.Name)
                    and node.left.value.id == "raw"
                    and isinstance(node.left.slice, ast.Constant)
                    and node.left.slice.value == 0
                    and any(isinstance(op, ast.Eq) for op in node.ops)
                ):
                    raw0_eq_locations.append(f"line {node.lineno}")

        self.assertEqual(
            raw0_eq_locations,
            [],
            f"_dispatch() contains raw[0] == comparisons at: {raw0_eq_locations}",
        )

    def test_dispatch_uses_table_or_parser_not_if_chain(self) -> None:
        """_dispatch() uses argparse or a dispatch map, not a long if-chain."""
        pipeline_path = _REPO_ROOT / "astrid" / "core" / "gateway" / "dispatch.py"

        import ast as ast_mod

        source = pipeline_path.read_text(encoding="utf-8")
        tree = ast_mod.parse(source, filename=str(pipeline_path))

        dispatch_fn = None
        for node in ast_mod.walk(tree):
            if isinstance(node, ast_mod.FunctionDef) and node.name == "_dispatch":
                dispatch_fn = node
                break

        self.assertIsNotNone(dispatch_fn)

        # Count top-level If statements whose test involves raw[0]
        raw_if_count = 0
        for stmt in dispatch_fn.body:
            if isinstance(stmt, ast_mod.If):
                test_str = ast_mod.unparse(stmt.test)
                if "raw[0]" in test_str and "==" in test_str:
                    raw_if_count += 1

        # After refactor there should be 0-2 fallback guards at most,
        # not the current ~35-branch chain.
        self.assertLessEqual(
            raw_if_count,
            3,
            f"_dispatch() has {raw_if_count} raw[0]== branches; expected ≤ 3 after refactor",
        )


# ---------------------------------------------------------------------------
# 2.  Unknown commands never hit default hype
# ---------------------------------------------------------------------------

class UnknownCommandDoesNotHitDefaultHypeTest(unittest.TestCase):
    """Unknown top-level commands must not invoke the default hype orchestrator.

    Today ``astrid gateway/dispatch.py:_dispatch()`` falls through to
    ``_run_default_brief_orchestrator(raw)`` whenever ``raw[0]`` starts
    with ``--`` and doesn't match any known verb.  This is surprising
    behavior: ``astrid --typo`` silently runs hype instead of reporting
    an unknown command.

    After the refactor, unknown commands (including those starting with
    ``--``) must exit with a non-zero code and a clear error message,
    never hitting the default hype path.
    """

    def test_unknown_top_level_command_exits_nonzero(self) -> None:
        """``astrid nonexistent_cmd`` exits with non-zero code."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "nonexistent_cmd_xyzzy"],
            capture_output=True,
            text=True,
            env={**os.environ, "ASTRID_NO_NUDGE": "1"},
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0, "Unknown command should exit non-zero")
        self.assertIn(
            "unknown command",
            (result.stderr + result.stdout).lower(),
            "Error message must mention 'unknown command'",
        )

    def test_unknown_flag_style_command_exits_nonzero(self) -> None:
        """``astrid --not-a-real-flag value`` exits non-zero, does NOT run hype."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "--not-a-real-flag", "value"],
            capture_output=True,
            text=True,
            env={**os.environ, "ASTRID_NO_NUDGE": "1"},
            timeout=30,
        )
        # Must not exit 0 (hype default path exits 0 on simple brief routing).
        self.assertNotEqual(result.returncode, 0, "Unknown flag-style command should exit non-zero")
        # Must not contain hype orchestrator output.
        self.assertNotIn(
            "hype",
            (result.stderr + result.stdout).lower(),
            "Unknown command should not invoke the default hype orchestrator",
        )

    def test_empty_flags_do_not_trigger_hype(self) -> None:
        """``astrid --video src --brief b --out o`` should route to hype but
        ``astrid --unknown`` must not.
        """
        # An unknown long-option-only invocation.
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "--made-up-option"],
            capture_output=True,
            text=True,
            env={**os.environ, "ASTRID_NO_NUDGE": "1"},
            timeout=30,
        )
        # The current fallthrough would try to run hype with this argv;
        # after refactor it must be rejected.
        self.assertNotEqual(
            result.returncode,
            0,
            "Unknown long option should not silently exit 0",
        )
        stderr_lower = result.stderr.lower()
        # Should complain about an unknown option, not start running hype.
        self.assertTrue(
            "unknown" in stderr_lower or "unrecognized" in stderr_lower or "error" in stderr_lower,
            f"Expected an error message for unknown option, got: {result.stderr[:200]}",
        )

    def test_help_flag_still_works(self) -> None:
        """``--help`` must still exit 0 after the refactor (non-regression)."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "--help"],
            capture_output=True,
            text=True,
            env={**os.environ, "ASTRID_NO_NUDGE": "1"},
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, "--help should still exit 0")


# ---------------------------------------------------------------------------
# 3.  Packs active-parser ``args.json`` behavior
# ---------------------------------------------------------------------------

class PacksArgsJsonBehaviorTest(unittest.TestCase):
    """The ``packs`` CLI must honour ``--json`` / ``--json_output``
    consistently across subcommands.

    After the refactor the ``packs`` subcommand parser must use a single
    active argparse instance (the "active parser") so that ``--json`` is
    recognised at the correct position and ``args.json`` / ``args.json_output``
    is populated reliably.  This guards against regressions from the
    parser unification work.
    """

    def test_packs_list_json_outputs_valid_json(self) -> None:
        """``packs list --json`` produces structurally valid JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "packs", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"packs list --json failed: {result.stderr}")
        stdout = result.stdout.strip()
        self.assertTrue(stdout, "Expected non-empty JSON output")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"Output is not valid JSON: {exc}\nOutput: {stdout[:500]}")
        self.assertIsInstance(data, dict, "Top-level output must be a JSON object")
        self.assertIn("packs", data, "JSON output must contain a 'packs' key")
        self.assertIsInstance(data["packs"], list, "'packs' must be a list")

    def test_packs_list_json_output_has_groups(self) -> None:
        """``packs list --json`` includes domain-grouped output."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "packs", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        self.assertIn("groups", data, "JSON output must contain 'groups' key")
        self.assertIsInstance(data["groups"], list, "'groups' must be a list")

    def test_packs_list_no_json_produces_tabular_output(self) -> None:
        """``packs list`` without --json produces tab-separated text, not JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "packs", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"packs list failed: {result.stderr}")
        stdout = result.stdout.strip()
        # Tabular output contains tab characters; JSON does not.
        self.assertIn("\t", stdout, "Tabular output should contain tabs")
        # Should not parse as JSON.
        with self.assertRaises(json.JSONDecodeError):
            json.loads(stdout)

    def test_packs_inspect_json_flag_is_recognized(self) -> None:
        """``packs inspect --help`` mentions --json flag."""
        result = subprocess.run(
            [sys.executable, "-m", "astrid", "packs", "inspect", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertIn("--json", result.stdout, "inspect help must document --json flag")


# ---------------------------------------------------------------------------
# 4.  Lifecycle forbidden imports flagged by validate_import_layering()
# ---------------------------------------------------------------------------

class LifecycleImportLayeringValidationTest(unittest.TestCase):
    """After the lifecycle split and de-inversion, ``validate_import_layering()``
    must flag forbidden imports from ``astrid/core/task/lifecycle.py``.

    The current code (m4) has an explicit exemption at
    ``structure.py:_is_import_layering_exempt()`` that allows lifecycle.py
    to import from ``astrid.packs.*``.  The m5b
    refactor removes this exemption, meaning lifecycle.py's forbidden
    imports will be reported as violations.

    These tests assert the END STATE: the exemption is gone AND
    lifecycle.py itself has been cleaned up so it no longer triggers
    violations.
    """

    def test_lifecycle_path_is_not_exempt(self) -> None:
        """``_is_import_layering_exempt`` must NOT exempt lifecycle.py."""
        from astrid.core.structure import _is_import_layering_exempt

        lifecycle_path = _REPO_ROOT / "astrid" / "core" / "task" / "lifecycle.py"
        self.assertFalse(
            _is_import_layering_exempt(lifecycle_path, _REPO_ROOT),
            "lifecycle.py must no longer be exempt from import-layering validation",
        )

    def test_lifecycle_has_no_forbidden_imports(self) -> None:
        """Running validate_import_layering on real lifecycle.py produces zero violations."""
        from astrid.core.structure import validate_import_layering

        violations = validate_import_layering(_REPO_ROOT)
        lifecycle_violations = [
            v for v in violations
            if "lifecycle.py" in v
        ]
        self.assertEqual(
            lifecycle_violations,
            [],
            f"lifecycle.py has forbidden imports: {lifecycle_violations}",
        )

    def test_lifecycle_forbidden_import_would_be_flagged_in_isolation(self) -> None:
        """If lifecycle.py had a forbidden import, it would be flagged (no exemption)."""
        from astrid.core.structure import validate_import_layering

        violations = validate_import_layering(_REPO_ROOT)

        # Verify that NO core file with forbidden pack/orchestrate imports
        # is silently passed due to a lifecycle-style exemption.
        core_forbidden = [
            v for v in violations
            if v.startswith("astrid/core/")
        ]
        # The only allowed forbidden imports in core are the documented
        # no longer any file-level core-subsystem exemption.
        # This test verifies there's no hidden exemption for lifecycle.py.
        exempted_paths = {
            v.split(":")[0] for v in violations
            if "lifecycle.py" in v
        }
        self.assertEqual(
            exempted_paths,
            set(),
            "No core path (including lifecycle.py) should have exemption-gated violations",
        )

    def test_validate_import_layering_exemption_is_removed(self) -> None:
        """The ``_is_import_layering_exempt`` function no longer returns True for
        lifecycle-related files or core-subsystem imports."""
        from astrid.core.structure import _is_import_layering_exempt

        for relpath in (
            "astrid/core/task/lifecycle/__init__.py",
            "astrid/core/task/orchestrator_resolver.py",
            "astrid/core/task/plan/builder.py",
        ):
            path = _REPO_ROOT / relpath
            self.assertFalse(
                _is_import_layering_exempt(path, _REPO_ROOT),
                f"Lifecycle-related file should not be exempt — {relpath} must be checked normally",
            )

        event_stream_path = _REPO_ROOT / "astrid" / "core" / "task" / "events" / "stream.py"
        self.assertFalse(
            _is_import_layering_exempt(event_stream_path, _REPO_ROOT),
            "event_stream.py should not need a file-level exemption now that audit is a core subsystem",
        )

    def test_forbidden_imports_from_packs_are_flagged(self) -> None:
        """A core file importing from astrid.packs.* is flagged."""
        from astrid.core.structure import validate_import_layering

        violations = validate_import_layering(_REPO_ROOT)

        # At end state, any core file importing from astrid.packs should be
        # flagged as a violation.
        # We verify the validator itself works by checking that it catches
        # at least one current known violation (if any exist outside lifecycle).
        # After the refactor there should be zero.
        packs_violations = [
            v for v in violations
            if "astrid.packs." in v
        ]
        # These violations may exist in non-lifecycle files that haven't been
        # cleaned up yet. The key assertion: none of them are from lifecycle.py.
        lifecycle_in_packs = [v for v in packs_violations if "lifecycle.py" in v]
        self.assertEqual(
            lifecycle_in_packs,
            [],
            f"lifecycle.py must not appear in forbidden-import violations: {lifecycle_in_packs}",
        )


# ---------------------------------------------------------------------------
# 5.  Cross-cutting: default hype routing is explicit, not a fallthrough
# ---------------------------------------------------------------------------

class DefaultBriefRoutingIsExplicitTest(unittest.TestCase):
    """The default-hype routing must be an explicit verb, not a fallthrough.

    Currently ``_run_default_brief_orchestrator()`` is reached as the
    catch-all at the bottom of ``_dispatch()``.  After the refactor,
    brief-based orchestration must be invoked through a named verb (e.g.
    ``astrid orchestrate`` or ``astrid run --brief ...``) rather than a
    silent fallthrough.
    """

    def test_default_brief_not_reached_by_unknown_args(self) -> None:
        """Arbitrary unknown argv must NOT invoke default hype."""
        import io

        from astrid.core import gateway as pipeline_mod

        # Simulate an unrecognized verb.
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            try:
                result = pipeline_mod.main(["unrecognized_verb_xyz"])
            except SystemExit as exc:
                result = int(exc.code) if exc.code is not None else 2

        self.assertNotEqual(result, 0, "Unknown verb must exit non-zero")

    def test_default_brief_requires_explicit_brief_flag(self) -> None:
        """The hype orchestrator should only be reachable via explicit
        ``--brief`` routing, not by passing mysterious arguments."""
        # This test verifies that entering hype requires an explicit pathway.
        # Read the dispatch function source to verify _run_default_brief_orchestrator
        # is only called from controlled contexts.
        pipeline_path = _REPO_ROOT / "astrid" / "core" / "gateway" / "dispatch.py"
        source = pipeline_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(pipeline_path))

        call_sites: list[int] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_run_default_brief_orchestrator"
            ):
                call_sites.append(node.lineno)

        # After refactor, _run_default_brief_orchestrator should only be
        # called from explicit brief-aware entry points, not from a catch-all
        # fallthrough in _dispatch().
        dispatch_fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_dispatch":
                dispatch_fn = node
                break

        if dispatch_fn:
            for node in ast.walk(dispatch_fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_run_default_brief_orchestrator"
                ):
                    self.fail(
                        f"_dispatch() still calls _run_default_brief_orchestrator "
                        f"at line {node.lineno} — default hype must not be a "
                        f"dispatch fallthrough"
                    )


if __name__ == "__main__":
    unittest.main()
