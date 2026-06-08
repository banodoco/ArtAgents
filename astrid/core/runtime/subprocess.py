"""Shared subprocess runner for orchestrator steps.

Minimal helper that wraps :func:`subprocess.run` with consistent
:class:`AstridError` raising on non-zero exit.  All orchestrators that
shell out to child commands should route through this module so
recovery_command and state_snapshot metadata stay uniform.
"""

from __future__ import annotations

import subprocess
from typing import Any

from astrid.core.contracts.errors import AstridError


def run_subprocess(
    cmd: list[str],
    *,
    label: str,
    orchestrator: str | None = None,
    **kwargs: Any,
) -> str:
    """Run *cmd* and return its captured stdout.

    ``capture_output=True`` and ``text=True`` are hard-coded.  Extra
    keyword arguments (e.g. ``env``, ``cwd``) are forwarded to
    :func:`subprocess.run`.

    Raises :class:`AstridError` when the child exits non-zero.
    """
    proc = subprocess.run(cmd, capture_output=True, text=True, **kwargs)

    if proc.returncode != 0:
        prefix = f"[{orchestrator}] " if orchestrator else ""
        raise AstridError(
            f"{prefix}{label} failed (exit {proc.returncode})",
            recovery_command=(
                f"check the child command and rerun: {' '.join(cmd)}"
            ),
            state_snapshot={
                "command": " ".join(cmd),
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )

    return proc.stdout


__all__ = ["run_subprocess"]
