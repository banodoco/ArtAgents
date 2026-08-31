"""Runtime-bound project execution helpers.

Project and run identity are owned by the workspace runtime.  This module
contains only the small, transport-neutral helpers needed while a capability
is being staged for that runtime; it deliberately has no filesystem CRUD or
run-ledger access.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from astrid.core.contracts.errors import AstridError
from astrid.core.env_vars import ASTRID_PROJECT_SLUG, ASTRID_PROJECTS_ROOT
from astrid.core.foundation import project_paths as paths

PROJECT_RUN_ENV = "ASTRID_PROJECT_RUN"


class ProjectRuntimeError(AstridError):
    """Raised when runtime-bound project staging cannot be prepared."""


def reject_project_with_out(project: str | None, out: str | Path | None) -> None:
    if project and out not in (None, ""):
        raise ProjectRuntimeError(
            "--project cannot be combined with --out; the workspace runtime owns project run output"
        )


def project_run_env(
    project_slug: str | None = None, *, root: str | Path | None = None
) -> dict[str, str]:
    """Return only environment hints for a runtime-bound child process."""

    env = {PROJECT_RUN_ENV: "1"}
    if project_slug:
        env[ASTRID_PROJECT_SLUG] = project_slug
    if root:
        env[ASTRID_PROJECTS_ROOT] = str(Path(root).expanduser().resolve())
    return env


def _project_subprocess_env(request: Any) -> dict[str, str]:
    return project_run_env(
        getattr(request, "project", None),
        root=getattr(request, "projects_root", None),
    )


def step_dir_for(
    slug: str,
    run_id: str,
    plan_step_id: str,
    *,
    step_version: int = 1,
    root: str | Path | None = None,
) -> Path:
    """Return an ephemeral staging path for an attached child.

    This path is not a run identity lookup and must never be used to authorize
    or select a run.  The runtime response/environment supplies the identity.
    """

    paths.validate_project_slug(slug)
    paths.validate_run_id(run_id)
    paths.validate_run_id(plan_step_id)
    if not isinstance(step_version, int) or isinstance(step_version, bool) or step_version < 1:
        raise ProjectRuntimeError("step_version must be an int >= 1")
    base = Path(root).expanduser().resolve() if root is not None else Path.cwd().resolve()
    return base / ".astrid-runtime-staging" / slug / run_id / "steps" / plan_step_id / f"v{step_version}"


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
    "step_dir_for",
]
