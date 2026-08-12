"""Hype plan-template helpers.

Static callers can still use :func:`build_plan_v2`, but project-mode hype
emission uses :func:`build_runtime_plan_v2` so the task plan matches the
parsed CLI arguments and the graph selected by ``select_steps(args)``.
"""

from __future__ import annotations

import shlex
import uuid
from collections.abc import Sequence
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
from astrid.packs.video_editing.orchestrators.hype.config import STEP_ORDER
from astrid.packs.video_editing.orchestrators.hype.steps import Step as HypeStep

_RENDER_ONLY_STEPS = frozenset({"refine", "render", "editor_review", "validate"})

_PRODUCES_NAMES = {
    "transcript.json": "transcript",
    "scenes.json": "scenes",
    "quality_zones.json": "quality_zones",
    "shots.json": "shots",
    "scene_triage.json": "scene_triage",
    "scene_descriptions.json": "scene_descriptions",
    "quote_candidates.json": "quote_candidates",
    "pool.json": "pool",
    "arrangement.json": "arrangement",
    "hype.timeline.json": "timeline",
    "hype.assets.json": "assets_registry",
    "hype.metadata.json": "metadata",
    "refine.json": "refinement",
    "hype.mp4": "video",
    "hype.mp4.provenance.json": "provenance",
    "editor_review.json": "editor_review",
    "validation.json": "validation",
}


