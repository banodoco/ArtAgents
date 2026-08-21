"""Shared version helpers for the timeline CLI.

Extracted from ``astrid/core/timeline/cli.py`` to break the circular-facade
dependency: the command-handler leaf modules (``cli_crud``, ``cli_output``,
``cli_edits``, ``cli_events``, ``cli_backends``) previously reached *back* into
``cli`` via in-function imports to obtain these shared helpers, while ``cli``
re-exports the leaves' handlers at module level — a genuine import cycle.

The legacy session-binding helpers were retired with the task-mode session
layer; the timeline CLI now resolves project context from ``--project`` only
and derives a stable request-scoped actor.
"""

from __future__ import annotations

import argparse

from astrid.core.contracts.errors import AstridError

from .events.schema import TimelineActor


def _resolve_optional_session(args: argparse.Namespace) -> None:
    """Retired session resolver — timeline commands no longer bind sessions."""
    return None


def _resolve_project_slug(args: argparse.Namespace, session: object | None = None) -> str:
    """Resolve a project slug from args (session parameter retained for compat)."""
    project_slug = getattr(args, "project", None)
    if project_slug:
        return project_slug
    raise AstridError(
        "no project specified; use --project <slug>",
        recovery_command="astrid timelines <verb> --project <slug>",
    )


def _require_session(slug: str | None = None) -> None:
    """Retired session gate — sessions are no longer bound or required.

    Kept as the monkeypatch seam for the legacy timeline CLI tests; timeline
    commands resolve project context from ``--project`` instead.
    """
    raise AstridError(
        "a timeline command requires --project (sessions are retired)",
        recovery_command="re-run with --project <slug>",
    )


def _expected_version_kwargs(args: argparse.Namespace) -> dict[str, int]:
    expected_version = getattr(args, "expected_version", None)
    if expected_version is None:
        return {}
    return {"expected_version": expected_version}


def _resolve_edit_context(
    project_slug: str,
    args: argparse.Namespace,
) -> tuple[TimelineActor, str]:
    """Resolve a stable request-scoped actor + project for edit handlers.

    The actor identity is deterministic per project slug; timeline edits no
    longer require a bound session.
    """
    resolved_project = project_slug or getattr(args, "project", None)
    if not resolved_project:
        raise AstridError(
            "no project specified; use --project <slug>",
            recovery_command="astrid timelines <verb> --project <slug>",
        )

    actor = TimelineActor(
        type="agent",
        id=f"agent:project:{resolved_project}",
        display=f"project:{resolved_project}",
    )
    return actor, resolved_project
