"""T12: cmd_start writes active_run.json + AGENT.md + plan_initialized; second
start rejected; missing build/<name>.json prints compile recovery + rc=1.
"""

from __future__ import annotations

import io
import hashlib
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import bind_writer_session, make_pack, setup_packs_and_compile  # noqa: E402

from tests.helpers.current_run import read_seeded_current_run
from astrid.core.task.lifecycle import cmd_start
from astrid.core.task.plan import compute_plan_hash
from astrid.core.task.preamble import PROHIBITION_PREAMBLE
from astrid.core.orchestrator.registry import load_default_registry
from astrid.core.project.project import create_project
from astrid.core.timeline.crud import create_timeline


_BODY_CODE = '''from astrid.core.orchestrate import orchestrator, code
@orchestrator("demo.app")
def app(): return [code("step_a", argv=["echo", "x"])]
'''


def test_start_writes_active_run_with_correct_hash(tmp_path: Path) -> None:
    packs, projects = setup_packs_and_compile(tmp_path, "demo", "app", _BODY_CODE, "demo.app")
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")
    rc = cmd_start(
        ["demo.app", "--project", "p", "--name", "r1"],
        packs_root=packs,
        projects_root=projects,
    )
    assert rc == 0
    active = read_seeded_current_run("p", root=projects)
    assert active is not None
    assert active["run_id"] == "r1"
    plan_hash = compute_plan_hash(projects / "p" / "plan.json")
    assert active["plan_hash"] == plan_hash
    run_plan = json.loads(
        (projects / "p" / "runs" / "r1" / "plan.json").read_text(encoding="utf-8")
    )
    project_plan = json.loads((projects / "p" / "plan.json").read_text(encoding="utf-8"))
    assert run_plan == project_plan


def test_events_jsonl_starts_with_plan_initialized_then_run_started(tmp_path: Path) -> None:
    packs, projects = setup_packs_and_compile(tmp_path, "demo", "app", _BODY_CODE, "demo.app")
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")
    cmd_start(["demo.app", "--project", "p", "--name", "r2"], packs_root=packs, projects_root=projects)
    events_path = projects / "p" / "runs" / "r2" / "events.jsonl"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    assert lines, "events.jsonl must have at least one line"
    assert len(lines) >= 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["kind"] == "plan_initialized"
    assert first["run_id"] == "r2"
    assert first["plan"]["version"] == 2
    assert second["kind"] == "run_started"
    assert second["run_id"] == "r2"


def test_agent_md_includes_preamble(tmp_path: Path) -> None:
    packs, projects = setup_packs_and_compile(tmp_path, "demo", "app", _BODY_CODE, "demo.app")
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")
    cmd_start(["demo.app", "--project", "p", "--name", "r3"], packs_root=packs, projects_root=projects)
    agent_md = (projects / "p" / "runs" / "r3" / "AGENT.md").read_text(encoding="utf-8")
    assert PROHIBITION_PREAMBLE in agent_md
    assert "demo.app" in agent_md
    assert "r3" in agent_md


def test_second_start_rejected_with_recovery(tmp_path: Path) -> None:
    packs, projects = setup_packs_and_compile(tmp_path, "demo", "app", _BODY_CODE, "demo.app")
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")
    cmd_start(["demo.app", "--project", "p", "--name", "r4"], packs_root=packs, projects_root=projects)
    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        rc = cmd_start(
            ["demo.app", "--project", "p"],
            packs_root=packs,
            projects_root=projects,
        )
    assert rc == 1
    msg = err.getvalue()
    assert "active run already exists" in msg
    assert "astrid abort --project p" in msg


def test_missing_build_json_prints_compile_recovery(tmp_path: Path) -> None:
    # Pack exists but we never compile; build/<name>.json is absent.
    packs = tmp_path / "packs"
    projects = tmp_path / "projects"
    packs.mkdir()
    projects.mkdir()
    make_pack(packs, "demo", "uncompiled", _BODY_CODE.replace("demo.app", "demo.uncompiled"))
    create_project("q", root=projects)
    create_timeline("q", "main", root=projects, is_default=True)
    bind_writer_session(projects, "q")
    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        rc = cmd_start(
            ["demo.uncompiled", "--project", "q"],
            packs_root=packs,
            projects_root=projects,
        )
    assert rc == 1
    assert "astrid author compile demo.uncompiled" in err.getvalue()


