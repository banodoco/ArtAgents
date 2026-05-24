from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.adapter import RunContext
from astrid.core.adapter.remote_artifact import RemoteArtifactAdapter
from astrid.core.adapter.remote_artifact_fetch import FetchResult, fetch_artifacts
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.lease import write_lease_init
from astrid.core.session.model import Session, now_iso
from astrid.core.session.paths import session_path
from astrid.core.task.events import append_event, read_events
from astrid.core.task.lifecycle import cmd_step_retry_fetch
from astrid.core.task.plan import Check, ProducesEntry, Step, compute_plan_hash
from astrid.core.project.current_run import write_current_run


DEFERRAL_FRAGMENT = "remote-artifact is reserved for Sprint 5a"


def _ctx(tmp_path: Path) -> RunContext:
    project_root = tmp_path / "projects" / "demo"
    project_root.mkdir(parents=True, exist_ok=True)
    return RunContext(
        slug="demo",
        run_id="run-1",
        project_root=project_root,
        plan_step_path=("render",),
        step_version=1,
    )


def _remote_step() -> Step:
    return Step(
        id="render",
        adapter="remote-artifact",
        command="echo job-1",
        produces=(
            ProducesEntry(
                name="result",
                path="result.json",
                check=Check(check_id="file_nonempty", params={}, sentinel=False),
            ),
        ),
    )


def test_remote_artifact_adapter_methods_fail_with_same_deferral(
    tmp_path: Path,
) -> None:
    adapter = RemoteArtifactAdapter()
    step = _remote_step()
    ctx = _ctx(tmp_path)

    for method_name in ("dispatch", "poll", "complete"):
        method = getattr(adapter, method_name)
        with pytest.raises(RuntimeError, match=DEFERRAL_FRAGMENT):
            method(step, ctx)


def test_direct_fetch_artifacts_fails_with_deferral(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=DEFERRAL_FRAGMENT):
        fetch_artifacts(_remote_step(), _ctx(tmp_path))


def _build_retry_fetch_run(tmp_path: Path) -> tuple[Path, Path]:
    projects_root = tmp_path / "projects"
    proj_root = projects_root / "demo"
    run_dir = proj_root / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (proj_root / "plan.json").write_text(
        json.dumps(
            {
                "plan_id": "p",
                "version": 2,
                "steps": [
                    {
                        "id": "render",
                        "adapter": "remote-artifact",
                        "command": "echo job-1",
                        "produces": {
                            "result": {
                                "path": "result.json",
                                "check": {
                                    "check_id": "file_nonempty",
                                    "params": {},
                                    "sentinel": False,
                                },
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    step_dir = run_dir / "steps" / "render" / "v1"
    (step_dir / "produces").mkdir(parents=True)
    (step_dir / "remote_state.json").write_text("{}", encoding="utf-8")
    sid = "S-REMOTE-ARTIFACT-DEFERRAL"
    session_path(sid).parent.mkdir(parents=True, exist_ok=True)
    Session(
        id=sid,
        project="demo",
        agent_id="test",
        attached_at=now_iso(),
        last_used_at=now_iso(),
        role="writer",
        timeline=None,
        run_id="run-1",
    ).to_json(session_path(sid))
    with patch.dict("os.environ", {ASTRID_SESSION_ID_ENV: sid}):
        plan_hash = compute_plan_hash(proj_root / "plan.json")
        write_lease_init(run_dir, session_id=sid, plan_hash=plan_hash)
        write_current_run("demo", "run-1", root=projects_root)
        events_path = run_dir / "events.jsonl"
        append_event(events_path, {"kind": "run_started", "run_id": "run-1"})
        append_event(
            events_path,
            {
                "kind": "step_dispatched",
                "plan_step_path": ["render"],
                "adapter": "remote-artifact",
                "step_version": 1,
                "command": "echo job-1",
            },
        )
        append_event(
            events_path,
            {
                "kind": "step_awaiting_fetch",
                "plan_step_path": ["render"],
                "adapter": "remote-artifact",
                "missing": ["result.json"],
                "mismatched": [],
            },
        )
    return projects_root, run_dir


def test_retry_fetch_cli_defers_and_does_not_append_remote_artifact_events(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    projects_root, run_dir = _build_retry_fetch_run(tmp_path)
    before = read_events(run_dir / "events.jsonl")

    with patch.dict("os.environ", {ASTRID_SESSION_ID_ENV: "S-REMOTE-ARTIFACT-DEFERRAL"}), patch(
        "astrid.core.adapter.remote_artifact_fetch.fetch_artifacts",
        return_value=FetchResult(status="completed", fetched=["result.json"]),
    ):
        rc = cmd_step_retry_fetch(
            ["render", "--project", "demo", "--run", "run-1"],
            projects_root=projects_root,
        )

    captured = capsys.readouterr()
    after = read_events(run_dir / "events.jsonl")
    assert rc == 1
    assert DEFERRAL_FRAGMENT in captured.err
    assert after == before


def test_retry_fetch_help_defers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cmd_step_retry_fetch(["--help"])

    captured = capsys.readouterr()
    assert rc == 1
    assert DEFERRAL_FRAGMENT in captured.err
