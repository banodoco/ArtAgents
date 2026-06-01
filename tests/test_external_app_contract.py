from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# External app script source -- must only use `import astrid` + stdlib.
# This string is written to a temporary file outside the repo and executed
# via subprocess.
# ---------------------------------------------------------------------------
_EXTERNAL_APP_SCRIPT = dedent("""\
import json
import sys

import astrid  # public SDK boundary -- no `from astrid ...` allowed

def _run() -> dict[str, object]:
    inventory = astrid.discover(include_installed=False)

    # Prove we got real executors and orchestrators
    executor_ids = [c.id for c in inventory.executors]
    orchestrator_ids = [c.id for c in inventory.orchestrators]
    element_ids = [c.id for c in inventory.elements]

    # Resolve a known executor through the public SDK
    cap = astrid.get_capability("editorial.arrange", kind="executor", include_installed=False)
    alias_cap = astrid.get_capability(
        "editorial.inspect_cut", kind="executor", include_installed=False,
    )

    return {
        "executor_count": len(executor_ids),
        "orchestrator_count": len(orchestrator_ids),
        "element_count": len(element_ids),
        "has_arrange": "editorial.arrange" in executor_ids,
        "arrange_id": cap.id,
        "arrange_capability_type": cap.capability_type,
        "alias_aliases": [a.alias for a in alias_cap.handle.aliases],
        "packs": [p["id"] for p in inventory.packs if p.get("source_kind") == "source"],
    }


if __name__ == "__main__":
    result = _run()
    json.dump(result, sys.stdout, sort_keys=True)
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ast_check_script(script_path: Path) -> None:
    """Parse *script_path* and assert it has no banned internal imports."""
    tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    banned_prefixes = ("astrid.core", "astrid.packs", "tests.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Only `import astrid` is allowed; forbid `import astrid.core` etc.
                if alias.name.startswith(banned_prefixes):
                    raise AssertionError(
                        f"External app script imports banned module: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(banned_prefixes):
                raise AssertionError(
                    f"External app script imports from banned module: {module}"
                )
            # `from astrid import ...` is banned; only `import astrid` allowed.
            if module == "astrid" or module.startswith("astrid."):
                raise AssertionError(
                    f"External app script uses 'from astrid' import: from {module} import ..."
                )


def _ast_check_self() -> None:
    """Verify *this* test file does not import from banned internal modules."""
    module_path = Path(__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    banned_prefixes = ("astrid.core", "astrid.packs", "tests.")
    allowed_modules = {"tests._sdk_contract"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(banned_prefixes), (
                    f"Test file self-imports banned module: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in allowed_modules:
                continue
            assert not module.startswith(banned_prefixes), (
                f"Test file imports from banned module: {module}"
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_external_app_runs_from_outside_repo() -> None:
    """Write the external app script to a temp directory, run it via
    subprocess, and verify it exercises the public SDK correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        app_path = tmp_path / "app.py"
        app_path.write_text(_EXTERNAL_APP_SCRIPT, encoding="utf-8")

        # AST-check the external script before execution
        _ast_check_script(app_path)

        completed = subprocess.run(
            [sys.executable, str(app_path)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=60,
        )

        assert completed.returncode == 0, (
            f"External app exited {completed.returncode}\n"
            f"STDERR:\n{completed.stderr}"
        )

        result: dict[str, Any] = json.loads(completed.stdout)

        assert result["executor_count"] > 0
        assert result["orchestrator_count"] > 0
        assert result["element_count"] > 0
        assert result["has_arrange"] is True
        assert result["arrange_id"] == "editorial.arrange"
        assert result["arrange_capability_type"] == "executor"
        assert "builtin.inspect_cut" in result["alias_aliases"]


def test_external_app_script_rejects_from_astrid_imports() -> None:
    """Prove that an external app using `from astrid import ...` (or any
    `from astrid.xxx ...`) is rejected by the AST guard."""
    bad_scripts = [
        # from astrid import discover
        "import json, sys\nfrom astrid import discover\n",
        # import astrid.core  (sub-module bypass)
        "import json, sys\nimport astrid.core.executor.registry\n",
        # from astrid.sdk import discover
        "import json, sys\nfrom astrid.sdk import discover\n",
        # from astrid.packs.builtin import run
        "import json, sys\nfrom astrid.packs.builtin import run\n",
    ]

    for idx, script_src in enumerate(bad_scripts):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_path = tmp_path / f"bad_app_{idx}.py"
            app_path.write_text(script_src, encoding="utf-8")

            with pytest.raises(AssertionError):
                _ast_check_script(app_path)


def test_test_file_itself_avoids_internal_imports() -> None:
    """The contract test file must itself avoid importing from
    astrid.core, astrid.packs, or tests.* (except tests._sdk_contract)."""
    _ast_check_self()