def test_start_rejects_multiple_timelines_when_default_sentinel_is_none(
    tmp_path: Path,
) -> None:
    packs, projects = setup_packs_and_compile(tmp_path, "demo", "app", _BODY_CODE, "demo.app")
    create_project("p", root=projects)
    create_timeline("p", "primary", root=projects)
    create_timeline("p", "secondary", root=projects)
    bind_writer_session(projects, "p")

    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        rc = cmd_start(
            ["demo.app", "--project", "p", "--name", "r-no-default"],
            packs_root=packs,
            projects_root=projects,
        )

    assert rc == 1
    assert "has no default timeline and 2 live timelines" in err.getvalue()
    assert "timelines set-default" in err.getvalue()
    assert not (projects / "p" / "runs" / "r-no-default").exists()


def test_start_rejects_missing_project_before_creating_run_dir(tmp_path: Path) -> None:
    packs, projects = setup_packs_and_compile(tmp_path, "demo", "app", _BODY_CODE, "demo.app")
    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        rc = cmd_start(
            ["demo.app", "--project", "missing"],
            packs_root=packs,
            projects_root=projects,
        )
    assert rc == 1
    assert "project 'missing' not found" in err.getvalue()
    assert not (projects / "missing" / "runs").exists()


def test_start_builtin_canonical_orchestrators_ignore_stale_build_json_and_use_runtime_inputs(
    tmp_path: Path,
) -> None:
    packs_root = tmp_path / "packs"
    projects_root = tmp_path / "projects"
    packs_root.mkdir()
    projects_root.mkdir()

    for qualified_id in (
        "video_editing.hype",
        "video_editing.event_talks",
        "video_editing.thumbnail_maker",
    ):
        _, name = qualified_id.split(".", 1)
        build_dir = packs_root / "builtin" / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        stale_content = json.dumps(
            {
                "plan_id": f"STALE-{name}-MARKER",
                "version": 2,
                "steps": [
                    {
                        "id": "stale-step",
                        "adapter": "local",
                        "command": "echo STALE_COMPILED_CONTENT",
                        "produces": [],
                        "cost": {"amount": 0, "source": "local"},
                    }
                ],
            }
        )
        (build_dir / f"{name}.json").write_text(stale_content, encoding="utf-8")

        slug = name.replace("_", "-")
        create_project(slug, root=projects_root)
        create_timeline(slug, "main", root=projects_root, is_default=True)
        bind_writer_session(projects_root, slug, sid=f"S-{slug}")

        proj_root = projects_root / slug
        source = proj_root / "source.mp4"
        source.write_bytes(f"source-{qualified_id}".encode("utf-8"))
        expected_consumes = {
            str(source.resolve()): hashlib.sha256(source.read_bytes()).hexdigest()
        }

        if qualified_id == "video_editing.hype":
            brief = proj_root / "brief.txt"
            brief.write_text("make it punchy\n", encoding="utf-8")
            expected_consumes[str(brief.resolve())] = hashlib.sha256(
                brief.read_bytes()
            ).hexdigest()
        elif qualified_id == "video_editing.event_talks":
            transcript = proj_root / "transcript.json"
            transcript.write_text('{"segments":[]}\n', encoding="utf-8")
            expected_consumes[str(transcript.resolve())] = hashlib.sha256(
                transcript.read_bytes()
            ).hexdigest()
        else:
            query = proj_root / "query.txt"
            query.write_text("dramatic speaker on stage\n", encoding="utf-8")
            expected_consumes[str(query.resolve())] = hashlib.sha256(
                query.read_bytes()
            ).hexdigest()

        run_id = f"run-{slug}"
        rc = cmd_start(
            [qualified_id, "--project", slug, "--name", run_id],
            packs_root=packs_root,
            projects_root=projects_root,
        )

        assert rc == 0
        run_dir = proj_root / "runs" / run_id
        run_json = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        consumes = {
            entry["source"]: entry["sha256"]
            for entry in run_json.get("consumes", [])
        }
        assert consumes == expected_consumes

        plan_text = (proj_root / "plan.json").read_text(encoding="utf-8")
        assert str(run_dir) in plan_text
        # Verify stale build content did NOT leak into the plan
        assert "STALE-" not in plan_text, (
            f"Plan for {qualified_id} contains stale build content: {plan_text[:200]}"
        )
        assert "STALE_COMPILED_CONTENT" not in plan_text
        assert "stale-step" not in plan_text
        if qualified_id == "video_editing.event_talks":
            assert str((proj_root / "transcript.json").resolve()) in plan_text
        if qualified_id == "video_editing.thumbnail_maker":
            assert "dramatic speaker on stage" in plan_text


