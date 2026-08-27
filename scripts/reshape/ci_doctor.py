"""Run the deploy doctor against a disposable, initialized CI data root.

The normal ``astrid doctor`` command intentionally fails closed when a
projects root or database is absent.  That is the correct operator behavior,
but a clean checkout has no ambient ``projects/.astrid`` database for the
Makefile's pre-CI doctor target to inspect.  This helper owns a temporary root,
initializes it through the public projects CLI, and then runs the unchanged
read-only doctor against that exact root.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )


def _report_failure(
    label: str, result: subprocess.CompletedProcess[str]
) -> None:
    print(f"CI doctor {label} failed (exit {result.returncode})", file=sys.stderr)
    if result.stdout:
        print(result.stdout, file=sys.stderr, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")


def main() -> int:
    python = sys.executable
    env = os.environ.copy()

    # TemporaryDirectory guarantees cleanup even when create or doctor fails.
    # The ambient ASTRID_PROJECTS_ROOT is deliberately replaced for the
    # initialization command; doctor receives the same root explicitly below.
    with tempfile.TemporaryDirectory(prefix="astrid-make-doctor-") as root:
        ci_env = {**env, "ASTRID_PROJECTS_ROOT": root}
        create = _run(
            [
                python,
                "-m",
                "astrid",
                "projects",
                "create",
                "ci-doctor",
                "--name",
                "CI Doctor",
                "--idempotency-key",
                "make-ci-doctor-v1",
                "--json",
            ],
            env=ci_env,
        )
        if create.returncode != 0:
            _report_failure("project initialization", create)
            return create.returncode

        doctor = _run(
            [
                python,
                "-m",
                "astrid",
                "doctor",
                "--json",
                "--projects-root",
                str(Path(root)),
            ],
            env=ci_env,
        )
        if doctor.returncode != 0:
            _report_failure("health check", doctor)
            return doctor.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
