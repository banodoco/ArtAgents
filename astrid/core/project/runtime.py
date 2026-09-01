"""Runtime-bound project execution helpers.

Project and run identity are owned by the workspace runtime.  This module
contains only the small, transport-neutral helpers needed while a capability
is being staged for that runtime; it deliberately has no filesystem CRUD or
run-ledger access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from astrid.core.contracts.errors import AstridError
from astrid.core.env_vars import ASTRID_PROJECT_SLUG

PROJECT_RUN_ENV = "ASTRID_PROJECT_RUN"


class ProjectRuntimeError(AstridError):
    """Raised when runtime-bound project staging cannot be prepared."""


def reject_project_with_out(project: str | None, out: str | Path | None) -> None:
    if project and out not in (None, ""):
        raise ProjectRuntimeError(
            "--project cannot be combined with --out; the workspace runtime owns project run output"
        )


def project_run_env(project_slug: str | None = None) -> dict[str, str]:
    """Return runtime identity hints, never a project-tree locator.

    The workspace runtime owns project storage.  Child processes receive only
    the admitted project identity; all files they may consume are materialized
    beneath the current attempt by the host.
    """

    env = {PROJECT_RUN_ENV: "1"}
    if project_slug:
        env[ASTRID_PROJECT_SLUG] = project_slug
    return env


def _project_subprocess_env(request: Any) -> dict[str, str]:
    return project_run_env(getattr(request, "project", None))


def redact_cli_args(argv: Iterable[str]) -> list[str]:
    """Redact secrets before passing diagnostic arguments to a child."""

    sensitive = ("access_key", "api_key", "apikey", "auth", "bearer", "credential", "password", "secret", "token")
    result: list[str] = []
    hide_next = False
    for raw in argv:
        arg = str(raw)
        if hide_next:
            result.append("<redacted>")
            hide_next = False
            continue
        key = arg.split("=", 1)[0].lstrip("-").replace("-", "_").lower()
        if any(token in key for token in sensitive):
            if "=" in arg:
                result.append(f"{arg.split('=', 1)[0]}=<redacted>")
            else:
                result.append(arg)
                hide_next = True
        else:
            result.append(arg)
    return result


__all__ = [
    "PROJECT_RUN_ENV",
    "ProjectRuntimeError",
    "_project_subprocess_env",
    "project_run_env",
    "redact_cli_args",
    "reject_project_with_out",
]
