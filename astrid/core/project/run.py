"""Retired project-run compatibility namespace.

Run identity and lifecycle are owned by the workspace runtime. The former
local ``prepare/finalize/load/update`` helpers intentionally no longer exist:
there is no supported path that can mint or authorize a run from ``runs/*``
files. Runtime-bound staging helpers live in :mod:`astrid.core.project.runtime`.

This module remains as a small migration marker so old third-party imports fail
with an actionable error instead of silently creating a second ledger. New
code must use ``AstridClient.projects`` and ``AstridClient.runs``.
"""

from __future__ import annotations

from astrid.core.project.runtime import (
    ProjectRuntimeError,
    _project_subprocess_env,
    project_run_env,
    redact_cli_args,
    reject_project_with_out,
    step_dir_for,
)


class ProjectRunError(ProjectRuntimeError):
    """A retired local project-run operation was requested."""


def _retired(operation: str) -> None:
    raise ProjectRunError(
        f"{operation} is retired; use AstridClient.projects/runs through the workspace runtime"
    )


def prepare_project_run(*args, **kwargs):  # type: ignore[no-untyped-def]
    del args, kwargs
    _retired("local project run preparation")


def finalize_project_run(*args, **kwargs):  # type: ignore[no-untyped-def]
    del args, kwargs
    _retired("local project run finalization")


def load_run_record(*args, **kwargs):  # type: ignore[no-untyped-def]
    del args, kwargs
    _retired("local run.json reads")


def require_run_record(*args, **kwargs):  # type: ignore[no-untyped-def]
    del args, kwargs
    _retired("local run.json reads")


def update_run_record(*args, **kwargs):  # type: ignore[no-untyped-def]
    del args, kwargs
    _retired("local run.json updates")


def write_run_record(*args, **kwargs):  # type: ignore[no-untyped-def]
    del args, kwargs
    _retired("local run.json writes")


__all__ = [
    "ProjectRunError",
    "_project_subprocess_env",
    "finalize_project_run",
    "load_run_record",
    "prepare_project_run",
    "project_run_env",
    "redact_cli_args",
    "reject_project_with_out",
    "require_run_record",
    "update_run_record",
    "write_run_record",
    "step_dir_for",
]
