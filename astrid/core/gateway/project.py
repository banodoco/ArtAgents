"""Gateway project resolution and auto-bind helpers.

Extracted from ``astrid/gateway.py`` during M4 batch 39 (T40) to keep the
gateway facade narrowly focused while preserving environment constants
and characterized project helper names through the gateway facade.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from astrid.core._shared.capability_common import _has_cli_option
from astrid.core.contracts.errors import AstridError

# ---------------------------------------------------------------------------
# Project resolution environment constants
# ---------------------------------------------------------------------------

# Compatibility exports retained while auto-binding is intentionally disabled.
# A default is an attach-time suggestion, never execution authorization.
DEFAULT_PROJECT_SLUG = "default"
ASTRID_GATEWAY_RESOLVED_PROJECT_ENV = "ASTRID_GATEWAY_RESOLVED_PROJECT"
_AUTO_BIND_RUN_VERBS: tuple[tuple[str, ...], ...] = ()
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
        from astrid.core.foundation.project_paths import resolve_projects_root

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


def _invocation_is_auto_bindable_run(raw: list[str]) -> bool:
    """Compatibility predicate: project auto-binding is no longer legal."""

    del raw
    return False


def _auto_bind_default_project_session(raw: list[str]) -> Any:
    """Compatibility shim: auto-binding is disabled and has no side effects."""

    del raw
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
