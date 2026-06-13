"""Static shape definitions for the Arnold host allowlist.

This module declares the canonical set of Arnold workflow shapes that the
host supports. Each shape is a hand-authored static graph; no runtime
topology synthesis or host-side control loop is introduced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from astrid.core.integrations.arnold.host.invocation import (
    ALLOWLISTED_INVOCATION_TEMPLATES,
    build_human_resume_input_schema,
    build_workflow_step_invocation,
)
from astrid.core.integrations.arnold.host.registry import ShapeEntry

WE_REFINE_IMAGE_ID: str = "we.refine_image"
WE_BEST_OF_4_ID: str = "we.best_of_4"
TEXT_ANALYSIS_SUMMARIZE_ID: str = "text_analysis.summarize"
BUILTIN_AGENT_PROBE_ID: str = "builtin.agent_probe"
STREAM_CONTENT_DISTILL_ID: str = "stream_content.distill"
FOLEY_MAP_ID: str = "foley.foley_map"
ANIMATE_IMAGE_ID: str = "video_editing.animate_image"
LOGO_IDEAS_ID: str = "video_editing.logo_ideas"
VARY_GRID_ID: str = "video_editing.vary_grid"
ITERATION_VIDEO_ID: str = "video_editing.iteration_video"

WE_REFINE_IMAGE_ALIAS: str = "refine"
WE_BEST_OF_4_ALIAS: str = "best4"
TEXT_ANALYSIS_SUMMARIZE_ALIAS: str = "summarize"
BUILTIN_AGENT_PROBE_ALIAS: str = "agent-probe"
STREAM_CONTENT_DISTILL_ALIAS: str = "distill"
FOLEY_MAP_ALIAS: str = "foley-map"
ANIMATE_IMAGE_ALIAS: str = "animate-image"
LOGO_IDEAS_ALIAS: str = "logo-ideas"
VARY_GRID_ALIAS: str = "vary-grid"
ITERATION_VIDEO_ALIAS: str = "iteration-video"

ANIMATE_IMAGE_EDIT_MODEL_ID: str = "openai/gpt-image-2/edit"
ANIMATE_IMAGE_ANIMATE_MODEL_ID: str = "fal-ai/wan/v2.2-14b/animate/move"
LOGO_IDEAS_FIREWORKS_MODEL_ID: str = "accounts/fireworks/models/kimi-k2p5"
LOGO_IDEAS_GRID_MODEL_ID: str = "openai/gpt-image-2"
LOGO_IDEAS_PER_IMAGE_MODEL_ID: str = "fal-ai/z-image/turbo"
VARY_GRID_EDIT_MODEL_ID: str = "openai/gpt-image-2/edit"
VARY_GRID_FIREWORKS_MODEL_ID: str = "accounts/fireworks/models/kimi-k2p5"
ITERATION_VIDEO_SUMMARIZER_MODEL_ID: str = "understanding.understand.v1"


@dataclass(frozen=True)
class _ShapeGraphSpec:
    """Read-only metadata about one frozen pipeline shape."""

    entry_stage_id: str
    stage_labels: dict[str, str] = field(default_factory=dict)


_WE_REFINE_IMAGE_SPEC = _ShapeGraphSpec(
    entry_stage_id="generate",
    stage_labels={
        "generate": "Generate",
        "review": "Review",
        "halt": "Halt",
    },
)

_WE_BEST_OF_4_SPEC = _ShapeGraphSpec(
    entry_stage_id="generate",
    stage_labels={
        "generate": "Generate",
        "gen_0": "Gen 0",
        "gen_1": "Gen 1",
        "gen_2": "Gen 2",
        "gen_3": "Gen 3",
        "judge": "Judge",
        "review": "Review",
        "halt": "Halt",
    },
)

_TEXT_ANALYSIS_SUMMARIZE_SPEC = _ShapeGraphSpec(
    entry_stage_id="read_input",
    stage_labels={
        "read_input": "Read Input",
        "write_summary": "Write Summary",
        "write_verdict": "Write Verdict",
        "halt": "Halt",
    },
)

_BUILTIN_AGENT_PROBE_SPEC = _ShapeGraphSpec(
    entry_stage_id="per_item",
    stage_labels={
        "per_item": "Per Item",
        "halt": "Halt",
    },
)

_STREAM_CONTENT_DISTILL_SPEC = _ShapeGraphSpec(
    entry_stage_id="transcribe",
    stage_labels={
        "transcribe": "Transcribe",
        "scenes": "Scenes",
        "segment-map": "Segment Map",
        "extract-segments": "Extract Segments",
        "clip-candidates": "Clip Candidates",
        "review": "Review",
        "halt": "Halt",
    },
)

_FOLEY_MAP_SPEC = _ShapeGraphSpec(
    entry_stage_id="tile-video",
    stage_labels={
        "tile-video": "Tile Video",
        "tile-fanout": "Tile Fanout",
        "tile-prompts": "Tile Prompts",
        "foley-audio": "Foley Audio",
        "review": "Review",
        "spatial-page": "Spatial Page",
        "halt": "Halt",
    },
)

_ANIMATE_IMAGE_SPEC = _ShapeGraphSpec(
    entry_stage_id="validate-inputs",
    stage_labels={
        "validate-inputs": "Validate Inputs",
        "prepare-source": "Prepare Source",
        "plan-commands": "Plan Commands",
        "edit-image": "Edit Image",
        "animate-video": "Animate Video",
        "write-artifacts": "Write Artifacts",
        "halt": "Halt",
    },
)

_LOGO_IDEAS_SPEC = _ShapeGraphSpec(
    entry_stage_id="normalize-brief",
    stage_labels={
        "normalize-brief": "Normalize Brief",
        "draft-concepts": "Draft Concepts",
        "render-candidates": "Render Candidates",
        "write-artifacts": "Write Artifacts",
        "halt": "Halt",
    },
)

_VARY_GRID_SPEC = _ShapeGraphSpec(
    entry_stage_id="inspect-source",
    stage_labels={
        "inspect-source": "Inspect Source",
        "slice-source-grid": "Slice Source Grid",
        "select-prompt-pattern": "Select Prompt Pattern",
        "reference-fanout": "Reference Fanout",
        "draft-variations": "Draft Variations",
        "render-grid": "Render Grid",
        "write-artifacts": "Write Artifacts",
        "halt": "Halt",
    },
)

_ITERATION_VIDEO_SPEC = _ShapeGraphSpec(
    entry_stage_id="resolve-thread",
    stage_labels={
        "resolve-thread": "Resolve Thread",
        "prepare-iteration": "Prepare Iteration",
        "select-renderers": "Select Renderers",
        "assemble-brief": "Assemble Brief",
        "render-video": "Render Video",
        "finalize-iteration": "Finalize Iteration",
        "halt": "Halt",
    },
)


class UnsupportedStepError(ValueError):
    """Raised when a shape leaf is not backed by a known executor."""


def _validate_leaves_executor_backed(
    *leaf_stage_ids: str,
    workflow_id: str,
) -> None:
    """Fail shape construction before any state mutation when a leaf has no executor."""
    missing: list[str] = []
    templates = ALLOWLISTED_INVOCATION_TEMPLATES.get(workflow_id, {})
    for stage_id in leaf_stage_ids:
        if stage_id not in templates:
            missing.append(stage_id)
    if missing:
        raise UnsupportedStepError(
            f"workflow {workflow_id!r} contains unsupported step(s) "
            f"that are not executor-backed: {missing!r}"
        )


def build_refine_image_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the frozen WE-1 graph: generate -> review -> {halt|generate}."""
    from astrid.core.integrations.arnold.host.builder import (
        build_edge,
        build_stage,
        builder_add_edge,
        builder_add_stage,
        builder_finalize,
        builder_set_entry_stage,
    )
    from astrid.core.integrations.arnold.host.compat import compat

    builder = compat.PipelineBuilder()
    generate_stage = build_stage(
        compat.Stage,
        stage_id="generate",
        label=_WE_REFINE_IMAGE_SPEC.stage_labels["generate"],
        invocation=build_workflow_step_invocation(
            WE_REFINE_IMAGE_ID,
            "generate",
            state=state,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
        ),
        metadata={
            "workflow_id": WE_REFINE_IMAGE_ID,
            "stage_id": "generate",
            "entry": True,
        },
    )
    review_stage = build_stage(
        compat.Stage,
        stage_id="review",
        label=_WE_REFINE_IMAGE_SPEC.stage_labels["review"],
        invocation=build_workflow_step_invocation(
            WE_REFINE_IMAGE_ID,
            "review",
            state=state,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
        ),
        suspension=compat.Suspension(
            resume_input_schema=build_human_resume_input_schema()
        ),
        metadata={
            "workflow_id": WE_REFINE_IMAGE_ID,
            "stage_id": "review",
            "human_gate": True,
        },
    )
    halt_stage = build_stage(
        compat.Stage,
        stage_id="halt",
        label=_WE_REFINE_IMAGE_SPEC.stage_labels["halt"],
        metadata={
            "workflow_id": WE_REFINE_IMAGE_ID,
            "stage_id": "halt",
            "terminal": True,
        },
    )

    for stage in (generate_stage, review_stage, halt_stage):
        builder_add_stage(builder, stage)

    for edge in (
        build_edge(
            compat.Edge,
            source="generate",
            target="review",
            label="next",
        ),
        build_edge(
            compat.Edge,
            source="review",
            target="halt",
            label="approve",
        ),
        build_edge(
            compat.Edge,
            source="review",
            target="generate",
            label="reject",
        ),
    ):
        builder_add_edge(builder, edge)

    builder_set_entry_stage(builder, _WE_REFINE_IMAGE_SPEC.entry_stage_id)
    return builder_finalize(builder)


