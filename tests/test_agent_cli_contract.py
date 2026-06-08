"""Cross-surface JSON stdout contract tests for the agent CLI."""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import (  # noqa: E402
    bind_writer_session,
    setup_packs_and_compile,
    setup_run,
)

from astrid.core import gateway  # noqa: E402
from astrid.core.project import paths as project_paths  # noqa: E402
from astrid.core.project.project import create_project  # noqa: E402
from astrid.core.session import paths as session_paths  # noqa: E402
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV  # noqa: E402
from astrid.core.session.identity import Identity, write_identity  # noqa: E402
from astrid.core.task.events import ZERO_HASH, _event_hash  # noqa: E402
from astrid.core.task.lifecycle import (  # noqa: E402
    cmd_abort,
    cmd_ack,
    cmd_next,
    cmd_start,
    cmd_status,
)
from astrid.core.task.lifecycle_skip import cmd_skip  # noqa: E402
from astrid.core.task.plan import compute_plan_hash  # noqa: E402
from astrid.core.timeline.crud import create_timeline  # noqa: E402
from tests.helpers.current_run import seed_current_run  # noqa: E402
from tests.helpers.cli_runner import run_cli  # noqa: E402

_CODE_BODY = """from astrid.core.orchestrate import orchestrator, code
@orchestrator("demo.code")
def main(): return [code("step_a", argv=["echo", "alpha"])]
"""

_ATTESTED_BODY = """from astrid.core.orchestrate import orchestrator, attested
@orchestrator("demo.review")
def main(): return [attested("review", command="review.sh", instructions="please review", ack="human")]
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    home = tmp_path / "home"
    projects = tmp_path / "projects"
    home.mkdir()
    projects.mkdir()
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(home))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects))
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    return {"home": home, "projects": projects}


def _write_identity() -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))


def _load_single_json(stdout: str) -> dict[str, object]:
    assert stdout.endswith("\n"), f"missing trailing newline: {stdout!r}"
    lines = stdout.splitlines()
    assert len(lines) == 1, f"expected exactly one stdout line, got {len(lines)}: {stdout!r}"
    payload = json.loads(lines[0])
    assert isinstance(payload, dict), f"expected JSON object, got {type(payload)!r}"
    return payload


def _run_pipeline(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = -1
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = int(pipeline.main(argv))
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    return rc, out.getvalue(), err.getvalue()


def _seed_optional_skip_project(projects_root: Path) -> None:
    slug = "p"
    run_id = "r-skip"
    create_project(slug, root=projects_root)
    session = bind_writer_session(projects_root, slug, run_id=run_id)
    plan_path = projects_root / slug / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "plan_id": "p",
                "version": 2,
                "steps": [
                    {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
                    {"id": "s2", "adapter": "local", "command": "echo s2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_hash = compute_plan_hash(plan_path)
    seed_current_run(
        slug,
        run_id=run_id,
        plan_hash=plan_hash,
        root=projects_root,
        session_id=session.id,
    )
    run_dir = projects_root / slug / "runs" / run_id
    events_path = run_dir / "events.jsonl"
    run_started = {
        "kind": "run_started",
        "plan_hash": plan_hash,
        "run_id": run_id,
        "ts": "2026-01-01T00:00:00Z",
    }
    run_started["hash"] = _event_hash(ZERO_HASH, run_started)
    events_path.write_text(
        json.dumps(run_started, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )


def _run_attach_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    _write_identity()
    create_project("demo")
    create_timeline("demo", "primary", is_default=True)
    result = run_cli(pipeline.main, ["attach", "demo", "--json"])
    return int(result.exit_code or 0), result.stdout, result.stderr


def _run_session_status_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    _write_identity()
    create_project("demo")
    return _run_pipeline(["status", "--json"])


def _run_task_status_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    case_root = tmp_path / "status_task"
    case_root.mkdir()
    _, projects = setup_run(case_root, "demo", "code", _CODE_BODY, "demo.code", run_id="r-status")
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_status(["--project", "p", "--json"], projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _run_start_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    case_root = tmp_path / "start"
    case_root.mkdir()
    packs, projects = setup_packs_and_compile(
        case_root,
        "demo",
        "code",
        _CODE_BODY,
        "demo.code",
    )
    create_project("p", root=projects, exist_ok=True)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")
    os.environ["ASTRID_ACTOR"] = "starter"
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_start(
            ["demo.code", "--project", "p", "--name", "r-start", "--json"],
            packs_root=packs,
            projects_root=projects,
        )
    return rc, out.getvalue(), err.getvalue()


def _run_next_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    case_root = tmp_path / "next"
    case_root.mkdir()
    _, projects = setup_run(case_root, "demo", "code", _CODE_BODY, "demo.code", run_id="r-next")
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_next(["--project", "p", "--json"], projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _run_abort_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    case_root = tmp_path / "abort"
    case_root.mkdir()
    _, projects = setup_run(case_root, "demo", "code", _CODE_BODY, "demo.code", run_id="r-abort")
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_abort(["--project", "p", "--json"], projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _run_ack_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    case_root = tmp_path / "ack"
    case_root.mkdir()
    _, projects = setup_run(case_root, "demo", "review", _ATTESTED_BODY, "demo.review", run_id="r-ack")
    os.environ["ASTRID_ACTOR"] = "alice"
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_ack(
            ["review", "--project", "p", "--decision", "approve", "--human", "alice", "--json"],
            projects_root=projects,
        )
    return rc, out.getvalue(), err.getvalue()


def _run_skip_json(env: dict[str, Path], tmp_path: Path) -> tuple[int, str, str]:
    _seed_optional_skip_project(env["projects"])
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_skip(["s1", "--project", "p", "--json"], projects_root=env["projects"])
    return rc, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    ("case_id", "runner"),
    [
        ("attach", _run_attach_json),
        ("status-session", _run_session_status_json),
        ("status-task", _run_task_status_json),
        ("start", _run_start_json),
        ("next", _run_next_json),
        ("abort", _run_abort_json),
        ("ack", _run_ack_json),
        ("skip", _run_skip_json),
    ],
)
def test_agent_cli_json_commands_emit_exactly_one_stdout_object(
    case_id: str,
    runner,
    env: dict[str, Path],
    tmp_path: Path,
) -> None:
    rc, stdout, stderr = runner(env, tmp_path)

    assert rc == 0, f"{case_id}: rc={rc} stderr={stderr!r}"
    payload = _load_single_json(stdout)
    assert payload["schema_version"] == 1, f"{case_id}: missing schema version"
    assert "state" in payload, f"{case_id}: missing state"
