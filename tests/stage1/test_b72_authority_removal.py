"""B7.2 negative proof for the generated-client cutover boundary."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_product_parser_graph_does_not_load_local_authority() -> None:
    """Nested product parsers must be importable without SQLite/repositories."""
    probe = (
        "import sys; "
        "from astrid.core.cli.domain_media import build_parser as media; "
        "from astrid.packs.references.cli import build_parser as references; "
        "from astrid.packs.shots.cli import build_parser as shots; "
        "print('sqlite3' in sys.modules); "
        "print(any(name.startswith('astrid.core.store') or "
        "name.startswith('astrid.core.repositories') or "
        "name.endswith('.repository') for name in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]


def test_removed_media_realm_and_render_execution_mode_are_absent() -> None:
    media = _source("astrid/core/cli/domain_media.py")
    render = _source("astrid/packs/rendering/executors/render/task_adapter.py")
    assert "external_local" not in media
    assert 'execution_mode="in_process"' not in render


def test_product_parsers_have_no_repository_imports() -> None:
    for relative in (
        "astrid/core/cli/domain_media.py",
        "astrid/packs/references/cli.py",
        "astrid/packs/shots/cli.py",
    ):
        tree = ast.parse(_source(relative), filename=relative)
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any(module.endswith(".repository") for module in imported), relative


def test_shots_repository_module_has_no_sqlite_authority_import() -> None:
    source = _source("astrid/packs/shots/repository.py")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "sqlite3" not in imported
    assert "astrid.core.store.writer" not in {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
