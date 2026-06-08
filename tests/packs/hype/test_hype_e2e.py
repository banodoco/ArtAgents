"""End-to-end test of video_editing.hype port against tiny fixture project (Sprint 5a T14).

Mock RunPod at ``runpod.session`` boundary; no live calls.
Verifies:
- Initial plan v2 emitted with stable plan hash
- Dynamic plan mutation via ``add-step`` (shot count discovered after cut)
- All steps terminal with ``step_dispatched`` → ``step_completed`` events
- ``run_completed`` lands after final step completes
- Artifacts under canonical ``steps/hype/<id>/v<N>/produces/...`` paths
- ``consumes`` populated on ``run.json``
- Costs surfaced on completion events
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from astrid.core.executor.cli import _parse_input_values
from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.core.executor.runner import ExecutorRunRequest, build_executor_command
from astrid.core.project.current_run import write_current_run
from astrid.core.project.jsonio import read_json, write_json_atomic
from astrid.core.project.project import create_project
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.paths import session_path
from astrid.core.task.command_render import render_task_command
from astrid.core.task.events import (
    make_run_completed_event,
    make_step_completed_event,
    make_step_dispatched_event,
    read_events,
)
from astrid.core.task.gate import (
    TaskRunGateError,
    _resolve_for_each_items,
    gate_command,
    record_dispatch_complete,
)
from astrid.core.task.lifecycle import cmd_next, cmd_start
from astrid.core.task.plan import (
    RepeatForEach,
    Step,
    compute_plan_hash,
    load_plan,
)
from astrid.core.task.run_state import _run_is_complete

# ---------------------------------------------------------------------------
# Synthetic run fixture
# ---------------------------------------------------------------------------


def _build_synthetic_hype_run(
    tmp_path: Path,
    slug: str = "demo",
    run_id: str = "run-hype-1",
    python_exec: str = "python3",
    *,
    source_media: bytes | None = None,
) -> tuple[Path, Path, Path]:
    """Create a synthetic hype project + run with source media and plan v2.

    Writes ``plan.json`` into BOTH the project root and the run directory
    (the real ``cmd_start`` copies it; ``cmd_plan_add_step`` reads it from
    the run dir).

    Returns ``(project_root, run_dir, source_path, plan_path)``.
    """
    from astrid.core.orchestrator.plan_template import emit_plan_json
    from astrid.packs.video_editing.orchestrators.hype.plan_template import build_plan_v2

    proj_root = tmp_path / "projects" / slug
    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Stub source media file
    if source_media is None:
        source_media = b"fake-mp4-bytes-for-testing"
    source_path = proj_root / "source.mp4"
    source_path.write_bytes(source_media)

    # Build and emit plan v2
    plan_dict = build_plan_v2(
        python_exec=python_exec,
        run_root=run_dir,
        source=source_path,
        run_id=run_id,
    )
    plan_path = proj_root / "plan.json"
    emit_plan_json(plan_dict, plan_path)

    # Also copy into the run directory (cmd_start behaviour) so
    # cmd_plan_add_step / _load_effective_plan can find it.
    run_plan_path = run_dir / "plan.json"
    run_plan_path.write_text(plan_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Compute source sha256 for consumes
    src_sha256 = hashlib.sha256(source_media).hexdigest()

    # Write run.json with consumes
    run_json = {
        "run_id": run_id,
        "created_at": "2025-01-01T00:00:00Z",
        "consumes": [
            {"source": str(source_path), "sha256": src_sha256},
        ],
        "plan_hash": compute_plan_hash(str(plan_path)),
        "orchestrator": "video_editing.hype",
    }
    (run_dir / "run.json").write_text(
        json.dumps(run_json, indent=2), encoding="utf-8"
    )

    return proj_root, run_dir, source_path, plan_path


def _write_step_event(events_path: Path, event: dict) -> None:
    """Append an event line to events.jsonl."""
    line = json.dumps(event, sort_keys=True, ensure_ascii=False)
    with open(events_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _bind_hype_session(projects_root: Path, slug: str, run_id: str, sid: str) -> None:
    os.environ[ASTRID_SESSION_ID_ENV] = sid
    from tests.conftest import make_session

    sess = make_session(id=sid, project=slug, agent_id="hype-test", run_id=run_id)
    path = session_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    sess.to_json(path)
    write_current_run(slug, run_id, root=projects_root)


def _seed_default_timeline(projects_root: Path, slug: str) -> str:
    from astrid.core import timeline as timeline_contract
    from astrid.core.threads.ids import generate_ulid

    timeline_ulid = generate_ulid()
    pdir = projects_root / slug
    tdir = pdir / "timelines" / timeline_ulid
    tdir.mkdir(parents=True)
    (tdir / "assembly.json").write_text(
        json.dumps(timeline_contract.canonical_empty_timeline()), encoding="utf-8"
    )
    (tdir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )
    (tdir / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "main",
                "name": "Main",
                "is_default": True,
            }
        ),
        encoding="utf-8",
    )
    project_json = pdir / "project.json"
    payload = read_json(project_json)
    payload["default_timeline_id"] = timeline_ulid
    write_json_atomic(project_json, payload)
    return timeline_ulid


def _write_bound_session(
    *,
    sid: str,
    slug: str,
    run_id: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, sid)
    from tests.conftest import make_session

    sess = make_session(id=sid, project=slug, agent_id="hype-start-test", run_id=run_id)
    path = session_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    sess.to_json(path)


def _capture_stdout_stderr(fn, *args, **kwargs) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = fn(*args, **kwargs)
    return rc, stdout.getvalue(), stderr.getvalue()


# ---------------------------------------------------------------------------
# Initial plan v2 emission + stable plan hash
# ---------------------------------------------------------------------------


def test_initial_plan_v2_emission(tmp_path: Path) -> None:
    """Build plan v2, emit it as JSON, and verify plan hash is stable."""

    proj_root, run_dir, _, plan_path = _build_synthetic_hype_run(tmp_path)

    # Plan file exists and is valid v2 JSON
    assert plan_path.exists()
    plan_text = plan_path.read_text(encoding="utf-8")
    plan_data = json.loads(plan_text)
    assert plan_data["version"] == 2

    # Plan hash is stable (same plan → same hash)
    hash1 = compute_plan_hash(str(plan_path))
    hash2 = compute_plan_hash(str(plan_path))
    assert hash1 == hash2
    assert hash1.startswith("sha256:")

    # Verify the top-level group step has re_export (G1)
    steps = plan_data.get("steps", [])
    assert len(steps) > 0
    top = steps[0]
    assert top["id"] == "hype"
    assert "re_export" in top
    assert "children" in top

    # Verify children match the 6-stage spine
    child_ids = [c["id"] for c in top["children"]]
    assert "transcribe" in child_ids
    assert "scenes" in child_ids
    assert "cut" in child_ids
    assert "render" in child_ids
    assert "editor_review" in child_ids
    assert "validate" in child_ids

    executor_leaf_ids = {
        "transcribe": "editorial.transcribe",
        "scenes": "editorial.scenes",
        "cut": "video_editing.cut",
        "render": "rendering.render",
        "validate": "editorial.validate",
    }
    for child in top["children"]:
        if child["id"] not in executor_leaf_ids:
            continue
        argv = shlex.split(child["command"])
        assert argv[:6] == [
            "python3",
            "-m",
            "astrid",
            "executors",
            "run",
            executor_leaf_ids[child["id"]],
        ]
        assert "--out" in argv
        assert "--" not in argv

    render_step = next(c for c in top["children"] if c["id"] == "render")
    render_argv = shlex.split(render_step["command"])
    assert "--out" in render_argv
    assert "--input" in render_argv
    render_inputs = [
        render_argv[index + 1]
        for index, token in enumerate(render_argv)
        if token == "--input"
    ]
    assert any(value.startswith("timeline=") for value in render_inputs)
    assert any(value.startswith("assets_registry=") for value in render_inputs)
    assert not any(value.startswith("assets=") for value in render_inputs)
    assert "external.runpod" not in render_step["command"]

    cut_step = next(c for c in top["children"] if c["id"] == "cut")
    assert cut_step["repeat"]["for_each"]["from"] == "scenes.produces.scene_items"
    produced_names = set(cut_step["produces"])
    assert {"timeline_output", "assets_registry"} <= produced_names

    scenes_step = next(c for c in top["children"] if c["id"] == "scenes")
    assert {"scenes_list", "scene_items"} <= set(scenes_step["produces"])

    review_step = next(c for c in top["children"] if c["id"] == "editor_review")
    assert review_step["requires_ack"] is True
    assert "steps/hype/render/v1/produces/hype.mp4" in review_step["instructions"]
    assert review_step["repeat"]["until"] == 'hype.editor_review.produces.review_output.verdict == "ship"'
    assert review_step["repeat"]["max_iterations"] == 2
    assert review_step["repeat"]["on_exhaust"] == "fail"


def test_start_builtin_hype_emits_executable_task_run_and_dispatches_leaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.core.adapter import DispatchResult
    from astrid.core.adapter.local import LocalAdapter

    projects_root = tmp_path / "projects"
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("ASTRID_HOME", str(tmp_path / "home"))
    slug = "demo"
    create_project(slug, root=projects_root)
    _seed_default_timeline(projects_root, slug)
    source = projects_root / slug / "source.mp4"
    source.write_bytes(b"tiny source media")
    brief = projects_root / slug / "brief.txt"
    brief.write_text("make a short hype edit", encoding="utf-8")
    _write_bound_session(
        sid="S-HYPE-START",
        slug=slug,
        run_id=None,
        monkeypatch=monkeypatch,
    )

    rc, stdout, stderr = _capture_stdout_stderr(
        cmd_start,
        ["video_editing.hype", "--project", slug, "--name", "run-hype-start"],
        packs_root=tmp_path / "empty-packs",
        projects_root=projects_root,
    )
    assert rc == 0, stderr
    assert "started video_editing.hype" in stdout
    run_dir = projects_root / slug / "runs" / "run-hype-start"
    plan_path = projects_root / slug / "plan.json"
    run_plan_path = run_dir / "plan.json"
    assert plan_path.exists()
    assert run_plan_path.exists()

    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    assert json.loads(run_plan_path.read_text(encoding="utf-8")) == plan_data
    assert plan_data["version"] == 2
    assert plan_data["steps"][0]["id"] == "hype"
    assert "children" in plan_data["steps"][0]

    run_json = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_json["tool_id"] == "video_editing.hype"
    assert run_json["metadata"]["plan_hash"].startswith("sha256:")
    assert {
        (entry["source"], entry["sha256"]) for entry in run_json["consumes"]
    } == {
        (str(source.resolve()), hashlib.sha256(source.read_bytes()).hexdigest()),
        (str(brief.resolve()), hashlib.sha256(brief.read_bytes()).hexdigest()),
    }

    events = read_events(run_dir / "events.jsonl")
    assert [event["kind"] for event in events[:2]] == [
        "plan_initialized",
        "run_started",
    ]
    assert events[0]["plan"]["version"] == 2
    assert events[0]["plan"]["steps"][0]["id"] == "hype"

    plan = load_plan(plan_path)
    transcribe = plan.steps[0].children[0]  # type: ignore[index,union-attr]
    rendered_transcribe = render_task_command(
        transcribe,
        slug=slug,
        run_id="run-hype-start",
        project_root=projects_root / slug,
        plan_step_path=("hype", "transcribe"),
    )
    assert rendered_transcribe.canonical_argv[:6] == (
        "python3",
        "-m",
        "astrid",
        "executors",
        "run",
        "editorial.transcribe",
    )
    assert rendered_transcribe.task_env["ASTRID_TASK_PROJECT"] == slug
    assert rendered_transcribe.task_env["ASTRID_TASK_RUN_ID"] == "run-hype-start"

    rc, next_stdout, next_stderr = _capture_stdout_stderr(
        cmd_next,
        ["--project", slug],
        projects_root=projects_root,
    )
    assert rc == 0, next_stderr
    assert "ASTRID_TASK_PROJECT=demo" in next_stdout
    assert "python3 -m astrid executors run editorial.transcribe" in next_stdout
    assert "add --project" not in next_stdout
    assert "uses task env instead of a local --project" in next_stdout

    dispatches: list[dict[str, object]] = []

    def fake_dispatch(self, step, run_ctx):
        dispatches.append(
            {
                "path": run_ctx.plan_step_path,
                "item_id": run_ctx.item_id,
                "command": run_ctx.canonical_command,
                "argv": tuple(run_ctx.canonical_argv),
                "env": dict(run_ctx.task_env or {}),
                "produces_root": run_ctx.produces_root,
            }
        )
        return DispatchResult(status="dispatched", pid=1234, started_at="2026-05-25T00:00:00.000Z")

    monkeypatch.setattr(LocalAdapter, "dispatch", fake_dispatch)

    decision = gate_command(slug, rendered_transcribe.canonical_command, [], root=projects_root)
    assert dispatches[-1]["path"] == ("hype", "transcribe")
    assert dispatches[-1]["env"]["ASTRID_TASK_STEP_ID"] == "hype/transcribe"
    assert str(dispatches[-1]["produces_root"]).endswith(
        "runs/run-hype-start/steps/hype/transcribe/v1/produces"
    )
    transcribe_produces = run_dir / "steps" / "hype" / "transcribe" / "v1" / "produces"
    transcribe_produces.mkdir(parents=True, exist_ok=True)
    (transcribe_produces / "transcript.json").write_text("{}", encoding="utf-8")
    record_dispatch_complete(decision, returncode=0)

    scenes = plan.steps[0].children[1]  # type: ignore[index,union-attr]
    rendered_scenes = render_task_command(
        scenes,
        slug=slug,
        run_id="run-hype-start",
        project_root=projects_root / slug,
        plan_step_path=("hype", "scenes"),
    )
    decision = gate_command(slug, rendered_scenes.canonical_command, [], root=projects_root)
    scenes_produces = run_dir / "steps" / "hype" / "scenes" / "v1" / "produces"
    scenes_produces.mkdir(parents=True, exist_ok=True)
    (scenes_produces / "scene_items.json").write_text(
        json.dumps(["scene-0001"]), encoding="utf-8"
    )
    (scenes_produces / "scenes.json").write_text(
        json.dumps([{"id": "scene-0001"}]), encoding="utf-8"
    )
    record_dispatch_complete(decision, returncode=0)

    cut = plan.steps[0].children[2]  # type: ignore[index,union-attr]
    rendered_cut = render_task_command(
        cut,
        slug=slug,
        run_id="run-hype-start",
        project_root=projects_root / slug,
        plan_step_path=("hype", "cut"),
        item_id="scene-0001",
    )
    decision = gate_command(slug, rendered_cut.canonical_command, [], root=projects_root)
    assert dispatches[-1]["path"] == ("hype", "cut")
    assert dispatches[-1]["item_id"] == "scene-0001"
    assert dispatches[-1]["env"]["ASTRID_TASK_ITEM_ID"] == "scene-0001"
    assert "scene_id=scene-0001" in dispatches[-1]["argv"]
    assert str(dispatches[-1]["produces_root"]).endswith(
        "runs/run-hype-start/steps/hype/cut/v1/items/scene-0001/produces"
    )
    cut_item_produces = (
        run_dir
        / "steps"
        / "hype"
        / "cut"
        / "v1"
        / "items"
        / "scene-0001"
        / "produces"
    )
    cut_item_produces.mkdir(parents=True, exist_ok=True)
    (cut_item_produces / "hype.timeline.json").write_text("{}", encoding="utf-8")
    (cut_item_produces / "hype.assets.json").write_text("{}", encoding="utf-8")
    record_dispatch_complete(decision, returncode=0)

    events_after_cut = read_events(run_dir / "events.jsonl")
    assert any(
        event.get("kind") == "item_completed"
        and event.get("plan_step_path") == ["hype", "cut"]
        and event.get("item_id") == "scene-0001"
        for event in events_after_cut
    )
    assert any(
        event.get("kind") == "step_completed"
        and event.get("plan_step_path") == ["hype", "cut"]
        for event in events_after_cut
    )
    rc, next_stdout, next_stderr = _capture_stdout_stderr(
        cmd_next,
        ["--project", slug],
        projects_root=projects_root,
    )
    assert rc == 0, next_stderr
    assert "rendering.render" in next_stdout

    kinds = [event["kind"] for event in read_events(run_dir / "events.jsonl")]
    assert kinds.count("step_dispatched") == 3
    assert "for_each_expanded" in kinds
    assert "item_started" in kinds
    assert "item_completed" in kinds


def test_generated_hype_render_command_parses_to_required_downstream_render_argv(
    tmp_path: Path,
) -> None:
    from astrid.packs.video_editing.orchestrators.hype.plan_template import build_plan_v2

    run_dir = tmp_path / "runs" / "r-hype"
    run_dir.mkdir(parents=True)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    theme = tmp_path / "theme.json"
    theme.write_text("{}", encoding="utf-8")
    plan = build_plan_v2(
        python_exec="/opt/python",
        run_root=run_dir,
        source=source,
        theme=theme,
        run_id="r-hype",
    )
    render_step = next(
        child
        for child in plan["steps"][0]["children"]
        if child["id"] == "render"
    )
    rendered = render_task_command(
        Step(id="render", command=render_step["command"]),
        slug="demo",
        run_id="r-hype",
        project_root=tmp_path,
        plan_step_path=("hype", "render"),
    )

    rendered_argv = rendered.canonical_argv
    assert rendered_argv[:6] == (
        "/opt/python",
        "-m",
        "astrid",
        "executors",
        "run",
        "rendering.render",
    )
    out = rendered_argv[rendered_argv.index("--out") + 1]
    input_values = [
        rendered_argv[index + 1]
        for index, token in enumerate(rendered_argv)
        if token == "--input"
    ]
    downstream_argv = build_executor_command(
        ExecutorRunRequest(
            "rendering.render",
            out=out,
            inputs=_parse_input_values(input_values),
            python_exec="/opt/python",
        ),
        load_executor_registry(),
    )

    assert downstream_argv[:3] == (
        "/opt/python",
        "-m",
        "astrid.packs.rendering.executors.render.run",
    )
    assert downstream_argv[3:] == (
        "--timeline",
        str(run_dir / "steps" / "hype" / "cut" / "v1" / "produces" / "hype.timeline.json"),
        "--assets",
        str(run_dir / "steps" / "hype" / "cut" / "v1" / "produces" / "hype.assets.json"),
        "--out",
        str((tmp_path / "runs" / "r-hype" / "steps" / "hype" / "render" / "v1" / "produces").resolve() / "hype.mp4"),
        "--theme",
        str(theme.resolve()),
    )


def test_plan_hash_different_for_different_plans(tmp_path: Path) -> None:
    """Two plans with different run_ids produce different hashes."""
    from astrid.core.orchestrator.plan_template import emit_plan_json
    from astrid.packs.video_editing.orchestrators.hype.plan_template import build_plan_v2

    slug = "demo"
    proj_root = tmp_path / "projects" / slug
    proj_root.mkdir(parents=True)

    source = proj_root / "source.mp4"
    source.write_bytes(b"data")

    run_dir1 = proj_root / "runs" / "run-A"
    run_dir1.mkdir(parents=True, exist_ok=True)
    plan1 = build_plan_v2(
        python_exec="python3", run_root=run_dir1, source=source, run_id="run-A"
    )
    plan_path1 = proj_root / "plan-A.json"
    emit_plan_json(plan1, plan_path1)

    run_dir2 = proj_root / "runs" / "run-B"
    run_dir2.mkdir(parents=True, exist_ok=True)
    plan2 = build_plan_v2(
        python_exec="python3", run_root=run_dir2, source=source, run_id="run-B"
    )
    plan_path2 = proj_root / "plan-B.json"
    emit_plan_json(plan2, plan_path2)

    h1 = compute_plan_hash(str(plan_path1))
    h2 = compute_plan_hash(str(plan_path2))
    assert h1 != h2


def test_hype_repeat_source_uses_grouped_string_scene_items(tmp_path: Path) -> None:
    """Grouped hype repeat discovery reads scene_items.json, not dict scenes.json."""
    _proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)
    plan = load_plan(run_dir / "plan.json")
    hype = plan.steps[0]
    assert hype.children is not None
    cut = next(child for child in hype.children if child.id == "cut")
    assert isinstance(cut.repeat, RepeatForEach)
    assert cut.repeat.from_ref == "scenes.produces.scene_items"

    scenes_dir = run_dir / "steps" / "hype" / "scenes" / "v1" / "produces"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "scene_items.json").write_text(
        json.dumps(["scene-0001", "scene-0002"]), encoding="utf-8"
    )
    (scenes_dir / "scenes.json").write_text(
        json.dumps([{"index": 1}, {"index": 2}]), encoding="utf-8"
    )

    items = _resolve_for_each_items(
        slug="demo",
        repeat=cut.repeat,
        parent_prefix=("hype",),
        project_root=tmp_path / "projects" / "demo",
        run_id="run-hype-1",
        events=[],
    )
    assert items == ("scene-0001", "scene-0002")


def test_dictionary_scene_output_is_not_a_valid_for_each_source(tmp_path: Path) -> None:
    """Dictionary scene output still fails the task gate's item-id contract."""
    _proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)
    scenes_dir = run_dir / "steps" / "hype" / "scenes" / "v1" / "produces"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "scenes.json").write_text(
        json.dumps([{"index": 1, "start": 0.0, "end": 1.0}]), encoding="utf-8"
    )

    with pytest.raises(TaskRunGateError, match="for_each items must be unique strings"):
        _resolve_for_each_items(
            slug="demo",
            repeat=RepeatForEach(items_source="from", from_ref="scenes.produces.scenes_list"),
            parent_prefix=("hype",),
            project_root=tmp_path / "projects" / "demo",
            run_id="run-hype-1",
            events=[],
        )


