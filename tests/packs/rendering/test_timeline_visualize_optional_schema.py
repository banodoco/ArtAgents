"""Clean-install regression for the optional canonical timeline schema."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_parity_suite_runs_without_external_schema_package() -> None:
    """Only the canonical-schema cases may skip when the package is absent."""

    blocker = r'''
import importlib.abc
import sys


class _BlockTimelineSchema(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "banodoco_timeline_schema" or fullname.startswith(
            "banodoco_timeline_schema."
        ):
            raise ModuleNotFoundError(
                "blocked by clean-install regression", name="banodoco_timeline_schema"
            )
        return None


sys.meta_path.insert(0, _BlockTimelineSchema())
import pytest

raise SystemExit(
    pytest.main(
        [
            "-q",
            "--disable-warnings",
            "tests/packs/rendering/test_timeline_visualize_parity.py",
        ]
    )
)
'''
    result = subprocess.run(
        [sys.executable, "-c", blocker],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "28 passed" in output, output
    assert "10 skipped" in output, output
