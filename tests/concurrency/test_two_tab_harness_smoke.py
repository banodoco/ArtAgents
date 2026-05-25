"""Smoke test for the two-tab harness: race two astrid status calls against the same project."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from astrid.core.project.project import create_project
from astrid.core.task.active_run import write_active_run
from astrid.core.task.plan import compute_plan_hash
from tests.concurrency.two_tab_harness import race_two_tabs


def test_two_concurrent_status_reads_ok(tmp_projects_root: Path) -> None:
    """Race two ``python3 -m astrid status`` calls — both should succeed (reads are safe)."""
    slug = "smoke"

    # Create a project with a plan and active run
    create_project(slug, root=tmp_projects_root)
    plan_path = tmp_projects_root / slug / "plan.json"
    # Sprint-3 contract: plan version must be 2.
    plan_payload = {
        "plan_id": "p1",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "python3 -c \"print('ok')\"",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
            },
        ],
    }
    plan_path.write_text(
        __import__("json").dumps(plan_payload), encoding="utf-8"
    )
    plan_hash = compute_plan_hash(plan_path)
    write_active_run(slug, run_id="run-1", plan_hash=plan_hash, root=tmp_projects_root)

    projects_root = str(tmp_projects_root)

    def setup() -> Path:
        return tmp_projects_root / slug

    result = race_two_tabs(
        setup_fn=setup,
        contended_command=[
            "python3",
            "-m",
            "astrid",
            "status",
            "--project",
            slug,
        ],
        env_overlay={"ASTRID_PROJECTS_ROOT": projects_root},
        expected_winner_count=2,
        timeout_seconds=30.0,
    )

    assert result.p1_exit_code == 0, f"P1 failed: {result.p1_stderr}"
    assert result.p2_exit_code == 0, f"P2 failed: {result.p2_stderr}"
    assert result.final_disk_state, "Disk state should be captured"


def test_race_two_tabs_accepts_explicit_env_overlay(tmp_path: Path) -> None:
    script = tmp_path / "print_env.py"
    script.write_text(
        "import os\n"
        "print(os.environ['TWO_TAB_SENTINEL'])\n"
        "assert 'TWO_TAB_REMOVED' not in os.environ\n",
        encoding="utf-8",
    )

    def setup() -> Path:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        return run_dir

    result = race_two_tabs(
        setup_fn=setup,
        contended_command=[sys.executable, str(script)],
        env_overlay={"TWO_TAB_SENTINEL": "isolated", "TWO_TAB_REMOVED": None},
        expected_winner_count=2,
        timeout_seconds=10.0,
    )

    assert result.p1_stdout.strip() == "isolated"
    assert result.p2_stdout.strip() == "isolated"


def test_reshape_two_tab_wrapper_uses_temp_projects_root_without_live_leakage(
    tmp_path: Path, monkeypatch
) -> None:
    live_projects = tmp_path / "live-projects"
    live_projects.mkdir()
    (live_projects / "sentinel.txt").write_text("keep\n", encoding="utf-8")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(live_projects))
    monkeypatch.setenv("ASTRID_SESSION_ID", "S-LIVE")

    child_script = tmp_path / "write_child_env.py"
    child_script.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "root = Path(os.environ['ASTRID_PROJECTS_ROOT'])\n"
        "project = os.environ['ASTRID_TASK_PROJECT']\n"
        "run_id = os.environ['ASTRID_TASK_RUN_ID']\n"
        "session_id = os.environ['ASTRID_SESSION_ID']\n"
        "assert session_id == 'S-test-two-tab'\n"
        "target = root / project / 'runs' / run_id / f'tab-{os.getpid()}.txt'\n"
        "target.write_text(str(root) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    isolated_projects = tmp_path / "isolated-projects"
    isolated_home = tmp_path / "isolated-home"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.reshape.two_tab_harness",
            "--projects-root",
            str(isolated_projects),
            "--astrid-home",
            str(isolated_home),
            "--project-slug",
            "safe-project",
            "--run-id",
            "safe-run",
            "--session-id",
            "S-test-two-tab",
            "--command",
            f"{sys.executable} {child_script}",
            "--expected-winner-count",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["projects_root"] == str(isolated_projects.resolve())
    written = sorted((isolated_projects / "safe-project" / "runs" / "safe-run").glob("tab-*.txt"))
    assert len(written) == 2
    assert all(path.read_text(encoding="utf-8").strip() == str(isolated_projects.resolve()) for path in written)
    assert (live_projects / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (live_projects / "safe-project").exists()
    assert (isolated_home / "sessions" / "S-test-two-tab.json").is_file()
