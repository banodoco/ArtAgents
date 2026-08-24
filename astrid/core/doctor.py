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
   accessible, managed and external locators resolve to the recorded bytes,
   and any orphaned ``.staging`` directories are reported;
5. ``data_paths`` — the projects root and ``.astrid/`` are accessible;
6. ``python_version`` — the Python 3.10+ floor.

The doctor is **strictly read-only**: it never runs ``VACUUM``, ``REINDEX``,
or any repair, and it never opens a writable connection. On a missing or
corrupt database it fails closed — an existing managed root with a missing or
corrupt database reports ``fail`` with a stable detail, the overall ``ok`` is
``false``, and the process exits ``1``. A root with no ``.astrid`` store yet is
reported as ``uninitialized`` (with ``ok: true`` and exit ``0``), so the
first-run diagnostic distinguishes a setup state from an unhealthy store.

The JSON surface is stable: ``{"ok": bool, "checks": [{"name", "status",
"detail", "required"}, ...], "state": "uninitialized|ready|unhealthy",
"next_action": string | null}``. A pristine root remains healthy
(``ok: true``, exit ``0``) while exposing the one setup action needed next.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.io.media_import import managed_media_path, sha256_file_bytes
from astrid.core.kernel.database import resolve_kernel_database_authority
from astrid.core.migrations.runner import MigrationError, probe_database

Status = str

MIN_PYTHON = (3, 10)

MANAGED_DIR_NAME = ".astrid"
MEDIA_DIR_NAME = "media"
SHA256_DIR_NAME = "sha256"
STAGING_DIR_NAME = ".staging"
EXTERNAL_FAILURE_DETAIL_LIMIT = 8

NEW_ROOT_GUIDANCE = (
    "expected on a brand-new projects root; run "
    "`astrid projects create <slug> --name <Name>` to initialize it"
)

NEW_ROOT_NEXT_ACTION = (
    "Initialize a project with `python3 -m astrid projects create "
    "<slug> --name <Name>`"
)


def _is_uninitialized_root(root: Path) -> bool:
    """Return true only when no managed store has been started yet."""

    authority = resolve_kernel_database_authority(root)
    return not (root / MANAGED_DIR_NAME).exists() and not authority.exists


