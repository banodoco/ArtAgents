"""Assert exactly ONE HYPE_ACTIVE_THEME writer: the runner's scoped-config emit.

This is the regression gate for T7 — deleting the implicit env writer from
hype/parser.py leaves ONLY the runner as the canonical emission point.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ASTRID_DIR = REPO_ROOT / "astrid"

# Patterns that match HYPE_ACTIVE_THEME / ACTIVE_THEME_ENV SET (assignment)
# in production code. We exclude _spike and test files.
_WRITER_PATTERN = r'(?:os\.environ|env)\[[^\]]*(?:ACTIVE_THEME_ENV|HYPE_ACTIVE_THEME)[^\]]*\]\s*='


def _run_grep(pattern: str, path: str) -> list[str]:
    """Run ripgrep and return matching lines (non-test, non-_spike)."""
    try:
        result = subprocess.run(
            [
                "rg", "--no-heading", "-n",
                "--glob", "!**/_spike/**",
                "--glob", "!**/tests/**",
                pattern, path,
            ],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        # Fall back to grep -rP if rg is not available
        result = subprocess.run(
            ["grep", "-rnP", pattern, path],
            capture_output=True, text=True, timeout=30,
        )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines


def test_no_direct_os_environ_theme_writers():
    """No production code should write HYPE_ACTIVE_THEME via os.environ directly."""
    pattern = r'os\.environ\[[^\]]*(?:ACTIVE_THEME_ENV|HYPE_ACTIVE_THEME)[^\]]*\]\s*='
    lines = _run_grep(pattern, str(ASTRID_DIR))
    assert len(lines) == 0, (
        f"Found {len(lines)} direct os.environ writer(s) for "
        f"HYPE_ACTIVE_THEME/ACTIVE_THEME_ENV:\n" + "\n".join(lines)
    )


def test_exactly_one_theme_env_writer():
    """Exactly ONE production-code site sets HYPE_ACTIVE_THEME: the runner."""
    lines = _run_grep(_WRITER_PATTERN, str(ASTRID_DIR))
    assert len(lines) == 1, (
        f"Expected exactly 1 HYPE_ACTIVE_THEME writer (runner), "
        f"found {len(lines)}:\n" + "\n".join(lines)
    )
    # The single writer must be in executor/runner.py
    assert "executor/runner.py" in lines[0] or "runner.py" in lines[0], (
        f"Single writer is not in runner.py:\n{lines[0]}"
    )


def test_project_run_env_no_implicit_theme():
    """project_run_env with no project_slug returns only PROJECT_RUN_ENV."""
    from astrid.core.env_vars import ASTRID_PROJECT_RUN as PROJECT_RUN_ENV
    from astrid.core.project.run import project_run_env

    env = project_run_env(None)
    assert env == {PROJECT_RUN_ENV: "1"}, (
        f"project_run_env(None) should return only PROJECT_RUN_ENV, got {env}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
