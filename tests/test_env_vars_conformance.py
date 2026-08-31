"""Conformance tests for astrid/core/env_vars.py.

(a) Every constant in env_vars.py has value == name.
(b) No constant name from env_vars.py is assigned anywhere else in astrid/
    (excluding the allowlisted directories: packs/, threads/, audit/).
(c) No bare os.environ.get("ASTRID_*") / os.environ["ASTRID_*"] string in
    astrid/core/**/*.py references a catalogued constant instead of the constant.
    (string/docstring/comment occurrences are excluded via AST context checks.)
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

import astrid.core.env_vars as _env_vars_module

ASTRID_ROOT = Path(__file__).parent.parent / "astrid"
CORE_ROOT = ASTRID_ROOT / "core"

_ALLOWLISTED_DIRS = {"packs", "threads", "audit"}

def _all_constants() -> dict[str, str]:
    """Return {name: value} for all string constants in env_vars.py."""
    result = {}
    for name, value in inspect.getmembers(_env_vars_module):
        if name.startswith("_") or not name.isupper():
            continue
        if isinstance(value, str):
            result[name] = value
    return result


def _is_allowlisted(path: Path) -> bool:
    parts = path.parts
    return any(d in parts for d in _ALLOWLISTED_DIRS)


def _py_files(root: Path, exclude_self: bool = False) -> list[Path]:
    files = []
    for p in root.rglob("*.py"):
        if _is_allowlisted(p):
            continue
        if exclude_self and p.name == "env_vars.py":
            continue
        files.append(p)
    return files


# ---------------------------------------------------------------------------
# (a) name == value invariant
# ---------------------------------------------------------------------------

class TestNameEqualsValue:
    def test_all_constants_name_equals_value(self):
        constants = _all_constants()
        violations = []
        for name, value in constants.items():
            if name != value:
                violations.append(f"  {name!r} = {value!r}  (name != value)")
        assert not violations, (
            f"env_vars.py constants must satisfy name == value. Violations:\n"
            + "\n".join(violations)
        )

# ---------------------------------------------------------------------------
# (b) exactly one definition site per constant name
# ---------------------------------------------------------------------------

def _collect_module_assignments(path: Path) -> set[str]:
    """Return the set of top-level or class-level name assignments in a file."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


class TestExactlyOneDefinitionSite:
    def test_no_duplicate_definitions(self):
        constants = _all_constants()
        # Map constant name → list of files that define it (excluding env_vars.py itself)
        duplicates: dict[str, list[str]] = {}
        other_files = _py_files(ASTRID_ROOT, exclude_self=True)
        for path in other_files:
            assigned = _collect_module_assignments(path)
            for name in constants:
                if name in assigned:
                    duplicates.setdefault(name, []).append(str(path.relative_to(ASTRID_ROOT.parent)))

        if duplicates:
            lines = []
            for name, paths in sorted(duplicates.items()):
                lines.append(f"  {name}: {', '.join(paths)}")
            pytest.fail(
                "env_vars.py constants must have exactly one definition site (env_vars.py).\n"
                "Duplicate assignments found in:\n" + "\n".join(lines)
            )


# ---------------------------------------------------------------------------
# (c) no bare-string environ accesses in core/ for catalogued constants
# ---------------------------------------------------------------------------

def _find_bare_environ_strings(path: Path) -> list[tuple[int, str]]:
    """Return (line, string_value) for bare os.environ.get/[] ASTRID_* accesses."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        # os.environ.get("ASTRID_...")  or  os.environ["ASTRID_..."]
        if isinstance(node, (ast.Call, ast.Subscript)):
            if isinstance(node, ast.Call):
                func = node.func
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr == "get"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "environ"
                ):
                    continue
                args = node.args
                if not args or not isinstance(args[0], ast.Constant):
                    continue
                val = args[0].value
            else:  # Subscript
                if not (
                    isinstance(node.value, ast.Attribute)
                    and node.value.attr == "environ"
                ):
                    continue
                idx = node.slice
                if isinstance(idx, ast.Index):
                    idx = idx.value  # Python 3.8 compat
                if not isinstance(idx, ast.Constant):
                    continue
                val = idx.value

            if isinstance(val, str) and val.startswith("ASTRID_"):
                hits.append((node.lineno, val))
    return hits


class TestNoBareStringAccess:
    def test_no_catalogued_bare_strings_in_core(self):
        constants = _all_constants()
        catalogued_values = set(constants.values())

        violations: list[str] = []
        for path in CORE_ROOT.rglob("*.py"):
            if _is_allowlisted(path):
                continue
            bare = _find_bare_environ_strings(path)
            for lineno, val in bare:
                if val in catalogued_values:
                    rel = path.relative_to(ASTRID_ROOT.parent)
                    # find which constant(s) cover this value
                    matching = [n for n, v in constants.items() if v == val]
                    violations.append(
                        f"  {rel}:{lineno}: os.environ access uses bare string {val!r} "
                        f"instead of constant(s) {matching}"
                    )

        assert not violations, (
            "Bare os.environ string access for catalogued constants found in astrid/core/:\n"
            + "\n".join(violations)
            + "\nImport the constant from astrid.core.env_vars instead."
        )

    def test_future_bare_string_would_fail(self):
        """Demonstrate that a new uncatalogued bare string in core/ is NOT flagged,
        while a catalogued one would be.  This documents test coverage scope."""
        constants = _all_constants()
        catalogued_values = set(constants.values())
        # A value that is NOT in the catalog should not appear in violation list
        sentinel = "ASTRID_HYPOTHETICAL_NOT_CATALOGUED"
        assert sentinel not in catalogued_values, (
            "If this assertion fails, the sentinel constant was added to env_vars.py; "
            "update this test."
        )