def _uninitialized_check(name: str, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status="uninitialized", detail=detail, required=False)


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
    state = (
        "unhealthy"
        if failed
        else "uninitialized"
        if any(check.status == "uninitialized" for check in checks)
        else "ready"
    )
    next_action = NEW_ROOT_NEXT_ACTION if state == "uninitialized" else None
    if args.json:
        payload = {
            "ok": not failed,
            "checks": [asdict(check) for check in checks],
            "state": state,
            "next_action": next_action,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Astrid doctor")
        print(f"state: {state}")
        if next_action is not None:
            print(f"next action: {next_action}")
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
    if _is_uninitialized_root(root):
        return _uninitialized_check(
            "data_paths",
            f"projects root is ready to initialize: {root} ({NEW_ROOT_GUIDANCE})",
        )
    if not root.is_dir():
        return DoctorCheck(
            name="data_paths",
            status="fail",
            detail=f"projects root does not exist: {root}",
        )
    authority = resolve_kernel_database_authority(root)
    if authority.mode == "legacy":
        return DoctorCheck(
            name="data_paths",
            status="warn",
            detail=(
                f"legacy database fallback active: {authority.selected_path}; "
                f"canonical database is absent: {authority.canonical_path}. "
                "Complete the intended migration or restore, then rerun doctor; "
                "do not remove either ledger until canonical data is verified."
            ),
            required=False,
        )
    astrid_dir = root / MANAGED_DIR_NAME
    if not astrid_dir.is_dir():
        return DoctorCheck(
            name="data_paths",
            status="fail",
            detail=f"managed data directory is missing: {astrid_dir}",
        )
    if authority.coexists:
        ignored = ", ".join(str(path) for path in authority.existing_legacy_paths)
        return DoctorCheck(
            name="data_paths",
            status="warn",
            detail=(
                f"canonical database selected: {authority.canonical_path}; "
                f"ignored legacy database path(s): {ignored}. Complete the "
                "intended migration, then archive or remove legacy ledgers only "
                "after canonical data is verified."
            ),
            required=False,
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
        structural = DoctorCheck(
            name="media_paths",
            status="ok",
            detail="no managed-media tree yet",
            required=False,
        )
        return _with_external_integrity(root, structural)
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
    locator_problem = _managed_media_locator_problem(root)
    external_problem = _external_media_locator_problem(root)
    if locator_problem is not None or external_problem is not None:
        return DoctorCheck(
            name="media_paths",
            status="fail",
            detail=locator_problem or external_problem or "media integrity check failed",
        )
    if orphaned:
        paths = _orphaned_staging_paths(staging_dir)
        shown = ", ".join(str(path) for path in paths)
        remaining = orphaned - len(paths)
        if remaining:
            shown += f", (+{remaining} more)"
        cleanup = (
            "safe cleanup: after confirming no active media command owns them, "
            "remove only the listed staging directories"
        )
        return _with_external_integrity(root, DoctorCheck(
            name="media_paths",
            status="warn",
            detail=(
                f"{orphaned} orphaned staging director(ies) under {staging_dir}: "
                f"{shown}; {cleanup}"
            ),
            required=False,
        ))
    if sha256_dir.is_dir():
        return _with_external_integrity(root, DoctorCheck(
            name="media_paths",
            status="ok",
            detail="managed-media sha256 tree accessible; managed locators resolve",
        ))
    return _with_external_integrity(root, DoctorCheck(
        name="media_paths",
        status="ok",
        detail="managed-media tree accessible, no digest tree yet; managed locators resolve",
        required=False,
    ))


def _with_external_integrity(root: Path, check: DoctorCheck) -> DoctorCheck:
    """Make the external integrity coverage explicit in every healthy detail.

    External media is intentionally checked here rather than treated as an
    optional hint: a healthy doctor result must not hide a missing or mutated
    external locator. The check is read-only and hashes each external file
    against the immutable ``media.content_hash`` identity.
    """
    managed_problem = _managed_media_locator_problem(root)
    external_problem = _external_media_locator_problem(root)
    if managed_problem is not None or external_problem is not None:
        return DoctorCheck(
            name=check.name,
            status="fail",
            detail=managed_problem or external_problem or "media integrity check failed",
            required=True,
        )
    count = _external_media_count(root)
    if count is None:
        return check
    if count:
        suffix = f"; external_local integrity verified ({count} locator(s))"
        # Keep an orphan-staging warning optional even when external integrity
        # is healthy; any actual external failure above is always a required
        # ``fail`` regardless of this presentation flag.
        required = check.required
    else:
        suffix = "; no external_local media locators to verify"
        required = check.required
    return DoctorCheck(
        name=check.name,
        status=check.status,
        detail=check.detail + suffix,
        required=required,
    )


def _external_media_count(root: Path) -> int | None:
    """Return the number of external locations, or ``None`` if unreadable."""
    db_path = _database_path(root)
    if not db_path.is_file():
        return 0
    try:
        conn = _open_read_only(db_path)
    except sqlite3.Error:
        return None
    try:
        try:
            row = conn.execute(
                "SELECT count(*) FROM media_locations "
                "WHERE realm = 'external_local'"
            ).fetchone()
        except sqlite3.Error:
            return None
    finally:
        conn.close()
    return int(row[0]) if row is not None else 0


def _managed_media_locator_problem(root: Path) -> str | None:
    """Return an actionable problem when managed locators are stale or missing.

    ``media_paths`` used to inspect only the directory shape, allowing a
    restored database to retain absolute locators into another projects root.
    The database projection is part of the managed-media contract: every
    ``managed_local`` locator must be the digest-derived path in this root and
    that path must resolve to a regular file.
    """
    db_path = _database_path(root)
    if not db_path.is_file():
        return None
    try:
        conn = _open_read_only(db_path)
    except sqlite3.Error as exc:
        return f"cannot inspect managed media locators: {exc}"
    try:
        try:
            rows = conn.execute(
                "SELECT l.id, l.locator, m.content_hash "
                "FROM media_locations AS l "
                "JOIN media AS m ON m.id = l.media_id "
                "WHERE l.realm = 'managed_local' "
                "ORDER BY l.id"
            ).fetchall()
        except sqlite3.Error as exc:
            return f"cannot inspect managed media locators: {exc}"
    finally:
        conn.close()

    for location_id, locator, content_hash in rows:
        try:
            expected = managed_media_path(root, content_hash).resolve()
        except (TypeError, ValueError) as exc:
            return (
                f"managed media locator {location_id} has invalid content hash "
                f"{content_hash!r}: {exc}"
            )
        locator_path = Path(str(locator))
        actual = locator_path.resolve()
        if actual != expected:
            return (
                f"managed media locator {location_id} points outside this root "
                f"({locator}); expected {expected}; run backup restore or "
                "media relocate --realm managed_local"
            )
        if locator_path.is_symlink() or not actual.is_file():
            return (
                f"managed media locator {location_id} does not resolve to a "
                f"regular file: {actual}; restore or relocate the media"
            )
    return None


def _external_media_locator_problem(root: Path) -> str | None:
    """Return an actionable problem for a missing or mutated external file.

    External locators are user-owned paths, so doctor never rewrites or moves
    them. It reports the location/media/project identity and the public verify
    and relocate recovery commands instead.
    """
    db_path = _database_path(root)
    if not db_path.is_file():
        return None
    try:
        conn = _open_read_only(db_path)
    except sqlite3.Error as exc:
        return f"cannot inspect external media locators: {exc}"
    try:
        try:
            rows = conn.execute(
                "SELECT l.id, l.locator, m.id, m.content_hash, "
                "m.project_id, p.slug "
                "FROM media_locations AS l "
                "JOIN media AS m ON m.id = l.media_id "
                "JOIN projects AS p ON p.id = m.project_id "
                "WHERE l.realm = 'external_local' ORDER BY l.id"
            ).fetchall()
        except sqlite3.Error as exc:
            return f"cannot inspect external media locators: {exc}"
    finally:
        conn.close()

    failures: list[tuple[str, str]] = []
    counts = {"hash_mismatch": 0, "unavailable": 0, "unreadable": 0}
    for location_id, locator, media_id, expected_hash, project_id, project_slug in rows:
        locator_path = Path(str(locator)).expanduser()
        verify_command = (
            f"astrid media verify {media_id} --project {project_slug} "
            "--realm external_local"
        )
        relocate_command = (
            f"astrid media relocate {media_id} --project {project_slug} "
            "--realm external_local --locator <source-file>"
        )
        identity = (
            f"external media locator {location_id} for media {media_id} "
            f"(project {project_slug}/{project_id}) at {locator_path}"
        )
        if not locator_path.is_file():
            counts["unavailable"] += 1
            failures.append((
                "unavailable",
                f"{identity} is unavailable; restore the external file or run "
                f"`{relocate_command}` (verify with `{verify_command}`)",
            ))
            continue
        try:
            actual_hash = sha256_file_bytes(locator_path)
        except (OSError, ValueError) as exc:
            counts["unreadable"] += 1
            failures.append((
                "unreadable",
                f"{identity} could not be read ({exc}); restore the external "
                f"file or run `{relocate_command}` (verify with `{verify_command}`)",
            ))
            continue
        if actual_hash != str(expected_hash):
            counts["hash_mismatch"] += 1
            failures.append((
                "hash_mismatch",
                f"{identity} hash mismatch: expected {expected_hash}, "
                f"found {actual_hash}; restore the external file or run "
                f"`{relocate_command}` (verify with `{verify_command}`)",
            ))
    if not failures:
        return None

    total = len(failures)
    shown = failures[:EXTERNAL_FAILURE_DETAIL_LIMIT]
    entries = " | ".join(f"[{kind}] {detail}" for kind, detail in shown)
    truncated = total - len(shown)
    counts_text = ", ".join(
        f"{name}={counts[name]}" for name in ("hash_mismatch", "unavailable", "unreadable")
        if counts[name]
    )
    truncation = f"; truncated={truncated}" if truncated else "; truncated=0"
    return (
        f"external_local integrity failed: checked {len(rows)} locator(s), "
        f"failed {total} ({counts_text}); showing {len(shown)}/{total}; "
        f"cap={EXTERNAL_FAILURE_DETAIL_LIMIT}; entries: {entries}{truncation}"
    )


def _orphaned_staging_paths(staging_dir: Path, *, limit: int = 8) -> list[Path]:
    """Return a deterministic, bounded list of orphan staging directories."""
    try:
        entries = sorted(
            (entry for entry in staging_dir.iterdir() if entry.is_dir()),
            key=lambda path: str(path),
        )
    except OSError:
        return []
    return entries[:limit]


# ---------------------------------------------------------------------------
# sqlite_quick_check
# ---------------------------------------------------------------------------


def _database_path(root: Path) -> Path:
    return resolve_kernel_database_authority(root).selected_path


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{db_path}?mode=ro", uri=True, isolation_level=None
    )


def _check_sqlite_quick_check(root: Path) -> DoctorCheck:
    db_path = _database_path(root)
    if not db_path.is_file():
        if _is_uninitialized_root(root):
            return _uninitialized_check(
                "sqlite_quick_check",
                f"database not initialized: {db_path} ({NEW_ROOT_GUIDANCE})",
            )
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
        if _is_uninitialized_root(root):
            return _uninitialized_check(
                "fk_integrity",
                f"database not initialized: {db_path} ({NEW_ROOT_GUIDANCE})",
            )
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
        if _is_uninitialized_root(root):
            return _uninitialized_check(
                "schema_versions",
                f"database not initialized: {db_path} ({NEW_ROOT_GUIDANCE})",
            )
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