def test_canonical_start_orchestrators_declare_plan_builder_metadata() -> None:
    registry = load_default_registry(include_installed=False)

    expected_modules = {
        "video_editing.hype": "astrid.packs.video_editing.orchestrators.hype.plan_template",
        "video_editing.event_talks": "astrid.packs.video_editing.orchestrators.event_talks.plan_template",
        "video_editing.thumbnail_maker": "astrid.packs.video_editing.orchestrators.thumbnail_maker.plan_template",
    }

    for orchestrator_id, module_name in expected_modules.items():
        orchestrator = registry.get(orchestrator_id)
        assert orchestrator.metadata["plan_builder_module"] == module_name
        assert orchestrator.metadata["plan_builder_entrypoint"] == "build_plan_v2"


def test_canonical_start_creates_task_events_not_pack_audit_log(
    tmp_path: Path,
) -> None:
    """``cmd_start`` for canonical orchestrators must write only task-run
    ``events.jsonl``, NOT the pack-level ``pack_events.jsonl`` audit log."""
    packs_root = tmp_path / "packs"
    projects_root = tmp_path / "projects"
    packs_root.mkdir()
    projects_root.mkdir()

    for qualified_id in (
        "video_editing.event_talks",
        "video_editing.thumbnail_maker",
    ):
        _, name = qualified_id.split(".", 1)
        # Seed stale build JSON so we can also verify it is ignored
        build_dir = packs_root / "builtin" / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        stale = json.dumps(
            {
                "plan_id": f"STALE-{name}-MARKER",
                "version": 2,
                "steps": [
                    {
                        "id": "stale-step",
                        "adapter": "local",
                        "command": "echo STALE_AUDIT_MARKER",
                        "produces": [],
                        "cost": {"amount": 0, "source": "local"},
                    }
                ],
            }
        )
        (build_dir / f"{name}.json").write_text(stale, encoding="utf-8")

        slug = name.replace("_", "-")
        create_project(slug, root=projects_root)
        create_timeline(slug, "main", root=projects_root, is_default=True)
        bind_writer_session(projects_root, slug, sid=f"S-{slug}-audit")

        proj_root = projects_root / slug
        source = proj_root / "source.mp4"
        source.write_bytes(f"audit-source-{qualified_id}".encode("utf-8"))

        if qualified_id == "video_editing.event_talks":
            (proj_root / "transcript.json").write_text('{"segments":[]}\n', encoding="utf-8")
        else:
            (proj_root / "query.txt").write_text("test query\n", encoding="utf-8")

        run_id = f"run-audit-{slug}"
        rc = cmd_start(
            [qualified_id, "--project", slug, "--name", run_id],
            packs_root=packs_root,
            projects_root=projects_root,
        )

        assert rc == 0
        run_dir = proj_root / "runs" / run_id

        # Task-run events MUST exist
        events_path = run_dir / "events.jsonl"
        assert events_path.is_file(), (
            f"{qualified_id}: missing events.jsonl in {run_dir}"
        )
        lines = events_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 2, f"{qualified_id}: expected >=2 events, got {len(lines)}"
        first = json.loads(lines[0])
        assert first["kind"] == "plan_initialized"
        second = json.loads(lines[1])
        assert second["kind"] == "run_started"

        # Pack audit log MUST NOT exist (only created by direct pack-run invocation)
        pack_log = run_dir / "pack_events.jsonl"
        assert not pack_log.exists(), (
            f"{qualified_id}: pack_events.jsonl should not exist in task-run directory;"
            f" pack-run audit log must be separate from task-run events.jsonl"
        )

        # Also verify stale build markers are absent from plan
        plan_text = (proj_root / "plan.json").read_text(encoding="utf-8")
        assert "STALE-" not in plan_text


