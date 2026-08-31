"""Human-facing project discovery and selection guidance."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from astrid.core.env_vars import ASTRID_PROJECT_SLUG
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.preferences import resolve_default_project


def _runtime_projects() -> list[dict[str, Any]]:
    """Return projects from the selected runtime, or an empty unavailable read."""

    try:
        from astrid.sdk.client import AstridClient

        with AstridClient.open() as client:
            result = client.projects.list()
            data = result.data
            if isinstance(data, dict):
                data = data.get("items", [])
            if not result.ok or not isinstance(data, list):
                return []
            rows: list[dict[str, Any]] = []
            for item in data:
                if hasattr(item, "__dict__") and not isinstance(item, dict):
                    item = vars(item)
                if isinstance(item, dict):
                    rows.append(dict(item))
            return rows
    except Exception:
        # Guidance is shown while handling another command.  Runtime
        # unavailability must produce concise recovery text, never a local
        # filesystem approximation of project authority.
        return []


def project_summaries(
    *,
    root: str | Path | None = None,
    include_test_projects: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return recent projects with enough context to choose one safely."""

    del root
    default = resolve_default_project()
    rows: list[dict[str, Any]] = []
    for project in _runtime_projects():
        slug = str(project.get("slug") or project.get("project_id") or project.get("id") or "")
        if not slug:
            continue
        if not include_test_projects and slug.startswith("agentic-"):
            continue
        name = str(project.get("name") or slug)
        description = str(project.get("description") or project.get("metadata", {}).get("description", ""))
        theme = str(project.get("theme") or project.get("metadata", {}).get("theme", ""))
        updated_at = str(project.get("updated_at") or "")
        runs = _runtime_run_count(slug)
        timelines = _runtime_timeline_count(slug)
        rows.append(
            {
                "slug": slug,
                "name": name,
                "description": description,
                "theme": theme,
                "updated_at": updated_at,
                "is_default": slug == default,
                "runs": runs,
                "timelines": timelines,
                "experiments": 0,
            }
        )
        if limit is not None and len(rows) >= limit:
            break
    return rows


def format_project_required_guidance(*, operation: str) -> str:
    """Render a compact, actionable missing-project screen."""

    default = resolve_default_project()
    rows = project_summaries(limit=5)
    lines = [
        f"project required: every {operation} belongs to exactly one project.",
        "No project is attached, and this command did not include --project.",
        "",
        "Choose how to continue:",
        "  astrid projects list",
        "  astrid projects select <project>    # persist a default preference (suggestion only)",
        "  re-run this command with --project <project>  # attach for this run",
        '  astrid projects create <slug> --name "Display Name"',
        "",
        "Nothing is auto-selected: pass --project <project> on each command",
        "(a configured default is a suggestion only, never a selection).",
    ]
    if default:
        lines.extend(
            [
                "",
                f"Configured default: {default} (suggestion only; not selected)",
                f"  astrid projects select {default}",
            ]
        )
    if rows:
        lines.extend(["", "Recent projects:"])
        for row in rows:
            label = row["slug"]
            if row["name"] != row["slug"]:
                label += f" — {row['name']}"
            if row["is_default"]:
                label += " [configured default]"
            lines.append(f"  {label}")
            if row["description"]:
                lines.append(f"    {row['description']}")
            lines.append(
                "    "
                f"{row['runs']} runs · {row['timelines']} timelines · "
                f"{row['experiments']} experiments"
            )
            lines.append(
                f"    set preference: astrid projects select {row['slug']}"
            )
    else:
        lines.extend(
            [
                "",
                "No projects exist yet.",
                '  astrid projects create <slug> --name "Display Name"',
            ]
        )
    return "\n".join(lines)


def selected_project(explicit_project: str | None) -> tuple[str | None, str]:
    """Resolve explicit, attached, or an unambiguous runtime project.

    Configured defaults and path inference are intentionally excluded.  A
    single project returned by the runtime is safe to address; multiple
    projects remain an explicit-selection requirement.
    """

    if explicit_project:
        return explicit_project, "explicit"
    attached = os.environ.get(ASTRID_PROJECT_SLUG)
    if attached:
        return attached, "attached"
    projects = _runtime_projects()
    if len(projects) == 1:
        project = projects[0]
        ref = project.get("project_id") or project.get("id") or project.get("slug")
        if ref:
            return str(ref), "runtime"
    return None, "missing"


def _runtime_run_count(project: str) -> int:
    try:
        from astrid.sdk.client import AstridClient

        with AstridClient.open() as client:
            result = client.runs.list(project)
            return len(result.data) if result.ok and isinstance(result.data, list) else 0
    except Exception:
        return 0


def _runtime_timeline_count(project: str) -> int:
    try:
        from astrid.sdk.client import AstridClient

        with AstridClient.open() as client:
            result = client.timelines.list(project)
            return len(result.data) if result.ok and isinstance(result.data, list) else 0
    except Exception:
        return 0

__all__ = [
    "format_project_required_guidance",
    "project_summaries",
    "selected_project",
]
