"""Assert exactly ONE HYPE_ACTIVE_THEME writer: the runner's scoped-config emit.

This is the regression gate for T7 — deleting the implicit env writer from
hype/parser.py leaves ZERO direct os.environ writers and validates that the
runner owns the canonical env-dict emission.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ASTRID_DIR = REPO_ROOT / "astrid"

# Direct os.environ write pattern (the implicit-writer class being deleted).
_OS_ENVIRON_WRITE = (
    r'os\.environ\[[^\]]*(?:ACTIVE_THEME_ENV|HYPE_ACTIVE_THEME)[^\]]*\]\s*='
)

# Any env-dict write that sets HYPE_ACTIVE_THEME or ACTIVE_THEME_ENV.
_ENV_DICT_WRITE = (
    r'env\[[^\]]*(?:ACTIVE_THEME_ENV|HYPE_ACTIVE_THEME)[^\]]*\]\s*='
)


def _run_grep(pattern: str, path: str) -> list[str]:
    """Run ripgrep and return matching lines (non-test, non-_spike)."""
    try:
        result = subprocess.run(
            [
                "rg", "--no-heading", "-n",
                "--glob", "!**/_spike/**",
                "--glob", "!**/tests/**",
                pattern, str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        result = subprocess.run(
            ["grep", "-rnP", pattern, str(path)],
            capture_output=True, text=True, timeout=30,
        )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines


def test_no_direct_os_environ_theme_writers():
    """No production code may write HYPE_ACTIVE_THEME via os.environ directly.

    The runner is the SINGLE emission point and writes to a subprocess env dict,
    never to os.environ.  Any os.environ write is a regression of the T7
    implicit-writer cleanup (hype/parser.py's ``os.environ[ACTIVE_THEME_ENV]=``).
    """
    lines = _run_grep(_OS_ENVIRON_WRITE, str(ASTRID_DIR))
    assert len(lines) == 0, (
        f"Found {len(lines)} direct os.environ writer(s) for "
        f"HYPE_ACTIVE_THEME/ACTIVE_THEME_ENV:\n" + "\n".join(lines)
    )


def test_runner_is_the_canonical_theme_writer():
    """The runner (executor/runner.py) emits HYPE_ACTIVE_THEME via scoped-config.

    The runner's ``_emit_scoped_config_env`` is the canonical writer.  We assert
    that at least one writer exists in runner.py (the scoped-config emit) and
    that no OTHER file contains a direct os.environ write.
    """
    # Find all dict-based writers
    all_lines = _run_grep(_ENV_DICT_WRITE, str(ASTRID_DIR))

    runner_writers = [l for l in all_lines if "executor/runner.py" in l]
    assert len(runner_writers) >= 1, (
        f"Runner must have at least one HYPE_ACTIVE_THEME writer; "
        f"found 0 in:\n" + "\n".join(all_lines)
    )

    # The runner's scoped-config emit must be present (line ~953)
    scoped_emit = [l for l in runner_writers if "scoped-config emit" in l]
    assert len(scoped_emit) == 1, (
        f"Expected exactly 1 scoped-config emit comment in runner, "
        f"found {len(scoped_emit)}:\n" + "\n".join(runner_writers)
    )

    # No other file may use os.environ directly for this env var
    os_lines = _run_grep(_OS_ENVIRON_WRITE, str(ASTRID_DIR))
    assert len(os_lines) == 0, (
        f"Found {len(os_lines)} direct os.environ writer(s):\n"
        + "\n".join(os_lines)
    )


def test_project_run_env_no_implicit_theme():
    """project_run_env with no project_slug returns only PROJECT_RUN_ENV."""
    from astrid.core.env_vars import ASTRID_PROJECT_RUN as PROJECT_RUN_ENV
    from astrid.core.project.runtime import project_run_env

    env = project_run_env(None)
    assert env == {PROJECT_RUN_ENV: "1"}, (
        f"project_run_env(None) should return only PROJECT_RUN_ENV, got {env}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
