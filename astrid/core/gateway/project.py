"""Gateway project resolution and auto-bind helpers.

Extracted from ``astrid/gateway.py`` during M4 batch 39 (T40) to keep the
gateway facade narrowly focused while preserving environment constants
and characterized project helper names through the gateway facade.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
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


def _extract_project_slug_from_run_paths(raw: list[str]) -> str | None:
    """Infer a local project slug from file-scoped run arguments.

    ``executors run`` and friends are often invoked with only explicit file
    paths, e.g. ``--out projects/demo/runs/x`` and
    ``--input timeline=projects/demo/runs/x/hype.timeline.json``. In that
    case, falling back to the configured global default project is surprising
    and can route provenance to the wrong project. Infer the slug only when all
    project-root paths point at the same local project.
    """
    if _extract_project_slug(raw) is not None or not _is_request_scoped_run(raw):
        return None
    slugs = _project_slugs_from_run_paths(raw)
    if len(slugs) == 1:
        return next(iter(slugs))
    return None


def _project_slugs_from_run_paths(raw: list[str]) -> set[str]:
    if _extract_project_slug(raw) is not None or not _is_request_scoped_run(raw):
        return set()
    try:
        from astrid.core.project.paths import resolve_projects_root

        projects_root = resolve_projects_root().resolve()
    except Exception:
        return set()
    slugs: set[str] = set()
    for value in _iter_file_scoped_run_values(raw):
        slug = _project_slug_for_path_value(value, projects_root)
        if slug:
            slugs.add(slug)
    return slugs


def _raise_on_ambiguous_run_path_projects(raw: list[str]) -> None:
    if _extract_project_slug(raw) is not None or _has_cli_option(raw, "--timeline-id"):
        return
    slugs = _project_slugs_from_run_paths(raw)
    if len(slugs) <= 1:
        return
    choices = ", ".join(sorted(slugs))
    raise AstridError(
        f"ambiguous project context: run paths reference multiple projects ({choices})",
        recovery_command="pass --project <slug> explicitly",
        state_snapshot={"argv": raw, "projects": sorted(slugs)},
    )


def _is_request_scoped_run(raw: list[str]) -> bool:
    for prefix in _REQUEST_SCOPED_PROJECT_RUN_VERBS:
        if tuple(raw[: len(prefix)]) == prefix:
            return True
    return False


def _iter_file_scoped_run_values(raw: list[str]) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token in {"--out", "--brief"} and index + 1 < len(raw):
            values.append(raw[index + 1]); index += 2; continue
        if token.startswith("--out=") or token.startswith("--brief="):
            values.append(token.split("=", 1)[1]); index += 1; continue
        if token == "--input" and index + 1 < len(raw):
            values.append(raw[index + 1].split("=", 1)[-1]); index += 2; continue
        if token.startswith("--input="):
            values.append(token.split("=", 1)[1].split("=", 1)[-1]); index += 1; continue
        index += 1
    return values


def _project_slug_for_path_value(value: str, projects_root: Path) -> str | None:
    if not value or "://" in value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        relative = path.resolve(strict=False).relative_to(projects_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    slug = relative.parts[0]
    project_json = projects_root / slug / "project.json"
    return slug if project_json.is_file() else None


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
    return _is_request_scoped_run(raw)


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

        slug = _extract_project_slug_from_run_paths(raw) or resolve_default_project_for_sdk(
            fallback_slug=DEFAULT_PROJECT_SLUG
        )
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
    if _is_request_scoped_run(raw):
        return str(getattr(session, "project", "") or "") or None
    return None


def _dispatch_with_resolved_project(raw: list[str], project_slug: str | None) -> int:
    if not project_slug:
        # Late import to avoid circular dependency at module load time.
        from astrid.core.gateway import _dispatch

        return _dispatch(raw)
    previous = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    os.environ[ASTRID_GATEWAY_RESOLVED_PROJECT_ENV] = project_slug
    try:
        from astrid.core.gateway import _dispatch

        return _dispatch(raw)
    finally:
        if previous is None:
            os.environ.pop(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV, None)
        else:
            os.environ[ASTRID_GATEWAY_RESOLVED_PROJECT_ENV] = previous
