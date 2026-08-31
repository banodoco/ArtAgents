"""Static-grep regression gate: no legacy theme globals or secret leaks.

This is the static-grep half of the T12 cleanup — asserting that the
ambient-global infrastructure (``_ACTIVE_THEME_DIR``, ``set_active_theme``)
and implicit secrets propagation (``os.environ.setdefault('FAL_KEY')``,
``os.environ['FAL_KEY']=``) are fully removed from production code.

Run via pytest or directly with ``python``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ASTRID_DIR = REPO_ROOT / "astrid"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Legacy theme globals — must be ZERO hits in production code.
_THEME_GLOBALS_PATTERN = r'_ACTIVE_THEME_DIR|set_active_theme'

# Direct os.environ secret writes — must be ZERO hits in production code.
_SECRETS_OS_ENVIRON_PATTERN = (
    r'os\.environ\[.FAL_KEY.\]|os\.environ\.setdefault\(.FAL_KEY.'
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_grep(pattern: str, path: str, *, exclude_tests: bool = True) -> list[str]:
    """Run ripgrep (fall back to grep) and return matching non-empty lines."""
    cmd: list[str]
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        cmd = [
            "rg", "--no-heading", "-n",
            "--glob", "!**/__pycache__/**",
        ]
        if exclude_tests:
            cmd.extend(["--glob", "!**/tests/**"])
        cmd.extend([pattern, str(path)])
    except (FileNotFoundError, subprocess.CalledProcessError):
        cmd = ["grep", "-rnP", pattern, str(path)]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30,
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines


# ---------------------------------------------------------------------------
# Theme globals regression
# ---------------------------------------------------------------------------


def test_no_legacy_theme_globals_in_production() -> None:
    """``_ACTIVE_THEME_DIR`` and ``set_active_theme`` must be absent from production."""
    lines = _run_grep(_THEME_GLOBALS_PATTERN, str(ASTRID_DIR))
    assert len(lines) == 0, (
        f"Found {len(lines)} legacy theme global(s) in production code:\n"
        + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# Secrets regression
# ---------------------------------------------------------------------------


def test_no_direct_fal_key_os_environ_writes() -> None:
    """No production code may write FAL_KEY via ``os.environ`` directly."""
    lines = _run_grep(_SECRETS_OS_ENVIRON_PATTERN, str(ASTRID_DIR))
    assert len(lines) == 0, (
        f"Found {len(lines)} direct ``os.environ`` FAL_KEY write(s):\n"
        + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# Confirm the spike is gone
# ---------------------------------------------------------------------------


def test_spike_directory_does_not_exist() -> None:
    """``astrid/core/_spike/`` must be fully removed."""
    spike_dir = ASTRID_DIR / "core" / "_spike"
    assert not spike_dir.exists(), (
        f"Spike directory still exists at {spike_dir}"
    )


# ---------------------------------------------------------------------------
# Confirm runner is the canonical theme writer (≤1 hit from scoped-config emit)
# ---------------------------------------------------------------------------


def test_no_theme_environment_writer() -> None:
    """Theme truth is an input document, never a subprocess environment value."""
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        cmd = [
            "rg", "--no-heading", "-n",
            "--glob", "!**/__pycache__/**",
            "--glob", "!**/tests/**",
            r'HYPE_ACTIVE_THEME\]\s*=',
            str(ASTRID_DIR),
        ]
    except (FileNotFoundError, subprocess.CalledProcessError):
        cmd = [
            "grep", "-rnP",
            r'HYPE_ACTIVE_THEME\]\s*=',
            str(ASTRID_DIR),
        ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30,
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]

    assert not lines

    non_runner_lines = [l for l in lines if "executor/runner.py" not in l]
    assert len(non_runner_lines) == 0, (
        f"Found {len(non_runner_lines)} non-runner HYPE_ACTIVE_THEME writer(s):\n"
        + "\n".join(non_runner_lines)
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
