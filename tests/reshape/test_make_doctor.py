"""Regression coverage for the Makefile doctor target's clean-checkout mode."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import TracebackType

from scripts.reshape import ci_doctor

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_make_doctor_owns_disposable_root_when_ambient_root_is_missing(
    tmp_path: Path,
) -> None:
    """A clean checkout must not require or populate repo/projects/.astrid."""
    ambient_root = tmp_path / "ambient-projects-root-that-must-stay-absent"
    env = os.environ.copy()
    env["ASTRID_PROJECTS_ROOT"] = str(ambient_root)

    result = subprocess.run(
        ["make", "--no-print-directory", "doctor", f"PY={sys.executable}"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"make doctor failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not ambient_root.exists()


def test_doctor_still_fails_closed_for_an_uninitialized_explicit_root(
    tmp_path: Path,
) -> None:
    """The CI wrapper must not weaken doctor’s missing-database contract."""
    missing_root = tmp_path / "missing-projects-root"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "astrid",
            "doctor",
            "--json",
            "--projects-root",
            str(missing_root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert {check["name"] for check in payload["checks"] if check["status"] == "fail"} >= {
        "data_paths",
        "sqlite_quick_check",
        "fk_integrity",
        "schema_versions",
    }


def test_ci_doctor_cleans_disposable_root(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The helper removes its initialized root after both subprocesses finish."""
    real_temporary_directory = ci_doctor.tempfile.TemporaryDirectory
    created_roots: list[Path] = []

    class TrackingTemporaryDirectory:
        def __init__(self, *, prefix: str | None = None) -> None:
            self._delegate = real_temporary_directory(prefix=prefix)
            self.path: Path | None = None

        def __enter__(self) -> str:
            root = self._delegate.__enter__()
            self.path = Path(root)
            created_roots.append(self.path)
            return root

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            self._delegate.__exit__(exc_type, exc_value, traceback)
            assert self.path is not None
            assert not self.path.exists()

    monkeypatch.setattr(ci_doctor.tempfile, "TemporaryDirectory", TrackingTemporaryDirectory)
    assert ci_doctor.main() == 0
    assert len(created_roots) == 1
