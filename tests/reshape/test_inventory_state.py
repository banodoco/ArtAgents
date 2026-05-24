from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

from scripts.reshape.inventory_state import (
    CSV_COLUMNS,
    collect_inventory,
    main,
    write_inventory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_roots(tmp_path: Path) -> tuple[Path, Path]:
    projects_root = tmp_path / "projects-root"
    repo_root = tmp_path / "repo-root"

    _write(projects_root / "alpha" / "active_run.json")
    _write(projects_root / "alpha" / "current_run.json")
    _write(projects_root / "alpha" / "timeline.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "timeline.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "plan.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "lease.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "events.jsonl", '{"kind":"x"}\n')
    _write(projects_root / "alpha" / "runs" / "run-1" / "audit" / "ledger.jsonl", "{}\n")
    _write(projects_root / "alpha" / "runs" / "run-1" / "hype.plan.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "_llm_debug" / "request.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "artifact.mp4", "not state\n")
    _write(projects_root / "beta" / "current_run.json")

    _write(repo_root / ".astrid" / "threads.json")
    _write(repo_root / ".astrid" / "threads" / "thread-1" / "groups.json")
    _write(repo_root / ".astrid" / "threads" / "thread-1" / "selections.jsonl", "{}\n")
    _write(repo_root / ".astrid" / "threads" / "thread-1" / "scratch.txt")
    _write(repo_root / "runs" / "out-1" / ".astrid.variants.json")
    _write(repo_root / "src" / "not-state.py", "print('no')\n")
    return projects_root, repo_root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == CSV_COLUMNS
        return list(reader)


def test_inventory_state_emits_required_multiroot_rows_and_metadata(tmp_path: Path) -> None:
    projects_root, repo_root = _fixture_roots(tmp_path)
    out = tmp_path / "inventory.csv"

    rows = collect_inventory(projects_root=projects_root, repo_root=repo_root)
    written = write_inventory(rows, out)

    assert written == out.resolve()
    records = _read_csv(out)
    assert records == sorted(
        records,
        key=lambda row: (
            row["root_kind"],
            row["project_slug"],
            row["run_id"],
            row["state_kind"],
            row["relative_path"],
        ),
    )

    relative_paths = {row["relative_path"] for row in records}
    assert "alpha/active_run.json" in relative_paths
    assert "alpha/current_run.json" in relative_paths
    assert "alpha/timeline.json" in relative_paths
    assert "alpha/runs/run-1/timeline.json" in relative_paths
    assert "alpha/runs/run-1/plan.json" in relative_paths
    assert "alpha/runs/run-1/lease.json" in relative_paths
    assert "alpha/runs/run-1/events.jsonl" in relative_paths
    assert "alpha/runs/run-1/audit/ledger.jsonl" in relative_paths
    assert "alpha/runs/run-1/hype.plan.json" in relative_paths
    assert "alpha/runs/run-1/_llm_debug/request.json" in relative_paths
    assert ".astrid/threads.json" in relative_paths
    assert ".astrid/threads/thread-1/groups.json" in relative_paths
    assert ".astrid/threads/thread-1/selections.jsonl" in relative_paths
    assert "runs/out-1/.astrid.variants.json" in relative_paths
    assert "alpha/runs/run-1/artifact.mp4" not in relative_paths
    assert "src/not-state.py" not in relative_paths
    assert all(not Path(row["relative_path"]).is_absolute() for row in records)

    kinds = {row["state_kind"] for row in records}
    assert {
        "legacy_active_run",
        "current_run",
        "project_timeline",
        "run_timeline",
        "run_plan",
        "run_lease",
        "run_events",
        "audit_ledger",
        "hype_plan",
        "llm_debug",
        "repo_thread_index",
        "repo_thread_group",
        "repo_thread_selection",
        "variant_sidecar",
    } <= kinds

    by_path = {row["relative_path"]: row for row in records}
    lease = by_path["alpha/runs/run-1/lease.json"]
    lease_path = projects_root / lease["relative_path"]
    assert lease["root_kind"] == "projects"
    assert lease["project_slug"] == "alpha"
    assert lease["run_id"] == "run-1"
    assert int(lease["size_bytes"]) == lease_path.stat().st_size
    assert int(lease["mtime_ns"]) == lease_path.stat().st_mtime_ns
    assert lease["sha256"] == hashlib.sha256(lease_path.read_bytes()).hexdigest()

    thread_index = by_path[".astrid/threads.json"]
    assert thread_index["root_kind"] == "repo"
    assert thread_index["project_slug"] == ""
    assert thread_index["run_id"] == ""
    assert thread_index["sha256"] == hashlib.sha256((repo_root / ".astrid" / "threads.json").read_bytes()).hexdigest()


def test_inventory_state_cli_and_legacy_wrapper_write_same_contract(tmp_path: Path) -> None:
    projects_root, repo_root = _fixture_roots(tmp_path)
    canonical_out = tmp_path / "canonical.csv"
    wrapper_out = tmp_path / "wrapper.csv"

    assert main(
        [
            "--projects-root",
            str(projects_root),
            "--repo-root",
            str(repo_root),
            "--out",
            str(canonical_out),
        ]
    ) == 0

    result = subprocess.run(
        [
            sys.executable,
            "scripts/inventory_astrid_projects.py",
            "--projects-root",
            str(projects_root),
            "--repo-root",
            str(repo_root),
            "--out",
            str(wrapper_out),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Inventory written to" in result.stdout
    assert _read_csv(wrapper_out) == _read_csv(canonical_out)
