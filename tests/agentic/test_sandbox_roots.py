"""Offline meta-test: agentic suite filesystem roots must not escape to real $HOME.

Collectable by pytest without running any agentic scenario.  Verifies that the
constants exposed by cleanup.py and parallel_runner.py resolve under $TMPDIR
(or an env-var override) and never under the developer's real home directory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _home() -> Path:
    return Path.home()


def _tmpdir() -> Path:
    return Path(tempfile.gettempdir())


# ---------------------------------------------------------------------------
# cleanup.py roots
# ---------------------------------------------------------------------------


def test_cleanup_projects_root_not_under_real_home() -> None:
    """PROJECTS_ROOT must not be a descendant of the real home directory."""
    from tests.agentic.cleanup import PROJECTS_ROOT

    real_home = _home()
    try:
        PROJECTS_ROOT.relative_to(real_home)
    except ValueError:
        return  # not under home — correct
    raise AssertionError(
        f"cleanup.PROJECTS_ROOT {PROJECTS_ROOT!r} resolves under real $HOME {real_home!r}"
    )


def test_cleanup_astrid_home_not_under_real_home() -> None:
    """ASTRID_HOME must not be a descendant of the real home directory."""
    from tests.agentic.cleanup import ASTRID_HOME

    real_home = _home()
    try:
        ASTRID_HOME.relative_to(real_home)
    except ValueError:
        return
    raise AssertionError(
        f"cleanup.ASTRID_HOME {ASTRID_HOME!r} resolves under real $HOME {real_home!r}"
    )


def test_cleanup_projects_root_under_sandbox_when_no_env_override() -> None:
    """When ASTRID_PROJECTS_ROOT is not set, PROJECTS_ROOT resolves under $TMPDIR."""
    if os.environ.get("ASTRID_PROJECTS_ROOT"):
        return  # env override is present — sandbox rule does not apply
    from tests.agentic.cleanup import PROJECTS_ROOT

    tmpdir = _tmpdir()
    try:
        PROJECTS_ROOT.relative_to(tmpdir)
    except ValueError:
        raise AssertionError(
            f"cleanup.PROJECTS_ROOT {PROJECTS_ROOT!r} is not under $TMPDIR {tmpdir!r} "
            "and no ASTRID_PROJECTS_ROOT env var is set"
        )


def test_cleanup_astrid_home_under_sandbox_when_no_env_override() -> None:
    """When ASTRID_HOME is not set, ASTRID_HOME resolves under $TMPDIR."""
    if os.environ.get("ASTRID_HOME"):
        return
    from tests.agentic.cleanup import ASTRID_HOME

    tmpdir = _tmpdir()
    try:
        ASTRID_HOME.relative_to(tmpdir)
    except ValueError:
        raise AssertionError(
            f"cleanup.ASTRID_HOME {ASTRID_HOME!r} is not under $TMPDIR {tmpdir!r} "
            "and no ASTRID_HOME env var is set"
        )


# ---------------------------------------------------------------------------
# parallel_runner.py identity source
# ---------------------------------------------------------------------------


def test_parallel_runner_suite_sandbox_not_under_real_home() -> None:
    """parallel_runner._SUITE_SANDBOX must not be under the real home directory."""
    from tests.agentic.parallel_runner import _SUITE_SANDBOX

    real_home = _home()
    try:
        _SUITE_SANDBOX.relative_to(real_home)
    except ValueError:
        return
    raise AssertionError(
        f"parallel_runner._SUITE_SANDBOX {_SUITE_SANDBOX!r} resolves under real $HOME {real_home!r}"
    )


def test_parallel_runner_identity_source_not_under_real_home() -> None:
    """The identity.json source path in parallel_runner must not be under real $HOME."""
    from tests.agentic.parallel_runner import _SUITE_SANDBOX

    identity_source = _SUITE_SANDBOX / "home" / "identity.json"
    real_home = _home()
    try:
        identity_source.relative_to(real_home)
    except ValueError:
        return
    raise AssertionError(
        f"identity source {identity_source!r} resolves under real $HOME {real_home!r}"
    )


def test_parallel_runner_suite_sandbox_under_tmpdir() -> None:
    """parallel_runner._SUITE_SANDBOX resolves under $TMPDIR."""
    from tests.agentic.parallel_runner import _SUITE_SANDBOX

    tmpdir = _tmpdir()
    try:
        _SUITE_SANDBOX.relative_to(tmpdir)
    except ValueError:
        raise AssertionError(
            f"parallel_runner._SUITE_SANDBOX {_SUITE_SANDBOX!r} is not under $TMPDIR {tmpdir!r}"
        )
