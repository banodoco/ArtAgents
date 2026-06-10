from __future__ import annotations

import sys
from pathlib import Path

from astrid.core.execution.executor.folder import load_folder_executor
from astrid.core.execution.orchestrator.folder import load_folder_orchestrator

# Unique sentinel placed on ``sys.path`` so the assertion does not depend on the
# checkout directory name (the loader builds the child PYTHONPATH from
# ``sys.path``). This keeps the test green in any worktree.
_PYTHONPATH_SENTINEL = "astrid-quality-sprint"


def test_folder_executor_metadata_uses_controlled_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_FOLDER_SECRET", "leaked")
    monkeypatch.syspath_prepend(_PYTHONPATH_SENTINEL)
    root = tmp_path / "folder_exec"
    root.mkdir()
    (root / "executor.py").write_text(
        """
import os

EXECUTOR = {
    "id": "test.folder_exec",
    "name": "Folder Exec",
    "kind": "external",
    "version": "1.0",
    "metadata": {
        "has_repo_pythonpath": "astrid-quality-sprint" in os.environ.get("PYTHONPATH", ""),
        "secret": os.environ.get("ASTRID_FOLDER_SECRET", ""),
    },
    "command": {"argv": ["python3", "-c", "pass"]},
}
""",
        encoding="utf-8",
    )

    definition = load_folder_executor(root)

    assert definition.metadata["has_repo_pythonpath"] is True
    assert "secret" not in definition.metadata


def test_folder_orchestrator_metadata_uses_controlled_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_FOLDER_SECRET", "leaked")
    monkeypatch.syspath_prepend(_PYTHONPATH_SENTINEL)
    root = tmp_path / "folder_orch"
    root.mkdir()
    (root / "orchestrator.py").write_text(
        """
import os

ORCHESTRATOR = {
    "id": "test.folder_orch",
    "name": "Folder Orch",
    "kind": "built_in",
    "version": "1.0",
    "metadata": {
        "has_repo_pythonpath": "astrid-quality-sprint" in os.environ.get("PYTHONPATH", ""),
        "secret": os.environ.get("ASTRID_FOLDER_SECRET", ""),
    },
    "runtime": {"kind": "command", "command": {"argv": ["python3", "-c", "pass"]}},
}
""",
        encoding="utf-8",
    )

    definition = load_folder_orchestrator(root)

    assert definition.metadata["has_repo_pythonpath"] is True
    assert "secret" not in definition.metadata
