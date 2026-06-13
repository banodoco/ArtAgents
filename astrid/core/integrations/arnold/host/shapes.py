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

WE_REFINE_IMAGE_ALIAS: str = "refine"
WE_BEST_OF_4_ALIAS: str = "best4"
TEXT_ANALYSIS_SUMMARIZE_ALIAS: str = "summarize"


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
    entry_stage_id="summarize",
    stage_labels={
        "summarize": "Summarize",
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
    from astrid.core.integrations.arnold.host.compat import compat

    builder = compat.PipelineBuilder()
    generate_stage = _build_stage(
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
    review_stage = _build_stage(
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
    halt_stage = _build_stage(
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
        _builder_add_stage(builder, stage)

    for edge in (
        _build_edge(
            compat.Edge,
            source="generate",
            target="review",
            label="next",
        ),
        _build_edge(
            compat.Edge,
            source="review",
            target="halt",
            label="approve",
        ),
        _build_edge(
            compat.Edge,
            source="review",
            target="generate",
            label="reject",
        ),
    ):
        _builder_add_edge(builder, edge)

    _builder_set_entry_stage(builder, _WE_REFINE_IMAGE_SPEC.entry_stage_id)
    return _builder_finalize(builder)


def build_best_of_4_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the frozen WE-3 graph: generate(4×) -> judge -> review -> {halt|generate}."""
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
        sub_stage = _build_stage(
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

    generate_stage = _build_parallel_stage(
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

    judge_stage = _build_stage(
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

    review_stage = _build_stage(
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

    halt_stage = _build_stage(
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
        _builder_add_stage(builder, stage)

    for edge in (
        _build_edge(
            compat.Edge,
            source="generate",
            target="judge",
            label="next",
        ),
        _build_edge(
            compat.Edge,
            source="judge",
            target="review",
            label="next",
        ),
        _build_edge(
            compat.Edge,
            source="review",
            target="halt",
            label="approve",
        ),
        _build_edge(
            compat.Edge,
            source="review",
            target="generate",
            label="reject",
        ),
    ):
        _builder_add_edge(builder, edge)

    _builder_set_entry_stage(builder, _WE_BEST_OF_4_SPEC.entry_stage_id)
    return _builder_finalize(builder)


def build_text_analysis_summarize_pipeline(
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the frozen text_analysis.summarize graph: summarize -> halt.

    This is a linear control shape.  Every leaf must be an executor-backed
    stage listed in ALLOWLISTED_INVOCATION_TEMPLATES; construction fails
    with UnsupportedStepError before any state mutation otherwise.
    """
    # ── validate every leaf before touching builder state ──────────────
    _validate_leaves_executor_backed(
        "summarize",
        workflow_id=TEXT_ANALYSIS_SUMMARIZE_ID,
    )

    from astrid.core.integrations.arnold.host.compat import compat

    builder = compat.PipelineBuilder()

    summarize_stage = _build_stage(
        compat.Stage,
        stage_id="summarize",
        label=_TEXT_ANALYSIS_SUMMARIZE_SPEC.stage_labels["summarize"],
        invocation=build_workflow_step_invocation(
            TEXT_ANALYSIS_SUMMARIZE_ID,
            "summarize",
            state=state,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
        ),
        metadata={
            "workflow_id": TEXT_ANALYSIS_SUMMARIZE_ID,
            "stage_id": "summarize",
            "entry": True,
            "linear": True,
        },
    )

    halt_stage = _build_stage(
        compat.Stage,
        stage_id="halt",
        label=_TEXT_ANALYSIS_SUMMARIZE_SPEC.stage_labels["halt"],
        metadata={
            "workflow_id": TEXT_ANALYSIS_SUMMARIZE_ID,
            "stage_id": "halt",
            "terminal": True,
        },
    )

    for stage in (summarize_stage, halt_stage):
        _builder_add_stage(builder, stage)

    for edge in (
        _build_edge(
            compat.Edge,
            source="summarize",
            target="halt",
            label="next",
        ),
    ):
        _builder_add_edge(builder, edge)

    _builder_set_entry_stage(builder, _TEXT_ANALYSIS_SUMMARIZE_SPEC.entry_stage_id)
    return _builder_finalize(builder)


def _build_parallel_stage(
    parallel_stage_type: type[Any],
    *,
    stage_id: str,
    label: str,
    sub_stages: list[Any],
    metadata: dict[str, Any] | None = None,
) -> Any:
    kwargs_meta = dict(metadata or {})
    for candidate in (
        {
            "stage_id": stage_id,
            "label": label,
            "stages": list(sub_stages),
            "metadata": kwargs_meta,
        },
        {
            "id": stage_id,
            "label": label,
            "stages": list(sub_stages),
            "metadata": kwargs_meta,
        },
        {
            "name": stage_id,
            "label": label,
            "stages": list(sub_stages),
            "metadata": kwargs_meta,
        },
        {
            "stage_id": stage_id,
            "label": label,
            "sub_stages": list(sub_stages),
            "metadata": kwargs_meta,
        },
        {
            "stage_id": stage_id,
            "label": label,
            "children": list(sub_stages),
            "metadata": kwargs_meta,
        },
    ):
        try:
            return parallel_stage_type(**candidate)
        except TypeError:
            continue
    raise TypeError(
        f"could not construct ParallelStage for {stage_id!r}"
    )


def _build_stage(
    stage_type: type[Any],
    *,
    stage_id: str,
    label: str,
    invocation: Any | None = None,
    suspension: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    kwargs = {
        "stage_id": stage_id,
        "label": label,
        "invocation": invocation,
        "suspension": suspension,
        "metadata": dict(metadata or {}),
    }
    for candidate in (
        kwargs,
        {
            "id": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": dict(metadata or {}),
        },
        {
            "name": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": dict(metadata or {}),
        },
    ):
        try:
            return stage_type(**candidate)
        except TypeError:
            continue
    raise TypeError(f"could not construct Stage for {stage_id!r}")


def _build_edge(
    edge_type: type[Any],
    *,
    source: str,
    target: str,
    label: str,
) -> Any:
    for candidate in (
        {"source": source, "target": target, "label": label},
        {"from_stage": source, "to_stage": target, "label": label},
        {"source_id": source, "target_id": target, "label": label},
    ):
        try:
            return edge_type(**candidate)
        except TypeError:
            continue
    raise TypeError(f"could not construct Edge {source!r}->{target!r}")


def _builder_add_stage(builder: Any, stage: Any) -> None:
    for name in ("add_stage", "stage", "with_stage", "register_stage"):
        method = getattr(builder, name, None)
        if callable(method):
            method(stage)
            return
    stages = getattr(builder, "stages", None)
    if isinstance(stages, list):
        stages.append(stage)
        return
    raise TypeError("PipelineBuilder does not support stage registration")


def _builder_add_edge(builder: Any, edge: Any) -> None:
    for name in ("add_edge", "edge", "with_edge", "register_edge"):
        method = getattr(builder, name, None)
        if callable(method):
            method(edge)
            return
    edges = getattr(builder, "edges", None)
    if isinstance(edges, list):
        edges.append(edge)
        return
    raise TypeError("PipelineBuilder does not support edge registration")


def _builder_set_entry_stage(builder: Any, stage_id: str) -> None:
    for name in ("set_entry_stage", "entry_stage", "set_entrypoint"):
        method = getattr(builder, name, None)
        if callable(method):
            method(stage_id)
            return
    if hasattr(builder, "entry_stage_id"):
        builder.entry_stage_id = stage_id
        return
    raise TypeError("PipelineBuilder does not support entry-stage selection")


def _builder_finalize(builder: Any) -> Any:
    build = getattr(builder, "build", None)
    if callable(build):
        return build()
    return builder


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
            "Simple text analysis shape for demonstration. Summarizes input "
            "text and presents the result."
        ),
        cli_alias=TEXT_ANALYSIS_SUMMARIZE_ALIAS,
        accepts_human_input=False,
        metadata={
            "kind": "analysis",
            "parallel_fan_out": 1,
            "judge_required": False,
        },
        entry_stage_id=_TEXT_ANALYSIS_SUMMARIZE_SPEC.entry_stage_id,
        stage_labels=dict(_TEXT_ANALYSIS_SUMMARIZE_SPEC.stage_labels),
        pipeline_builder=build_text_analysis_summarize_pipeline,
    ),
)

ALLOWLISTED_SHAPE_IDS: frozenset[str] = frozenset(
    entry.workflow_id for entry in SHAPE_DEFINITIONS
)

