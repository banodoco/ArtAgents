from __future__ import annotations

import sys

from astrid.orchestrate.test_runner import _run_fallback_subprocess


def test_fallback_subprocess_uses_canonical_env_without_host_spread(monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_AUTHOR_TEST_UNDECLARED", "from-host")
    cmd = [
        sys.executable,
        "-c",
        "import os, sys; sys.exit(0 if os.environ.get('ASTRID_AUTHOR_TEST_UNDECLARED', '') == '' else 3)",
    ]

    completed = _run_fallback_subprocess(cmd)

    assert completed.returncode == 0
