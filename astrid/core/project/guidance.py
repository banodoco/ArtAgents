"""Human-facing project discovery and selection guidance."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json
from astrid.core.env_vars import ASTRID_PROJECT_SLUG
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.preferences import resolve_default_project


def _discover_projects(*, root: str | Path | None = None) -> list[str]:
    """Return project slugs under the projects root, sorted by mtime descending."""

    projects_root = resolve_projects_root(root)
    if not projects_root.exists():
        return []
    candidates: list[tuple[float, str]] = []
    for entry in projects_root.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / "project.json").exists():
            continue
        candidates.append((entry.stat().st_mtime, entry.name))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [name for _, name in candidates]


def project_summaries(
    *,
    root: str | Path | None = None,
    include_test_projects: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return recent projects with enough context to choose one safely."""

    projects_root = resolve_projects_root(root)
    default = resolve_default_project()
    rows: list[dict[str, Any]] = []
    for slug in _discover_projects(root=projects_root):
        if not include_test_projects and slug.startswith("agentic-"):
            continue
        project_root = projects_root / slug
        try:
            payload = read_json(project_root / "project.json")
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        rows.append(
            {
                "slug": slug,
                "name": str(payload.get("name") or slug),
                "description": str(payload.get("description") or ""),
                "theme": str(payload.get("theme") or ""),
                "updated_at": str(payload.get("updated_at") or ""),
                "is_default": slug == default,
                "runs": _kernel_or_fs_run_count(slug, projects_root, project_root),
                "timelines": _count_children(project_root / "timelines"),
                "experiments": _count_children(project_root / "experiments"),
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
    """Resolve only explicit or genuinely attached project context.

    Configured defaults and path inference are intentionally excluded.
    """

    if explicit_project:
        return explicit_project, "explicit"
    attached = os.environ.get(ASTRID_PROJECT_SLUG)
    if attached:
        return attached, "attached"
    return None, "missing"


def _count_children(path: Path, *, marker: str | None = None) -> int:
    if not path.is_dir():
        return 0
    try:
        return sum(
            1
            for child in path.iterdir()
            if child.is_dir() and (marker is None or (child / marker).is_file())
        )
    except OSError:
        return 0


def _kernel_or_fs_run_count(slug: str, projects_root: Path, project_root: Path) -> int:
    # Kernel-first: count kernel runs for this project if DB present; FS fallback for historical dirs.
    try:
        import sqlite3

        db_path = projects_root / "kernel.sqlite3"
        if db_path.is_file():
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                prow = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
                project_id = prow[0] if prow is not None else slug
                row = conn.execute("SELECT COUNT(*) FROM runs WHERE project_id = ?", (project_id,)).fetchone()
                if row is not None:
                    return int(row[0])
            finally:
                conn.close()
    except Exception:
        pass
    return _count_children(project_root / "runs", marker="run.json")

__all__ = [
    "format_project_required_guidance",
    "project_summaries",
    "selected_project",
]
