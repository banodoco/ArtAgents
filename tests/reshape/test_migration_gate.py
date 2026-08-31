from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.reshape.migration_gate import main, run_gate
from scripts.reshape.snapshot_state import create_snapshot


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot_fixture(tmp_path: Path) -> Path:
    projects_root = tmp_path / "source-projects"
    repo_root = tmp_path / "source-repo"
    out_dir = tmp_path / "snapshots"

    repo_root.mkdir(parents=True)
    _write(projects_root / "alpha" / "current_run.json")
    _write(projects_root / "alpha" / "runs" / "run-1" / "events.jsonl")
    _write(projects_root / "alpha" / "runs" / "run-1" / "lease.json")
    _write(repo_root / "runs" / "out-1" / ".astrid.variants.json")
    return create_snapshot(
        projects_root=projects_root,
        repo_root=repo_root,
        out_dir=out_dir,
        timestamp="20260524-050607",
    )


def _positive_migration_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_migration.py"
    script.write_text(
        """
from __future__ import annotations

import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--projects-root", required=True)
parser.add_argument("--repo-root", required=True)
args = parser.parse_args()

projects = Path(args.projects_root)
repo = Path(args.repo_root)
assert os.environ["ASTRID_PROJECTS_ROOT"] == str(projects)
assert os.environ["ASTRID_REPO_ROOT"] == str(repo)
assert "ASTRID_SESSION_ID" not in os.environ
assert "ASTRID_TASK_PROJECT" not in os.environ

plan = projects / "alpha" / "runs" / "run-1" / "plan.json"
if not plan.exists():
    plan.write_text('{"version":2}\\n', encoding="utf-8")
variant = repo / "migrated" / ".astrid.variants.json"
if not variant.exists():
    variant.parent.mkdir(parents=True, exist_ok=True)
    variant.write_text('{"variants":[]}\\n', encoding="utf-8")
""".lstrip(),
        encoding="utf-8",
    )
    return script


def _ambient_live_root_script(tmp_path: Path) -> Path:
    script = tmp_path / "ambient_live_root_migration.py"
    script.write_text(
        """
from __future__ import annotations

import os
from pathlib import Path

projects = Path(os.environ["ASTRID_PROJECTS_ROOT"])
repo = Path(os.environ["ASTRID_REPO_ROOT"])
(projects / "live-projects-were-touched.txt").write_text("bad\\n", encoding="utf-8")
(repo / "live-repo-was-touched.txt").write_text("bad\\n", encoding="utf-8")
""".lstrip(),
        encoding="utf-8",
    )
    return script


