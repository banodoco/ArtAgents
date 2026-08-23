"""External pack contract proof.

Verifies that a pack fixture placed outside the repository and loaded
via ``ASTRID_PACKS_PATH`` is discovered with ``source_kind == "env"``
and its elements are resolvable through the public SDK using only
``import astrid``.  The test file itself avoids internal imports
(``astrid.core``, ``astrid.packs``, ``tests.``).

The fixture lives under ``tests/fixtures/external_pack/`` and contains
only reviewable static files: ``pack.yaml``, ``element.yaml``, and
``component.tsx``.  No Python files.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helper: check the fixture directory for Python files / banned imports
# ---------------------------------------------------------------------------

def _with_repo_pythonpath(env: dict[str, str]) -> dict[str, str]:
    updated = dict(env)
    existing = updated.get("PYTHONPATH")
    updated["PYTHONPATH"] = str(_REPO_ROOT) if not existing else os.pathsep.join((str(_REPO_ROOT), existing))
    return updated


def _assert_fixture_has_no_python_files(fixture_root: Path) -> None:
    """Fail if the fixture directory contains any ``.py`` file."""
    py_files = list(fixture_root.rglob("*.py"))
    assert not py_files, (
        f"Fixture must contain no Python files; found: {py_files}"
    )


# ---------------------------------------------------------------------------
# AST self-check: the test file must avoid internal imports
# ---------------------------------------------------------------------------

def _ast_check_self() -> None:
    """Verify *this* test file does not import from banned internal modules."""
    module_path = Path(__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    banned_prefixes = ("astrid.core", "astrid.packs", "tests.")
    allowed_modules: set[str] = set()

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
# External script source (the proof runs via subprocess from outside repo)
# ---------------------------------------------------------------------------

_EXTERNAL_PACK_SCRIPT = (
    "import json, os, sys\n"
    "import astrid\n"
    "\n"
    "def _check() -> dict:\n"
    '    inventory = astrid.discover(include_installed=False)\n'
    "\n"
    '    env_packs = [p for p in inventory.packs if p.get("source_kind") == "env"]\n'
    '    assert len(env_packs) >= 1, f"Expected >=1 env pack, got {len(env_packs)}"\n'
    "\n"
    '    external_pack = next((p for p in env_packs if p["id"] == "external_pack"), None)\n'
    '    assert external_pack is not None, "external_pack not found in env packs"\n'
    '    assert external_pack["source_kind"] == "env"\n'
    "\n"
    '    glow = astrid.get_capability(\n'
    '        "glow",\n'
    '        kind="element",\n'
    '        element_kind="widget",\n'
    '        include_installed=False,\n'
    "    )\n"
    '    # Capability.id uses canonical kind/id form (kind is plural canonical)\n'
    '    assert glow.id == "widgets/glow", f"unexpected id: {glow.id}"\n'
    '    assert glow.capability_type == "element"\n'
    '    assert glow.native_kind == "widgets"\n'
    "\n"
    "    return {\n"
    '        "pack_ids": [p["id"] for p in env_packs],\n'
    '        "external_pack_source_kind": external_pack["source_kind"],\n'
    '        "glow_id": glow.id,\n'
    '        "glow_capability_type": glow.capability_type,\n'
    '        "glow_native_kind": glow.native_kind,\n'
    "    }\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    result = _check()\n"
    "    json.dump(result, sys.stdout, sort_keys=True)\n"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fixture_has_no_python_files() -> None:
    """The static fixture must not contain Python source files."""
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "external_pack"
    assert fixture_root.is_dir(), f"Missing fixture: {fixture_root}"
    _assert_fixture_has_no_python_files(fixture_root)


def test_external_pack_via_env_path() -> None:
    """Copy the fixture outside the repo, set ``ASTRID_PACKS_PATH``,
    run a subprocess that uses only ``import astrid``, and assert the
    pack is discovered as ``source_kind == "env"`` and its ``glow``
    widget element resolves correctly."""

    fixture_src = Path(__file__).resolve().parent / "fixtures" / "external_pack"
    assert fixture_src.is_dir(), f"Missing fixture: {fixture_src}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Copy the entire fixture tree to the temp directory
        pack_dest = tmp_path / "external_pack"
        shutil.copytree(fixture_src, pack_dest)

        # Write the external script
        script_path = tmp_path / "check.py"
        script_path.write_text(_EXTERNAL_PACK_SCRIPT, encoding="utf-8")

        # AST-validate the external script
        tree = ast.parse(
            script_path.read_text(encoding="utf-8"),
            filename=str(script_path),
        )
        banned_prefixes = ("astrid.core", "astrid.packs", "tests.")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        raise AssertionError(
                            f"External script imports banned: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(banned_prefixes):
                    raise AssertionError(
                        f"External script imports from banned: {module}"
                    )
                if module == "astrid" or module.startswith("astrid."):
                    raise AssertionError(
                        f"External script uses 'from astrid' import: {module}"
                    )

        # Run the check script with ASTRID_PACKS_PATH set to the
        # copied root, cwd outside the repo
        env = os.environ.copy()
        env["ASTRID_PACKS_PATH"] = str(tmp_path)
        env = _with_repo_pythonpath(env)

        completed = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=60,
        )

        assert completed.returncode == 0, (
            f"External pack script exited {completed.returncode}\n"
            f"STDERR:\n{completed.stderr}"
        )

        result = json.loads(completed.stdout)

        assert "external_pack" in result["pack_ids"], (
            f"external_pack missing from env packs: {result['pack_ids']}"
        )
        assert result["external_pack_source_kind"] == "env"
        assert result["glow_id"] == "widgets/glow", f"unexpected glow_id: {result['glow_id']}"
        assert result["glow_capability_type"] == "element"
        assert result["glow_native_kind"] == "widgets"


def test_external_pack_python_executor_validates_and_runs() -> None:
    """An env-discovered external pack can expose a top-level Python module executor."""
    pack_id = "external_py_exec"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pack_root = tmp_path / pack_id
        exec_root = pack_root / "executors" / "echo"
        exec_root.mkdir(parents=True)
        (pack_root / "pack.yaml").write_text(
            f"""\
