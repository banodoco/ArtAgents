"""Migrate legacy projects into the kernel DB (receipt key per project).

For every inventoried (non-``agentic-*``) project::

    client.projects.create(
        slug=slug, name=name,
        settings={"legacy": {"created_at": ..., "updated_at": ...}},
        idempotency_key="v10-migrate:project:{slug}",
    )

``default_timeline_id`` is deliberately **not** passed in settings — it is
repository-owned state (SD1) and is written later via
``TimelineRepository.create(set_default=True)`` during timeline migration.

Dry-run by default; ``--apply`` mutates the kernel DB (which must have
zero project rows — migrate_all guards this before invoking any phase).

Usage::

    python3 scripts/migrations/v10/migrate_projects.py --apply [--project SLUG]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import project_key  # noqa: E402


def migrate_projects(
    inventory: dict,
    apply: bool,
    project_filter: set[str],
    root: Path | None = None,
) -> list[dict]:
    from astrid.sdk.client import AstridClient

    projects = [
        p
        for p in inventory["projects"]
        if not project_filter or p["slug"] in project_filter
    ]
    results: list[dict] = []
    with AstridClient.open(projects_root=root) as client:
        for project in projects:
            slug = project["slug"]
            legacy = {}
            project_json = project.get("project_json") or {}
            for key in ("created_at", "updated_at", "theme"):
                if project_json.get(key):
                    legacy[key] = project_json[key]
            settings = {"legacy": legacy} if legacy else {}
            if not apply:
                results.append(
                    {
                        "slug": slug,
                        "action": "plan",
                        "name": project["name"],
                        "settings": settings,
                        "key": project_key(slug),
                    }
                )
                continue
            result = client.projects.create(
                slug=slug,
                name=project["name"],
                settings=settings,
                idempotency_key=project_key(slug),
            )
            if not result.ok:
                raise SystemExit(
                    f"project {slug}: create failed: "
                    f"{result.error.code}: {result.error.message}"
                )
            results.append(
                {
                    "slug": slug,
                    "action": "replayed" if result.receipt is None else "created",
                    "name": result.data.get("name"),
                    "settings": result.data.get("settings"),
                    "key": project_key(slug),
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="v10: migrate legacy projects")
    parser.add_argument("--root", default=None, help="projects root (client open)")
    parser.add_argument(
        "--inventory",
        default=str(Path(__file__).resolve().parent / "inventory.json"),
    )
    parser.add_argument("--apply", action="store_true", help="mutate the kernel DB")
    parser.add_argument(
        "--project", action="append", default=[], help="restrict to one slug"
    )
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    if not inventory_path.is_file():
        print(f"migrate_projects: inventory not found: {inventory_path}", file=sys.stderr)
        return 2
    import json

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    results = migrate_projects(
        inventory,
        apply=args.apply,
        project_filter=set(args.project),
        root=root,
    )
    for row in results:
        print(
            f"project {row['slug']}: {row['action']} "
            f"(name={row['name']!r}, key={row['key']})"
        )
    print(f"migrate_projects: {'applied' if args.apply else 'dry-run'} {len(results)} projects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
