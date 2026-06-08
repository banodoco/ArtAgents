"""Project persistence APIs.

After the placement-schema collapse (T10), local ``project.json`` keeps an
opaque ``project_id`` that points at the canonical reigh-app row. Local
``timeline.json`` is no longer the source of truth — timeline reads/writes go
through ``astrid.core.integrations.reigh.SupabaseDataProvider`` as a legacy compatibility
bridge. The local provenance cache (``sources/`` and ``runs/`` directories)
survives.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.theme import load_theme_by_id
from astrid.core.util.hash import sha256_file
from astrid.core.util.time import utc_now_seconds

from . import paths
from .jsonio import read_json, write_json_atomic
from .schema import build_project, build_source, validate_project

# Skeleton for the per-project plan.md — a human/agent-readable working notes
# doc at the project root.  This is DISTINCT from <project>/runs/<run-id>/plan.json
# which is the executable runtime step tree; plan.md is project-level prose for
# current focus, open threads, key decisions, and scratch notes.
_PLAN_MD_SKELETON = """# {slug} — Plan

_Live working notes for this project. Read on attach; keep updated as the plan evolves._

## Current focus



## Open threads



## Key decisions



## Notes

"""


class ProjectError(AstridError):
    """Raised when project persistence operations fail."""

    def __init__(self, cause: str) -> None:
        super().__init__(cause)


def create_project(
    slug: str,
    *,
    name: str | None = None,
    project_id: str | None = None,
    root: str | Path | None = None,
    exist_ok: bool = False,
) -> dict[str, Any]:
    project_root = paths.project_dir(slug, root=root)
    project_path = project_root / "project.json"

    # Pre-check: reject if a directory with this slug already exists under the
    # projects root.  Projects under different ASTRID_PROJECTS_ROOT values
    # are independent — each root is checked separately.
    if project_root.exists() and not exist_ok:
        raise ProjectError(f"project '{slug}' already exists at {project_root}")

    if project_path.exists() and not exist_ok:
        raise ProjectError(f"project already exists: {slug}")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "sources").mkdir(exist_ok=True)
    (project_root / "runs").mkdir(exist_ok=True)
    # T9 / FLAG-S1-003 / all_locations-2: defensive double-coverage gitignore
    # for the file-bound session pointer so it never lands in git.
    _project_gitignore = project_root / ".gitignore"
    if not _project_gitignore.exists():
        _project_gitignore.write_text(".astrid-session\n", encoding="utf-8")
    payload = build_project(slug, name=name, project_id=project_id)
    if exist_ok and project_path.exists():
        payload = validate_project(read_json(project_path))
    else:
        write_json_atomic(project_path, payload)
    # plan.md: per-project human/agent working notes at the project root.
    # Distinct from runs/<run-id>/plan.json (the runtime step tree).
    # Idempotent — if it already exists, leave it alone.
    plan_path = project_root / "plan.md"
    if not plan_path.exists():
        _write_text_atomic(plan_path, _PLAN_MD_SKELETON.format(slug=slug))
    return payload


def _write_text_atomic(path: Path, content: str) -> None:
    """Atomic text write — temp file in same dir, then rename."""
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def load_project(slug: str, *, root: str | Path | None = None) -> dict[str, Any]:
    return validate_project(read_json(paths.project_json_path(slug, root=root)))


def require_project(slug: str, *, root: str | Path | None = None) -> dict[str, Any]:
    project_path = paths.project_json_path(slug, root=root)
    if not project_path.exists():
        raise ProjectError(f"project not found: {slug}. Next command: python3 -m astrid projects create {slug}")
    return validate_project(read_json(project_path))


def show_project(slug: str, *, root: str | Path | None = None) -> dict[str, Any]:
    """Return a cache-only view of the project tree.

    Live timeline state (clip count, theme, etc.) lives on the canonical
    reigh-app row keyed by ``project.project_id``. Callers that need it should
    use ``astrid.core.integrations.reigh.SupabaseDataProvider.load_timeline`` directly;
    this helper deliberately stays offline so ``projects show`` works without
    network access.
    """

    project = require_project(slug, root=root)
    run_root = paths.runs_dir(slug, root=root)
    runs = sorted(path.name for path in run_root.iterdir() if (path / "run.json").exists()) if run_root.exists() else []
    return {
        "project": project,
        "project_id": project.get("project_id"),
        "root": str(paths.project_dir(slug, root=root)),
        "runs": runs,
        "sources": list_project_sources(slug, root=root),
        "theme": project.get("theme"),
    }


def set_project_theme(
    slug: str,
    theme: str | None,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    payload = require_project(slug, root=root)
    if theme is None:
        payload.pop("theme", None)
    else:
        theme_slug = paths.validate_project_slug(theme)
        load_theme_by_id(theme_slug)
        payload["theme"] = theme_slug
    payload["updated_at"] = utc_now_seconds()
    payload = validate_project(payload)
    write_json_atomic(paths.project_json_path(slug, root=root), payload)
    return payload


def get_project_theme(slug: str, *, root: str | Path | None = None) -> str | None:
    payload = require_project(slug, root=root)
    theme = payload.get("theme")
    return theme if isinstance(theme, str) else None


def list_project_sources(slug: str, *, root: str | Path | None = None) -> list[dict[str, Any]]:
    require_project(slug, root=root)
    source_root = paths.sources_dir(slug, root=root)
    if not source_root.exists():
        return []
    entries: list[dict[str, Any]] = []
    for child in sorted(source_root.iterdir(), key=lambda item: item.name):
        if child.is_dir() and (child / "source.json").exists():
            valid, reason = _source_id_validity(child.name)
            entry: dict[str, Any] = {
                "kind": "registered",
                "source_id": child.name,
                "valid": valid,
                "path": str(child),
            }
            if reason:
                entry["validation_error"] = reason
            entries.append(entry)
        elif child.is_file():
            valid, reason = _source_id_validity(child.name)
            stat = child.stat()
            entry = {
                "kind": "file",
                "source_id": child.name,
                "filename": child.name,
                "valid": valid,
                "path": str(child),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
            if reason:
                entry["validation_error"] = reason
            entries.append(entry)
    return entries


def register_source_file(
    slug: str,
    filename: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    require_project(slug, root=root)
    if Path(filename).name != filename:
        raise ProjectError("source filename must be a bare filename under sources/")
    source_id = paths.validate_source_id(filename)
    source_root = paths.sources_dir(slug, root=root)
    bare_path = source_root / filename
    if not bare_path.is_file():
        raise FileNotFoundError(f"bare source file not found: {filename}")
    source_dir = paths.source_dir(slug, source_id, root=root)
    if source_dir.exists() and not source_dir.is_file():
        raise ProjectError(f"source already exists: {source_id}")

    stat = bare_path.stat()
    digest = sha256_file(bare_path).removeprefix("sha256:")
    mime_type, _encoding = mimetypes.guess_type(filename)
    temp_path = source_root / f".{filename}.registering"
    if temp_path.exists():
        raise ProjectError(f"temporary registration path already exists: {temp_path.name}")
    os.replace(bare_path, temp_path)
    try:
        source_dir.mkdir(parents=True)
        target_path = source_dir / filename
        os.replace(temp_path, target_path)
        asset: dict[str, Any] = {"file": str(target_path)}
        if mime_type:
            asset["type"] = mime_type
        payload = build_source(
            slug,
            source_id,
            asset=asset,
            metadata={
                "original_filename": filename,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "sha256": digest,
            },
        )
        write_json_atomic(source_dir / "source.json", payload)
        (source_dir / "analysis").mkdir(exist_ok=True)
        return payload
    except Exception:
        if temp_path.exists() and not bare_path.exists():
            os.replace(temp_path, bare_path)
        raise


def _source_id_validity(source_id: str) -> tuple[bool, str | None]:
    try:
        paths.validate_source_id(source_id)
    except ValueError as exc:
        return False, str(exc)
    return True, None


def _touch_project(slug: str, *, root: str | Path | None = None) -> None:
    payload = load_project(slug, root=root)
    payload["updated_at"] = utc_now_seconds()
    write_json_atomic(paths.project_json_path(slug, root=root), validate_project(payload))