def test_canonical_step_reentry_records_completion_and_events_verify_bypasses_gate(
    tmp_path: Path,
) -> None:
    """The ``astrid next`` command for a canonical pack step is copy/paste runnable."""
    os.environ["ASTRID_HOME"] = str(tmp_path / "home")
    packs_root = tmp_path / "packs"
    projects_root = tmp_path / "projects"
    packs_root.mkdir()
    projects_root.mkdir()

    slug = "smoke-event"
    run_id = "run-event"
    create_project(slug, root=projects_root)
    create_timeline(slug, "main", root=projects_root, is_default=True)
    bind_writer_session(projects_root, slug, sid="S-smoke-event")
    proj_root = projects_root / slug
    (proj_root / "source.mp4").write_bytes(b"fake mp4 bytes")
    (proj_root / "transcript.json").write_text('{"segments":[]}\n', encoding="utf-8")

    assert cmd_start(
        ["video_editing.event_talks", "--project", slug, "--name", run_id],
        packs_root=packs_root,
        projects_root=projects_root,
    ) == 0

    from astrid.core.task.lifecycle import cmd_next

    out = io.StringIO()
    with redirect_stdout(out):
        assert cmd_next(["--project", slug], projects_root=projects_root) == 0
    command = next(
        line.removeprefix("run: ")
        for line in out.getvalue().splitlines()
        if line.startswith("run: ")
    )

    env = os.environ.copy()
    env["ASTRID_PROJECTS_ROOT"] = str(projects_root)
    completed = subprocess.run(
        command,
        shell=True,
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    events = [
        json.loads(line)
        for line in (proj_root / "runs" / run_id / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert any(event["kind"] == "step_completed" for event in events)

    from astrid.core.gateway import main as astrid_main

    os.environ["ASTRID_TASK_PROJECT"] = slug
    os.environ["ASTRID_TASK_RUN_ID"] = run_id
    os.environ["ASTRID_TASK_STEP_ID"] = "ados-sunday-template"
    try:
        assert astrid_main(["events", "verify", "--project", slug, "--run", run_id]) == 0
    finally:
        os.environ.pop("ASTRID_TASK_PROJECT", None)
        os.environ.pop("ASTRID_TASK_RUN_ID", None)
        os.environ.pop("ASTRID_TASK_STEP_ID", None)


def test_start_accepts_legacy_alias_but_records_canonical_orchestrator_id(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()

    slug = "legacy-hype"
    run_id = "run-legacy-hype"
    create_project(slug, root=projects_root)
    create_timeline(slug, "main", root=projects_root, is_default=True)
    bind_writer_session(projects_root, slug, sid="S-legacy-hype")

    proj_root = projects_root / slug
    (proj_root / "source.mp4").write_bytes(b"fake mp4 bytes")
    (proj_root / "brief.txt").write_text("make it punchy\n", encoding="utf-8")

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        rc = cmd_start(
            ["builtin.hype", "--project", slug, "--name", run_id],
            projects_root=projects_root,
        )

    assert rc == 0
    assert stdout.getvalue().splitlines()[0] == "started video_editing.hype"

    run_json = json.loads(
        (proj_root / "runs" / run_id / "run.json").read_text(encoding="utf-8")
    )
    assert run_json["tool_id"] == "video_editing.hype"

    agent_md = (proj_root / "runs" / run_id / "AGENT.md").read_text(encoding="utf-8")
    assert "QUALIFIED ORCHESTRATOR: video_editing.hype" in agent_md
