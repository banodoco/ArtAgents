"""Shared session/version helpers for the timeline CLI.

Extracted from ``astrid/core/timeline/cli.py`` to break the circular-facade
dependency: the command-handler leaf modules (``cli_crud``, ``cli_output``,
``cli_edits``, ``cli_events``, ``cli_backends``) previously reached *back* into
``cli`` via in-function imports to obtain these shared helpers, while ``cli``
re-exports the leaves' handlers at module level — a genuine import cycle.

This module is a **leaf**: it may import from ``session``/``contracts`` but must
never import from ``timeline.cli`` or any of the handler leaves.  ``cli`` imports
these names from here and re-exports them, so the legacy monkeypatch seam
``astrid.core.timeline.cli._require_session`` (et al.) keeps resolving.
"""

from __future__ import annotations

import argparse
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.session.binding import (
    SessionBindingError,
    resolve_current_session,
)

from .events.schema import TimelineActor

_SESSION_GATE_HINT = (
    "A timeline command requires a bound session. "
    "Run 'astrid attach <project>' first."
)


def _resolve_optional_session(args: argparse.Namespace) -> Any:
    """Resolve a session if possible, but don't raise when not found.

    Used by commands that accept --project as an alternative to session binding.
    """
    try:
        return resolve_current_session(slug=getattr(args, "project", None) or None)
    except Exception:
        return None


def _resolve_project_slug(args: argparse.Namespace, session: Any) -> str:
    """Resolve a project slug from args or session."""
    project_slug = getattr(args, "project", None)
    if project_slug:
        return project_slug
    if session is not None:
        return session.project
    raise AstridError(
        "no project specified; use --project <slug> or bind a session with 'astrid attach'",
        recovery_command="astrid attach <project>",
    )


def _require_session(slug: str | None = None) -> Any:
    # T9 / FLAG-S1-003: optional slug for file-bound fallback; env-only when
    # caller has no --project context to plumb.
    session = resolve_current_session(slug=slug)
    if session is None:
        raise SessionBindingError(_SESSION_GATE_HINT)
    return session


def _expected_version_kwargs(args: argparse.Namespace) -> dict[str, int]:
    expected_version = getattr(args, "expected_version", None)
    if expected_version is None:
        return {}
    return {"expected_version": expected_version}


def _timeline_actor_from_session(session: Any) -> TimelineActor:
    agent_id = getattr(session, "agent_id", "") or "unknown-agent"
    session_id = getattr(session, "id", "") or "unknown-session"
    return TimelineActor(
        type="agent",
        id=f"{agent_id}:{session_id}",
        display=agent_id,
    )