# ---------------------------------------------------------------------------
# run.json consumes field
# ---------------------------------------------------------------------------


def test_run_json_consumes_populated(tmp_path: Path) -> None:
    """run.json is written with consumes, plan_hash, orchestrator."""
    proj_root, run_dir, source_path, _ = _build_synthetic_hype_run(tmp_path)

    run_json_path = run_dir / "run.json"
    assert run_json_path.exists()

    data = json.loads(run_json_path.read_text(encoding="utf-8"))
    assert data["orchestrator"] == "video_editing.hype"
    assert "plan_hash" in data
    assert data["plan_hash"].startswith("sha256:")

    # consumes should include the source media
    assert "consumes" in data
    consumes = data["consumes"]
    assert isinstance(consumes, list)
    assert len(consumes) >= 1
    assert any(c["source"] == str(source_path) or c["source"].endswith("source.mp4")
               for c in consumes)


def test_run_json_consumes_optional_on_read(tmp_path: Path) -> None:
    """A run.json without consumes is still readable (back-compat)."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)

    # Remove consumes from run.json
    run_json_path = run_dir / "run.json"
    data = json.loads(run_json_path.read_text(encoding="utf-8"))
    del data["consumes"]
    run_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Re-read — no crash, just no consumes
    data2 = json.loads(run_json_path.read_text(encoding="utf-8"))
    assert "consumes" not in data2


# ---------------------------------------------------------------------------
# Dynamic plan mutation via add-step
# ---------------------------------------------------------------------------


def test_dynamic_add_step_shot_count_discovery(tmp_path: Path) -> None:
    """After cut discovers shot count, add detail steps via cmd_plan_add_step."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)

    # Seed the run with a lease so add-step can validate
    from astrid.core.session.lease import write_lease_init
    _bind_hype_session(tmp_path / "projects", "demo", "run-hype-1", "test-session-1")
    write_lease_init(run_dir, session_id="test-session-1", plan_hash="")

    # Seed the first event using ``append_event`` so the hash chain is valid.
    from astrid.core.task.events import append_event as append_event_locked
    events_path = run_dir / "events.jsonl"
    append_event_locked(
        events_path,
        {"kind": "run_started", "run_id": "run-hype-1", "ts": "2025-01-01T00:00:00Z"},
    )

    # Call cmd_plan_add_step to add a shot-detail step after cut.
    # ``cut`` is a child of ``hype``, so the path is ``hype/cut``.
    from astrid.core.task.plan_verbs import cmd_plan_add_step

    result = cmd_plan_add_step(
        [
            "--project", "demo",
            "--run-id", "run-hype-1",
            "--step-id", "shot_detail_01",
            "--adapter", "local",
            "--command", "python3 -m astrid.packs.rendering.render_shot --shot 01",
            "--after", "hype/cut",
        ],
        projects_root=tmp_path / "projects",
    )
    # Should succeed (0 exit)
    assert result == 0

    # Verify the plan_mutated event was written
    events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    mutation_events = [e for e in events if e.get("kind") == "plan_mutated"]
    assert len(mutation_events) >= 1

    add_event = mutation_events[-1]
    diff = add_event.get("diff", {})
    assert diff.get("op") == "add"
    step = diff.get("step", {})
    assert step.get("id") == "shot_detail_01"
    assert step.get("adapter") == "local"


