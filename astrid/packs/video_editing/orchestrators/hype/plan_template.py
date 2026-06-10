"""Hype plan-template for Sprint 5a — emits a plan v2 with the leaner 6-stage spine."""

from __future__ import annotations

import shlex
import uuid
from pathlib import Path
from typing import Any

from astrid.core.execution.orchestrator.plan_template import (
    build_group_template,
    build_leaf_template,
    build_plan_template,
    cost_entry,
    file_output,
    repeat_for_each_from,
    repeat_until,
)


def build_plan_v2(
    *,
    python_exec: str,
    run_root: str | Path,
    source: str | Path | None = None,
    brief: str | Path | None = None,
    theme: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a plan v2 dict for the hype pipeline.

    The plan follows the leaner S5a spine:
      transcribe → scenes → cut → render → editor_review → validate

    - All executor leaves use the task-mode executor runner contract.
    - Render stays local and calls ``rendering.render`` unless a future plan
      explicitly promotes it to ``remote-artifact``.
    - ``editor_review`` uses ``adapter: manual`` for human-in-the-loop.
    - The top-level group step ``hype`` declares ``re_export`` per G1.
    - ``cut`` fans out across discovered scene item ids via
      ``repeat.for_each.from_ref: "scenes.produces.scene_items"`` (G5).

    Dynamic discovery (shot count after cut) is handled by the orchestrator
    calling ``astrid plan add-step`` at runtime — not by this template.
    """
    run_root = Path(run_root)
    plan_id = f"hype-{run_id or uuid.uuid4().hex[:12]}"

    # Command interpolation: {python_exec}, {run_root}, {source} are resolved
    # at plan-emission time per G3.
    cmd_transcribe = _build_transcribe_cmd(python_exec, run_root, source)
    cmd_scenes = _build_scenes_cmd(python_exec, run_root, source)
    cmd_cut = _build_cut_cmd(python_exec, run_root, source, brief)
    cmd_render = _build_render_cmd(python_exec, run_root, theme)
    cmd_validate = _build_validate_cmd(python_exec, run_root)

    children = [
        build_leaf_template(
            "transcribe",
            command=cmd_transcribe,
            produces=[file_output("transcript_output", "transcript.json")],
            cost=cost_entry(0.002, source="gemini"),
        ),
        build_leaf_template(
            "scenes",
            command=cmd_scenes,
            produces=[
                file_output("scenes_list", "scenes.json"),
                file_output("scene_items", "scene_items.json"),
            ],
            cost=cost_entry(0.005, source="gemini"),
        ),
        build_leaf_template(
            "cut",
            command=cmd_cut,
            repeat=repeat_for_each_from("scenes.produces.scene_items"),
            produces=[
                file_output("timeline_output", "hype.timeline.json"),
                file_output("assets_registry", "hype.assets.json"),
            ],
            cost=cost_entry(0.010, source="claude"),
        ),
        build_leaf_template(
            "render",
            command=cmd_render,
            produces=[file_output("video_output", "hype.mp4")],
            cost=cost_entry(0.50, source="runpod"),
        ),
        build_leaf_template(
            "editor_review",
            adapter="manual",
            command="editor-review",
            requires_ack=True,
            instructions=(
                "Review the rendered video at steps/hype/render/v1/produces/hype.mp4. "
                "Write editor_review.json with verdict 'ship' to approve, or a non-ship "
                "verdict to request another review pass. Ack with "
                "'astrid ack hype/editor_review --decision approve'."
            ),
            repeat=repeat_until(
                'hype.editor_review.produces.review_output.verdict == "ship"',
                max_iterations=2,
                on_exhaust="fail",
            ),
            produces=[file_output("review_output", "editor_review.json")],
        ),
        build_leaf_template(
            "validate",
            command=cmd_validate,
            produces=[file_output("validation_output", "validation.json")],
        ),
    ]
    return build_plan_template(
        plan_id=plan_id,
        steps=[
            build_group_template(
                "hype",
                re_export={
                    "final_video": "render.produces.video_output",
                    "timeline": "cut.produces.timeline_output",
                    "transcript": "transcribe.produces.transcript_output",
                    "scenes": "scenes.produces.scenes_list",
                },
                children=children,
            )
        ],
    )


def _build_transcribe_cmd(
    python_exec: str, run_root: Path, source: str | Path | None
) -> str:
    src = str(Path(source).resolve()) if source else ""
    return _executor_cmd(
        python_exec,
        "editorial.transcribe",
        "{produces_root}",
        {"audio": src},
    )


def _build_scenes_cmd(
    python_exec: str, run_root: Path, source: str | Path | None
) -> str:
    src = str(Path(source).resolve()) if source else ""
    return _executor_cmd(
        python_exec,
        "editorial.scenes",
        "{produces_root}",
        {"video": src},
    )


def _build_cut_cmd(
    python_exec: str,
    run_root: Path,
    source: str | Path | None,
    brief: str | Path | None,
) -> str:
    src = str(Path(source).resolve()) if source else ""
    brief_path = str(Path(brief).resolve()) if brief else ""
    scenes_json = run_root / "steps" / "hype" / "scenes" / "v1" / "produces" / "scenes.json"
    return _executor_cmd(
        python_exec,
        "video_editing.cut",
        "{produces_root}",
        {
            "brief": brief_path,
            "video": src,
            "audio": src,
            "scene_id": "{item_id}",
            "scenes_json": scenes_json,
        },
    )


def _build_render_cmd(python_exec: str, run_root: Path, theme: str | Path | None = None) -> str:
    timeline = run_root / "steps" / "hype" / "cut" / "v1" / "produces" / "hype.timeline.json"
    assets_registry = run_root / "steps" / "hype" / "cut" / "v1" / "produces" / "hype.assets.json"
    inputs: dict[str, str | Path] = {
        "timeline": timeline,
        "assets_registry": assets_registry,
    }
    if theme:
        inputs["theme"] = Path(theme).resolve()
    return _executor_cmd(
        python_exec,
        "rendering.render",
        "{produces_root}",
        inputs,
    )


def _build_validate_cmd(python_exec: str, run_root: Path) -> str:
    video = run_root / "steps" / "hype" / "render" / "v1" / "produces" / "hype.mp4"
    timeline = run_root / "steps" / "hype" / "cut" / "v1" / "produces" / "hype.timeline.json"
    metadata = run_root / "steps" / "hype" / "cut" / "v1" / "produces" / "hype.metadata.json"
    return _executor_cmd(
        python_exec,
        "editorial.validate",
        "{produces_root}",
        {
            "video": video,
            "timeline": timeline,
            "metadata": metadata,
        },
    )


def _executor_cmd(
    python_exec: str,
    executor_id: str,
    out: str | Path,
    inputs: dict[str, str | Path],
) -> str:
    parts = [
        shlex.quote(str(python_exec)),
        "-m",
        "astrid",
        "executors",
        "run",
        shlex.quote(executor_id),
        "--out",
        shlex.quote(str(out)),
    ]
    for name, value in inputs.items():
        text = str(value)
        if text:
            parts.extend(["--input", shlex.quote(f"{name}={text}")])
    return " ".join(parts)
