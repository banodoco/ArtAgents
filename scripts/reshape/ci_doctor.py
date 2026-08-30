"""Run the deploy doctor through the workspace runtime.

Stage1 removed Astrid's local project/database authority.  The Makefile
doctor target therefore delegates directly to the runtime-backed public
doctor command and never creates or inspects a disposable local store.
"""

from __future__ import annotations

import os
import subprocess
import sys


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
    result = _run([sys.executable, "-m", "astrid", "doctor", "--json"], env=os.environ.copy())
    if result.returncode != 0:
        _report_failure("health check", result)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
