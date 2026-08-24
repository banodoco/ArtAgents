"""Derived filesystem bindings for kernel-owned projects.

The ``projects`` table is authoritative.  ``project.json`` and ``plan.md``
exist only so file-oriented capabilities can bind a kernel project to its
workspace.  This module keeps that projection logic in core so both project
creation and backup restore can materialize the same shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from astrid.core.foundation.atomic_io import write_json_atomic, write_text_atomic
from astrid.core.foundation.project_paths import project_dir, project_json_path
from astrid.core.project.project import PLAN_MD_SKELETON
from astrid.core.project.schema import build_project


def materialize_project_workspace(
    *,
    slug: str,
    name: str,
    project_id: str,
    projects_root: str | Path | None,
    created_at: str | None = None,
    updated_at: str | None = None,
    default_timeline_id: str | None = None,
    reconcile_binding: bool = False,
) -> dict[str, object]:
    """Ensure one kernel project's non-authoritative workspace projection.

    ``plan.md`` is never overwritten.  By default an existing ``project.json``
    is also left untouched, matching project-create behavior.  Restore passes
    ``reconcile_binding=True``: user/extension fields are preserved when the
    existing file is a JSON object, while the kernel-derived identity fields
    are atomically refreshed.  A malformed binding is replaced because it is
    a derived locator, never project authority.
    """

    root = project_dir(slug, root=projects_root)
    root.mkdir(parents=True, exist_ok=True)

    plan_path = root / "plan.md"
    plan_created = False
    if not plan_path.exists():
        write_text_atomic(plan_path, PLAN_MD_SKELETON.format(slug=slug))
        plan_created = True

    binding_path = project_json_path(slug, root=projects_root)
    binding_created = not binding_path.exists()
    binding_updated = False
    if binding_created or reconcile_binding:
        existing: Mapping[str, Any] = {}
        if binding_path.is_file():
            try:
                candidate = json.loads(binding_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                candidate = {}
            if isinstance(candidate, dict):
                existing = candidate

        canonical = build_project(
            slug,
            name=name,
            project_id=project_id,
            created_at=created_at,
            default_timeline_id=default_timeline_id,
        )
        if updated_at is not None:
            canonical["updated_at"] = str(updated_at)
        canonical["kernel_authority"] = True
        payload = {**dict(existing), **canonical}
        if binding_created or payload != dict(existing):
            write_json_atomic(binding_path, payload)
            binding_updated = not binding_created

    return {
        "project_dir": str(root.resolve()),
        "project_json": str(binding_path.resolve()),
        "plan_md": str(plan_path.resolve()),
        "binding_created": binding_created,
        "binding_updated": binding_updated,
        "plan_created": plan_created,
    }


__all__ = ["materialize_project_workspace"]
