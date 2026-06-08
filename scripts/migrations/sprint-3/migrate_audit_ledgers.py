#!/usr/bin/env python3
"""Migrate run-local audit ledgers to schema_version:2 hash chains.

Usage:
  scripts/migrations/sprint-3/migrate_audit_ledgers.py --dry-run   # default
  scripts/migrations/sprint-3/migrate_audit_ledgers.py --apply

Walks ``audit/ledger.jsonl`` files under Astrid project runs and rewrites valid
legacy ledgers in place. Apply mode writes ``ledger.jsonl.audit-ledger.sprint3.bak``
before the rewrite. Corrupted or truncated ledgers are reported and left
untouched.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from astrid.core.audit.transport import (  # noqa: E402
    AUDIT_LEDGER_SCHEMA_VERSION,
    AuditLedgerError,
    migrate_records_to_v2,
    parse_ledger_bytes,
    serialize_records,
    verify_records,
)

PROJECTS_ROOT_DEFAULT = os.path.expanduser("~/Documents/reigh-workspace/astrid-projects")
BACKUP_SUFFIX = ".audit-ledger.sprint3.bak"


@dataclass(frozen=True)
class MigrationResult:
    action: str
    reason: str


def find_ledgers(root: Path) -> list[Path]:
    if not root.exists():
        return []
    ledgers = set(root.glob("*/runs/*/audit/ledger.jsonl"))
    ledgers.update(root.glob("runs/*/audit/ledger.jsonl"))
    if root.name == "audit" and (root / "ledger.jsonl").is_file():
        ledgers.add(root / "ledger.jsonl")
    if root.name != "audit" and (root / "audit" / "ledger.jsonl").is_file():
        ledgers.add(root / "audit" / "ledger.jsonl")
    return sorted(ledgers)


def classify_ledger(ledger_path: Path) -> tuple[MigrationResult, list[dict]]:
    try:
        records = parse_ledger_bytes(ledger_path.read_bytes(), require_final_newline=True)
    except (OSError, AuditLedgerError) as exc:
        return MigrationResult("corrupt", str(exc)), []

    ok, line_number, reason = verify_records(records)
    if not ok:
        location = f"line {line_number}: " if line_number is not None else ""
        return MigrationResult("corrupt", f"{location}{reason}"), []

    if not records:
        return MigrationResult("skip", "empty ledger"), records
    if all(record.get("schema_version") == AUDIT_LEDGER_SCHEMA_VERSION for record in records):
        return MigrationResult("skip", "already schema_version:2"), records
    return MigrationResult("migrate", "legacy records require v2 hash-chain fields"), records


def migrate_ledger_path(ledger_path: Path, *, apply: bool) -> MigrationResult:
    result, records = classify_ledger(ledger_path)
    if result.action != "migrate" or not apply:
        return result

    migrated = migrate_records_to_v2(records)
    new_text = serialize_records(migrated)
    backup_path = ledger_path.with_name(ledger_path.name + BACKUP_SUFFIX)
    if not backup_path.exists():
        backup_path.write_bytes(ledger_path.read_bytes())

    fd, tmp_name = tempfile.mkstemp(prefix=ledger_path.name + ".", suffix=".tmp", dir=str(ledger_path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(new_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, ledger_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return MigrationResult("migrated", f"rewrote with backup {backup_path.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate audit/ledger.jsonl files to v2 hash-chain transport.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview changes without modifying files (default)")
    parser.add_argument("--apply", action="store_true", help="Commit changes to disk")
    parser.add_argument(
        "--projects-root",
        default=PROJECTS_ROOT_DEFAULT,
        help=f"Root of astrid-projects or a run directory (default: {PROJECTS_ROOT_DEFAULT})",
    )
    args = parser.parse_args(argv)
    apply = bool(args.apply)
    root = Path(os.path.expanduser(args.projects_root))
    ledgers = find_ledgers(root)
    if not ledgers:
        print(f"No audit ledgers found under {root}. Workspace is clean.")
        return 0

    counts = {"migrate": 0, "migrated": 0, "skip": 0, "corrupt": 0}
    for ledger_path in ledgers:
        result = migrate_ledger_path(ledger_path, apply=apply)
        counts[result.action] = counts.get(result.action, 0) + 1
        rel = ledger_path.relative_to(root) if ledger_path.is_relative_to(root) else ledger_path
        verb = "rewrite" if result.action in {"migrate", "migrated"} else result.action
        print(f"  {verb}: {rel} ({result.reason})")

    action = "APPLIED" if apply else "DRY-RUN"
    pending_or_done = counts["migrated"] if apply else counts["migrate"]
    print(
        f"Audit ledger migration {action}: {pending_or_done} rewritten, "
        f"{counts['skip']} skipped, {counts['corrupt']} corrupt"
    )
    return 1 if counts["corrupt"] else 0


if __name__ == "__main__":
    sys.exit(main())
