"""Shared CLI capture helper: run_cli(main, argv) -> CliResult."""

from __future__ import annotations

import contextlib
import dataclasses
import io
from typing import Callable, List, Optional


@dataclasses.dataclass
class CliResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str


def run_cli(main: Callable[[List[str]], Optional[int]], argv: List[str]) -> CliResult:
    """Call main(argv) in-process, capturing stdout, stderr, and exit code."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        exit_code = main(argv)
    return CliResult(
        exit_code=exit_code,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )
