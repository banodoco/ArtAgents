"""Run a Sprint 0 migration safety gate against extracted dual roots."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.reshape.inventory_state import (
    InventoryRow,
    collect_inventory,
    write_inventory,
)
from scripts.reshape.restore_rehearsal import rehearse_restore

PROJECTS_PLACEHOLDER = "{projects_root}"
REPO_PLACEHOLDER = "{repo_root}"

_SCRUB_ENV_PREFIXES = ("ASTRID_TASK_",)
_SCRUB_ENV_NAMES = {
    "ASTRID_SESSION_ID",
    "ASTRID_PROJECT",
    "ASTRID_PROJECT_SLUG",
    "ASTRID_PROJECT_RUN",
    "ASTRID_CURRENT_RUN",
    "ASTRID_CURRENT_SESSION",
    "ASTRID_ATTACHED_SESSION",
}


@dataclass(frozen=True)
class CommandRun:
    label: str
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GateReport:
    ok: bool
    snapshot: str
    work_dir: str
    migration_command: str
    command_contract: str
    inventories: dict[str, str]
    checks: dict[str, bool]
    row_counts: dict[str, int]
    migration_runs: list[CommandRun]
    summary: list[str]

    def as_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["migration_runs"] = [asdict(run) for run in self.migration_runs]
        return payload


def _validate_command_contract(command: str, allow_env_root_injection: bool) -> str:
    has_projects = PROJECTS_PLACEHOLDER in command
    has_repo = REPO_PLACEHOLDER in command
    if has_projects and has_repo:
        return "placeholders"
    if allow_env_root_injection:
        return "explicit_env_root_injection"
    missing = []
    if not has_projects:
        missing.append(PROJECTS_PLACEHOLDER)
    if not has_repo:
        missing.append(REPO_PLACEHOLDER)
    raise SystemExit(
        "ERROR: migration command must include both "
        f"{PROJECTS_PLACEHOLDER} and {REPO_PLACEHOLDER}; missing {', '.join(missing)}"
    )


def _format_command(command: str, *, projects_root: Path, repo_root: Path) -> list[str]:
    formatted = command.replace(PROJECTS_PLACEHOLDER, shlex.quote(str(projects_root)))
    formatted = formatted.replace(REPO_PLACEHOLDER, shlex.quote(str(repo_root)))
    return shlex.split(formatted)


def _child_env(projects_root: Path, repo_root: Path) -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        if key in _SCRUB_ENV_NAMES or any(key.startswith(prefix) for prefix in _SCRUB_ENV_PREFIXES):
            continue
        env[key] = value
    env["ASTRID_PROJECTS_ROOT"] = str(projects_root)
    env["ASTRID_REPO_ROOT"] = str(repo_root)
    return env


def _run_command(label: str, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> CommandRun:
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(env),
        text=True,
        capture_output=True,
        check=False,
    )
    run = CommandRun(
        label=label,
        argv=list(argv),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"ERROR: migration command {label!r} failed with exit {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return run


def _inventory_map(rows: Sequence[InventoryRow], *, include_mtime: bool) -> list[dict[str, object]]:
    comparable: list[dict[str, object]] = []
    for row in rows:
        data = row.as_csv_row()
        if not include_mtime:
            data.pop("mtime_ns", None)
        comparable.append(data)
    return comparable


def _write_inventory(label: str, *, projects_root: Path, repo_root: Path, out_dir: Path) -> tuple[Path, list[InventoryRow]]:
    rows = collect_inventory(projects_root=projects_root, repo_root=repo_root)
    path = out_dir / f"{label}.csv"
    write_inventory(rows, path)
    return path, rows


def run_gate(
    *,
    snapshot: Path,
    migration_cmd: str,
    out: Path,
    work_dir: Path | None = None,
    allow_env_root_injection: bool = False,
) -> GateReport:
    contract = _validate_command_contract(migration_cmd, allow_env_root_injection)
    out = out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    root = work_dir.expanduser().resolve() if work_dir is not None else Path(tempfile.mkdtemp(prefix="astrid-migration-gate-"))
    root.mkdir(parents=True, exist_ok=True)

    first_restore = rehearse_restore(snapshot=snapshot, out_dir=root / "first")
    inventory_dir = root / "inventories"
    inventory_dir.mkdir(parents=True, exist_ok=True)

    pre_path, pre_rows = _write_inventory(
        "pre",
        projects_root=first_restore.projects_dir,
        repo_root=first_restore.repo_dir,
        out_dir=inventory_dir,
    )

    argv = _format_command(migration_cmd, projects_root=first_restore.projects_dir, repo_root=first_restore.repo_dir)
    env = _child_env(first_restore.projects_dir, first_restore.repo_dir)
    runs = [
        _run_command("migration", argv, cwd=root, env=env),
    ]
    post_path, post_rows = _write_inventory(
        "post",
        projects_root=first_restore.projects_dir,
        repo_root=first_restore.repo_dir,
        out_dir=inventory_dir,
    )

    runs.append(_run_command("migration_idempotence", argv, cwd=root, env=env))
    post_second_path, post_second_rows = _write_inventory(
        "post_second_run",
        projects_root=first_restore.projects_dir,
        repo_root=first_restore.repo_dir,
        out_dir=inventory_dir,
    )

    second_restore = rehearse_restore(snapshot=snapshot, out_dir=root / "second_restore")
    restore_path, restore_rows = _write_inventory(
        "second_restore",
        projects_root=second_restore.projects_dir,
        repo_root=second_restore.repo_dir,
        out_dir=inventory_dir,
    )

    pre_comparable = _inventory_map(pre_rows, include_mtime=False)
    post_comparable = _inventory_map(post_rows, include_mtime=False)
    restore_comparable = _inventory_map(restore_rows, include_mtime=False)
    post_second_full = _inventory_map(post_second_rows, include_mtime=True)
    post_full = _inventory_map(post_rows, include_mtime=True)

    checks = {
        "restore_comparable": restore_comparable == pre_comparable,
        "migration_changed_inventory": post_comparable != pre_comparable,
        "idempotent_second_run": post_second_full == post_full,
    }
    if not checks["restore_comparable"]:
        raise SystemExit("ERROR: second snapshot extraction inventory does not match pre-migration inventory")
    if not checks["idempotent_second_run"]:
        raise SystemExit("ERROR: migration command is not idempotent on second run")

    report = GateReport(
        ok=all(checks.values()),
        snapshot=str(snapshot.expanduser().resolve()),
        work_dir=str(root),
        migration_command=migration_cmd,
        command_contract=contract,
        inventories={
            "pre": str(pre_path),
            "post": str(post_path),
            "post_second_run": str(post_second_path),
            "second_restore": str(restore_path),
        },
        checks=checks,
        row_counts={
            "pre": len(pre_rows),
            "post": len(post_rows),
            "post_second_run": len(post_second_rows),
            "second_restore": len(restore_rows),
        },
        migration_runs=runs,
        summary=[
            "Migration gate passed",
            f"command_contract={contract}",
            f"pre_rows={len(pre_rows)} post_rows={len(post_rows)} post_second_run_rows={len(post_second_rows)}",
            f"migration_changed_inventory={str(checks['migration_changed_inventory']).lower()}",
            f"idempotent_second_run={str(checks['idempotent_second_run']).lower()}",
            f"restore_comparable={str(checks['restore_comparable']).lower()}",
        ],
    )

    with out.open("w", encoding="utf-8") as fh:
        json.dump(report.as_json(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Sprint 0 dual-root migration gate.")
    parser.add_argument("--snapshot", type=Path, required=True, help="Multi-root snapshot tarball.")
    parser.add_argument(
        "--migration-cmd",
        required=True,
        help="Command template. Must include {projects_root} and {repo_root} unless env injection is explicitly allowed.",
    )
    parser.add_argument("--out", type=Path, required=True, help="Machine-readable JSON report path.")
    parser.add_argument("--work-dir", type=Path, help="Optional empty or new work directory for extracted roots.")
    parser.add_argument(
        "--allow-env-root-injection",
        action="store_true",
        help="Accept a command without placeholders when the command is known to read ASTRID_PROJECTS_ROOT and ASTRID_REPO_ROOT.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_gate(
        snapshot=args.snapshot,
        migration_cmd=args.migration_cmd,
        out=args.out,
        work_dir=args.work_dir,
        allow_env_root_injection=args.allow_env_root_injection,
    )
    for line in report.summary:
        print(line)
    print(f"json={args.out.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
