"""Read-only data diagnostics for Astrid (m6 v10 doctor rewrite).

This module replaces the old environment checks (executor/orchestrator
registries, element catalog, vibecomfy/remotion/runpod probing) with exactly
six read-only v10 checks over the managed database and media tree:

1. ``sqlite_quick_check`` — open the database ``mode=ro`` and run
   ``PRAGMA quick_check`` (page-level integrity);
2. ``fk_integrity`` — ``PRAGMA foreign_key_check`` (referential integrity);
3. ``schema_versions`` — the ``schema_migrations`` rows (core + installed
   pack versions) compared against the current standard registry;
4. ``media_paths`` — the managed-media root and ``sha256/`` digest tree are
   accessible, and any orphaned ``.staging`` directories are reported;
5. ``data_paths`` — the projects root and ``.astrid/`` are accessible;
6. ``python_version`` — the Python 3.10+ floor.

The doctor is **strictly read-only**: it never runs ``VACUUM``, ``REINDEX``,
or any repair, and it never opens a writable connection. On a missing or
corrupt database it fails closed — the affected checks report ``fail`` with a
stable detail, the overall ``ok`` is ``false``, and the process exits ``1``.

The JSON surface is stable: ``{"ok": bool, "checks": [{"name", "status",
"detail", "required"}, ...]}``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.migrations.runner import MigrationError, probe_database

Status = str

MIN_PYTHON = (3, 10)

MANAGED_DIR_NAME = ".astrid"
MEDIA_DIR_NAME = "media"
SHA256_DIR_NAME = "sha256"
STAGING_DIR_NAME = ".staging"

NEW_ROOT_GUIDANCE = (
    "expected on a brand-new projects root; run "
    "`astrid projects create <slug> --name <Name>` to initialize it"
)


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: Status
    detail: str
    required: bool = True

    def failed(self, *, strict_optional: bool = False) -> bool:
        if self.status == "fail":
            return True
        return strict_optional and not self.required and self.status == "warn"


def run_checks(
    *, projects_root: str | Path | None = None
) -> tuple[DoctorCheck, ...]:
    """Run the six read-only v10 checks against the resolved projects root."""
    root = resolve_projects_root(projects_root)
    return (
        _check_python_version(),
        _check_data_paths(root),
        _check_media_paths(root),
        _check_sqlite_quick_check(root),
        _check_fk_integrity(root),
        _check_schema_versions(root),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid doctor",
        description=(
            "Check the Astrid managed data environment (read-only) or run "
            "setup repair (``doctor setup``)."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable diagnostics."
    )
    parser.add_argument(
        "--strict-optional",
        action="store_true",
        help="Treat optional warnings as failures.",
    )
    parser.add_argument(
        "--projects-root",
        default=None,
        help="Projects root (default: ASTRID_PROJECTS_ROOT or the default root).",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("setup",),
        default=None,
        help=(
            "``setup`` deep re-hashes every stamped artifact against its "
            "signed manifest, repairs corrupt artifacts (targeted re-"
            "acquisition with --source), and reconciles a corrupted setup "
            "journal from filesystem reality."
        ),
    )
    parser.add_argument(
        "--source",
        default=None,
        help=(
            "Base URL for targeted re-acquisition during ``setup`` "
            "(artifact id is appended); setup mode is the only sanctioned "
            "outbound networking."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "setup":
        return _run_setup(args)
    checks = run_checks(projects_root=args.projects_root)
    failed = any(
        check.failed(strict_optional=args.strict_optional) for check in checks
    )
    if args.json:
        payload = {
            "ok": not failed,
            "checks": [asdict(check) for check in checks],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Astrid doctor")
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
    return 1 if failed else 0


def _run_setup(args: argparse.Namespace) -> int:
    """``astrid doctor setup`` — deep re-hash + repair + reconciliation."""
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.model_setup.acquire import acquire_artifact
    from astrid.core.model_setup.repair import doctor_setup

    root = resolve_projects_root(args.projects_root)

    def _acquire(manifest):  # type: ignore[no-untyped-def]
        acquire_artifact(
            manifest,
            root,
            f"{args.source.rstrip('/')}/{manifest.artifact_id}",
        )

    reports = doctor_setup(root, acquire=_acquire if args.source else None)
    failed = any(
        report.verdict in ("corrupt", "repair_failed", "orphaned")
        for report in reports
    )
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not failed,
                    "reports": [report.to_dict() for report in reports],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("Astrid doctor setup")
        for report in reports:
            print(f"[{report.verdict}] {report.artifact_id}: {report.detail}")
        if not reports:
            print("[ok] every stamped artifact verified; journal clean")
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# python_version
# ---------------------------------------------------------------------------


def _check_python_version() -> DoctorCheck:
    version = sys.version_info
    if version < MIN_PYTHON:
        return DoctorCheck(
            name="python_version",
            status="fail",
            detail=(
                f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required; "
                f"found {version.major}.{version.minor}.{version.micro}"
            ),
        )
    return DoctorCheck(
        name="python_version",
        status="ok",
        detail=f"{version.major}.{version.minor}.{version.micro}",
    )


# ---------------------------------------------------------------------------
# data_paths
# ---------------------------------------------------------------------------


def _check_data_paths(root: Path) -> DoctorCheck:
    if not root.is_dir():
        return DoctorCheck(
            name="data_paths",
            status="fail",
            detail=f"projects root does not exist: {root}",
        )
    astrid_dir = root / MANAGED_DIR_NAME
    if not astrid_dir.is_dir():
        return DoctorCheck(
            name="data_paths",
            status="fail",
            detail=f"managed data directory is missing: {astrid_dir}",
        )
    return DoctorCheck(
        name="data_paths",
        status="ok",
        detail=f"{root} and .astrid/ accessible",
    )


# ---------------------------------------------------------------------------
# media_paths
# ---------------------------------------------------------------------------


def _check_media_paths(root: Path) -> DoctorCheck:
    media_root = root / MANAGED_DIR_NAME / MEDIA_DIR_NAME
    if not media_root.exists():
        return DoctorCheck(
            name="media_paths",
            status="ok",
            detail="no managed-media tree yet",
            required=False,
        )
    if not media_root.is_dir():
        return DoctorCheck(
            name="media_paths",
            status="fail",
            detail=f"managed-media path is not a directory: {media_root}",
        )

    sha256_dir = media_root / SHA256_DIR_NAME
    if sha256_dir.exists() and not sha256_dir.is_dir():
        return DoctorCheck(
            name="media_paths",
            status="fail",
            detail=f"sha256 digest path is not a directory: {sha256_dir}",
        )

    staging_dir = media_root / STAGING_DIR_NAME
    orphaned = 0
    if staging_dir.is_dir():
        orphaned = sum(1 for entry in staging_dir.iterdir() if entry.is_dir())
    if orphaned:
        return DoctorCheck(
            name="media_paths",
            status="warn",
            detail=f"{orphaned} orphaned staging director(ies) under {staging_dir}",
            required=False,
        )
    if sha256_dir.is_dir():
        return DoctorCheck(
            name="media_paths",
            status="ok",
            detail="managed-media sha256 tree accessible",
        )
    return DoctorCheck(
        name="media_paths",
        status="ok",
        detail="managed-media tree accessible, no digest tree yet",
        required=False,
    )


# ---------------------------------------------------------------------------
# sqlite_quick_check
# ---------------------------------------------------------------------------


def _database_path(root: Path) -> Path:
    return derive_database_path(root)


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{db_path}?mode=ro", uri=True, isolation_level=None
    )


def _check_sqlite_quick_check(root: Path) -> DoctorCheck:
    db_path = _database_path(root)
    if not db_path.is_file():
        return DoctorCheck(
            name="sqlite_quick_check",
            status="fail",
            detail=f"database missing: {db_path} ({NEW_ROOT_GUIDANCE})",
        )
    try:
        conn = _open_read_only(db_path)
    except sqlite3.Error as exc:
        return DoctorCheck(
            name="sqlite_quick_check",
            status="fail",
            detail=f"cannot open database read-only: {exc}",
        )
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
    except sqlite3.Error as exc:
        return DoctorCheck(
            name="sqlite_quick_check",
            status="fail",
            detail=f"quick_check failed: {exc}",
        )
    finally:
        conn.close()
    if result != "ok":
        return DoctorCheck(
            name="sqlite_quick_check",
            status="fail",
            detail=f"quick_check reported: {result!r}",
        )
    return DoctorCheck(name="sqlite_quick_check", status="ok", detail="quick_check ok")


# ---------------------------------------------------------------------------
# fk_integrity
# ---------------------------------------------------------------------------


def _check_fk_integrity(root: Path) -> DoctorCheck:
    db_path = _database_path(root)
    if not db_path.is_file():
        return DoctorCheck(
            name="fk_integrity",
            status="fail",
            detail=f"database missing: {db_path} ({NEW_ROOT_GUIDANCE})",
        )
    try:
        conn = _open_read_only(db_path)
    except sqlite3.Error as exc:
        return DoctorCheck(
            name="fk_integrity",
            status="fail",
            detail=f"cannot open database read-only: {exc}",
        )
    try:
        rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.Error as exc:
        return DoctorCheck(
            name="fk_integrity",
            status="fail",
            detail=f"foreign_key_check failed: {exc}",
        )
    finally:
        conn.close()
    if rows:
        return DoctorCheck(
            name="fk_integrity",
            status="fail",
            detail=f"{len(rows)} foreign key violation(s)",
        )
    return DoctorCheck(
        name="fk_integrity", status="ok", detail="no foreign key violations"
    )


# ---------------------------------------------------------------------------
# schema_versions
# ---------------------------------------------------------------------------


def _check_schema_versions(root: Path) -> DoctorCheck:
    from astrid.core.schema_packs.standard import build_standard_registry

    db_path = _database_path(root)
    registry = build_standard_registry()
    try:
        probe = probe_database(db_path, registry)
    except MigrationError as exc:
        return DoctorCheck(
            name="schema_versions",
            status="fail",
            detail=str(exc),
        )
    except sqlite3.Error as exc:
        # Fail closed on a corrupt/unreadable database file: a doctor that
        # raises out of `run_checks` would crash the CLI instead of returning
        # the stable `{"ok": false}` envelope, so surface the read failure as
        # a failed check (matching sqlite_quick_check / fk_integrity).
        return DoctorCheck(
            name="schema_versions",
            status="fail",
            detail=f"cannot read database schema: {exc}",
        )
    if not probe.exists:
        return DoctorCheck(
            name="schema_versions",
            status="fail",
            detail=f"database missing: {db_path} ({NEW_ROOT_GUIDANCE})",
        )
    by_pack: dict[str, int] = {}
    for applied in probe.applied:
        by_pack[applied.pack] = applied.version
    detail = ", ".join(
        f"{pack}={version}" for pack, version in sorted(by_pack.items())
    )
    return DoctorCheck(
        name="schema_versions",
        status="ok",
        detail=detail or "no applied migrations",
    )


if __name__ == "__main__":
    raise SystemExit(main())
