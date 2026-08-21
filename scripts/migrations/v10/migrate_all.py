"""Orchestrate the v10 legacy-data migration end to end.

Pipeline (each phase is a module above; all writes go through
AstridClient + the SDK/repositories — no raw SQL, no importer tables)::

    inventory -> projects -> media -> timelines -> generations -> verify

- Dry-run by default: builds the inventory (read-only), prints the plan
  (counts per family, fence vs zero-child split) and exits without
  touching the kernel DB or the legacy tree.
- ``--apply``: guards the DB (must have zero project rows), backs up
  ``projects/.astrid/astrid.sqlite3`` to
  ``astrid.sqlite3.pre-v10-migration.bak``, runs every phase, then
  verifies.

Idempotency: every mutation carries a stable receipt key
(``v10-migrate:{family}:{stable-id}``) so a re-run replays with zero new
rows; the backup guard additionally refuses to re-apply over a migrated
DB.

Usage::

    python3 scripts/migrations/v10/migrate_all.py [--dry-run|--apply]
        [--project SLUG]... [--realm managed_local|external_local]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import write_json  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
INVENTORY_PATH = SCRIPT_DIR / "inventory.json"
BACKUP_NAME = "astrid.sqlite3.pre-v10-migration.bak"


def _load_inventory(root: Path, inventory_path: Path) -> dict:
    from inventory import build_inventory

    if inventory_path.is_file():
        try:
            return json.loads(inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    inventory = build_inventory(root)
    write_json(inventory_path, inventory)
    print(f"migrate_all: wrote fresh inventory: {inventory_path}")
    return inventory


def _guard_db_empty(root: Path) -> None:
    """Warn when the kernel DB already has project rows.

    The migration is receipt-idempotent (``v10-migrate:*`` keys gate every
    command), so a re-run after an interrupted apply resumes safely: every
    completed row/event/receipt replays with zero new rows and the
    remainder continues. The guard is a warning now, not a hard stop — an
    interrupted run must be resumable.
    """
    db = root / ".astrid" / "astrid.sqlite3"
    if not db.is_file():
        return
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT count(*) FROM projects").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return
    count = int(row[0]) if row else 0
    if count > 0:
        print(
            f"migrate_all: kernel DB already has {count} project rows — "
            "resuming (receipts gate replay; no double-apply)."
        )


def _backup_db(root: Path) -> Path:
    db = root / ".astrid" / "astrid.sqlite3"
    backup = root / ".astrid" / BACKUP_NAME
    if not db.is_file():
        print("migrate_all: no existing kernel DB to back up (fresh root)")
        return backup
    if backup.exists():
        # Resume after an interrupted apply: the existing backup is the
        # pre-migration snapshot — never clobber it with a mid-state DB.
        print(
            f"migrate_all: backup already exists: {backup} — retaining the "
            "pre-migration snapshot (resume)."
        )
        return backup
    shutil.copy2(db, backup)
    print(f"migrate_all: backed up {db} -> {backup}")
    return backup


def _plan(inventory: dict, project_filter: set[str]) -> dict:
    """Read-only plan: counts per family + fence/zero-child split."""
    plan: dict = {
        "projects": 0,
        "timelines": 0,
        "media": 0,
        "runs": 0,
        "runs_fence": 0,
        "runs_zero_child": 0,
        "per_project": {},
    }
    for project in inventory["projects"]:
        slug = project["slug"]
        if project_filter and slug not in project_filter:
            continue
        eligible = [r for r in project["runs"] if r["eligible"]]
        fence = sum(
            1 for r in eligible if any(o["exists"] for o in r.get("outputs", []))
        )
        plan["projects"] += 1
        plan["timelines"] += len(project["timelines"])
        plan["media"] += len(project["media"]["referenced"])
        plan["runs"] += len(eligible)
        plan["runs_fence"] += fence
        plan["runs_zero_child"] += len(eligible) - fence
        plan["per_project"][slug] = {
            "timelines": len(project["timelines"]),
            "media": len(project["media"]["referenced"]),
            "runs": len(eligible),
            "runs_fence": fence,
            "runs_zero_child": len(eligible) - fence,
        }
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="v10: orchestrate the legacy migration")
    parser.add_argument("--root", default=None, help="projects root")
    parser.add_argument(
        "--inventory",
        default=str(INVENTORY_PATH),
        help="inventory.json path (fresh walk when missing)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="run the migration")
    mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="read-only plan (default)",
    )
    parser.add_argument(
        "--project", action="append", default=[], help="restrict to one slug"
    )
    parser.add_argument(
        "--realm",
        default="managed_local",
        choices=["managed_local", "external_local"],
        help="media realm (default managed_local)",
    )
    parser.add_argument("--skip-verify", action="store_true", help="skip verify.py")
    parser.add_argument(
        "--media-map",
        default=str(SCRIPT_DIR / "media_map.json"),
        help="media_map.json path (default <scriptdir>/media_map.json)",
    )
    parser.add_argument(
        "--report",
        default=str(SCRIPT_DIR / "migration_report.json"),
        help="migration_report.json path (default <scriptdir>/migration_report.json)",
    )
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    project_filter = set(args.project)
    apply = args.apply
    inventory = _load_inventory(root, Path(args.inventory))

    plan = _plan(inventory, project_filter)
    print(
        "migrate_all: plan "
        + " ".join(
            f"{key}={value}"
            for key, value in sorted(plan.items())
            if key != "per_project"
        )
    )
    for slug, row in sorted(plan["per_project"].items()):
        print(
            f"migrate_all:   {slug}: "
            + " ".join(f"{key}={value}" for key, value in sorted(row.items()))
        )

    if not apply:
        print("migrate_all: dry-run — no mutation (use --apply to run)")
        return 0

    _guard_db_empty(root)
    backup = _backup_db(root)
    print(f"migrate_all: backup at {backup}")

    from migrate_projects import migrate_projects
    from migrate_media import migrate_media
    from migrate_timelines import migrate_timelines
    from migrate_generations import migrate_generations

    print("migrate_all: phase projects")
    migrate_projects(inventory, apply=True, project_filter=project_filter, root=root)
    print("migrate_all: phase media")
    from migrate_media import set_media_map_path as set_media_map

    set_media_map(Path(args.media_map))
    media_summary = migrate_media(
        inventory,
        apply=True,
        project_filter=project_filter,
        root=root,
        realm=args.realm,
    )
    print("migrate_all: phase timelines")
    from migrate_timelines import set_media_map_path as set_tl_media_map

    set_tl_media_map(Path(args.media_map))
    migrate_timelines(
        inventory, apply=True, project_filter=project_filter, root=root
    )
    print("migrate_all: phase generations")
    from migrate_generations import set_media_map_path as set_gen_media_map
    from migrate_generations import set_report_path

    set_gen_media_map(Path(args.media_map))
    set_report_path(Path(args.report))
    run_results = migrate_generations(
        inventory, apply=True, project_filter=project_filter, root=root
    )

    if args.skip_verify:
        print("migrate_all: --skip-verify, done")
        print(f"migrate_all: media {media_summary}")
        print(f"migrate_all: runs {len(run_results)}")
        return 0

    from verify import run_verification

    ok, report = run_verification(
        inventory, root=root, media_map_path=Path(args.media_map)
    )
    print(
        "migrate_all: verify "
        + ("PASS" if ok else "FAIL")
        + " — "
        + "; ".join(f"{key}={value}" for key, value in sorted(report.items()))
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