def build_runtime_plan_v2(
    *,
    args: Any,
    selected_steps: Sequence[HypeStep],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a plan v2 from hype's runtime-selected pipeline steps.

    This builder is intentionally downstream of parser resolution,
    ``prepare_brief_artifacts()``, registry lookup, fact discovery, and
    ``select_steps(args)``. It therefore emits the effective supported subset
    of the 15-step graph instead of the old static six-step spine.
    """
    children = [
        _runtime_leaf_for_step(step, args)
        for step in _effective_runtime_steps(selected_steps, args)
    ]
    if not children:
        raise ValueError("hype runtime plan has no executable steps for the supplied arguments")

    re_export = _runtime_re_exports({child.id for child in children})
    return build_plan_template(
        plan_id=f"hype-{run_id or uuid.uuid4().hex[:12]}",
        steps=[
            build_group_template(
                "hype",
                re_export=re_export,
                children=children,
            )
        ],
    )


def _effective_runtime_steps(
    selected_steps: Sequence[HypeStep], args: Any
) -> list[HypeStep]:
    skipped = set(getattr(args, "skip", ()) or ())
    from_step = getattr(args, "from_step", None)
    from_index = STEP_ORDER.index(from_step) if from_step else None
    render = bool(getattr(args, "render", False))
    effective: list[HypeStep] = []
    for step in selected_steps:
        if step.name in skipped:
            continue
        if from_index is not None and STEP_ORDER.index(step.name) < from_index:
            continue
        if step.name in _RENDER_ONLY_STEPS and not render:
            continue
        effective.append(step)
    return effective


def _runtime_leaf_for_step(step: HypeStep, args: Any) -> Any:
    command = shlex.join(step.build_cmd(args))
    repeat = None
    adapter = "local"
    requires_ack = False
    instructions = None
    if step.name == "editor_review":
        adapter = "manual"
        requires_ack = True
        command = _editor_review_ack_command(args)
        instructions = _editor_review_instructions(args)
        repeat = repeat_until(
            'hype.editor_review.produces.editor_review.verdict == "ship"',
            max_iterations=int(getattr(args, "max_editor_passes", 2)),
            on_exhaust="fail",
        )
    return build_leaf_template(
        step.name,
        command=command,
        adapter=adapter,
        requires_ack=requires_ack,
        ack_kind="human" if requires_ack else "agent",
        instructions=instructions,
        assignee="any-human" if requires_ack else "system",
        produces=_runtime_produces(step, args),
        repeat=repeat,
    )


def _editor_review_ack_command(args: Any) -> str:
    project = getattr(args, "project", None)
    base = ["astrid", "ack", "--engine", "arnold"]
    if project:
        base.extend(["--project", str(project)])
    else:
        base.extend(["--project", "<project>"])
    base.extend(["--stage", "hype/editor_review", "--payload", "<editor-review-payload-json>"])
    return shlex.join(base)


def _editor_review_instructions(args: Any) -> str:
    project = getattr(args, "project", None) or "<project>"
    return (
        "Review the rendered hype output and write editor_review.json. "
        "For a ship verdict, acknowledge this Arnold stage with "
        f"`astrid ack --engine arnold --project {project} --stage hype/editor_review "
        "--payload '{\"decision\":{\"action\":\"approve\",\"notes\":\"ship\",\"state_patch\":{}}}'`. "
        "For rework or micro-fix verdicts, acknowledge with a payload that includes the "
        "corresponding `plan_mutation.diff`. Arnold session-succession will record "
        "`plan_mutated`, "
        "freeze the current segment, and compile the successor segment; do not mutate "
        "the live Arnold graph."
    )


def _runtime_produces(step: HypeStep, args: Any) -> list[Any]:
    produces = []
    for path in _runtime_sentinel_paths(step, args):
        produces.append(
            file_output(
                _PRODUCES_NAMES.get(path.name, path.stem),
                path,
                sentinel=True,
            )
        )
    return produces


def _runtime_sentinel_paths(step: HypeStep, args: Any) -> list[Path]:
    root = args.brief_out if step.per_brief else args.out
    return [root / name for name in step.sentinels]


def _runtime_re_exports(child_ids: set[str]) -> dict[str, str]:
    refs = {
        "transcript": "transcribe.produces.transcript",
        "pool": "pool_build.produces.pool",
        "arrangement": "arrange.produces.arrangement",
        "timeline": "cut.produces.timeline",
        "video": "render.produces.video",
        "provenance": "render.produces.provenance",
        "editor_review": "editor_review.produces.editor_review",
        "validation": "validate.produces.validation",
    }
    return {
        name: ref
        for name, ref in refs.items()
        if ref.split(".", 1)[0] in child_ids
    }


def build_plan_v2(
    *,
    python_exec: str,
    run_root: str | Path,
    source: str | Path | None = None,
    brief: str | Path | None = None,
    theme: str | Path | None = None,
    run_id: str | None = None,
    render: bool = False,
    skip: Sequence[str] = (),
    from_step: str | None = None,
    max_editor_passes: int = 2,
    target_duration: float | None = None,
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
    if brief is not None:
        args = _runtime_args_from_template_inputs(
            python_exec=python_exec,
            run_root=run_root,
            source=source,
            brief=brief,
            theme=theme,
            render=render,
            skip=skip,
            from_step=from_step,
            max_editor_passes=max_editor_passes,
            target_duration=target_duration,
        )
        from astrid.packs.video_editing.orchestrators.hype.runner import (
            prepare_brief_artifacts,
        )
        from astrid.packs.video_editing.orchestrators.hype.steps import select_steps

        prepare_brief_artifacts(args)
        return build_runtime_plan_v2(
            args=args,
            selected_steps=select_steps(args),
            run_id=run_id,
        )

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
            produces=[
                file_output("video_output", "hype.mp4"),
                file_output("provenance", "hype.mp4.provenance.json"),
            ],
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
                    "render_provenance": "render.produces.provenance",
                    "timeline": "cut.produces.timeline_output",
                    "transcript": "transcribe.produces.transcript_output",
                    "scenes": "scenes.produces.scenes_list",
                },
                children=children,
            )
        ],
    )


def _runtime_args_from_template_inputs(
    *,
    python_exec: str,
    run_root: str | Path,
    source: str | Path | None,
    brief: str | Path,
    theme: str | Path | None,
    render: bool,
    skip: Sequence[str],
    from_step: str | None,
    max_editor_passes: int,
    target_duration: float | None,
) -> Any:
    import argparse

    from astrid.packs.video_editing.orchestrators.hype.config import usage_error

    out = Path(run_root).expanduser().resolve()
    brief_path = Path(brief).expanduser().resolve()
    video = Path(source).expanduser().resolve() if source is not None else None
    if video is None and target_duration is None:
        usage_error("astrid: --target-duration is required when both --video and --audio are omitted")
    if from_step is not None and from_step not in STEP_ORDER:
        usage_error(f"astrid: unknown --from step: {from_step}")
    unknown_skips = [name for name in skip if name not in STEP_ORDER]
    if unknown_skips:
        usage_error(f"astrid: unknown --skip step(s): {', '.join(unknown_skips)}")
    generic_brief_names = {"brief", "plan", "prompt"}
    brief_slug = out.name if brief_path.stem.lower() in generic_brief_names else brief_path.stem
    return argparse.Namespace(
        video=video,
        audio=video,
        target_duration=target_duration,
        out=out,
        brief=brief_path,
        brief_slug=brief_slug,
        brief_out=(out / "briefs" / brief_slug).resolve(),
        brief_copy=(out / "briefs" / brief_slug / "brief.txt").resolve(),
        source_slug=out.name,
        python_exec=str(python_exec),
        render=bool(render),
        skip=list(skip),
        from_step=from_step,
        max_editor_passes=int(max_editor_passes),
        theme=Path(theme).expanduser().resolve() if theme is not None else None,
        theme_explicit=theme is not None,
        env_file=None,
        extra_args={},
        asset_pairs=[],
        asset=[],
        primary_asset=None,
        allow_generative_effects=False,
        brief_allow_generative_visuals=False,
        project=None,
        timeline_slug=None,
        actor_via=None,
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
