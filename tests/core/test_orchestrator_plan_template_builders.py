from __future__ import annotations

import json
from pathlib import Path

from astrid.core.execution.orchestrator.plan_template import (
    build_group_template,
    build_leaf_template,
    build_plan_template,
    cost_entry,
    emit_plan_json,
    file_output,
    repeat_for_each_from,
)
from astrid.core.task.plan import load_plan


def test_builder_emits_loadable_collapsed_plan(tmp_path: Path) -> None:
    plan = build_plan_template(
        plan_id="demo",
        steps=[
            build_group_template(
                "workflow",
                re_export={"final": "render.produces.video"},
                children=[
                    build_leaf_template(
                        "enumerate",
                        command="python enumerate.py",
                        produces=[file_output("items", "items.json")],
                        cost=cost_entry(0, source="local"),
                    ),
                    build_leaf_template(
                        "render",
                        command="python render.py",
                        repeat=repeat_for_each_from("enumerate.produces.items"),
                        produces=[file_output("video", "video.mp4")],
                        cost=cost_entry(0.5, source="runpod"),
                    ),
                ],
            )
        ],
    )

    path = tmp_path / "plan.json"
    emit_plan_json(plan, path)
    loaded = load_plan(path)

    assert loaded.version == 2
    assert loaded.steps[0].id == "workflow"
    assert loaded.steps[0].children is not None
    assert loaded.steps[0].children[1].repeat is not None


def test_builtin_task_templates_round_trip_through_kernel(tmp_path: Path) -> None:
    from astrid.packs.video_editing.orchestrators.event_talks.plan_template import build_plan_v2 as build_event_talks
    from astrid.packs.video_editing.orchestrators.hype.plan_template import build_plan_v2 as build_hype
    from astrid.packs.video_editing.orchestrators.iteration_video.plan_template import build_plan_v2 as build_iteration
    from astrid.packs.video_editing.orchestrators.thumbnail_maker.plan_template import build_plan_v2 as build_thumbnail

    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    builders = [
        build_hype(python_exec="python3", run_root=tmp_path / "hype", source=source, run_id="run-hype"),
        build_event_talks(python_exec="python3", run_root=tmp_path / "events", source=source, run_id="run-events"),
        build_thumbnail(python_exec="python3", run_root=tmp_path / "thumbs", source=source, run_id="run-thumbs"),
        build_iteration(
            python_exec="python3",
            run_root=tmp_path / "iteration",
            target_run_id="01ARZ3NDEKTSV4RRFFQ69G5FV1",
            repo_root=tmp_path,
            run_id="run-iteration",
        ),
    ]

    for index, plan in enumerate(builders):
        path = tmp_path / f"plan-{index}.json"
        path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
        loaded = load_plan(path)
        assert loaded.version == 2
        assert loaded.steps
