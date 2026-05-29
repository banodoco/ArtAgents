"""Auto-skip CI self-tests when running inside the CI sandbox.

The reshape lane runs ``pytest tests/reshape -q``, which would discover
``test_ci_json.py`` and ``test_ci_changed_selection.py``.  Those tests
invoke the CI script itself, creating infinite recursion.  We detect the
CI sandbox by the presence of a temp-directory ASTRID_HOME (set by the
mktemp-based sandbox in run_ci_checks.sh line 9) and skip the self-tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _is_ci_sandbox() -> bool:
    """Return True if ASTRID_HOME points to a temp directory (CI sandbox)."""
    home = os.environ.get("ASTRID_HOME", "")
    if not home:
        return False
    # The real ASTRID_HOME lives under the user's home directory.
    # The CI sandbox (mktemp -d) creates directories under the system
    # temp location, which on macOS is /var/folders/.../T/ and on Linux
    # is typically /tmp/.  Neither is under $HOME.
    user_home = str(Path.home())
    if home.startswith(user_home):
        return False
    # Any ASTRID_HOME outside $HOME is almost certainly a CI sandbox
    # (or a deliberate override, which we treat the same way).
    return True


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip CI self-tests when running inside the CI sandbox."""
    if not _is_ci_sandbox():
        return
    for item in items:
        if "test_ci_" in item.nodeid:
            item.add_marker(
                pytest.mark.skip(reason="CI sandbox detected — skipping self-test")
            )