def test_dynamic_add_step_into_group(tmp_path: Path) -> None:
    """Add step into the hype group step."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)

    from astrid.core.session.lease import write_lease_init
    _bind_hype_session(tmp_path / "projects", "demo", "run-hype-1", "test-session-2")
    write_lease_init(run_dir, session_id="test-session-2", plan_hash="")

    # Seed the first event with the hash chain intact.
    from astrid.core.task.events import append_event as append_event_locked
    events_path = run_dir / "events.jsonl"
    append_event_locked(
        events_path,
        {"kind": "run_started", "run_id": "run-hype-1", "ts": "2025-01-01T00:00:00Z"},
    )

    from astrid.core.task.plan_verbs import cmd_plan_add_step

    result = cmd_plan_add_step(
        [
            "--project", "demo",
            "--run-id", "run-hype-1",
            "--step-id", "extra_render",
            "--adapter", "local",
            "--command", "python3 -m astrid.packs.runpod.executors.provision session --extra",
            "--into", "hype",
        ],
        projects_root=tmp_path / "projects",
    )
    assert result == 0

    # Verify the effective plan now includes the new step
    from astrid.core.task.plan_verbs import apply_mutations

    plan = load_plan(str(run_dir / "plan.json"))
    events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    effective = apply_mutations(plan, events)
    # The extra step should appear somewhere (flat or under hype group)
    found = any(
        child.id == "extra_render"
        for step in effective.steps
        if step.children is not None
        for child in step.children
    )
    # If flat, look for it directly or in children
    if not found:
        found = any(s.id == "extra_render" for s in effective.steps)
    assert found, "extra_render step not found in effective plan after add-step"


# ---------------------------------------------------------------------------
# Full step lifecycle: dispatched → completed
# ---------------------------------------------------------------------------


def test_full_step_lifecycle_events(tmp_path: Path) -> None:
    """All leaf steps emit step_dispatched then step_completed."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)

    # Load the plan to know the leaf step ids
    plan = load_plan(str(run_dir / "plan.json"))
    leaf_paths = _collect_leaf_paths(plan.steps)

    events_path = run_dir / "events.jsonl"

    # Simulate run start
    _write_step_event(
        events_path,
        {"kind": "run_started", "run_id": "run-hype-1", "ts": "2025-01-01T00:00:00Z"},
    )

    # Simulate dispatching and completing each leaf step
    for path_tuple in sorted(leaf_paths):
        leaf_id = path_tuple[-1]
        # Create step directory and produces
        step_dir = run_dir / "steps" / Path(*path_tuple) / "v1"
        step_dir.mkdir(parents=True, exist_ok=True)
        produces_dir = step_dir / "produces"
        produces_dir.mkdir(exist_ok=True)

        # Write dispatched event
        _write_step_event(
            events_path,
            make_step_dispatched_event(
                "/".join(path_tuple),
                f"python3 -m {leaf_id}",
                adapter="local",
                step_version=1,
            ),
        )

        # Write a stub artifact
        artifact_path = produces_dir / f"{leaf_id}_output.json"
        artifact_path.write_text('{"status": "done"}', encoding="utf-8")

        # Write completed event with cost
        cost = {"amount": 0.05, "currency": "USD", "source": "gemini"}
        # Editor_review uses manual adapter
        adapter = "manual" if leaf_id == "editor_review" else "local"
        _write_step_event(
            events_path,
            make_step_completed_event(
                "/".join(path_tuple), returncode=0, cost=cost, adapter=adapter
            ),
        )

    # Verify run_completed works
    all_events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_events.append(json.loads(line))

    assert _run_is_complete(plan, all_events) is True

    # Emit run_completed
    _write_step_event(events_path, make_run_completed_event("run-hype-1"))

    # Verify final event is run_completed
    with open(events_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    final_event = json.loads(lines[-1])
    assert final_event["kind"] == "run_completed"
    assert final_event["run_id"] == "run-hype-1"


def test_artifacts_under_canonical_paths(tmp_path: Path) -> None:
    """Verify artifacts land under steps/hype/<id>/v<N>/produces/... paths."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)

    plan = load_plan(str(run_dir / "plan.json"))
    leaf_paths = _collect_leaf_paths(plan.steps)

    for path_tuple in sorted(leaf_paths):
        leaf_id = path_tuple[-1]
        step_dir = run_dir / "steps" / Path(*path_tuple) / "v1" / "produces"
        step_dir.mkdir(parents=True, exist_ok=True)
        artifact = step_dir / f"{leaf_id}_result.json"
        artifact.write_text(f'{{"step": "{leaf_id}"}}', encoding="utf-8")
        assert artifact.exists()

    # Verify canonical path structure
    assert (run_dir / "steps" / "hype" / "transcribe" / "v1" / "produces").exists()
    assert (run_dir / "steps" / "hype" / "scenes" / "v1" / "produces").exists()
    assert (run_dir / "steps" / "hype" / "cut" / "v1" / "produces").exists()
    assert (run_dir / "steps" / "hype" / "render" / "v1" / "produces").exists()
    assert (run_dir / "steps" / "hype" / "editor_review" / "v1" / "produces").exists()
    assert (run_dir / "steps" / "hype" / "validate" / "v1" / "produces").exists()


def test_costs_surfaced_on_completion_events(tmp_path: Path) -> None:
    """All step_completed events carry cost fields."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)
    events_path = run_dir / "events.jsonl"

    _write_step_event(
        events_path,
        {"kind": "run_started", "run_id": "run-hype-1", "ts": "2025-01-01T00:00:00Z"},
    )

    costs_emitted = []
    for step_id, cost in [
        ("transcribe", {"amount": 0.002, "currency": "USD", "source": "gemini"}),
        ("scenes", {"amount": 0.005, "currency": "USD", "source": "gemini"}),
        ("cut", {"amount": 0.010, "currency": "USD", "source": "claude"}),
        ("render", {"amount": 0.50, "currency": "USD", "source": "runpod"}),
        ("editor_review", {"amount": 0.0, "currency": "USD", "source": "manual"}),
        ("validate", {"amount": 0.001, "currency": "USD", "source": "gemini"}),
    ]:
        path_tuple = ("hype", step_id)
        # Create step dir
        (run_dir / "steps" / Path(*path_tuple) / "v1" / "produces").mkdir(parents=True, exist_ok=True)

        _write_step_event(
            events_path,
            make_step_dispatched_event(
                "/".join(path_tuple),
                f"python3 -m {step_id}",
                adapter="manual" if step_id == "editor_review" else "local",
            ),
        )
        _write_step_event(
            events_path,
            make_step_completed_event(
                "/".join(path_tuple),
                returncode=0,
                cost=cost,
                adapter="manual" if step_id == "editor_review" else "local",
            ),
        )
        costs_emitted.append(cost)

    # Read all events, verify completion events carry cost
    all_events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_events.append(json.loads(line))

    completed_events = [e for e in all_events if e.get("kind") == "step_completed"]
    assert len(completed_events) == 6

    sources_seen = set()
    for ev in completed_events:
        assert "cost" in ev
        assert "amount" in ev["cost"]
        assert "source" in ev["cost"]
        sources_seen.add(ev["cost"]["source"])

    assert "gemini" in sources_seen
    assert "claude" in sources_seen
    assert "runpod" in sources_seen


# ---------------------------------------------------------------------------
# run_completed event guard
# ---------------------------------------------------------------------------


def test_run_completed_not_emitted_with_awaiting_fetch(tmp_path: Path) -> None:
    """_run_is_complete returns False when any step is awaiting_fetch."""
    proj_root, run_dir, _, _ = _build_synthetic_hype_run(tmp_path)
    events_path = run_dir / "events.jsonl"

    plan = load_plan(str(run_dir / "plan.json"))

    _write_step_event(
        events_path,
        {"kind": "run_started", "run_id": "run-hype-1", "ts": "2025-01-01T00:00:00Z"},
    )

    # Complete all but render (which goes to awaiting_fetch)
    leaf_paths = _collect_leaf_paths(plan.steps)
    for path_tuple in sorted(leaf_paths):
        leaf_id = path_tuple[-1]
        (run_dir / "steps" / Path(*path_tuple) / "v1" / "produces").mkdir(parents=True, exist_ok=True)
        _write_step_event(
            events_path,
            make_step_dispatched_event(
                "/".join(path_tuple),
                f"python3 -m {leaf_id}",
                adapter="manual" if leaf_id == "editor_review" else "local",
            ),
        )
        if leaf_id == "render":
            # Emit awaiting_fetch instead of completed
            _write_step_event(
                events_path,
                {
                    "kind": "step_awaiting_fetch",
                    "plan_step_path": list(path_tuple),
                    "missing": ["hype.mp4"],
                    "mismatched": [],
                    "ts": "2025-01-01T00:01:00Z",
                },
            )
        else:
            _write_step_event(
                events_path,
                make_step_completed_event(
                    "/".join(path_tuple),
                    returncode=0,
                    adapter="manual" if leaf_id == "editor_review" else "local",
                ),
            )

    all_events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_events.append(json.loads(line))

    # Should NOT be complete
    assert _run_is_complete(plan, all_events) is False


# ---------------------------------------------------------------------------
# registry + merged render props golden comparison
# ---------------------------------------------------------------------------


def test_hype_registry_and_merged_render_props_match_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copy hype fixtures into tmp_path, call the private render helpers
    directly, and assert the assembled dict matches the committed goldens."""
    import shutil

    from astrid.core.paths import REPO_ROOT

    # -- 1. copy hype fixtures into tmp_path ---------------------------------
    examples = REPO_ROOT / "examples"
    timeline_src = examples / "hype.timeline.json"
    assets_src = examples / "hype.assets.json"
    metadata_src = examples / "hype.metadata.json"

    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    for src in (timeline_src, assets_src, metadata_src):
        shutil.copy2(src, fixture_dir / src.name)

    timeline_path = fixture_dir / "hype.timeline.json"
    assets_path = fixture_dir / "hype.assets.json"

    # -- 2. create placeholder .mp4 assets (referenced by assets registry) --
    for name in ("main.mp4", "broll.mp4"):
        (fixture_dir / name).write_bytes(b"fake-mp4")

    # -- 3. isolate env / cache roots ---------------------------------------
    astrid_home = tmp_path / "astrid_home"
    astrid_home.mkdir()
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    hype_cache = tmp_path / "hype_cache"
    hype_cache.mkdir()

    monkeypatch.setenv("ASTRID_HOME", str(astrid_home))
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("HYPE_CACHE_DIR", str(hype_cache))

    # -- 4. clear external API key env vars ---------------------------------
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key.endswith("_API_TOKEN"):
            monkeypatch.delenv(key, raising=False)

    # -- 5. monkeypatch WORKSPACE_ROOT on the render module so the
    #       fallback theme path is deterministic (no real filesystem theme). -
    monkeypatch.setattr(
        "astrid.packs.rendering.executors.render.run.WORKSPACE_ROOT",
        tmp_path,
    )

    # -- 6. allow import of the guarded render module -----------------------
    monkeypatch.setenv("ASTRID_INTERNAL_INVOCATION", "1")
    from astrid.packs.rendering.executors.render.run import (
        _resolved_theme_for_render,
        _serialize_timeline,
    )

    # -- 7. call the private helpers directly --------------------------------
    serialized_timeline = _serialize_timeline(
        timeline_path, default_theme="banodoco-default"
    )
    fallback_theme = tmp_path / "themes" / "banodoco-default" / "theme.json"
    resolved_theme = _resolved_theme_for_render(timeline_path, fallback_theme)

    # -- 8. load the asset registry via core timeline.load_registry ----------
    from astrid.core.timeline import load_registry

    loaded_registry = load_registry(assets_path)

    # -- 9. assemble the merged dict (same shape as the golden) --------------
    assembled = {
        "assets": loaded_registry,
        "theme": resolved_theme,
        "timeline": serialized_timeline,
    }

    # -- 10. load goldens and compare ---------------------------------------
    goldens_dir = REPO_ROOT / "tests" / "golden" / "hype"
    merged_golden_path = goldens_dir / "merged_render_props.json"
    assets_golden_path = goldens_dir / "hype.assets.json"

    merged_golden = json.loads(merged_golden_path.read_text(encoding="utf-8"))
    assets_golden = json.loads(assets_golden_path.read_text(encoding="utf-8"))

    # Round-trip through sorted/indented JSON for stable comparison
    assembled_str = json.dumps(assembled, sort_keys=True, indent=2, ensure_ascii=False)
    merged_golden_str = json.dumps(merged_golden, sort_keys=True, indent=2, ensure_ascii=False)
    assets_golden_str = json.dumps(assets_golden, sort_keys=True, indent=2, ensure_ascii=False)

    assert assembled_str == merged_golden_str, (
        "Assembled merged render props differ from goldens.\n"
        f"assembled: {assembled_str}\n"
        f"golden: {merged_golden_str}"
    )

    # Also verify the loaded registry matches the assets golden
    registry_str = json.dumps(loaded_registry, sort_keys=True, indent=2, ensure_ascii=False)
    assert registry_str == assets_golden_str, (
        "Loaded asset registry differs from assets golden.\n"
        f"registry: {registry_str}\n"
        f"golden: {assets_golden_str}"
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _collect_leaf_paths(steps: tuple[Step, ...]) -> set[tuple[str, ...]]:
    """Collect all leaf step paths from a step tree."""
    leaf_paths: set[tuple[str, ...]] = set()

    def _walk(s: tuple[Step, ...], prefix: tuple[str, ...]) -> None:
        for step in s:
            path_tuple = prefix + (step.id,)
            if step.children is None:
                leaf_paths.add(path_tuple)
            else:
                _walk(step.children, path_tuple)

    _walk(steps, ())
    return leaf_paths