def build_best_of_4_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the frozen WE-3 graph: generate(4×) -> judge -> review -> {halt|generate}."""
    from astrid.core.integrations.arnold.host.builder import (
        build_edge,
        build_parallel_stage,
        build_stage,
        builder_add_edge,
        builder_add_stage,
        builder_finalize,
        builder_set_entry_stage,
    )
    from astrid.core.integrations.arnold.host.compat import compat

    builder = compat.PipelineBuilder()

    gen_sub_stages: list[Any] = []
    for branch in range(4):
        sub_invocation = build_workflow_step_invocation(
            WE_BEST_OF_4_ID,
            f"gen_{branch}",
            state=state,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
        )
        sub_stage = build_stage(
            compat.Stage,
            stage_id=f"gen_{branch}",
            label=_WE_BEST_OF_4_SPEC.stage_labels[f"gen_{branch}"],
            invocation=sub_invocation,
            metadata={
                "workflow_id": WE_BEST_OF_4_ID,
                "stage_id": f"gen_{branch}",
                "branch": branch,
            },
        )
        gen_sub_stages.append(sub_stage)

    generate_stage = build_parallel_stage(
        compat.ParallelStage,
        stage_id="generate",
        label=_WE_BEST_OF_4_SPEC.stage_labels["generate"],
        sub_stages=gen_sub_stages,
        metadata={
            "workflow_id": WE_BEST_OF_4_ID,
            "stage_id": "generate",
            "entry": True,
            "parallel_fan_out": 4,
        },
    )

    judge_stage = build_stage(
        compat.Stage,
        stage_id="judge",
        label=_WE_BEST_OF_4_SPEC.stage_labels["judge"],
        invocation=build_workflow_step_invocation(
            WE_BEST_OF_4_ID,
            "judge",
            state=state,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
        ),
        metadata={
            "workflow_id": WE_BEST_OF_4_ID,
            "stage_id": "judge",
            "judge_required": True,
            "lowers_verdict": True,
        },
    )

    review_stage = build_stage(
        compat.Stage,
        stage_id="review",
        label=_WE_BEST_OF_4_SPEC.stage_labels["review"],
        invocation=build_workflow_step_invocation(
            WE_BEST_OF_4_ID,
            "review",
            state=state,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
        ),
        suspension=compat.Suspension(
            resume_input_schema=build_human_resume_input_schema()
        ),
        metadata={
            "workflow_id": WE_BEST_OF_4_ID,
            "stage_id": "review",
            "human_gate": True,
        },
    )

    halt_stage = build_stage(
        compat.Stage,
        stage_id="halt",
        label=_WE_BEST_OF_4_SPEC.stage_labels["halt"],
        metadata={
            "workflow_id": WE_BEST_OF_4_ID,
            "stage_id": "halt",
            "terminal": True,
        },
    )

    for stage in (generate_stage, judge_stage, review_stage, halt_stage):
        builder_add_stage(builder, stage)

    for edge in (
        build_edge(
            compat.Edge,
            source="generate",
            target="judge",
            label="next",
        ),
        build_edge(
            compat.Edge,
            source="judge",
            target="review",
            label="next",
        ),
        build_edge(
            compat.Edge,
            source="review",
            target="halt",
            label="approve",
        ),
        build_edge(
            compat.Edge,
            source="review",
            target="generate",
            label="reject",
        ),
    ):
        builder_add_edge(builder, edge)

    builder_set_entry_stage(builder, _WE_BEST_OF_4_SPEC.entry_stage_id)
    return builder_finalize(builder)


def build_text_analysis_summarize_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the text_analysis.summarize graph via the DSL compiler.

    Produces a 3-stage linear pipeline:
      read_input -> write_summary -> write_verdict -> halt

    This shape is the single canonical Arnold shape for this workflow id;
    no hand-authored single-stage wrapper remains.
    """
    from astrid.core.orchestrate.compile import compile_to_pipeline

    # Resolve run_root to a concrete path string for the compiler
    resolved_run_root = run_root or (
        artifact_root if artifact_root else "/tmp/arnold-summarize-run"
    )

    result = compile_to_pipeline(
        TEXT_ANALYSIS_SUMMARIZE_ID,
        project=project or "default",
        run_root=resolved_run_root,
        state=dict(state or {}),
    )
    return result.pipeline


