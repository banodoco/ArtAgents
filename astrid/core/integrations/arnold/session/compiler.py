"""Compile TaskPlan segments into Arnold pipelines for session succession."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from astrid.core.integrations.arnold.host.invocation import (
    HUMAN_RESUME_INPUT_SCHEMA,
    build_adapter_metadata,
    build_step_invocation,
)
from astrid.core.task.events import canonical_event_json
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    RepeatUntil,
    Step,
    TaskPlan,
    iter_steps_with_path,
    parse_repeat_produces_ref,
    resolve_produces_ref,
)


TASK_ADAPTER_EXECUTOR_PREFIX = "task."
GROUP_ENTRY_SUFFIX = "__enter__"
GROUP_EXIT_SUFFIX = "__exit__"
HALT_STAGE_ID = "halt"


class CompileUnsupportedFeature(RuntimeError):
    """Raised when the compiler sees a plan feature not supported yet."""


@dataclass(frozen=True)
class CompileResult:
    """Opaque compiled pipeline plus the stable metadata derived from it."""

    pipeline: Any
    pipeline_manifest: dict[str, Any]
    plan_hash: str
    entry_stage_id: str
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _StageSpec:
    stage_id: str
    label: str
    invocation: Any | None
    suspension: Any | None
    metadata: dict[str, Any]
    decision_vocabulary: tuple[str, ...] = ()
    loop_condition: Callable[[Any], bool] | None = None


@dataclass(frozen=True)
class _EdgeSpec:
    source: str
    target: str
    label: str


@dataclass(frozen=True)
class _CompiledNode:
    entry_stage_id: str
    exit_stage_id: str
    stages: tuple[_StageSpec, ...]
    edges: tuple[_EdgeSpec, ...]
    continue_labels: tuple[str, ...]


def _plan_hash(plan: TaskPlan) -> str:
    import hashlib

    payload = canonical_event_json(plan.to_dict()).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _stage_id_for_path(path: tuple[str, ...]) -> str:
    return STEP_PATH_SEP.join(path)


def _group_boundary_stage_id(path: tuple[str, ...], suffix: str) -> str:
    return f"{_stage_id_for_path(path)}/{suffix}"


def _produces_metadata(step: Step) -> list[dict[str, Any]]:
    return [
        {
            "name": entry.name,
            "path": entry.path,
            "check": {
                "check_id": entry.check.check_id,
                "params": dict(entry.check.params),
                "sentinel": entry.check.sentinel,
            },
            "checksum": entry.checksum,
        }
        for entry in step.produces
    ]


def _supersede_metadata(step: Step) -> dict[str, Any] | None:
    if step.superseded_by is None:
        return None
    return {
        "to_version": step.superseded_by.to_version,
        "scope": step.superseded_by.scope,
    }


def _task_executor_id(step: Step) -> str:
    return f"{TASK_ADAPTER_EXECUTOR_PREFIX}{step.adapter}"


def _build_stage_metadata(
    *,
    step: Step,
    stage_id: str,
    segment_id: str,
    path: tuple[str, ...],
    adapter_config: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "segment_id": segment_id,
        "stage_id": stage_id,
        "plan_step_id": step.id,
        "plan_step_path": list(path),
        "source_plan_path": list(path),
        "step_version": step.version,
        "adapter": step.adapter,
        "manual": step.adapter == "manual",
        "requires_ack": step.requires_ack,
        "command": step.command,
        "produces": _produces_metadata(step),
        "adapter_config": dict(adapter_config),
    }
    superseded_by = _supersede_metadata(step)
    if superseded_by is not None:
        metadata["superseded_by"] = superseded_by
    if step.instructions:
        metadata["instructions"] = step.instructions
    if step.optional:
        metadata["optional"] = True
        metadata["decision_vocabulary"] = ["proceed", "skip"]
    return metadata


def _pipeline_manifest(pipeline: Any) -> dict[str, Any]:
    stages = []
    for stage in tuple(getattr(pipeline, "stages", ()) or ()):
        item = {
            "stage_id": getattr(stage, "stage_id", None),
            "label": getattr(stage, "label", None),
            "metadata": dict(getattr(stage, "metadata", {}) or {}),
        }
        decision_vocabulary = getattr(stage, "decision_vocabulary", None)
        if decision_vocabulary:
            item["decision_vocabulary"] = list(decision_vocabulary)
        if getattr(stage, "loop_condition", None) is not None:
            item["has_loop_condition"] = True
        stages.append(item)
    edges = []
    for edge in tuple(getattr(pipeline, "edges", ()) or ()):
        edges.append(
            {
                "source": getattr(edge, "source", None),
                "target": getattr(edge, "target", None),
                "label": getattr(edge, "label", None),
            }
        )
    return {
        "entry_stage_id": getattr(pipeline, "entry_stage_id", None),
        "stages": stages,
        "edges": edges,
    }


def _has_shape_field(shape_type: type[Any], field_name: str) -> bool:
    dataclass_fields = getattr(shape_type, "__dataclass_fields__", {})
    if field_name in dataclass_fields:
        return True
    annotations = getattr(shape_type, "__annotations__", {})
    if field_name in annotations:
        return True
    return hasattr(shape_type, field_name)


def _supports_repeat_until(stage_type: type[Any]) -> bool:
    return _has_shape_field(stage_type, "loop_condition")


def _resolved_re_export_metadata(
    plan: TaskPlan,
    *,
    step: Step,
    path: tuple[str, ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for export_name, export_ref in step.re_export or ():
        resolved = resolve_produces_ref(
            plan,
            parse_repeat_produces_ref(export_ref),
            base_path=path,
        )
        entries.append(
            {
                "export_name": export_name,
                "export_ref": export_ref,
                "source_plan_path": list(resolved.step_path),
                "source_step_id": resolved.step.id,
                "produces": {
                    "name": resolved.produces.name,
                    "path": resolved.produces.path,
                    "check": {
                        "check_id": resolved.produces.check.check_id,
                        "params": dict(resolved.produces.check.params),
                        "sentinel": resolved.produces.check.sentinel,
                    },
                    "checksum": resolved.produces.checksum,
                },
                "json_path": list(resolved.json_path),
            }
        )
    return entries


def _group_boundary_stage(
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    path: tuple[str, ...],
    step: Step,
    boundary: str,
    re_exports: list[dict[str, Any]] | None = None,
    decision_vocabulary: tuple[str, ...] = (),
) -> _StageSpec:
    metadata: dict[str, Any] = {
        "segment_id": segment_id,
        "stage_id": stage_id,
        "plan_step_id": step.id,
        "plan_step_path": list(path),
        "source_plan_path": list(path),
        "step_version": step.version,
        "adapter": step.adapter,
        "group_boundary": boundary,
    }
    superseded_by = _supersede_metadata(step)
    if superseded_by is not None:
        metadata["superseded_by"] = superseded_by
    if step.optional and boundary == "entry":
        metadata["optional"] = True
        metadata["decision_vocabulary"] = ["proceed", "skip"]
    if re_exports:
        metadata["re_exports"] = re_exports
    return _StageSpec(
        stage_id=stage_id,
        label=label,
        invocation=None,
        suspension=None,
        metadata=metadata,
        decision_vocabulary=decision_vocabulary,
    )


def _halt_stage() -> _StageSpec:
    return _StageSpec(
        stage_id=HALT_STAGE_ID,
        label="Halt",
        invocation=None,
        suspension=None,
        metadata={"stage_id": HALT_STAGE_ID, "terminal": True},
    )


def _leaf_stage_spec(
    *,
    step: Step,
    stage_id: str,
    segment_id: str,
    path: tuple[str, ...],
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    compat: Any,
) -> _StageSpec:
    adapter_config = build_adapter_metadata(
        executor_id=_task_executor_id(step),
        input_map={},
        inputs={},
        state=state,
        mode="inline",
        project=project,
        run_root=str(run_root_path),
        artifact_root=str(run_root_path),
        requires_ack=step.requires_ack,
        adapter=step.adapter,
        command=step.command,
        produces=_produces_metadata(step),
        step_version=step.version,
        superseded_by=_supersede_metadata(step),
        manual=step.adapter == "manual",
        source_plan_path=list(path),
        segment_id=segment_id,
    )
    invocation = build_step_invocation(
        executor_id=_task_executor_id(step),
        input_map={},
        inputs={},
        state=state,
        mode="inline",
        project=project,
        run_root=str(run_root_path),
        artifact_root=str(run_root_path),
        requires_ack=step.requires_ack,
        adapter=step.adapter,
        command=step.command,
        produces=_produces_metadata(step),
        step_version=step.version,
        superseded_by=_supersede_metadata(step),
        manual=step.adapter == "manual",
        source_plan_path=list(path),
        segment_id=segment_id,
    )
    suspension = None
    if step.adapter == "manual":
        suspension = compat.Suspension(resume_input_schema=HUMAN_RESUME_INPUT_SCHEMA)
    return _StageSpec(
        stage_id=stage_id,
        label=step.id,
        invocation=invocation,
        suspension=suspension,
        metadata=_build_stage_metadata(
            step=step,
            stage_id=stage_id,
            segment_id=segment_id,
            path=path,
            adapter_config=adapter_config,
        ),
        decision_vocabulary=("proceed", "skip") if step.optional else (),
    )


def _preflight_step_support(
    plan: TaskPlan,
    step: Step,
    *,
    path: tuple[str, ...],
    stage_type: type[Any],
) -> None:
    path_str = STEP_PATH_SEP.join(path)
    if isinstance(step.repeat, RepeatForEach):
        raise CompileUnsupportedFeature(
            f"repeat.for_each is not supported in frozen session compilation: {path_str}"
        )
    if isinstance(step.repeat, RepeatUntil) and not _supports_repeat_until(stage_type):
        raise CompileUnsupportedFeature(
            f"repeat.until requires static loop_condition support on Arnold stages: {path_str}"
        )
    if step.re_export:
        _resolved_re_export_metadata(plan, step=step, path=path)
    for child in step.children or ():
        _preflight_step_support(
            plan,
            child,
            path=path + (child.id,),
            stage_type=stage_type,
        )


def _compile_sequence(
    plan: TaskPlan,
    steps: tuple[Step, ...],
    *,
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    segment_id: str,
    base_path: tuple[str, ...],
    compat: Any,
) -> tuple[_CompiledNode, ...]:
    nodes: list[_CompiledNode] = []
    for step in steps:
        path = base_path + (step.id,)
        nodes.append(
            _compile_step(
                plan,
                step,
                path=path,
                project=project,
                run_root_path=run_root_path,
                state=state,
                segment_id=segment_id,
                compat=compat,
            )
        )
    return tuple(nodes)


def _compile_step(
    plan: TaskPlan,
    step: Step,
    *,
    path: tuple[str, ...],
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    segment_id: str,
    compat: Any,
) -> _CompiledNode:
    if step.children is None:
        stage_id = _stage_id_for_path(path)
        stage = _leaf_stage_spec(
            step=step,
            stage_id=stage_id,
            segment_id=segment_id,
            path=path,
            project=project,
            run_root_path=run_root_path,
            state=state,
            compat=compat,
        )
        return _CompiledNode(
            entry_stage_id=stage_id,
            exit_stage_id=stage_id,
            stages=(stage,),
            edges=(),
            continue_labels=("proceed", "skip") if step.optional else ("next",),
        )

    entry_id = _group_boundary_stage_id(path, GROUP_ENTRY_SUFFIX)
    exit_id = _group_boundary_stage_id(path, GROUP_EXIT_SUFFIX)
    child_nodes = _compile_sequence(
        plan,
        step.children,
        project=project,
        run_root_path=run_root_path,
        state=state,
        segment_id=segment_id,
        base_path=path,
        compat=compat,
    )
    entry_stage = _group_boundary_stage(
        stage_id=entry_id,
        label=f"{step.id}:enter",
        segment_id=segment_id,
        path=path,
        step=step,
        boundary="entry",
        decision_vocabulary=("proceed", "skip") if step.optional else (),
    )
    exit_stage = _group_boundary_stage(
        stage_id=exit_id,
        label=f"{step.id}:exit",
        segment_id=segment_id,
        path=path,
        step=step,
        boundary="exit",
        re_exports=_resolved_re_export_metadata(plan, step=step, path=path) or None,
    )
    stages: list[_StageSpec] = [entry_stage]
    edges: list[_EdgeSpec] = []

    if child_nodes:
        if step.optional:
            edges.append(_EdgeSpec(source=entry_id, target=child_nodes[0].entry_stage_id, label="proceed"))
            edges.append(_EdgeSpec(source=entry_id, target=exit_id, label="skip"))
        else:
            edges.append(_EdgeSpec(source=entry_id, target=child_nodes[0].entry_stage_id, label="next"))
        for index, node in enumerate(child_nodes):
            stages.extend(node.stages)
            edges.extend(node.edges)
            if index:
                previous = child_nodes[index - 1]
                for label in previous.continue_labels:
                    edges.append(
                        _EdgeSpec(
                            source=previous.exit_stage_id,
                            target=node.entry_stage_id,
                            label=label,
                        )
                    )
        for label in child_nodes[-1].continue_labels:
            edges.append(_EdgeSpec(source=child_nodes[-1].exit_stage_id, target=exit_id, label=label))
    else:
        edges.append(
            _EdgeSpec(
                source=entry_id,
                target=exit_id,
                label="skip" if step.optional else "next",
            )
        )

    stages.append(exit_stage)
    return _CompiledNode(
        entry_stage_id=entry_id,
        exit_stage_id=exit_id,
        stages=tuple(stages),
        edges=tuple(edges),
        continue_labels=("next",),
    )


def compile_plan_segment(
    plan: TaskPlan,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any],
    segment_id: str,
) -> CompileResult:
    """Compile a TaskPlan into a fresh Arnold pipeline segment."""
    from astrid.core.integrations.arnold.host.builder import (
        build_edge,
        build_stage,
        builder_add_edge,
        builder_add_stage,
        builder_finalize,
        builder_set_entry_stage,
    )
    from astrid.core.integrations.arnold.host.compat import compat

    run_root_path = Path(run_root)
    for path, step in iter_steps_with_path(plan):
        _preflight_step_support(plan, step, path=path, stage_type=compat.Stage)

    nodes = _compile_sequence(
        plan,
        plan.steps,
        project=project,
        run_root_path=run_root_path,
        state=state,
        segment_id=segment_id,
        base_path=(),
        compat=compat,
    )
    if not nodes:
        raise CompileUnsupportedFeature("compile_plan_segment requires at least one leaf step")

    builder = compat.PipelineBuilder()
    ordered_stage_specs: list[_StageSpec] = []
    ordered_edge_specs: list[_EdgeSpec] = []
    for index, node in enumerate(nodes):
        ordered_stage_specs.extend(node.stages)
        ordered_edge_specs.extend(node.edges)
        if index:
            previous = nodes[index - 1]
            for label in previous.continue_labels:
                ordered_edge_specs.append(
                    _EdgeSpec(
                        source=previous.exit_stage_id,
                        target=node.entry_stage_id,
                        label=label,
                    )
                )
    halt_stage = _halt_stage()
    ordered_stage_specs.append(halt_stage)
    for label in nodes[-1].continue_labels:
        ordered_edge_specs.append(
            _EdgeSpec(
                source=nodes[-1].exit_stage_id,
                target=HALT_STAGE_ID,
                label=label,
            )
        )

    for spec in ordered_stage_specs:
        builder_add_stage(
            builder,
            build_stage(
                compat.Stage,
                stage_id=spec.stage_id,
                label=spec.label,
                invocation=spec.invocation,
                suspension=spec.suspension,
                metadata=spec.metadata,
                decision_vocabulary=spec.decision_vocabulary or None,
                loop_condition=spec.loop_condition,
            ),
        )
    for edge_spec in ordered_edge_specs:
        builder_add_edge(
            builder,
            build_edge(
                compat.Edge,
                source=edge_spec.source,
                target=edge_spec.target,
                label=edge_spec.label,
            ),
        )

    entry_stage_id = nodes[0].entry_stage_id
    builder_set_entry_stage(builder, entry_stage_id)
    pipeline = builder_finalize(builder)
    manifest = _pipeline_manifest(pipeline)
    diagnostics = (
        f"compiled segment {segment_id}",
        f"stages={len(ordered_stage_specs)}",
        f"edges={len(ordered_edge_specs)}",
    )
    return CompileResult(
        pipeline=pipeline,
        pipeline_manifest=manifest,
        plan_hash=_plan_hash(plan),
        entry_stage_id=entry_stage_id,
        diagnostics=diagnostics,
    )


__all__ = [
    "CompileResult",
    "CompileUnsupportedFeature",
    "TASK_ADAPTER_EXECUTOR_PREFIX",
    "compile_plan_segment",
]
