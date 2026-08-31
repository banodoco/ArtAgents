"""Regression coverage for the first zero-shim import slice."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_project_theme_and_timeline_edges_are_absent_from_static_sources() -> None:
    project_schema = ast.parse(_source("astrid/core/project/schema.py"))
    theme_scope = ast.parse(_source("astrid/core/theme/scope.py"))
    imports = [
        node.module or ""
        for tree in (project_schema, theme_scope)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    assert "astrid.core.timeline.paths" not in imports
    assert "astrid.core.project.project" not in imports


def test_remote_and_contract_imports_are_cold_in_a_fresh_process() -> None:
    probe = """
import sys
import astrid.sdk.remote
import astrid.sdk.contracts
assert 'sqlite3' not in sys.modules
assert 'astrid.core.receipts.service' not in sys.modules
assert not any(name.startswith('astrid.core.store') for name in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr


def test_project_style_resolution_uses_injected_snapshot() -> None:
    from astrid.core.contracts.project_theme import ProjectStyleSnapshot
    from astrid.core.contracts.scoped_config import ScopeRequest
    from astrid.core.theme.scope import resolve_style_scope

    snapshot = ProjectStyleSnapshot(project_slug="demo", theme_id="project-theme")
    resolved = resolve_style_scope(ScopeRequest(project_slug="demo", project_style=snapshot))
    assert resolved.theme_dir == (ROOT / "themes" / "project-theme").resolve()


def test_timeline_identifiers_are_neutral_and_still_validate() -> None:
    from astrid.core.contracts.identifiers import validate_timeline_slug, validate_timeline_ulid

    assert validate_timeline_slug("primary") == "primary"
    assert validate_timeline_ulid("01ARZ3NDEKTSV4RRFFQ69G5FAV")
