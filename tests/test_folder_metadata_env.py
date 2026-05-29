from __future__ import annotations

from pathlib import Path

from astrid.core.executor.folder import load_folder_executor
from astrid.core.orchestrator.folder import load_folder_orchestrator


def test_folder_executor_metadata_uses_controlled_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_FOLDER_SECRET", "leaked")
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
