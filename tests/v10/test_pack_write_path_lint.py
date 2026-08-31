"""Pack write-path lint (adherence item 6).

Pack event writes must route through the pack repositories' own methods —
never through legacy timeline event-log entrypoints. This lint scans the v10
schema packs and the live cut/assemble/refine task workers and forbids:

- calls to ``pack_write_gateway``, ``EventLogBackend``, or any
  ``append_event`` call target — the direct event-append entrypoints
  (``astrid/packs/timeline/repository.py`` is allow-listed: it is the
  sanctioned pack write path);
- taking the ``astrid.core.store`` module handle (``import
  astrid.core.store`` / ``from astrid.core import store`` /
  ``from astrid.core.store import ...``) — the single-writer authority.
  Typed submodule imports (``from astrid.core.store.writer import
  DatabaseWriter``) are the documented caller-supplied-writer injection
  seam (authority-lint negative control) and stay legal: the pack receives
  the kernel writer, it never opens one;
- constructing a writer (``DatabaseWriter(...)`` / ``sqlite3.connect``) —
  writer construction lives in ``astrid/core/store`` and the composition
  root ``astrid/packs/__init__.py`` only.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PACKS_ROOT = _ROOT / "astrid" / "packs"

_SCHEMA_PACKS: tuple[str, ...] = ("timeline", "shots", "references")
_TASK_WORKER_ROOTS: tuple[Path, ...] = (
    _PACKS_ROOT / "video_editing/executors/cut",
    _PACKS_ROOT / "iteration/executors/assemble",
    _PACKS_ROOT / "editorial/executors/refine",
)

# Event-append entrypoints a pack must never call directly.
_FORBIDDEN_CALL_TAILS: tuple[str, ...] = ("pack_write_gateway", "append_event")
_FORBIDDEN_BACKEND_NAME = "EventLogBackend"

# The schema timeline repository is the sole sanctioned pack write path.
_ALLOWED_ENTRYPOINT_FILES: frozenset[Path] = frozenset(
    {
        _ROOT / "astrid/packs/timeline/repository.py",
    }
)


def _schema_pack_sources() -> list[Path]:
    schema_files = [
        path
        for pack in _SCHEMA_PACKS
        for path in sorted((_PACKS_ROOT / pack).rglob("*.py"))
    ]
    worker_files = [
        path
        for worker_root in _TASK_WORKER_ROOTS
        for path in sorted(worker_root.rglob("*.py"))
    ]
    if not schema_files or not worker_files:
        raise AssertionError("write-path lint did not scan every required source root")
    return schema_files + worker_files


def _dotted_tail(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _forbidden_entrypoint_reference(node: ast.AST) -> bool:
    """Whether one AST node references a forbidden event-append entrypoint."""
    if isinstance(node, ast.Call):
        tail = _dotted_tail(node.func)
        if any(tail == name or tail.endswith("." + name) for name in _FORBIDDEN_CALL_TAILS):
            return True
        if tail == _FORBIDDEN_BACKEND_NAME or tail.endswith("." + _FORBIDDEN_BACKEND_NAME):
            return True
    if isinstance(node, ast.Name) and node.id == _FORBIDDEN_BACKEND_NAME:
        return True
    if isinstance(node, ast.Attribute) and node.attr == _FORBIDDEN_BACKEND_NAME:
        return True
    return False


def _writer_construction(node: ast.AST) -> bool:
    """Whether one AST node constructs a write authority."""
    if not isinstance(node, ast.Call):
        return False
    tail = _dotted_tail(node.func)
    if tail == "DatabaseWriter" or tail.endswith(".DatabaseWriter"):
        return True
    if tail == "sqlite3.connect" or tail.endswith(".sqlite3.connect"):
        return True
    return False


def _store_module_handle_imports(tree: ast.AST) -> list[str]:
    """Import statements taking the ``astrid.core.store`` module handle."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "astrid.core.store":
                    errors.append("imports astrid.core.store (module handle)")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "astrid.core.store":
                errors.append("from astrid.core.store import ... (module handle)")
            elif node.module == "astrid.core":
                for alias in node.names:
                    if alias.name == "store":
                        errors.append("from astrid.core import store (module handle)")
    return errors


def _lint_source(path: Path) -> list[str]:
    """One file's write-path violations: ``(line, message)`` strings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    entrypoint_allowed = path.resolve() in _ALLOWED_ENTRYPOINT_FILES
    errors: list[str] = []
    for node in ast.walk(tree):
        if _forbidden_entrypoint_reference(node):
            if not entrypoint_allowed:
                label = (
                    _dotted_tail(node.func)
                    if isinstance(node, ast.Call)
                    else _FORBIDDEN_BACKEND_NAME
                )
                errors.append(
                    f"line {getattr(node, 'lineno', '?')}: references event-append "
                    f"entrypoint {label!r}"
                )
        if _writer_construction(node):
            assert isinstance(node, ast.Call)
            errors.append(
                f"line {getattr(node, 'lineno', '?')}: constructs a write "
                f"authority ({_dotted_tail(node.func)})"
            )
    for message in _store_module_handle_imports(tree):
        errors.append(message)
    return errors


def test_schema_pack_code_never_calls_event_append_entrypoints() -> None:
    """Pack event writes route through repository methods, never the legacy
    event-log entrypoints (``pack_write_gateway`` / ``EventLogBackend`` /
    ``append_event``)."""
    violations: list[str] = []
    for path in _schema_pack_sources():
        for message in _lint_source(path):
            violations.append(f"{path.relative_to(_ROOT)}: {message}")
    assert not violations, "\n".join(violations)


def test_schema_pack_code_never_takes_the_store_module_handle() -> None:
    """Packs never import ``astrid.core.store`` (single-writer authority);
    they receive the kernel writer by injection instead."""
    violations: list[str] = []
    for path in _schema_pack_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for message in _store_module_handle_imports(tree):
            violations.append(f"{path.relative_to(_ROOT)}: {message}")
    assert not violations, "\n".join(violations)
