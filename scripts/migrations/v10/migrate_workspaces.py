"""Repair phase: materialize/repair per-project workspaces (kernel binding).

The original migration predated the workspace materializer
(``ProjectsService.create`` → ``_materialize_workspace``), so migrated
projects can lack ``<root>/<slug>/plan.md`` / ``project.json`` — or carry a
pre-materializer ``project.json`` with no ``project_id`` /
``kernel_authority: true`` binding. Direct-mode resolution
(``astrid.core.project.project.require_project``) then fails or cannot tie
the filesystem project to its kernel row.

For every **kernel** project row (read-only SQL; the kernel DB is never
written by this phase):

- ``plan.md`` missing → write the documented skeleton;
- ``project.json`` missing → materialize the full binding skeleton through
  ``astrid.sdk.projects._materialize_workspace`` (the exact create-path
  helper: kernel project id + ``kernel_authority: true``);
- ``project.json`` present but binding invalid (missing/mismatched
  ``project_id``, or ``kernel_authority`` not ``true``) → patch in the two
  binding fields and rewrite atomically, preserving every other field
  (``default_timeline_id``, legacy timestamps, ...). Human-editable content
  (``plan.md``) is never overwritten; a valid existing binding is left
  byte-for-byte untouched (idempotent).

Only project workspace files are written — never kernel events, rows, or
receipts.

Usage::

    python3 scripts/migrations/v10/migrate_workspaces.py [--apply]
        [--root ...] [--project SLUG]...
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _kernel_projects(db_path: Path) -> list[dict]:
    """Read-only enumeration of kernel projects (slug, id, name)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT slug, id, name FROM projects ORDER BY slug"
        ).fetchall()
    finally:
        conn.close()
    return [{"slug": row[0], "id": row[1], "name": row[2]} for row in rows]


def _binding_is_valid(payload: dict, kernel_id: str) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("project_id") == kernel_id
        and payload.get("kernel_authority") is True
    )


def _repair_binding_file(
    path: Path,
    *,
    slug: str,
    name: str,
    kernel_id: str,
    root: Path,
) -> str:
    """Repair one ``project.json``; return the action taken."""
    from astrid.core.foundation.atomic_io import write_json_atomic
    from astrid.sdk.projects import _materialize_workspace

    if not path.exists():
        # Missing file: reuse the exact SDK create-path materializer so the
        # written skeleton matches every fresh create byte for byte.
        _materialize_workspace(
            slug=slug, name=name, project_id=kernel_id, projects_root=root
        )
        return "created"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    if not isinstance(payload, dict):
        return "unreadable"
    if _binding_is_valid(payload, kernel_id):
        return "ok"

    # Pre-materializer binding: patch only the two binding fields and keep
    # everything else (default_timeline_id, legacy timestamps, ...).
    payload.setdefault("slug", slug)
    payload["project_id"] = kernel_id
    payload["kernel_authority"] = True
    write_json_atomic(path, payload)
    return "patched"


def migrate_workspaces(
    *,
    apply: bool,
    root: Path,
    project_filter: set[str] | None = None,
) -> list[dict]:
    """Materialize/repair workspaces for every kernel project under *root*."""
    from astrid.core.foundation.atomic_io import write_text_atomic
    from astrid.core.foundation.project_paths import project_dir
    from astrid.core.project.project import PLAN_MD_SKELETON

    db = root / ".astrid" / "astrid.sqlite3"
    if not db.is_file():
        print(f"migrate_workspaces: no kernel DB at {db}", file=sys.stderr)
        raise SystemExit(2)
    projects = [
        p
        for p in _kernel_projects(db)
        if not project_filter or p["slug"] in project_filter
    ]

    results: list[dict] = []
    for project in projects:
        slug = project["slug"]
        project_root = project_dir(slug, root=root)
        plan_path = project_root / "plan.md"
        binding_path = project_root / "project.json"

        actions: list[str] = []
        if not apply:
            results.append({"slug": slug, "action": "plan"})
            continue

        project_root.mkdir(parents=True, exist_ok=True)
        if not plan_path.exists():
            write_text_atomic(plan_path, PLAN_MD_SKELETON.format(slug=slug))
            actions.append("plan.md")
        action = _repair_binding_file(
            binding_path,
            slug=slug,
            name=project["name"],
            kernel_id=project["id"],
            root=root,
        )
        if action == "created":
            actions.append("project.json")
        elif action == "patched":
            actions.append("binding-patch")
        elif action == "unreadable":
            actions.append("UNREADABLE")

        results.append({"slug": slug, "action": "+".join(actions) or "ok"})
    return results


def verify_workspaces(root: Path) -> tuple[bool, list[str]]:
    """Re-read kernel rows and assert every workspace binding is valid."""
    from astrid.core.foundation.project_paths import project_dir
    from astrid.core.project.project import require_project

    db = root / ".astrid" / "astrid.sqlite3"
    failures: list[str] = []
    for project in _kernel_projects(db):
        slug = project["slug"]
        project_dir_path = project_dir(slug, root=root)
        plan_path = project_dir_path / "plan.md"
        binding_path = project_dir_path / "project.json"
        if not plan_path.is_file():
            failures.append(f"{slug}: plan.md missing")
            continue
        if not binding_path.is_file():
            failures.append(f"{slug}: project.json missing")
            continue
        try:
            resolved = require_project(slug, root=root)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the audit
            failures.append(f"{slug}: require_project failed: {exc}")
            continue
        if resolved.get("project_id") != project["id"]:
            failures.append(
                f"{slug}: project_id {resolved.get('project_id')!r} != "
                f"kernel id {project['id']!r}"
            )
        if resolved.get("kernel_authority") is not True:
            failures.append(f"{slug}: kernel_authority is not true")
    return not failures, failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v10 repair: materialize per-project workspaces (kernel binding)"
    )
    parser.add_argument("--apply", action="store_true", help="write workspace files")
    parser.add_argument("--root", default=None, help="projects root")
    parser.add_argument(
        "--project", action="append", default=[], help="restrict to one slug"
    )
    args = parser.parse_args()

    root = (
        Path(args.root)
        if args.root
        else Path(__file__).resolve().parents[3] / "projects"
    )
    results = migrate_workspaces(
        apply=args.apply, root=root, project_filter=set(args.project)
    )
    for row in results:
        print(f"workspace {row['slug']}: {row['action']}")

    ok, failures = verify_workspaces(root)
    if args.apply:
        for failure in failures:
            print(f"migrate_workspaces: FAIL {failure}", file=sys.stderr)
    print(
        f"migrate_workspaces: {'applied' if args.apply else 'dry-run'} "
        f"{len(results)} projects; verify "
        f"{'PASS' if ok else 'FAIL'} ({len(failures)} invalid)"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