def test_migration_gate_runs_dual_root_command_and_writes_machine_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    script = _positive_migration_script(tmp_path)
    out = tmp_path / "gate.json"
    work_dir = tmp_path / "gate-work"
    live_projects = tmp_path / "live-projects"
    live_repo = tmp_path / "live-repo"
    _write(live_projects / "sentinel.txt", "keep\n")
    _write(live_repo / "sentinel.txt", "keep\n")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(live_projects))
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(live_repo))
    monkeypatch.setenv("ASTRID_SESSION_ID", "S-LIVE")
    monkeypatch.setenv("ASTRID_TASK_PROJECT", "live-alpha")

    report = run_gate(
        snapshot=snapshot,
        migration_cmd=f"{sys.executable} {script} --projects-root {{projects_root}} --repo-root {{repo_root}}",
        out=out,
        work_dir=work_dir,
    )

    assert report.ok is True
    assert report.command_contract == "placeholders"
    assert report.checks == {
        "restore_comparable": True,
        "migration_changed_inventory": True,
        "idempotent_second_run": True,
    }
    assert [run.label for run in report.migration_runs] == ["migration", "migration_idempotence"]
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["checks"]["idempotent_second_run"] is True
    assert payload["checks"]["restore_comparable"] is True
    assert payload["row_counts"]["post"] == payload["row_counts"]["post_second_run"]
    assert Path(payload["inventories"]["pre"]).is_file()
    assert Path(payload["inventories"]["post"]).is_file()
    assert Path(payload["inventories"]["second_restore"]).is_file()
    assert "migrated/.astrid.variants.json" in Path(payload["inventories"]["post"]).read_text(encoding="utf-8")
    assert "alpha/runs/run-1/plan.json" in Path(payload["inventories"]["post"]).read_text(encoding="utf-8")
    assert (live_projects / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert (live_repo / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (live_projects / "live-projects-were-touched.txt").exists()
    assert not (live_repo / "live-repo-was-touched.txt").exists()


def test_migration_gate_cli_prints_human_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    script = _positive_migration_script(tmp_path)
    out = tmp_path / "gate.json"

    rc = main(
        [
            "--snapshot",
            str(snapshot),
            "--migration-cmd",
            f"{sys.executable} {script} --projects-root {{projects_root}} --repo-root {{repo_root}}",
            "--out",
            str(out),
            "--work-dir",
            str(tmp_path / "gate-work"),
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "Migration gate passed" in stdout
    assert "idempotent_second_run=true" in stdout
    assert f"json={out.resolve()}" in stdout
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True


def test_migration_gate_rejects_ambiguous_command_before_touching_live_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    script = _ambient_live_root_script(tmp_path)
    live_projects = tmp_path / "live-projects"
    live_repo = tmp_path / "live-repo"
    _write(live_projects / "sentinel.txt", "keep\n")
    _write(live_repo / "sentinel.txt", "keep\n")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(live_projects))
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(live_repo))

    with pytest.raises(SystemExit, match=r"must include both \{projects_root\} and \{repo_root\}"):
        run_gate(
            snapshot=snapshot,
            migration_cmd=f"{sys.executable} {script}",
            out=tmp_path / "gate.json",
            work_dir=tmp_path / "gate-work",
        )

    assert (live_projects / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert (live_repo / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (live_projects / "live-projects-were-touched.txt").exists()
    assert not (live_repo / "live-repo-was-touched.txt").exists()


def test_migration_gate_rejects_single_root_placeholder_before_command_runs(tmp_path: Path) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    script = _ambient_live_root_script(tmp_path)

    with pytest.raises(SystemExit, match=r"missing \{repo_root\}"):
        run_gate(
            snapshot=snapshot,
            migration_cmd=f"{sys.executable} {script} --projects-root {{projects_root}}",
            out=tmp_path / "gate.json",
            work_dir=tmp_path / "gate-work",
        )


def test_migration_gate_explicit_env_injection_still_targets_extracted_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    script = tmp_path / "env_only_migration.py"
    script.write_text(
        """
from __future__ import annotations

import os
from pathlib import Path

projects = Path(os.environ["ASTRID_PROJECTS_ROOT"])
repo = Path(os.environ["ASTRID_REPO_ROOT"])
assert "ASTRID_SESSION_ID" not in os.environ
plan = projects / "alpha" / "runs" / "run-1" / "plan.json"
if not plan.exists():
    plan.write_text('{"version":2}\\n', encoding="utf-8")
variant = repo / "migrated-env" / ".astrid.variants.json"
if not variant.exists():
    variant.parent.mkdir(parents=True, exist_ok=True)
    variant.write_text("{}\\n", encoding="utf-8")
""".lstrip(),
        encoding="utf-8",
    )
    live_projects = tmp_path / "live-projects"
    live_repo = tmp_path / "live-repo"
    _write(live_projects / "sentinel.txt", "keep\n")
    _write(live_repo / "sentinel.txt", "keep\n")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(live_projects))
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(live_repo))
    monkeypatch.setenv("ASTRID_SESSION_ID", "S-LIVE")

    report = run_gate(
        snapshot=snapshot,
        migration_cmd=f"{sys.executable} {script}",
        out=tmp_path / "gate.json",
        work_dir=tmp_path / "gate-work",
        allow_env_root_injection=True,
    )

    assert report.ok is True
    assert report.command_contract == "explicit_env_root_injection"
    assert not (live_projects / "alpha" / "runs" / "run-1" / "plan.json").exists()
    assert not (live_repo / "migrated-env" / ".astrid.variants.json").exists()
    assert (live_projects / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert (live_repo / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"


def test_migration_gate_subprocess_cli_rejects_ambiguous_commands(tmp_path: Path) -> None:
    snapshot = _snapshot_fixture(tmp_path)
    script = _ambient_live_root_script(tmp_path)
    out = tmp_path / "gate.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.reshape.migration_gate",
            "--snapshot",
            str(snapshot),
            "--migration-cmd",
            f"{sys.executable} {script}",
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must include both" in result.stderr
    assert not out.exists()