schema_version: 1
id: {pack_id}
name: External Python Executor
version: 0.1.0
description: External Python executor contract fixture.
content:
  executors: executors
agent:
  purpose: Testing external Python executor dispatch.
  entrypoints:
    - validate
""",
            encoding="utf-8",
        )
        (pack_root / "AGENTS.md").write_text("# External Python Executor\n", encoding="utf-8")
        (pack_root / "README.md").write_text("# External Python Executor\n", encoding="utf-8")
        (exec_root / "STAGE.md").write_text("# Echo\n", encoding="utf-8")
        (exec_root / "executor.yaml").write_text(
            f"""\
schema_version: 1
id: {pack_id}.echo
name: Echo
kind: external
version: 0.1.0
description: Writes a JSON marker file.
command:
  argv:
    - "{{python_exec}}"
    - "-m"
    - "{pack_id}.executors.echo.run"
    - "--out"
    - "{{out}}/result.json"
metadata:
  runtime_module: {pack_id}.executors.echo.run
""",
            encoding="utf-8",
        )
        (exec_root / "run.py").write_text(
            """\
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": True}) + "\\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["ASTRID_PACKS_PATH"] = str(tmp_path)
        env = _with_repo_pythonpath(env)

        # Validate through the surviving in-process APIs, run in a subprocess
        # so this test file stays free of internal imports (the ``packs`` and
        # ``executors`` CLI verbs were retired with the legacy runtime).
        validate_script = tmp_path / "validate.py"
        validate_script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "from astrid.core.pack.validate import validate_pack\n"
            "from astrid.core.execution.executor.schema import load_executor_manifest_definitions\n"
            "pack_root = Path(sys.argv[1])\n"
            "errors, warnings = validate_pack(pack_root)\n"
            "assert not errors, f'pack validation failed: {errors}'\n"
            "defs = load_executor_manifest_definitions(\n"
            "    pack_root / 'executors' / 'echo' / 'executor.yaml'\n"
            ")\n"
            f"assert [d.id for d in defs] == ['{pack_id}.echo'], [d.id for d in defs]\n"
            "print('valid')\n",
            encoding="utf-8",
        )
        validate = subprocess.run(
            [sys.executable, str(validate_script), str(pack_root)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=60,
        )
        assert validate.returncode == 0, (
            f"External Python pack failed validation\nSTDOUT:\n{validate.stdout}\nSTDERR:\n{validate.stderr}"
        )

        # Run the executor through the kernel-admitted internal boundary.  The
        # supplied directory is staging; the runner must not create a second
        # filesystem run ledger.
        projects_root = tmp_path / "projects"
        run_script = tmp_path / "run_executor.py"
        run_script.write_text(
            "import os, sys\n"
            "from pathlib import Path\n"
            "os.environ['ASTRID_PROJECTS_ROOT'] = sys.argv[2]\n"
            "os.chdir(sys.argv[1])\n"
            "from astrid.core.project.project import create_project\n"
            "from astrid.core.timeline.crud import create_timeline\n"
            "create_project('demo')\n"
            "create_timeline('demo', 'main', is_default=True)\n"
            "from astrid.core.execution.executor.registry import load_default_registry\n"
            "from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor\n"
            "registry = load_default_registry(include_installed=False)\n"
            "staging = Path(sys.argv[2]) / 'demo' / '.astrid' / 'media' / '.staging' / 'external-pack'\n"
            "result = run_executor(\n"
            "    ExecutorRunRequest(\n"
            f"        executor_id='{pack_id}.echo',\n"
            "        out=staging,\n"
            "        project='demo',\n"
            "        python_exec=sys.executable,\n"
            "        project_was_auto_resolved=True,\n"
            "    ),\n"
            "    registry,\n"
            ")\n"
            "assert result.ok, str(result.error)\n"
            "assert result.run_root is None\n"
            "assert (staging / 'result.json').is_file(), 'result.json not written'\n"
            "assert not list((Path(sys.argv[2]) / 'demo' / 'runs').glob('**/run.json'))\n"
            "print('ran')\n",
            encoding="utf-8",
        )
        run = subprocess.run(
            [sys.executable, str(run_script), str(tmp_path), str(projects_root)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=60,
        )
        assert run.returncode == 0, (
            f"External Python executor failed\nSTDOUT:\n{run.stdout}\nSTDERR:\n{run.stderr}"
        )
        assert (
            projects_root
            / "demo"
            / ".astrid"
            / "media"
            / ".staging"
            / "external-pack"
            / "result.json"
        ).is_file()


def test_test_file_itself_avoids_internal_imports() -> None:
    """The contract test file must itself avoid importing from
    ``astrid.core``, ``astrid.packs``, or ``tests.*``."""
    _ast_check_self()