def build_builtin_agent_probe_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the builtin.agent_probe graph via the DSL compiler.

    Produces a repeat-for-each pipeline:
      per_item (fan_out_shape, repeat_for_each over [alpha, beta, gamma]) -> halt

    The repeat_for_each metadata on the per_item stage encodes per-item
    identity, ledger context, and output paths matching task runtime behavior.
    This shape is the single canonical Arnold shape for this workflow id.
    """
    from astrid.core.orchestrate.compile import compile_to_pipeline

    # Resolve run_root to a concrete path string for the compiler
    resolved_run_root = run_root or (
        artifact_root if artifact_root else "/tmp/arnold-agent-probe-run"
    )

    result = compile_to_pipeline(
        BUILTIN_AGENT_PROBE_ID,
        project=project or "default",
        run_root=resolved_run_root,
        state=dict(state or {}),
    )
    return result.pipeline


def build_stream_content_distill_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical distill shape with documented wrapper-then-unroll.

    The task runtime's segment extraction loop depends on the computed
    ``segment_map.json`` contents, so the host shape keeps the executor-backed
    stages explicit and models extraction as a wrapper-then-unroll stage whose
    metadata names the repeated child executor and parity-visible artifacts.
    """
    from pathlib import Path

    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    resolved_run_root = Path(
        run_root or artifact_root or "/tmp/arnold-stream-content-distill-run"
    )
    active_state = dict(state or {})
    stage_specs: list[lowering.StageSpec] = [
        lowering.adapter_stage_spec(
            stage_id="transcribe",
            label=_STREAM_CONTENT_DISTILL_SPEC.stage_labels["transcribe"],
            executor_id="editorial.transcribe",
            segment_id=STREAM_CONTENT_DISTILL_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            capability_kind="executor",
            source_orchestrator_id=STREAM_CONTENT_DISTILL_ID,
            metadata={
                "input_bindings": {"audio": "$.video"},
                "runtime_conditionals": ["skipped when $.transcript is provided"],
            },
        ),
        lowering.adapter_stage_spec(
            stage_id="scenes",
            label=_STREAM_CONTENT_DISTILL_SPEC.stage_labels["scenes"],
            executor_id="editorial.scenes",
            segment_id=STREAM_CONTENT_DISTILL_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            capability_kind="executor",
            source_orchestrator_id=STREAM_CONTENT_DISTILL_ID,
            metadata={
                "input_bindings": {"video": "$.video"},
                "runtime_conditionals": ["skipped when $.no_scenes is true"],
            },
        ),
        lowering.adapter_stage_spec(
            stage_id="segment-map",
            label=_STREAM_CONTENT_DISTILL_SPEC.stage_labels["segment-map"],
            executor_id="stream_content.segment_map",
            segment_id=STREAM_CONTENT_DISTILL_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            capability_kind="executor",
            source_orchestrator_id=STREAM_CONTENT_DISTILL_ID,
            metadata={
                "input_bindings": {
                    "video": "$.video",
                    "transcript": "transcribe.produces.transcript",
                    "scenes": "scenes.produces.scenes",
                },
            },
        ),
    ]
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="extract-segments",
        label=_STREAM_CONTENT_DISTILL_SPEC.stage_labels["extract-segments"],
        segment_id=STREAM_CONTENT_DISTILL_ID,
        path=(STREAM_CONTENT_DISTILL_ID, "extract-segments"),
        runtime="command",
        adapter="orchestrator",
        command="extract-segments",
        metadata={
            "wrapper_orchestrator_id": STREAM_CONTENT_DISTILL_ID,
            "wrapper_subcommand": "extract-segments",
            "fan_out_shape": True,
            "wrapper_then_unroll": {
                "kind": "segment_extract",
                "fanout_source_stage_id": "segment-map",
                "fanout_source_artifact": "segment_map",
                "segment_kinds": ["content", "screening"],
                "child_executor_id": "media.clip_extract",
                "manifest_artifact": "segments/segments.json",
                "output_directory": "segments/",
            },
            "input_bindings": {
                "video": "$.video",
                "segment_map": "segment-map.produces.segment_map",
            },
        },
    )
    stage_specs.append(
        lowering.adapter_stage_spec(
            stage_id="clip-candidates",
            label=_STREAM_CONTENT_DISTILL_SPEC.stage_labels["clip-candidates"],
            executor_id="stream_content.clip_candidates",
            segment_id=STREAM_CONTENT_DISTILL_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            capability_kind="executor",
            source_orchestrator_id=STREAM_CONTENT_DISTILL_ID,
            metadata={
                "input_bindings": {
                    "transcript": "transcribe.produces.transcript",
                    "segment_map": "segment-map.produces.segment_map",
                    "brief": "$.brief",
                },
            },
        )
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="review",
        label=_STREAM_CONTENT_DISTILL_SPEC.stage_labels["review"],
        segment_id=STREAM_CONTENT_DISTILL_ID,
        path=(STREAM_CONTENT_DISTILL_ID, "review"),
        runtime="command",
        adapter="orchestrator",
        command="review",
        metadata={
            "wrapper_orchestrator_id": STREAM_CONTENT_DISTILL_ID,
            "wrapper_subcommand": "review",
            "input_bindings": {
                "video": "$.video",
                "segment_map": "segment-map.produces.segment_map",
                "segments_manifest": "extract-segments.produces.segments_manifest",
                "candidates": "clip-candidates.produces.candidates",
            },
            "produces": ["review.html"],
        },
    )
    stage_specs.append(lowering.halt_stage())

    edge_specs = (
        lowering.EdgeSpec(source="transcribe", target="scenes", label="next"),
        lowering.EdgeSpec(source="scenes", target="segment-map", label="next"),
        lowering.EdgeSpec(source="segment-map", target="extract-segments", label="next"),
        lowering.EdgeSpec(source="extract-segments", target="clip-candidates", label="next"),
        lowering.EdgeSpec(source="clip-candidates", target="review", label="next"),
        lowering.EdgeSpec(source="review", target="halt", label="next"),
    )
    lowered = lowering.LoweredSegment(
        entry_stage_id=_STREAM_CONTENT_DISTILL_SPEC.entry_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=edge_specs,
        plan_hash="orchestrator:stream_content.distill@1.0",
        diagnostics=(
            "compiled wrapper-then-unroll orchestrator stream_content.distill",
            "fanout=segment_extract",
            "stages=7",
            "edges=6",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


def build_foley_map_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical Foley Map shape with explicit tile fanout metadata.

    The runtime keeps its tile/VLM/Foley work in bounded parallel batches. The
    host shape preserves that behavior by exposing a dedicated synthetic tile
    fanout stage, then wrapper stages that document the per-tile VLM prompt and
    Foley synthesis loops plus their dry-run and stop-after semantics.
    """
    from pathlib import Path

    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    resolved_run_root = Path(run_root or artifact_root or "/tmp/arnold-foley-map-run")
    active_state = dict(state or {})
    stage_specs: list[lowering.StageSpec] = [
        lowering.adapter_stage_spec(
            stage_id="tile-video",
            label=_FOLEY_MAP_SPEC.stage_labels["tile-video"],
            executor_id="foley.tile_video",
            segment_id=FOLEY_MAP_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            capability_kind="executor",
            source_orchestrator_id=FOLEY_MAP_ID,
            metadata={
                "input_bindings": {
                    "video": "$.video",
                    "grid": "$.grid",
                    "overlap": "$.overlap",
                    "trim": "$.trim",
                },
                "stop_after_value": "tile",
                "runtime_flags": {
                    "dry_run_executes": True,
                    "requires_network": False,
                },
            },
        ),
        lowering.adapter_stage_spec(
            stage_id="tile-fanout",
            label=_FOLEY_MAP_SPEC.stage_labels["tile-fanout"],
            executor_id="synthetic.fanout.fanout",
            segment_id=FOLEY_MAP_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            capability_kind="fanout",
            source_orchestrator_id=FOLEY_MAP_ID,
            metadata={
                "fan_out_shape": True,
                "synthetic_kind": "dynamic_fanout",
                "fanout_source_stage_id": "tile-video",
                "fanout_source_artifact": "tiles_manifest",
                "fanout_manifest_artifact": "tiles.json",
                "parallel_stage_hint": True,
                "fanout_branch_count": "dynamic",
                "fanout_branches": [],
            },
        ),
    ]
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="tile-prompts",
        label=_FOLEY_MAP_SPEC.stage_labels["tile-prompts"],
        segment_id=FOLEY_MAP_ID,
        path=(FOLEY_MAP_ID, "tile-prompts"),
        runtime="command",
        adapter="orchestrator",
        command="prompts",
        metadata={
            "wrapper_orchestrator_id": FOLEY_MAP_ID,
            "wrapper_subcommand": "prompts",
            "fan_out_shape": True,
            "wrapper_then_unroll": {
                "kind": "tile_prompt_map",
                "fanout_source_stage_id": "tile-fanout",
                "fanout_source_artifact": "tiles_manifest",
                "global_executor_id": "understanding.visual_understand",
                "child_executor_id": "understanding.visual_understand",
                "manifest_artifact": "prompts.json",
                "output_directory": "_vlm_scratch/",
            },
            "input_bindings": {
                "global_first_frame": "tile-video.produces.tiles_manifest.global_first_frame",
                "tiles_manifest": "tile-video.produces.tiles_manifest",
            },
            "runtime_flags": {
                "supports_dry_run": True,
                "dry_run_output_template": "[dry-run prompt for {tile_id}]",
                "stop_after_value": "prompts",
            },
            "bounded_parallelism": {
                "arg": "vlm_concurrency",
                "default": 4,
                "kind": "thread_pool",
            },
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="foley-audio",
        label=_FOLEY_MAP_SPEC.stage_labels["foley-audio"],
        segment_id=FOLEY_MAP_ID,
        path=(FOLEY_MAP_ID, "foley-audio"),
        runtime="command",
        adapter="orchestrator",
        command="foley",
        metadata={
            "wrapper_orchestrator_id": FOLEY_MAP_ID,
            "wrapper_subcommand": "foley",
            "fan_out_shape": True,
            "wrapper_then_unroll": {
                "kind": "tile_foley_map",
                "fanout_source_stage_id": "tile-fanout",
                "fanout_source_artifact": "tiles_manifest",
                "child_executor_id": "fal.fal_foley",
                "manifest_artifact": "tiles.json",
                "output_directory": "audio/",
                "retry_manifest_artifact": "flagged.json",
            },
            "input_bindings": {
                "tiles_manifest": "tile-video.produces.tiles_manifest",
                "prompts": "tile-prompts.produces.prompts",
            },
            "runtime_flags": {
                "supports_dry_run": True,
                "stop_after_value": "foley",
                "preserves_partial_manifest": True,
            },
            "bounded_parallelism": {
                "arg": "foley_concurrency",
                "default": 4,
                "kind": "thread_pool",
            },
        },
    )
    stage_specs.extend(
        [
            lowering.adapter_stage_spec(
                stage_id="review",
                label=_FOLEY_MAP_SPEC.stage_labels["review"],
                executor_id="foley.foley_review",
                segment_id=FOLEY_MAP_ID,
                project=project or "default",
                run_root_path=resolved_run_root,
                state=active_state,
                capability_kind="executor",
                source_orchestrator_id=FOLEY_MAP_ID,
                metadata={
                    "input_bindings": {"manifest": "foley-audio.produces.tiles_manifest"},
                    "stop_after_value": "review",
                    "produces": ["review.html", "flagged.json"],
                },
            ),
            lowering.adapter_stage_spec(
                stage_id="spatial-page",
                label=_FOLEY_MAP_SPEC.stage_labels["spatial-page"],
                executor_id="reigh.spatial_audio_page",
                segment_id=FOLEY_MAP_ID,
                project=project or "default",
                run_root_path=resolved_run_root,
                state=active_state,
                capability_kind="executor",
                source_orchestrator_id=FOLEY_MAP_ID,
                metadata={
                    "input_bindings": {"manifest": "foley-audio.produces.tiles_manifest"},
                    "stop_after_value": "page",
                    "media_timeline_outputs": ["page/index.html", "page/manifest.json"],
                },
            ),
            lowering.halt_stage(),
        ]
    )

    edge_specs = (
        lowering.EdgeSpec(source="tile-video", target="tile-fanout", label="next"),
        lowering.EdgeSpec(source="tile-fanout", target="tile-prompts", label="next"),
        lowering.EdgeSpec(source="tile-prompts", target="foley-audio", label="next"),
        lowering.EdgeSpec(source="foley-audio", target="review", label="next"),
        lowering.EdgeSpec(source="review", target="spatial-page", label="next"),
        lowering.EdgeSpec(source="spatial-page", target="halt", label="next"),
    )
    lowered = lowering.LoweredSegment(
        entry_stage_id=_FOLEY_MAP_SPEC.entry_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=edge_specs,
        plan_hash="orchestrator:foley.foley_map@0.1",
        diagnostics=(
            "compiled wrapper-then-unroll orchestrator foley.foley_map",
            "fanout=tile_dynamic_fanout",
            "stages=7",
            "edges=6",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


def build_animate_image_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical Animate Image shape with explicit named phases."""
    from pathlib import Path

    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    resolved_run_root = Path(
        run_root or artifact_root or "/tmp/arnold-video-editing-animate-image-run"
    )
    active_state = dict(state or {})
    stage_specs: list[lowering.StageSpec] = []

    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="validate-inputs",
        label=_ANIMATE_IMAGE_SPEC.stage_labels["validate-inputs"],
        segment_id=ANIMATE_IMAGE_ID,
        path=(ANIMATE_IMAGE_ID, "validate-inputs"),
        runtime="command",
        adapter="orchestrator",
        command="validate",
        metadata={
            "wrapper_orchestrator_id": ANIMATE_IMAGE_ID,
            "wrapper_subcommand": "validate",
            "input_bindings": {
                "style_image": "$.style_image",
                "ref_video": "$.ref_video",
                "out": "$.out",
                "prompt": "$.prompt",
                "replace_prompt": "$.replace_prompt",
                "skip_generate": "$.skip_generate",
                "use_image": "$.use_image",
                "skip_animate": "$.skip_animate",
            },
            "scoped_configs": ["credentials.fal"],
            "runtime_flags": {
                "supports_dry_run": True,
                "preserves_scoped_credentials": True,
            },
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="prepare-source",
        label=_ANIMATE_IMAGE_SPEC.stage_labels["prepare-source"],
        segment_id=ANIMATE_IMAGE_ID,
        path=(ANIMATE_IMAGE_ID, "prepare-source"),
        runtime="command",
        adapter="orchestrator",
        command="prepare-source",
        metadata={
            "wrapper_orchestrator_id": ANIMATE_IMAGE_ID,
            "wrapper_subcommand": "prepare-source",
            "input_bindings": {
                "ref_video": "$.ref_video",
                "out": "$.out",
            },
            "produces": ["first_frame.png"],
            "video_probe_artifact": "plan.video_dimensions",
            "target_size_artifact": "plan.gpt_image_2_size",
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="plan-commands",
        label=_ANIMATE_IMAGE_SPEC.stage_labels["plan-commands"],
        segment_id=ANIMATE_IMAGE_ID,
        path=(ANIMATE_IMAGE_ID, "plan-commands"),
        runtime="command",
        adapter="orchestrator",
        command="plan",
        metadata={
            "wrapper_orchestrator_id": ANIMATE_IMAGE_ID,
            "wrapper_subcommand": "plan",
            "input_bindings": {
                "style_image": "$.style_image",
                "ref_video": "$.ref_video",
                "first_frame": "prepare-source.produces.first_frame",
                "prompt": "$.prompt",
                "replace_prompt": "$.replace_prompt",
                "quality": "$.quality",
                "output_format": "$.output_format",
                "resolution": "$.resolution",
                "num_inference_steps": "$.num_inference_steps",
                "guidance_scale": "$.guidance_scale",
                "shift": "$.shift",
                "video_quality": "$.video_quality",
                "use_turbo": "$.use_turbo",
                "seed": "$.seed",
                "skip_generate": "$.skip_generate",
                "use_image": "$.use_image",
                "skip_animate": "$.skip_animate",
                "dry_run": "$.dry_run",
            },
            "produces": ["plan.json"],
            "planned_command_artifacts": ["plan.json"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="edit-image",
        label=_ANIMATE_IMAGE_SPEC.stage_labels["edit-image"],
        segment_id=ANIMATE_IMAGE_ID,
        path=(ANIMATE_IMAGE_ID, "edit-image"),
        runtime="command",
        adapter="orchestrator",
        command="edit-image",
        metadata={
            "wrapper_orchestrator_id": ANIMATE_IMAGE_ID,
            "wrapper_subcommand": "edit-image",
            "input_bindings": {
                "first_frame": "prepare-source.produces.first_frame",
                "style_image": "$.style_image",
                "prompt": "plan-commands.produces.plan.prompt",
                "output_format": "$.output_format",
                "skip_generate": "$.skip_generate",
                "use_image": "$.use_image",
                "dry_run": "$.dry_run",
            },
            "external_model_id": ANIMATE_IMAGE_EDIT_MODEL_ID,
            "runtime_conditionals": [
                "copies $.use_image when $.skip_generate is true",
                "writes deterministic placeholder output when $.dry_run is true",
            ],
            "produces": ["generated.<output-format>"],
            "dry_run_outputs": ["generated.<output-format>"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="animate-video",
        label=_ANIMATE_IMAGE_SPEC.stage_labels["animate-video"],
        segment_id=ANIMATE_IMAGE_ID,
        path=(ANIMATE_IMAGE_ID, "animate-video"),
        runtime="command",
        adapter="orchestrator",
        command="animate-video",
        metadata={
            "wrapper_orchestrator_id": ANIMATE_IMAGE_ID,
            "wrapper_subcommand": "animate-video",
            "input_bindings": {
                "image": "edit-image.produces.generated_image",
                "ref_video": "$.ref_video",
                "resolution": "$.resolution",
                "num_inference_steps": "$.num_inference_steps",
                "guidance_scale": "$.guidance_scale",
                "shift": "$.shift",
                "video_quality": "$.video_quality",
                "use_turbo": "$.use_turbo",
                "seed": "$.seed",
                "skip_animate": "$.skip_animate",
                "dry_run": "$.dry_run",
            },
            "external_model_id": ANIMATE_IMAGE_ANIMATE_MODEL_ID,
            "runtime_conditionals": [
                "skipped when $.skip_animate is true",
                "records placeholder animation metadata when $.dry_run is true",
            ],
            "produces": ["animation.mp4"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="write-artifacts",
        label=_ANIMATE_IMAGE_SPEC.stage_labels["write-artifacts"],
        segment_id=ANIMATE_IMAGE_ID,
        path=(ANIMATE_IMAGE_ID, "write-artifacts"),
        runtime="command",
        adapter="orchestrator",
        command="write-artifacts",
        metadata={
            "wrapper_orchestrator_id": ANIMATE_IMAGE_ID,
            "wrapper_subcommand": "write-artifacts",
            "input_bindings": {
                "plan": "plan-commands.produces.plan",
                "generated_image": "edit-image.produces.generated_image",
                "animation": "animate-video.produces.animation",
            },
            "produces": ["manifest.json"],
            "planned_command_artifacts": ["plan.json"],
            "dry_run_outputs": [
                "first_frame.png",
                "generated.<output-format>",
                "manifest.json",
            ],
            "final_sidecars": [
                "first_frame.png",
                "generated.<output-format>",
                "animation.mp4",
                "manifest.json",
            ],
            "media_timeline_outputs": ["timelines/<timeline-id>/assembly.jsonl"],
            "ledger_outputs": ["events.jsonl"],
        },
    )
    stage_specs.append(lowering.halt_stage())

    edge_specs = (
        lowering.EdgeSpec(source="validate-inputs", target="prepare-source", label="next"),
        lowering.EdgeSpec(source="prepare-source", target="plan-commands", label="next"),
        lowering.EdgeSpec(source="plan-commands", target="edit-image", label="next"),
        lowering.EdgeSpec(source="edit-image", target="animate-video", label="next"),
        lowering.EdgeSpec(source="animate-video", target="write-artifacts", label="next"),
        lowering.EdgeSpec(source="write-artifacts", target="halt", label="next"),
    )
    lowered = lowering.LoweredSegment(
        entry_stage_id=_ANIMATE_IMAGE_SPEC.entry_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=edge_specs,
        plan_hash="orchestrator:video_editing.animate_image@1.0",
        diagnostics=(
            "compiled staged wrapper orchestrator video_editing.animate_image",
            "shape=linear_media_wrapper",
            "stages=7",
            "edges=6",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


def build_logo_ideas_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical Logo Ideas shape with staged prompt/render/finalize steps."""
    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    active_state = dict(state or {})
    stage_specs: list[lowering.StageSpec] = []

    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="normalize-brief",
        label=_LOGO_IDEAS_SPEC.stage_labels["normalize-brief"],
        segment_id=LOGO_IDEAS_ID,
        path=(LOGO_IDEAS_ID, "normalize-brief"),
        runtime="command",
        adapter="orchestrator",
        command="plan",
        metadata={
            "wrapper_orchestrator_id": LOGO_IDEAS_ID,
            "wrapper_subcommand": "plan",
            "input_bindings": {
                "ideas": "$.ideas",
                "count": "$.count",
                "provider": "$.provider",
                "model": "$.model",
                "image_size": "$.image_size",
                "output_format": "$.output_format",
                "out": "$.out",
                "dry_run": "$.dry_run",
            },
            "produces": ["logo-plan.json"],
            "planned_command_artifacts": ["logo-plan.json"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="draft-concepts",
        label=_LOGO_IDEAS_SPEC.stage_labels["draft-concepts"],
        segment_id=LOGO_IDEAS_ID,
        path=(LOGO_IDEAS_ID, "draft-concepts"),
        runtime="command",
        adapter="orchestrator",
        command="concepts",
        metadata={
            "wrapper_orchestrator_id": LOGO_IDEAS_ID,
            "wrapper_subcommand": "concepts",
            "input_bindings": {
                "ideas": "$.ideas",
                "count": "$.count",
                "model": "$.model",
                "dry_run": "$.dry_run",
            },
            "external_model_id": LOGO_IDEAS_FIREWORKS_MODEL_ID,
            "credential_env": ["FIREWORKS_API_KEY"],
            "produces": ["concepts.json", "prompts.json"],
            "runtime_flags": {
                "supports_dry_run": True,
                "writes_prompt_manifest": True,
            },
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="render-candidates",
        label=_LOGO_IDEAS_SPEC.stage_labels["render-candidates"],
        segment_id=LOGO_IDEAS_ID,
        path=(LOGO_IDEAS_ID, "render-candidates"),
        runtime="command",
        adapter="orchestrator",
        command="render",
        metadata={
            "wrapper_orchestrator_id": LOGO_IDEAS_ID,
            "wrapper_subcommand": "render",
            "input_bindings": {
                "provider": "$.provider",
                "image_size": "$.image_size",
                "output_format": "$.output_format",
                "prompts": "draft-concepts.produces.prompts",
                "dry_run": "$.dry_run",
            },
            "external_model_ids": {
                "gpt-image": LOGO_IDEAS_GRID_MODEL_ID,
                "z-image": LOGO_IDEAS_PER_IMAGE_MODEL_ID,
            },
            "credential_env": ["FAL_KEY"],
            "runtime_flags": {
                "supports_dry_run": True,
                "provider_branching": True,
            },
            "runtime_conditionals": [
                "provider=gpt-image performs a single grid render and mirrors that artifact across candidate records",
                "provider=z-image renders one image per concept and leaves contact-sheet assembly to the final stage",
                "dry_run writes deterministic placeholder image artifacts for whichever provider branch is selected",
            ],
            "candidate_artifacts": [
                "grid.<output-format>",
                "images/logo-<nnn>.<output-format>",
            ],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="write-artifacts",
        label=_LOGO_IDEAS_SPEC.stage_labels["write-artifacts"],
        segment_id=LOGO_IDEAS_ID,
        path=(LOGO_IDEAS_ID, "write-artifacts"),
        runtime="command",
        adapter="orchestrator",
        command="finalize",
        metadata={
            "wrapper_orchestrator_id": LOGO_IDEAS_ID,
            "wrapper_subcommand": "finalize",
            "input_bindings": {
                "plan": "normalize-brief.produces.logo_plan",
                "concepts": "draft-concepts.produces.concepts",
                "prompts": "draft-concepts.produces.prompts",
                "candidate_outputs": "render-candidates.produces.candidate_artifacts",
                "provider": "$.provider",
            },
            "produces": ["logo-manifest.json", ".astrid.variants.json"],
            "contact_sheet_outputs": [
                "grid.<output-format>",
                "grid.jpg",
            ],
            "final_sidecars": [
                "concepts.json",
                "prompts.json",
                "logo-manifest.json",
                ".astrid.variants.json",
            ],
            "ledger_outputs": ["events.jsonl"],
        },
    )
    stage_specs.append(lowering.halt_stage())

    edge_specs = (
        lowering.EdgeSpec(source="normalize-brief", target="draft-concepts", label="next"),
        lowering.EdgeSpec(source="draft-concepts", target="render-candidates", label="next"),
        lowering.EdgeSpec(source="render-candidates", target="write-artifacts", label="next"),
        lowering.EdgeSpec(source="write-artifacts", target="halt", label="next"),
    )
    lowered = lowering.LoweredSegment(
        entry_stage_id=_LOGO_IDEAS_SPEC.entry_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=edge_specs,
        plan_hash="orchestrator:video_editing.logo_ideas@1.0",
        diagnostics=(
            "compiled staged wrapper orchestrator video_editing.logo_ideas",
            "shape=prompt_render_finalize",
            "stages=5",
            "edges=4",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


def build_vary_grid_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical Vary Grid shape with selection and fanout exposed."""
    from pathlib import Path

    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    resolved_run_root = Path(
        run_root or artifact_root or "/tmp/arnold-video-editing-vary-grid-run"
    )
    active_state = dict(state or {})
    stage_specs: list[lowering.StageSpec] = []

    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="inspect-source",
        label=_VARY_GRID_SPEC.stage_labels["inspect-source"],
        segment_id=VARY_GRID_ID,
        path=(VARY_GRID_ID, "inspect-source"),
        runtime="command",
        adapter="orchestrator",
        command="inspect-source",
        metadata={
            "wrapper_orchestrator_id": VARY_GRID_ID,
            "wrapper_subcommand": "inspect-source",
            "input_bindings": {
                "from": "$.from_path",
                "source_rows": "$.source_rows",
                "source_cols": "$.source_cols",
                "cells": "$.cells",
                "out": "$.out",
            },
            "produces": ["vary-plan.json"],
            "planned_command_artifacts": ["vary-plan.json"],
            "runtime_flags": {
                "supports_dry_run": True,
                "detects_source_layout": True,
            },
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="slice-source-grid",
        label=_VARY_GRID_SPEC.stage_labels["slice-source-grid"],
        segment_id=VARY_GRID_ID,
        path=(VARY_GRID_ID, "slice-source-grid"),
        runtime="command",
        adapter="orchestrator",
        command="slice-source-grid",
        metadata={
            "wrapper_orchestrator_id": VARY_GRID_ID,
            "wrapper_subcommand": "slice-source-grid",
            "input_bindings": {
                "from": "$.from_path",
                "source_layout": "inspect-source.produces.source_layout",
            },
            "produces": ["source_cells/cell-<nnn>.png"],
            "source_grid_artifact": "$.from_path",
        },
    )
    stage_specs.append(
        lowering.lower_pattern_select(
            stage_id="select-prompt-pattern",
            label=_VARY_GRID_SPEC.stage_labels["select-prompt-pattern"],
            segment_id=VARY_GRID_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            pattern_names=("kimi_variations", "no_kimi_direct", "dry_run_placeholders"),
            metadata={
                "pattern_selector": {
                    "kimi_variations": "default when $.no_kimi is false and $.dry_run is false",
                    "no_kimi_direct": "selected when $.no_kimi is true",
                    "dry_run_placeholders": "selected when $.dry_run is true",
                },
                "branch_metadata": [
                    {
                        "branch_id": "kimi_variations",
                        "credential_env": ["FIREWORKS_API_KEY"],
                        "external_model_id": VARY_GRID_FIREWORKS_MODEL_ID,
                        "produces": ["concepts.json", "prompts.json"],
                    },
                    {
                        "branch_id": "no_kimi_direct",
                        "credential_env": [],
                        "produces": ["concepts.json", "prompts.json"],
                    },
                    {
                        "branch_id": "dry_run_placeholders",
                        "credential_env": [],
                        "produces": ["concepts.json", "prompts.json"],
                    },
                ],
                "input_bindings": {
                    "ideas": "$.ideas",
                    "count": "$.count",
                    "no_kimi": "$.no_kimi",
                    "dry_run": "$.dry_run",
                },
            },
        )
    )
    stage_specs.extend(
        lowering.lower_dynamic_fanout(
            stage_id="reference-fanout",
            label=_VARY_GRID_SPEC.stage_labels["reference-fanout"],
            segment_id=VARY_GRID_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            fanout_branches=(
                {
                    "branch_id": "selected-reference-cell",
                    "source_artifact": "source_cells/cell-<nnn>.png",
                    "selector": "$.cells",
                    "output_artifact": "refs/ref-<nnn>.png",
                },
            ),
            metadata={
                "fan_out_shape": True,
                "fanout_source_stage_id": "slice-source-grid",
                "fanout_source_artifact": "source_cells",
                "fanout_selector": "$.cells",
                "fanout_manifest_artifact": "refs/",
                "fanout_branch_count": "dynamic",
                "dynamic_branch_id": "selected-reference-cell",
                "input_bindings": {
                    "cells": "$.cells",
                    "source_cells": "slice-source-grid.produces.source_cells",
                },
            },
        )
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="draft-variations",
        label=_VARY_GRID_SPEC.stage_labels["draft-variations"],
        segment_id=VARY_GRID_ID,
        path=(VARY_GRID_ID, "draft-variations"),
        runtime="command",
        adapter="orchestrator",
        command="draft-variations",
        metadata={
            "wrapper_orchestrator_id": VARY_GRID_ID,
            "wrapper_subcommand": "draft-variations",
            "input_bindings": {
                "ideas": "$.ideas",
                "count": "$.count",
                "refs": "reference-fanout.produces.refs",
                "selected_pattern": "select-prompt-pattern.produces.pattern",
            },
            "selected_pattern_stage_id": "select-prompt-pattern",
            "external_model_id": VARY_GRID_FIREWORKS_MODEL_ID,
            "credential_env": ["FIREWORKS_API_KEY"],
            "runtime_conditionals": [
                "skips Fireworks when $.no_kimi is true",
                "writes deterministic planned concepts when $.dry_run is true",
            ],
            "produces": ["concepts.json", "prompts.json"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="render-grid",
        label=_VARY_GRID_SPEC.stage_labels["render-grid"],
        segment_id=VARY_GRID_ID,
        path=(VARY_GRID_ID, "render-grid"),
        runtime="command",
        adapter="orchestrator",
        command="render-grid",
        metadata={
            "wrapper_orchestrator_id": VARY_GRID_ID,
            "wrapper_subcommand": "render-grid",
            "input_bindings": {
                "refs": "reference-fanout.produces.refs",
                "prompt": "draft-variations.produces.grid_prompt",
                "size": "$.size",
                "quality": "$.quality",
                "output_format": "$.output_format",
                "dry_run": "$.dry_run",
            },
            "external_model_id": VARY_GRID_EDIT_MODEL_ID,
            "credential_env": ["FAL_KEY"],
            "runtime_conditionals": [
                "writes deterministic placeholder grid when $.dry_run is true",
            ],
            "produces": ["grid.<output-format>"],
            "dry_run_outputs": ["grid.<output-format>"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="write-artifacts",
        label=_VARY_GRID_SPEC.stage_labels["write-artifacts"],
        segment_id=VARY_GRID_ID,
        path=(VARY_GRID_ID, "write-artifacts"),
        runtime="command",
        adapter="orchestrator",
        command="write-artifacts",
        metadata={
            "wrapper_orchestrator_id": VARY_GRID_ID,
            "wrapper_subcommand": "write-artifacts",
            "input_bindings": {
                "plan": "inspect-source.produces.vary_plan",
                "refs": "reference-fanout.produces.refs",
                "concepts": "draft-variations.produces.concepts",
                "prompts": "draft-variations.produces.prompts",
                "grid": "render-grid.produces.grid",
                "favicon": "$.favicon",
            },
            "produces": ["vary-manifest.json"],
            "final_sidecars": [
                "vary-plan.json",
                "concepts.json",
                "prompts.json",
                "vary-manifest.json",
                "grid.<output-format>",
                "favicons.png",
            ],
            "ledger_outputs": ["events.jsonl"],
        },
    )
    stage_specs.append(lowering.halt_stage())

    edge_specs = (
        lowering.EdgeSpec(source="inspect-source", target="slice-source-grid", label="next"),
        lowering.EdgeSpec(source="slice-source-grid", target="select-prompt-pattern", label="next"),
        lowering.EdgeSpec(source="select-prompt-pattern", target="reference-fanout", label="next"),
        lowering.EdgeSpec(source="reference-fanout", target="draft-variations", label="next"),
        lowering.EdgeSpec(source="draft-variations", target="render-grid", label="next"),
        lowering.EdgeSpec(source="render-grid", target="write-artifacts", label="next"),
        lowering.EdgeSpec(source="write-artifacts", target="halt", label="next"),
    )
    lowered = lowering.LoweredSegment(
        entry_stage_id=_VARY_GRID_SPEC.entry_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=edge_specs,
        plan_hash="orchestrator:video_editing.vary_grid@1.0",
        diagnostics=(
            "compiled staged wrapper orchestrator video_editing.vary_grid",
            "pattern_select=prompt_strategy",
            "fanout=selected_reference_cells",
            "stages=8",
            "edges=7",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


def build_iteration_video_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical Iteration Video shape with explicit finalization."""
    from pathlib import Path

    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    resolved_run_root = Path(
        run_root or artifact_root or "/tmp/arnold-video-editing-iteration-video-run"
    )
    active_state = dict(state or {})
    stage_specs: list[lowering.StageSpec] = []

    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="resolve-thread",
        label=_ITERATION_VIDEO_SPEC.stage_labels["resolve-thread"],
        segment_id=ITERATION_VIDEO_ID,
        path=(ITERATION_VIDEO_ID, "resolve-thread"),
        runtime="python",
        adapter="orchestrator",
        command="resolve_target_run_id",
        metadata={
            "wrapper_orchestrator_id": ITERATION_VIDEO_ID,
            "wrapper_subcommand": "resolve-target-run-id",
            "input_bindings": {
                "thread": "$.thread",
                "target_run_id": "$.target_run_id",
                "repo_root": "$.repo_root",
            },
            "produces": ["target.json"],
            "runtime_flags": {
                "supports_active_thread_ref": True,
                "validates_ulid_thread": True,
            },
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="prepare-iteration",
        label=_ITERATION_VIDEO_SPEC.stage_labels["prepare-iteration"],
        segment_id=ITERATION_VIDEO_ID,
        path=(ITERATION_VIDEO_ID, "prepare-iteration"),
        runtime="python",
        adapter="executor",
        command="iteration.prepare",
        metadata={
            "wrapper_orchestrator_id": ITERATION_VIDEO_ID,
            "executor_id": "iteration.prepare",
            "input_bindings": {
                "target_run_id": "resolve-thread.produces.target_run_id",
                "max_iterations": "$.max_iterations",
                "repo_root": "$.repo_root",
            },
            "produces": [
                ".<out>.prepare/iteration.manifest.json",
                ".<out>.prepare/iteration.quality.json",
            ],
            "cache_model_id": ITERATION_VIDEO_SUMMARIZER_MODEL_ID,
        },
    )
    stage_specs.append(
        lowering.lower_pattern_select(
            stage_id="select-renderers",
            label=_ITERATION_VIDEO_SPEC.stage_labels["select-renderers"],
            segment_id=ITERATION_VIDEO_ID,
            project=project or "default",
            run_root_path=resolved_run_root,
            state=active_state,
            pattern_names=("image_grid", "audio_waveform", "generic_card"),
            metadata={
                "pattern_selector": {
                    "image_grid": "selected for image artifacts",
                    "audio_waveform": "selected for audio artifacts",
                    "generic_card": "fallback for unsupported artifact modalities",
                },
                "input_bindings": {
                    "manifest": "prepare-iteration.produces.iteration_manifest",
                    "renderers": "$.renderers",
                },
                "branch_metadata": [
                    {
                        "branch_id": "image_grid",
                        "artifact_kind": "image",
                        "renderer": "image_grid",
                    },
                    {
                        "branch_id": "audio_waveform",
                        "artifact_kind": "audio",
                        "renderer": "audio_waveform",
                    },
                    {
                        "branch_id": "generic_card",
                        "artifact_kind": "fallback",
                        "renderer": "generic_card",
                    },
                ],
            },
        )
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="assemble-brief",
        label=_ITERATION_VIDEO_SPEC.stage_labels["assemble-brief"],
        segment_id=ITERATION_VIDEO_ID,
        path=(ITERATION_VIDEO_ID, "assemble-brief"),
        runtime="python",
        adapter="executor",
        command="iteration.assemble",
        metadata={
            "wrapper_orchestrator_id": ITERATION_VIDEO_ID,
            "executor_id": "iteration.assemble",
            "input_bindings": {
                "prepare_dir": "prepare-iteration.produces.prepare_dir",
                "selected_renderers": "select-renderers.produces.patterns",
                "direction": "$.direction",
                "mode": "$.mode",
                "audio_bed": "$.audio_bed",
                "force": "$.force",
            },
            "produces": [
                "hype.timeline.json",
                "hype.assets.json",
                "iteration.timeline.json",
                "iteration.manifest.json",
                "iteration.report.html",
                "iteration.quality.json",
            ],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="render-video",
        label=_ITERATION_VIDEO_SPEC.stage_labels["render-video"],
        segment_id=ITERATION_VIDEO_ID,
        path=(ITERATION_VIDEO_ID, "render-video"),
        runtime="python",
        adapter="executor",
        command="rendering.render",
        metadata={
            "wrapper_orchestrator_id": ITERATION_VIDEO_ID,
            "executor_id": "rendering.render",
            "input_bindings": {
                "timeline": "assemble-brief.produces.hype.timeline.json",
                "assets": "assemble-brief.produces.hype.assets.json",
                "out": "hype.mp4",
            },
            "produces": ["hype.mp4"],
        },
    )
    lowering.add_wrapper_stage(
        stage_specs,
        stage_id="finalize-iteration",
        label=_ITERATION_VIDEO_SPEC.stage_labels["finalize-iteration"],
        segment_id=ITERATION_VIDEO_ID,
        path=(ITERATION_VIDEO_ID, "finalize-iteration"),
        runtime="python",
        adapter="orchestrator",
        command="finalize-iteration",
        metadata={
            "wrapper_orchestrator_id": ITERATION_VIDEO_ID,
            "wrapper_subcommand": "finalize-iteration",
            "input_bindings": {
                "rendered_video": "render-video.produces.hype.mp4",
                "thread_id": "resolve-thread.produces.thread_id",
                "target_run_id": "resolve-thread.produces.target_run_id",
                "manifest": "assemble-brief.produces.iteration.manifest.json",
                "quality": "assemble-brief.produces.iteration.quality.json",
                "report": "assemble-brief.produces.iteration.report.html",
                "timeline": "assemble-brief.produces.iteration.timeline.json",
            },
            "produces": [
                "iteration.mp4",
                "iteration.timeline.json",
                "iteration.manifest.json",
                "iteration.report.html",
                "iteration.quality.json",
                ".astrid.variants.json",
                ".astrid/threads/<thread-id>/groups.json",
            ],
            "final_media_outputs": ["iteration.mp4"],
            "final_report_outputs": ["iteration.report.html"],
            "final_quality_outputs": ["iteration.quality.json"],
            "final_manifest_outputs": ["iteration.manifest.json"],
            "final_thread_group_outputs": [
                ".astrid.variants.json",
                ".astrid/threads/<thread-id>/groups.json",
            ],
            "final_sidecars": [
                "iteration.timeline.json",
                "iteration.manifest.json",
                "iteration.report.html",
                "iteration.quality.json",
                ".astrid.variants.json",
                ".astrid/threads/<thread-id>/groups.json",
            ],
            "ledger_outputs": ["events.jsonl"],
        },
    )
    stage_specs.append(lowering.halt_stage())

    edge_specs = (
        lowering.EdgeSpec(source="resolve-thread", target="prepare-iteration", label="next"),
        lowering.EdgeSpec(source="prepare-iteration", target="select-renderers", label="next"),
        lowering.EdgeSpec(source="select-renderers", target="assemble-brief", label="next"),
        lowering.EdgeSpec(source="assemble-brief", target="render-video", label="next"),
        lowering.EdgeSpec(source="render-video", target="finalize-iteration", label="next"),
        lowering.EdgeSpec(source="finalize-iteration", target="halt", label="next"),
    )
    lowered = lowering.LoweredSegment(
        entry_stage_id=_ITERATION_VIDEO_SPEC.entry_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=edge_specs,
        plan_hash="orchestrator:video_editing.iteration_video@1.0",
        diagnostics=(
            "compiled staged wrapper orchestrator video_editing.iteration_video",
            "pattern_select=renderer_strategy",
            "finalization=explicit",
            "stages=7",
            "edges=6",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


SHAPE_DEFINITIONS: tuple[ShapeEntry, ...] = (
    ShapeEntry(
        workflow_id=WE_REFINE_IMAGE_ID,
        description=(
            "WE-1: Single-generation refinement workflow. Generates an image, "
            "presents it for human review, and re-enters generation on reject."
        ),
        cli_alias=WE_REFINE_IMAGE_ALIAS,
        accepts_human_input=True,
        metadata={
            "kind": "generation",
            "max_iterations": 10,
            "judge_required": False,
            "parallel_fan_out": 1,
        },
        entry_stage_id=_WE_REFINE_IMAGE_SPEC.entry_stage_id,
        stage_labels=dict(_WE_REFINE_IMAGE_SPEC.stage_labels),
        pipeline_builder=build_refine_image_pipeline,
    ),
    ShapeEntry(
        workflow_id=WE_BEST_OF_4_ID,
        description=(
            "WE-3: Four-way parallel fan-out generation workflow. Runs 4 "
            "independent image generations in parallel, lowers a judge to "
            "select the best output, and gates the finalist for human review."
        ),
        cli_alias=WE_BEST_OF_4_ALIAS,
        accepts_human_input=True,
        metadata={
            "kind": "generation",
            "parallel_fan_out": 4,
            "judge_required": True,
            "max_iterations": 3,
        },
        entry_stage_id=_WE_BEST_OF_4_SPEC.entry_stage_id,
        stage_labels=dict(_WE_BEST_OF_4_SPEC.stage_labels),
        pipeline_builder=build_best_of_4_pipeline,
    ),
    ShapeEntry(
        workflow_id=TEXT_ANALYSIS_SUMMARIZE_ID,
        description=(
            "DSL-compiled 3-stage text analysis pipeline: reads input, "
            "writes a summary, and emits a verdict — all auto-compiled "
            "from the canonical orchestrator DSL definition."
        ),
        cli_alias=TEXT_ANALYSIS_SUMMARIZE_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "analysis",
            "parallel_fan_out": 1,
            "judge_required": False,
            "compiled": True,
        },
        entry_stage_id=_TEXT_ANALYSIS_SUMMARIZE_SPEC.entry_stage_id,
        stage_labels=dict(_TEXT_ANALYSIS_SUMMARIZE_SPEC.stage_labels),
        pipeline_builder=build_text_analysis_summarize_pipeline,
    ),
    ShapeEntry(
        workflow_id=BUILTIN_AGENT_PROBE_ID,
        description=(
            "DSL-compiled repeat-for-each probe pipeline: runs the per_item "
            "attested step across [alpha, beta, gamma] with fan_out_shape "
            "repeat_for_each metadata — all auto-compiled from the "
            "canonical orchestrator DSL definition."
        ),
        cli_alias=BUILTIN_AGENT_PROBE_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "probe",
            "parallel_fan_out": 3,
            "judge_required": False,
            "compiled": True,
        },
        entry_stage_id=_BUILTIN_AGENT_PROBE_SPEC.entry_stage_id,
        stage_labels=dict(_BUILTIN_AGENT_PROBE_SPEC.stage_labels),
        pipeline_builder=build_builtin_agent_probe_pipeline,
    ),
    ShapeEntry(
        workflow_id=STREAM_CONTENT_DISTILL_ID,
        description=(
            "Canonical distill pipeline with explicit executor-backed ingest "
            "stages and a documented wrapper-then-unroll extraction stage for "
            "per-segment media.clip_extract fanout before candidate scoring "
            "and review finalization."
        ),
        cli_alias=STREAM_CONTENT_DISTILL_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "stream_content",
            "parallel_fan_out": "dynamic",
            "judge_required": False,
            "compiled": True,
            "loop_lowering": "wrapper_then_unroll",
        },
        entry_stage_id=_STREAM_CONTENT_DISTILL_SPEC.entry_stage_id,
        stage_labels=dict(_STREAM_CONTENT_DISTILL_SPEC.stage_labels),
        pipeline_builder=build_stream_content_distill_pipeline,
    ),
    ShapeEntry(
        workflow_id=FOLEY_MAP_ID,
        description=(
            "Canonical Foley Map pipeline with explicit tile fanout, bounded "
            "parallel VLM/Foley wrapper stages, and executor-backed review "
            "plus spatial page finalization."
        ),
        cli_alias=FOLEY_MAP_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "foley",
            "parallel_fan_out": "dynamic",
            "judge_required": False,
            "compiled": True,
            "loop_lowering": "wrapper_then_unroll",
        },
        entry_stage_id=_FOLEY_MAP_SPEC.entry_stage_id,
        stage_labels=dict(_FOLEY_MAP_SPEC.stage_labels),
        pipeline_builder=build_foley_map_pipeline,
    ),
    ShapeEntry(
        workflow_id=ANIMATE_IMAGE_ID,
        description=(
            "Canonical Animate Image pipeline with explicit validation, "
            "first-frame preparation, plan write, GPT Image edit, WAN animate, "
            "and final artifact/ledger write stages."
        ),
        cli_alias=ANIMATE_IMAGE_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "video_editing",
            "parallel_fan_out": 1,
            "judge_required": False,
            "compiled": True,
            "loop_lowering": "staged_wrapper",
            "scoped_configs": ["credentials.fal"],
        },
        entry_stage_id=_ANIMATE_IMAGE_SPEC.entry_stage_id,
        stage_labels=dict(_ANIMATE_IMAGE_SPEC.stage_labels),
        pipeline_builder=build_animate_image_pipeline,
    ),
    ShapeEntry(
        workflow_id=LOGO_IDEAS_ID,
        description=(
            "Canonical Logo Ideas pipeline with explicit brief normalization, "
            "Fireworks concept drafting, provider-conditional candidate render, "
            "and final manifest/contact-sheet/variant-sidecar writes."
        ),
        cli_alias=LOGO_IDEAS_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "video_editing",
            "parallel_fan_out": 1,
            "judge_required": False,
            "compiled": True,
            "loop_lowering": "staged_wrapper",
            "scoped_configs": ["credentials.fal"],
            "credential_env": ["FIREWORKS_API_KEY", "FAL_KEY"],
        },
        entry_stage_id=_LOGO_IDEAS_SPEC.entry_stage_id,
        stage_labels=dict(_LOGO_IDEAS_SPEC.stage_labels),
        pipeline_builder=build_logo_ideas_pipeline,
    ),
    ShapeEntry(
        workflow_id=VARY_GRID_ID,
        description=(
            "Canonical Vary Grid pipeline with explicit source inspection, "
            "reference-cell dynamic fanout, prompt-pattern selection, fal edit "
            "render, and final manifest/grid sidecar writes."
        ),
        cli_alias=VARY_GRID_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "video_editing",
            "parallel_fan_out": "dynamic",
            "judge_required": False,
            "compiled": True,
            "loop_lowering": "pattern_select_dynamic_fanout",
            "scoped_configs": ["credentials.fal"],
            "credential_env": ["FIREWORKS_API_KEY", "FAL_KEY"],
        },
        entry_stage_id=_VARY_GRID_SPEC.entry_stage_id,
        stage_labels=dict(_VARY_GRID_SPEC.stage_labels),
        pipeline_builder=build_vary_grid_pipeline,
    ),
    ShapeEntry(
        workflow_id=ITERATION_VIDEO_ID,
        description=(
            "Canonical Iteration Video pipeline with explicit thread resolution, "
            "prepare/renderer-selection/assembly/render stages, and final media, "
            "report, quality, manifest, variant-sidecar, and thread-group writes."
        ),
        cli_alias=ITERATION_VIDEO_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "video_editing",
            "parallel_fan_out": 1,
            "judge_required": False,
            "compiled": True,
            "loop_lowering": "pattern_select_explicit_finalization",
            "child_executors": ["iteration.prepare", "iteration.assemble", "rendering.render"],
        },
        entry_stage_id=_ITERATION_VIDEO_SPEC.entry_stage_id,
        stage_labels=dict(_ITERATION_VIDEO_SPEC.stage_labels),
        pipeline_builder=build_iteration_video_pipeline,
    ),
)

ALLOWLISTED_SHAPE_IDS: frozenset[str] = frozenset(
    entry.workflow_id for entry in SHAPE_DEFINITIONS
)
