"""CLI for the operational ``backup`` family (m6 sprint plan, Phase 1).

Exposes::

    astrid backup restore <BACKUP_PATH> [--projects-root PATH] [--force] [--json]

The ``--json`` flag (accepted in any position) switches to machine-readable
output and, on restore failure, a non-zero exit code with a typed error
payload on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys

from astrid.core.backup.operations import (
    BackupError,
    RestoreValidationError,
    create_backup,
    restore_backup,
)
from astrid.core.store.ownership import OwnerLockError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astrid backup",
        description="Back up or restore the managed Astrid database and media.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a backup.")
    create.add_argument("--out", dest="out", default=None, help="Backup directory.")
    create.add_argument(
        "--projects-root",
        default=None,
        help="Projects root (default: ASTRID_PROJECTS_ROOT or the default root).",
    )

    restore = sub.add_parser("restore", help="Restore a backup.")
    restore.add_argument("backup_path", help="Path to the backup directory.")
    restore.add_argument(
        "--force",
        action="store_true",
        help=(
            "Replace an existing live database that already holds data "
            "(refused without this flag)."
        ),
    )
    restore.add_argument(
        "--projects-root",
        default=None,
        help="Projects root (default: ASTRID_PROJECTS_ROOT or the default root).",
    )
    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in raw
    filtered = [arg for arg in raw if arg != "--json"]
    args = build_parser().parse_args(filtered)

    if args.command == "create":
        try:
            result = create_backup(
                projects_root=args.projects_root, dest_path=args.out
            )
        except (BackupError, OwnerLockError) as exc:
            if json_mode:
                _print_json({"ok": False, "error": "backup_failed", "detail": str(exc)})
            else:
                print(f"backup failed: {exc}", file=sys.stderr)
            return 1
        if json_mode:
            _print_json({"ok": True, "dest_path": str(result.dest_path), **result.to_dict()})
        else:
            print(f"backup created at {result.dest_path}")
            print(f"  media files: {result.media_files}")
            print(f"  sqlite pages: {result.sqlite_pages}")
        return 0

    if args.command == "restore":
        try:
            result = restore_backup(
                args.backup_path,
                projects_root=args.projects_root,
                allow_overwrite=args.force,
            )
        except RestoreValidationError as exc:
            if json_mode:
                _print_json(
                    {"ok": False, "error": "restore_validation", "detail": str(exc)}
                )
            else:
                print(f"restore failed: {exc}", file=sys.stderr)
            return 1
        except (BackupError, OwnerLockError) as exc:
            if json_mode:
                _print_json({"ok": False, "error": "restore_failed", "detail": str(exc)})
            else:
                print(f"restore failed: {exc}", file=sys.stderr)
            return 1
        if json_mode:
            _print_json({"ok": True, **result.to_dict()})
        else:
            print(f"restore complete: {result.database_path}")
            print(f"  restored media files: {result.restored_media_files}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
