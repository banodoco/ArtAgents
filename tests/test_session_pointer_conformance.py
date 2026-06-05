"""Conformance tests for the single .astrid-session writer invariant.

Asserts that exactly one function body in astrid/ writes to a file named
'.astrid-session' or uses SESSION_FILE_NAME with a write call, and that
this writer is ``astrid.core.session.lifecycle.write_session_pointer``.

Also verifies the delegation chain: cmd_attach passes write_project_pointer=True
to attach_session, which delegates to lifecycle.create_session/open_session,
which in turn call lifecycle.write_session_pointer.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ASTRID_ROOT = Path(__file__).parent.parent / "astrid"

_ALLOWLISTED_DIRS = {"packs", "threads", "audit"}


def _is_allowlisted(path: Path) -> bool:
    parts = path.parts
    return any(d in parts for d in _ALLOWLISTED_DIRS)


def _py_files(root: Path) -> list[Path]:
    files = []
    for p in root.rglob("*.py"):
        if _is_allowlisted(p):
            continue
        files.append(p)
    return files


# ---------------------------------------------------------------------------
# AST helpers: find function bodies that write to .astrid-session
# ---------------------------------------------------------------------------

# Write-related method names and function names that indicate a file write
_WRITE_METHODS = {
    "write_text",
    "write_bytes",
    "write",
}

_WRITE_FUNCS = {
    "open",  # open(path, 'w') or open(path, 'a')
}


def _resolve_name(node: ast.expr) -> str | None:
    """Resolve a simple dotted name like 'session_file.write_text' to the attr."""
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _collect_string_constants_in_node(node: ast.AST) -> list[str]:
    """Collect all string literal values within an AST node."""
    strings: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            strings.append(child.value)
    return strings


def _has_session_file_write(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function body writes to a .astrid-session file.

    Pattern 1: The function references SESSION_FILE_NAME AND contains a write
    call (write_text, write_bytes, write). This catches the canonical path
    through lifecycle.py that uses the constant.

    Pattern 2: The function contains a bare '.astrid-session' string literal
    as a Path component (i.e., used in constructing a file path, not as write
    content). We detect this by looking for '.astrid-session' in an expression
    that appears as the target (LHS) of a write call or in a Path construction
    that flows to a write target.

    Note: Functions that write '.astrid-session' as content (e.g., into
    .gitignore) are intentionally excluded — only writing TO that filename
    matters.
    """
    has_write = False
    has_session_file_name = False

    for node in ast.walk(func_node):
        # Detect writes: .write_text(...), .write_bytes(...), .write(...)
        if isinstance(node, ast.Call):
            attr = _resolve_name(node.func)
            if attr in _WRITE_METHODS:
                has_write = True

        # Detect SESSION_FILE_NAME references (canonical constant)
        if isinstance(node, ast.Name) and node.id == "SESSION_FILE_NAME":
            has_session_file_name = True

    # Pattern 1: SESSION_FILE_NAME + write = canonical writer
    if has_write and has_session_file_name:
        return True

    # Pattern 2: Check for bare '.astrid-session' string used in a file-path
    # position (not as write content). Walk the AST to find write calls where
    # the target expression (the object being written to) contains
    # '.astrid-session'.
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            attr = _resolve_name(node.func)
            if attr not in _WRITE_METHODS:
                continue
            # node.func is the attribute (e.g., f.write_text)
            # The target object is node.func.value
            target = node.func.value
            if _expr_contains_astrid_session(target):
                return True

    return False


def _expr_contains_astrid_session(expr: ast.expr) -> bool:
    """Check if an expression tree contains '.astrid-session' as a string literal."""
    for child in ast.walk(expr):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if ".astrid-session" in child.value:
                return True
    return False


def _function_qualified_name(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    """Build a qualified name: module_rel:ClassName.method_name or module_rel:func_name."""
    rel = str(path.relative_to(ASTRID_ROOT.parent))
    return f"{rel}:{node.name}"


def _find_session_pointer_writers() -> list[str]:
    """Scan astrid/ for functions that write to .astrid-session.

    Returns list of qualified function names.
    """
    writers: list[str] = []
    for py_file in _py_files(ASTRID_ROOT):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _has_session_file_write(node):
                    writers.append(_function_qualified_name(py_file, node))

    return sorted(writers)


# ---------------------------------------------------------------------------
# Test: exactly one writer
# ---------------------------------------------------------------------------

_EXPECTED_WRITER = (
    "astrid/core/session/lifecycle.py:write_session_pointer"
)


class TestExactlyOneSessionPointerWriter:
    def test_only_lifecycle_write_session_pointer_writes_astrid_session(self):
        writers = _find_session_pointer_writers()
        assert len(writers) == 1, (
            f"Expected exactly 1 function writing .astrid-session, got {len(writers)}: {writers}\n"
            f"Expected: {_EXPECTED_WRITER}"
        )
        assert writers[0] == _EXPECTED_WRITER, (
            f"Expected writer {_EXPECTED_WRITER!r}, got {writers[0]!r}"
        )

    def test_write_session_pointer_signature(self):
        """Verify write_session_pointer accepts the required parameters."""
        import inspect
        from astrid.core.session.lifecycle import write_session_pointer

        sig = inspect.signature(write_session_pointer)
        params = list(sig.parameters.keys())
        # Keyword-only parameters
        assert "project_slug" in params, f"Missing project_slug param: {params}"
        assert "session_id" in params, f"Missing session_id param: {params}"
        assert "projects_root" in params, f"Missing projects_root param: {params}"


# ---------------------------------------------------------------------------
# Test: delegation chain — cmd_attach → attach_session → lifecycle
# ---------------------------------------------------------------------------

class TestCmdAttachDelegation:
    """Verify cmd_attach passes write_project_pointer=True to attach_session."""

    def test_cmd_attach_imports_attach_session(self):
        """cmd_attach relies on attach_session from binding module."""
        import inspect
        from astrid.core.session.cli import cmd_attach

        source = inspect.getsource(cmd_attach)
        assert "attach_session(" in source, (
            "cmd_attach must call attach_session"
        )
        assert "write_project_pointer=True" in source, (
            "cmd_attach must pass write_project_pointer=True to attach_session"
        )

    def test_attach_session_passes_through_to_lifecycle(self):
        """attach_session passes write_project_pointer to create_session/open_session."""
        import inspect
        from astrid.core.session.binding import attach_session

        source = inspect.getsource(attach_session)
        assert "write_project_pointer" in source, (
            "attach_session must forward write_project_pointer"
        )

    def test_lifecycle_create_session_writes_pointer(self):
        """create_session writes project pointer when write_project_pointer=True."""
        import inspect
        from astrid.core.session.lifecycle import create_session

        source = inspect.getsource(create_session)
        assert "write_project_pointer" in source, (
            "create_session must handle write_project_pointer"
        )
        assert "write_session_pointer" in source, (
            "create_session must call write_session_pointer"
        )

    def test_lifecycle_open_session_writes_pointer(self):
        """open_session writes project pointer when write_project_pointer=True."""
        import inspect
        from astrid.core.session.lifecycle import open_session

        source = inspect.getsource(open_session)
        assert "write_project_pointer" in source, (
            "open_session must handle write_project_pointer"
        )
        assert "write_session_pointer" in source, (
            "open_session must call write_session_pointer"
        )
