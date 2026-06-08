"""Gateway project resolution and auto-bind helpers.

Extracted from ``astrid/gateway.py`` during M4 batch 39 (T40) to keep the
gateway facade narrowly focused while preserving environment constants
and characterized project helper names through the gateway facade.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from astrid.core.util.log_and_swallow import log_and_swallow

# ---------------------------------------------------------------------------
# Project resolution environment constants
# ---------------------------------------------------------------------------

# Onboarding-ceremony reduction: a stateless executor/orchestrator run (e.g.
# `astrid executors run generation.generate_image --out ...`) should not force
# the user to first `astrid attach`. When the session gate finds no bound
# session for one of these run verbs, we auto-bind to a default project
# (creating it on first use) instead of erroring with "no session bound".
DEFAULT_PROJECT_SLUG = "default"
ASTRID_GATEWAY_RESOLVED_PROJECT_ENV = "ASTRID_GATEWAY_RESOLVED_PROJECT"
_AUTO_BIND_RUN_VERBS: tuple[tuple[str, ...], ...] = (
    ("executors", "run"),
    ("orchestrators", "run"),
    ("scratch", "run"),
)
_REQUEST_SCOPED_PROJECT_RUN_VERBS: tuple[tuple[str, ...], ...] = (
    ("executors", "run"),
    ("orchestrators", "run"),
    ("scratch", "run"),
)


# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------


def _extract_project_slug(raw: list[str]) -> str | None:
    for index, token in enumerate(raw):
        if token == "--project":
            return raw[index + 1] if index + 1 < len(raw) else None
        if token.startswith("--project="):
            value = token.split("=", 1)[1]
            return value or None
    return None


def _has_cli_option(raw: list[str], option: str) -> bool:
    return any(token == option or token.startswith(f"{option}=") for token in raw)


def _invocation_is_auto_bindable_run(raw: list[str]) -> bool:
    """True for stateless run verbs that may auto-bind a default project.

    Only ``executors run`` / ``orchestrators run`` qualify. An explicit
    ``--project`` is respected by leaving auto-bind off (the dispatched command
    owns project resolution). A ``--timeline-id`` (reigh-app UUID handoff mode)
    is also left to the dispatched command.
    """
    if _extract_project_slug(raw) is not None:
        return False
    if "--timeline-id" in raw:
        return False
    for prefix in _AUTO_BIND_RUN_VERBS:
        if tuple(raw[: len(prefix)]) == prefix:
            return True
    return False


def _auto_bind_default_project_session(raw: list[str]) -> Any:
    """Bind an offline default-project session for a stateless run, or None.

    Reuses the existing offline/cache-only project + session machinery rather
    than inventing a parallel path:

    * the workspace/user default project (``astrid attach --default`` writes it)
      is honored when configured; otherwise the slug ``default`` is used;
    * the project is created on first use (``create_project(..., exist_ok)``);
    * a session is bound via the SDK ``create_session`` primitive and
      ``ASTRID_SESSION_ID`` is set for the current process so the rest of the
      gate (and the dispatched command) sees a bound session.

    Returns the bound :class:`Session`, or ``None`` when the invocation is not
    an auto-bindable stateless run or binding fails (so the caller falls back to
    the documented "no session bound" error).
    """
    if not _invocation_is_auto_bindable_run(raw):
        return None
    try:
        from astrid.core.project.paths import resolve_projects_root
        from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
        from astrid.core.session.config import resolve_default_project_for_sdk
        from astrid.core.session.identity import read_identity
        from astrid.core.session.lifecycle import create_session
        from astrid.core.session.paths import sessions_dir

        slug = resolve_default_project_for_sdk(fallback_slug=DEFAULT_PROJECT_SLUG)
        projects_root = resolve_projects_root()
        session_root = sessions_dir()

        identity = read_identity()
        agent_id = identity.agent_id if identity is not None else DEFAULT_PROJECT_SLUG

        session = create_session(
            project_slug=slug,
            agent_id=agent_id,
            projects_root=projects_root,
            session_root=session_root,
            write_project_pointer=True,
        )
        os.environ[ASTRID_SESSION_ID_ENV] = session.id
        print(
            f"(auto-bound default project {slug!r}; no attach required for "
            f"stateless runs — pass --project to override)",
            file=sys.__stderr__,
        )
        return session
    except Exception as exc:  # noqa: BLE001
        # Never let auto-bind crash the gate; fall back to the standard error.
        log_and_swallow(exc, context="gateway.auto_bind_default_project_session")
        return None


def _resolved_request_project_slug(raw: list[str], session: Any) -> str | None:
    if session is None or _extract_project_slug(raw) is not None or _has_cli_option(raw, "--timeline-id"):
        return None
    for prefix in _REQUEST_SCOPED_PROJECT_RUN_VERBS:
        if tuple(raw[: len(prefix)]) == prefix:
            return str(getattr(session, "project", "") or "") or None
    return None


def _dispatch_with_resolved_project(raw: list[str], project_slug: str | None) -> int:
    if not project_slug:
        # Late import to avoid circular dependency at module load time.
        from astrid.gateway import _dispatch

        return _dispatch(raw)
    previous = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    os.environ[ASTRID_GATEWAY_RESOLVED_PROJECT_ENV] = project_slug
    try:
        from astrid.gateway import _dispatch

        return _dispatch(raw)
    finally:
        if previous is None:
            os.environ.pop(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV, None)
        else:
            os.environ[ASTRID_GATEWAY_RESOLVED_PROJECT_ENV] = previous
