"""Shared lowering helpers for Arnold session pipeline compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from astrid.core.contracts.schema import Output, Port
from astrid.core.events import canonical_event_json
from astrid.core.integrations.arnold.host.builder import edge_manifest_entry
from astrid.core.integrations.arnold.host.invocation import (
    HUMAN_DECISION_ROUTES,
    HUMAN_RESUME_INPUT_SCHEMA,
    build_adapter_metadata,
    build_step_invocation,
)
from astrid.core.plan import TaskPlanError
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    RepeatUntil,
    Step,
    TaskPlan,
    is_legacy_repeat_until_condition,
    iter_steps_with_path,
    parse_repeat_produces_ref,
    parse_repeat_until_expression,
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
class StageSpec:
    stage_id: str
    label: str
    invocation: Any | None
    suspension: Any | None
    metadata: dict[str, Any]
    decision_vocabulary: tuple[str, ...] = ("next",)
    loop_condition: Callable[[Any], bool] | None = None
    decision_routes: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeSpec:
    source: str
    target: str
    label: str
    source_port: str | None = None
    target_port: str | None = None
    logical_type: str | None = None
    artifact_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledNode:
    entry_stage_id: str
    exit_stage_id: str
    stages: tuple[StageSpec, ...]
    edges: tuple[EdgeSpec, ...]
    continue_labels: tuple[str, ...]


@dataclass(frozen=True)
class LoweredSegment:
    entry_stage_id: str
    ordered_stage_specs: tuple[StageSpec, ...]
    ordered_edge_specs: tuple[EdgeSpec, ...]
    plan_hash: str
    diagnostics: tuple[str, ...]


def plan_hash(plan: TaskPlan) -> str:
    import hashlib

    payload = canonical_event_json(plan.to_dict()).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def stage_id_for_path(path: tuple[str, ...]) -> str:
    return STEP_PATH_SEP.join(path)


def group_boundary_stage_id(path: tuple[str, ...], suffix: str) -> str:
    return f"{stage_id_for_path(path)}/{suffix}"


def produces_metadata(step: Step) -> list[dict[str, Any]]:
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


def supersede_metadata(step: Step) -> dict[str, Any] | None:
    if step.superseded_by is None:
        return None
    return {
        "to_version": step.superseded_by.to_version,
        "scope": step.superseded_by.scope,
    }


def resolve_decision_vocabulary(step: Step) -> tuple[str, ...]:
    """Return the decision vocabulary for *step*.

    Optional steps produce ``("proceed", "skip")`` so the runtime can
    route a positive or bypass decision.  Non-optional steps produce
    ``("next",)`` — a single linear forward edge.

    This is the canonical lowering of the ``optional`` flag on a
    ``Step`` into the Arnold stage-vocabulary contract.  Every call
    site that needs to set ``StageSpec.decision_vocabulary``,
    ``CompiledNode.continue_labels``, or the ``"decision_vocabulary"``
    key in stage metadata **must** use this helper so that the
    vocabulary stays consistent across the pipeline graph.
    """
    return ("proceed", "skip") if step.optional else ("next",)


def human_decision_routes_for_labels(labels: tuple[str, ...]) -> dict[str, str]:
    label_set = set(labels)
    if {"next", "repeat"}.issubset(label_set):
        return {
            "approve": HUMAN_DECISION_ROUTES["approve"],
            "reject": HUMAN_DECISION_ROUTES["reject"],
        }
    if {"proceed", "skip"}.issubset(label_set):
        return {"approve": "proceed", "reject": "skip"}
    if "next" in label_set:
        return {"approve": "next"}
    return {}



def task_executor_id(step: Step) -> str:
    return f"{TASK_ADAPTER_EXECUTOR_PREFIX}{step.adapter}"


def build_stage_metadata(
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
        "produces": produces_metadata(step),
        "adapter_config": dict(adapter_config),
    }
    superseded_by = supersede_metadata(step)
    if superseded_by is not None:
        metadata["superseded_by"] = superseded_by
    if step.instructions:
        metadata["instructions"] = step.instructions
    decision_vocabulary = resolve_decision_vocabulary(step)
    if step.optional:
        metadata["optional"] = True
    metadata["decision_vocabulary"] = list(decision_vocabulary)
    metadata["vocabulary"] = list(decision_vocabulary)
    return metadata


def pipeline_manifest(
    pipeline: Any,
    *,
    edge_specs: tuple[EdgeSpec, ...] | None = None,
    stage_specs: tuple[StageSpec, ...] | None = None,
) -> dict[str, Any]:
    if stage_specs is None:
        stage_specs = getattr(pipeline, "_astrid_stage_specs", None)
    if edge_specs is None:
        edge_specs = getattr(pipeline, "_astrid_edge_specs", None)
    stage_spec_by_id: dict[str, StageSpec] = {}
    if stage_specs is not None:
        stage_spec_by_id = {spec.stage_id: spec for spec in stage_specs}

    stages = []
    stages_attr = getattr(pipeline, "stages", None)
    if isinstance(stages_attr, dict):
        stage_iter = tuple(stages_attr.values())
    elif stages_attr:
        stage_iter = tuple(stages_attr)
    else:
        stage_iter = ()
    for stage in stage_iter:
        stage_id = getattr(stage, "stage_id", None) or getattr(stage, "name", None)
        spec = stage_spec_by_id.get(stage_id) if stage_id is not None else None
        item: dict[str, Any] = {
            "stage_id": stage_id,
            "label": spec.label if spec is not None else getattr(stage, "label", None),
            "metadata": dict(spec.metadata) if spec is not None else dict(getattr(stage, "metadata", {}) or {}),
        }
        decision_vocabulary = getattr(stage, "decision_vocabulary", None)
        if decision_vocabulary:
            # Preserve the ordered tuple from the spec when available; the
            # runtime frozenset is unordered and only used as a fallback.
            ordered_vocabulary = (
                spec.decision_vocabulary
                if spec is not None and spec.decision_vocabulary
                else decision_vocabulary
            )
            item["vocabulary"] = list(ordered_vocabulary)
        suspension = getattr(stage, "suspension", None)
        if suspension is not None:
            to_json = getattr(suspension, "to_json", None)
            if callable(to_json):
                item["suspension"] = to_json()
        elif spec is not None and spec.suspension is not None:
            to_json = getattr(spec.suspension, "to_json", None)
            if callable(to_json):
                item["suspension"] = to_json()
        decision_routes = getattr(stage, "decision_routes", None)
        if decision_routes:
            item["decision_routes"] = dict(decision_routes)
        if getattr(stage, "loop_condition", None) is not None:
            item["has_loop_condition"] = True
        stages.append(item)
    edges = []
    runtime_edges = tuple(getattr(pipeline, "edges", ()) or ())
    if edge_specs is not None:
        for spec in edge_specs:
            edges.append(
                edge_manifest_entry(
                    source=spec.source,
                    target=spec.target,
                    label=spec.label,
                    source_port=spec.source_port,
                    target_port=spec.target_port,
                    logical_type=spec.logical_type,
                    artifact_type=spec.artifact_type,
                    metadata=spec.metadata,
                )
            )
    else:
        for edge in runtime_edges:
            edges.append(
                edge_manifest_entry(
                    source=getattr(edge, "source", None),
                    target=getattr(edge, "target", None),
                    label=getattr(edge, "label", None),
                    source_port=getattr(edge, "source_port", None),
                    target_port=getattr(edge, "target_port", None),
                    logical_type=getattr(edge, "logical_type", None),
                    artifact_type=getattr(edge, "artifact_type", None),
                    metadata=getattr(edge, "metadata", None),
                )
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


def _repeat_until_error(
    *,
    path: tuple[str, ...],
    condition: str,
    reason: str,
) -> CompileUnsupportedFeature:
    path_str = STEP_PATH_SEP.join(path)
    return CompileUnsupportedFeature(
        f"repeat.until unsupported on {path_str} with expression {condition!r}: {reason}"
    )


def resolve_repeat_until_metadata(
    plan: TaskPlan,
    *,
    step: Step,
    path: tuple[str, ...],
) -> dict[str, Any] | None:
    repeat = step.repeat
    if not isinstance(repeat, RepeatUntil):
        return None
    if is_legacy_repeat_until_condition(repeat.condition):
        raise _repeat_until_error(
            path=path,
            condition=repeat.condition,
            reason="legacy repeat.until condition names are not supported by Arnold lowering",
        )
    try:
        expr = parse_repeat_until_expression(repeat.condition)
        resolved = resolve_produces_ref(plan, expr.ref, base_path=path)
    except TaskPlanError as exc:
        raise _repeat_until_error(
            path=path,
            condition=repeat.condition,
            reason=str(exc),
        ) from exc
    return {
        "predicate": "repeat.until",
        "condition": repeat.condition,
        "operator": expr.op,
        "literal": expr.literal,
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
        "max_iterations": repeat.max_iterations,
        "on_exhaust": repeat.on_exhaust,
    }


def resolved_re_export_metadata(
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


def group_boundary_stage(
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    path: tuple[str, ...],
    step: Step,
    boundary: str,
    re_exports: list[dict[str, Any]] | None = None,
    decision_vocabulary: tuple[str, ...] = ("next",),
) -> StageSpec:
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
    superseded_by = supersede_metadata(step)
    if superseded_by is not None:
        metadata["superseded_by"] = superseded_by
    if step.optional and boundary == "entry":
        metadata["optional"] = True
    metadata["decision_vocabulary"] = list(decision_vocabulary)
    metadata["vocabulary"] = list(decision_vocabulary)
    if re_exports:
        metadata["re_exports"] = re_exports
    return StageSpec(
        stage_id=stage_id,
        label=label,
        invocation=None,
        suspension=None,
        metadata=metadata,
        decision_vocabulary=decision_vocabulary,
    )


def halt_stage() -> StageSpec:
    return StageSpec(
        stage_id=HALT_STAGE_ID,
        label="Halt",
        invocation=None,
        suspension=None,
        metadata={"stage_id": HALT_STAGE_ID, "terminal": True, "vocabulary": ["terminal"]},
        decision_vocabulary=("terminal",),
    )


def leaf_stage_spec(
    *,
    step: Step,
    stage_id: str,
    segment_id: str,
    path: tuple[str, ...],
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    compat: Any,
) -> StageSpec:
    adapter_config = build_adapter_metadata(
        executor_id=task_executor_id(step),
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
        produces=produces_metadata(step),
        step_version=step.version,
        superseded_by=supersede_metadata(step),
        manual=step.adapter == "manual",
        source_plan_path=list(path),
        segment_id=segment_id,
    )
    invocation = build_step_invocation(
        executor_id=task_executor_id(step),
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
        produces=produces_metadata(step),
        step_version=step.version,
        superseded_by=supersede_metadata(step),
        manual=step.adapter == "manual",
        source_plan_path=list(path),
        segment_id=segment_id,
    )
    suspension = None
    if step.adapter == "manual":
        suspension = compat.Suspension(
            kind="human",
            resume_input_schema=HUMAN_RESUME_INPUT_SCHEMA,
        )
    return StageSpec(
        stage_id=stage_id,
        label=step.id,
        invocation=invocation,
        suspension=suspension,
        metadata=build_stage_metadata(
            step=step,
            stage_id=stage_id,
            segment_id=segment_id,
            path=path,
            adapter_config=adapter_config,
        ),
        decision_vocabulary=resolve_decision_vocabulary(step),
        decision_routes=human_decision_routes_for_labels(
            resolve_decision_vocabulary(step)
        ),
    )


def adapter_stage_spec(
    *,
    stage_id: str,
    label: str,
    executor_id: str,
    segment_id: str,
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    capability_kind: str,
    source_orchestrator_id: str | None = None,
    input_map: dict[str, str] | None = None,
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StageSpec:
    """Build a generic adapter-backed stage for non-TaskPlan compiler fronts."""

    normalized_input_map = dict(input_map or {})
    normalized_inputs = dict(inputs or {})
    adapter_config = build_adapter_metadata(
        executor_id=executor_id,
        input_map=normalized_input_map,
        inputs=normalized_inputs,
        state=state,
        mode="inline",
        project=project,
        run_root=str(run_root_path),
        artifact_root=str(run_root_path),
        requires_ack=False,
    )
    invocation = build_step_invocation(
        executor_id=executor_id,
        input_map=normalized_input_map,
        inputs=normalized_inputs,
        state=state,
        mode="inline",
        project=project,
        run_root=str(run_root_path),
        artifact_root=str(run_root_path),
        requires_ack=False,
    )
    stage_metadata: dict[str, Any] = {
        "segment_id": segment_id,
        "stage_id": stage_id,
        "executor_id": executor_id,
        "capability_kind": capability_kind,
        "adapter_config": dict(adapter_config),
        "decision_vocabulary": ["next"],
        "vocabulary": ["next"],
    }
    if source_orchestrator_id is not None:
        stage_metadata["source_orchestrator_id"] = source_orchestrator_id
    if metadata:
        stage_metadata.update(metadata)
    return StageSpec(
        stage_id=stage_id,
        label=label,
        invocation=invocation,
        suspension=None,
        metadata=stage_metadata,
        decision_vocabulary=("next",),
    )


def add_wrapper_stage(
    stage_specs: list[StageSpec],
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    path: tuple[str, ...],
    runtime: str,
    adapter: str,
    command: str | None = None,
    metadata: dict[str, Any] | None = None,
    decision_vocabulary: tuple[str, ...] = ("next",),
) -> StageSpec:
    """Append a wrapper-runtime stage spec for future command/python wrappers."""

    wrapper_metadata = {
        "segment_id": segment_id,
        "stage_id": stage_id,
        "source_plan_path": list(path),
        "adapter": adapter,
        "wrapper_runtime": runtime,
    }
    if command is not None:
        wrapper_metadata["command"] = command
    if metadata:
        wrapper_metadata.update(metadata)
    wrapper_metadata.setdefault("vocabulary", list(decision_vocabulary))
    spec = StageSpec(
        stage_id=stage_id,
        label=label,
        invocation=None,
        suspension=None,
        metadata=wrapper_metadata,
        decision_vocabulary=decision_vocabulary,
    )
    stage_specs.append(spec)
    return spec


def index_port_declarations(
    *,
    inputs: tuple[Port, ...] | None = None,
    outputs: tuple[Output, ...] | None = None,
) -> tuple[dict[str, Port], dict[str, Output]]:
    """Index Port inputs and Output outputs by name from capability definitions.

    Returns two dicts: ``(inputs_by_name, outputs_by_name)``.  Both dicts
    are empty when the corresponding declarations are ``None`` or empty.

    This helper is shared between the TaskPlan session compiler and the
    folder-orchestrator graph lowering front-end.
    """
    inputs_by_name: dict[str, Port] = {}
    if inputs:
        for port in inputs:
            inputs_by_name[port.name] = port

    outputs_by_name: dict[str, Output] = {}
    if outputs:
        for output in outputs:
            outputs_by_name[output.name] = output

    return inputs_by_name, outputs_by_name


def resolve_port_edge(
    *,
    source: str,
    target: str,
    label: str = "next",
    source_port: str | None = None,
    target_port: str | None = None,
    producer_outputs: dict[str, Output] | None = None,
    consumer_inputs: dict[str, Port] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EdgeSpec:
    """Create an EdgeSpec with port metadata from capability declarations.

    Lenient port-keyed validation:

    * Only consults declarations when **both** *producer_outputs* and
      *consumer_inputs* are supplied (non-``None``, non-empty).
    * For legacy nodes without declarations the function behaves as a
      vanilla ``EdgeSpec`` constructor — ``logical_type`` stays ``None``,
      ``artifact_type`` stays ``None``, and no port-name checks are
      performed.
    * When declarations are present, the function copies the declared
      ``artifact_type`` (from the producer ``Output`` or consumer ``Port``,
      in that order) into the edge spec **as metadata only** — no
      executor-level type enforcement is performed and mismatches are
      never raised.
    """
    logical_type: str | None = None
    artifact_type: str | None = None

    # Only inspect declarations when both sides are supplied.
    if producer_outputs is not None and consumer_inputs is not None:
        if source_port is not None and source_port in producer_outputs:
            producer_output = producer_outputs[source_port]
            if artifact_type is None and producer_output.artifact_type:
                artifact_type = producer_output.artifact_type

        if target_port is not None and target_port in consumer_inputs:
            consumer_port = consumer_inputs[target_port]
            if artifact_type is None and consumer_port.artifact_type:
                artifact_type = consumer_port.artifact_type

    # logical_type is intentionally always None for now —
    # the type system is a future switch (see plan open questions).
    return EdgeSpec(
        source=source,
        target=target,
        label=label,
        source_port=source_port,
        target_port=target_port,
        logical_type=logical_type,
        artifact_type=artifact_type,
        metadata=metadata or {},
    )


def preflight_step_support(
    plan: TaskPlan,
    step: Step,
    *,
    path: tuple[str, ...],
    stage_type: type[Any],
    allow_repeat_for_each: bool = False,
) -> None:
    path_str = STEP_PATH_SEP.join(path)
    if isinstance(step.repeat, RepeatForEach) and not allow_repeat_for_each:
        raise CompileUnsupportedFeature(
            f"repeat.for_each is not supported in frozen session compilation: {path_str}"
        )
    if isinstance(step.repeat, RepeatUntil) and not _supports_repeat_until(stage_type):
        raise CompileUnsupportedFeature(
            f"repeat.until requires static loop_condition support on Arnold stages: {path_str}"
        )
    resolve_repeat_until_metadata(plan, step=step, path=path)
    if step.re_export:
        resolved_re_export_metadata(plan, step=step, path=path)
    for child in step.children or ():
        preflight_step_support(
            plan,
            child,
            path=path + (child.id,),
            stage_type=stage_type,
            allow_repeat_for_each=allow_repeat_for_each,
        )


def compile_sequence(
    plan: TaskPlan,
    steps: tuple[Step, ...],
    *,
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    segment_id: str,
    base_path: tuple[str, ...],
    compat: Any,
    allow_repeat_for_each: bool = False,
) -> tuple[CompiledNode, ...]:
    nodes: list[CompiledNode] = []
    for step in steps:
        path = base_path + (step.id,)
        nodes.append(
            compile_step(
                plan,
                step,
                path=path,
                project=project,
                run_root_path=run_root_path,
                state=state,
                segment_id=segment_id,
                compat=compat,
                allow_repeat_for_each=allow_repeat_for_each,
            )
        )
    return tuple(nodes)


def compile_step(
    plan: TaskPlan,
    step: Step,
    *,
    path: tuple[str, ...],
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    segment_id: str,
    compat: Any,
    allow_repeat_for_each: bool = False,
) -> CompiledNode:
    repeat_until_metadata = resolve_repeat_until_metadata(plan, step=step, path=path)
    repeat_for_each_metadata = None
    if allow_repeat_for_each and isinstance(step.repeat, RepeatForEach):
        repeat_for_each_metadata = {
            "kind": "for_each",
            "items_source": step.repeat.items_source,
        }
        if step.repeat.items_source == "static":
            repeat_for_each_metadata["items"] = list(step.repeat.items)
        else:
            repeat_for_each_metadata["from_ref"] = step.repeat.from_ref
    if step.children is None:
        stage_id = stage_id_for_path(path)
        stage = leaf_stage_spec(
            step=step,
            stage_id=stage_id,
            segment_id=segment_id,
            path=path,
            project=project,
            run_root_path=run_root_path,
            state=state,
            compat=compat,
        )
        if repeat_for_each_metadata is not None:
            stage = StageSpec(
                stage_id=stage.stage_id,
                label=stage.label,
                invocation=stage.invocation,
                suspension=stage.suspension,
                metadata={
                    **stage.metadata,
                    "repeat_for_each": repeat_for_each_metadata,
                    "fan_out_shape": True,
                },
                decision_vocabulary=stage.decision_vocabulary,
                loop_condition=stage.loop_condition,
            )
        if repeat_until_metadata is not None:
            stage = StageSpec(
                stage_id=stage.stage_id,
                label=stage.label,
                invocation=stage.invocation,
                suspension=stage.suspension,
                metadata={
                    **stage.metadata,
                    "decision_vocabulary": ["repeat", "next"],
                    "vocabulary": ["repeat", "next"],
                    "repeat_until": repeat_until_metadata,
                },
                decision_vocabulary=("repeat", "next"),
                loop_condition=(lambda _value: False),
                decision_routes=human_decision_routes_for_labels(("repeat", "next")),
            )
            edges = (
                EdgeSpec(
                    source=stage_id,
                    target=stage_id,
                    label="repeat",
                    metadata=repeat_until_metadata,
                ),
            )
        else:
            edges = ()
        return CompiledNode(
            entry_stage_id=stage_id,
            exit_stage_id=stage_id,
            stages=(stage,),
            edges=edges,
            continue_labels=("next",) if repeat_until_metadata is not None else resolve_decision_vocabulary(step),
        )

    entry_id = group_boundary_stage_id(path, GROUP_ENTRY_SUFFIX)
    exit_id = group_boundary_stage_id(path, GROUP_EXIT_SUFFIX)
    child_nodes = compile_sequence(
        plan,
        step.children,
        project=project,
        run_root_path=run_root_path,
        state=state,
        segment_id=segment_id,
        base_path=path,
        compat=compat,
        allow_repeat_for_each=allow_repeat_for_each,
    )
    entry_stage = group_boundary_stage(
        stage_id=entry_id,
        label=f"{step.id}:enter",
        segment_id=segment_id,
        path=path,
        step=step,
        boundary="entry",
        decision_vocabulary=resolve_decision_vocabulary(step),
    )
    exit_stage = group_boundary_stage(
        stage_id=exit_id,
        label=f"{step.id}:exit",
        segment_id=segment_id,
        path=path,
        step=step,
        boundary="exit",
        re_exports=resolved_re_export_metadata(plan, step=step, path=path) or None,
    )
    if repeat_for_each_metadata is not None:
        entry_stage = StageSpec(
            stage_id=entry_stage.stage_id,
            label=entry_stage.label,
            invocation=entry_stage.invocation,
            suspension=entry_stage.suspension,
            metadata={
                **entry_stage.metadata,
                "repeat_for_each": repeat_for_each_metadata,
                "fan_out_shape": True,
            },
            decision_vocabulary=entry_stage.decision_vocabulary,
            loop_condition=entry_stage.loop_condition,
        )
    if repeat_until_metadata is not None:
        exit_stage = StageSpec(
            stage_id=exit_stage.stage_id,
            label=exit_stage.label,
            invocation=exit_stage.invocation,
            suspension=exit_stage.suspension,
            metadata={
                **exit_stage.metadata,
                "decision_vocabulary": ["repeat", "next"],
                "vocabulary": ["repeat", "next"],
                "repeat_until": repeat_until_metadata,
            },
            decision_vocabulary=("repeat", "next"),
            loop_condition=(lambda _value: False),
        )
    stages: list[StageSpec] = [entry_stage]
    edges: list[EdgeSpec] = []

    if child_nodes:
        if step.optional:
            edges.append(EdgeSpec(source=entry_id, target=child_nodes[0].entry_stage_id, label="proceed"))
            edges.append(EdgeSpec(source=entry_id, target=exit_id, label="skip"))
        else:
            edges.append(EdgeSpec(source=entry_id, target=child_nodes[0].entry_stage_id, label="next"))
        for index, node in enumerate(child_nodes):
            stages.extend(node.stages)
            edges.extend(node.edges)
            if index:
                previous = child_nodes[index - 1]
                for label in previous.continue_labels:
                    edges.append(
                        EdgeSpec(
                            source=previous.exit_stage_id,
                            target=node.entry_stage_id,
                            label=label,
                        )
                    )
        for label in child_nodes[-1].continue_labels:
            edges.append(EdgeSpec(source=child_nodes[-1].exit_stage_id, target=exit_id, label=label))
    else:
        edges.append(
            EdgeSpec(
                source=entry_id,
                target=exit_id,
                label="skip" if step.optional else "next",
            )
        )

    stages.append(exit_stage)
    if repeat_until_metadata is not None:
        edges.append(
            EdgeSpec(
                source=exit_id,
                target=entry_id,
                label="repeat",
                metadata=repeat_until_metadata,
            )
        )
    return CompiledNode(
        entry_stage_id=entry_id,
        exit_stage_id=exit_id,
        stages=tuple(stages),
        edges=tuple(edges),
        continue_labels=("next",),
    )


def lower_plan_segment(
    plan: TaskPlan,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any],
    segment_id: str,
    compat: Any,
    allow_repeat_for_each: bool = False,
) -> LoweredSegment:
    run_root_path = Path(run_root)
    for path, step in iter_steps_with_path(plan):
        preflight_step_support(
            plan,
            step,
            path=path,
            stage_type=compat.Stage,
            allow_repeat_for_each=allow_repeat_for_each,
        )

    nodes = compile_sequence(
        plan,
        plan.steps,
        project=project,
        run_root_path=run_root_path,
        state=state,
        segment_id=segment_id,
        base_path=(),
        compat=compat,
        allow_repeat_for_each=allow_repeat_for_each,
    )
    if not nodes:
        raise CompileUnsupportedFeature("compile_plan_segment requires at least one leaf step")

    ordered_stage_specs: list[StageSpec] = []
    ordered_edge_specs: list[EdgeSpec] = []
    for index, node in enumerate(nodes):
        ordered_stage_specs.extend(node.stages)
        ordered_edge_specs.extend(node.edges)
        if index:
            previous = nodes[index - 1]
            for label in previous.continue_labels:
                ordered_edge_specs.append(
                    EdgeSpec(
                        source=previous.exit_stage_id,
                        target=node.entry_stage_id,
                        label=label,
                    )
                )
    ordered_stage_specs.append(halt_stage())
    for label in nodes[-1].continue_labels:
        ordered_edge_specs.append(
            EdgeSpec(
                source=nodes[-1].exit_stage_id,
                target=HALT_STAGE_ID,
                label=label,
            )
        )

    diagnostics = (
        f"compiled segment {segment_id}",
        f"stages={len(ordered_stage_specs)}",
        f"edges={len(ordered_edge_specs)}",
    )
    return LoweredSegment(
        entry_stage_id=nodes[0].entry_stage_id,
        ordered_stage_specs=tuple(ordered_stage_specs),
        ordered_edge_specs=tuple(ordered_edge_specs),
        plan_hash=plan_hash(plan),
        diagnostics=diagnostics,
    )


def build_pipeline(
    lowered: LoweredSegment,
    *,
    compat: Any,
) -> Any:
    from astrid.core.integrations.arnold.host.builder import (
        build_edge,
        build_stage,
        builder_add_edge,
        builder_add_stage,
        builder_finalize,
        builder_set_entry_stage,
    )

    # Pre-build edges and group them by source stage so they can be attached
    # directly to the owning Stage. Real Arnold edges are sourceless; the
    # PipelineBuilder's add_edge path cannot reliably attach them, so we pass
    # them through the Stage constructor's ``edges`` parameter instead.
    edges_by_source: dict[str, list[Any]] = {}
    built_edges: list[Any] = []
    for edge_spec in lowered.ordered_edge_specs:
        edge = build_edge(
            compat.Edge,
            source=edge_spec.source,
            target=edge_spec.target,
            label=edge_spec.label,
            source_port=edge_spec.source_port,
            target_port=edge_spec.target_port,
            logical_type=edge_spec.logical_type,
            artifact_type=edge_spec.artifact_type,
            metadata=edge_spec.metadata,
        )
        built_edges.append(edge)
        source = edge_spec.source or ""
        edges_by_source.setdefault(source, []).append(edge)

    builder = compat.PipelineBuilder()
    for spec in lowered.ordered_stage_specs:
        stage_edges = tuple(edges_by_source.get(spec.stage_id, []))
        builder_add_stage(
            builder,
            build_stage(
                compat.Stage,
                stage_id=spec.stage_id,
                label=spec.label,
                invocation=spec.invocation,
                suspension=spec.suspension,
                metadata=spec.metadata,
                decision_vocabulary=spec.decision_vocabulary,
                loop_condition=spec.loop_condition,
                decision_routes=spec.decision_routes,
                edges=stage_edges,
            ),
        )
    # Also register edges through the builder helper so legacy / fake builders
    # that surface a ``pipeline.edges`` collection still populate it. For the
    # real Arnold builder this is a no-op because sourceless edges are ignored
    # by ``add_edge`` and have already been attached to their owning Stage.
    for edge in built_edges:
        builder_add_edge(builder, edge)
    builder_set_entry_stage(builder, lowered.entry_stage_id)
    pipeline = builder_finalize(builder)
    # Attach spec sidecars so downstream manifest/invocation consumers can
    # recover metadata that the real Arnold contract intentionally keeps off
    # runtime Stage/Edge objects.
    try:
        object.__setattr__(
            pipeline, "_astrid_stage_specs", tuple(lowered.ordered_stage_specs)
        )
        object.__setattr__(
            pipeline, "_astrid_edge_specs", tuple(lowered.ordered_edge_specs)
        )
    except (AttributeError, TypeError):
        pass
    return pipeline


def compile_plan_segment(
    plan: TaskPlan,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any],
    segment_id: str,
) -> CompileResult:
    """Compile a TaskPlan into a fresh Arnold pipeline segment."""

    from astrid.core.integrations.arnold.host.compat import compat

    lowered = lower_plan_segment(
        plan,
        project=project,
        run_root=run_root,
        state=state,
        segment_id=segment_id,
        compat=compat,
    )
    pipeline = build_pipeline(lowered, compat=compat)
    return CompileResult(
        pipeline=pipeline,
        pipeline_manifest=pipeline_manifest(
            pipeline,
            edge_specs=lowered.ordered_edge_specs,
            stage_specs=lowered.ordered_stage_specs,
        ),
        plan_hash=lowered.plan_hash,
        entry_stage_id=lowered.entry_stage_id,
        diagnostics=lowered.diagnostics,
    )


# ── Synthetic media / judge / fan-out lowering primitives (A4a T21) ──────────

# Executor-id prefixes for synthetic adapter-backed primitives.
_MEDIA_EXECUTOR_PREFIX = "synthetic.media."
_JUDGE_EXECUTOR_PREFIX = "synthetic.judge."
_FANOUT_EXECUTOR_PREFIX = "synthetic.fanout."


def _arnold_has_parallel_stage() -> bool:
    """Return True when the Arnold public surface exposes ``ParallelStage``.

    This is deliberately a lazy runtime probe so that callers never pay
    an import cost just to check capability.  The probe inspects the
    ``compat`` namespace loaded by ``astrid.core.integrations.arnold.host``
    and falls back to ``False`` when Arnold is not installed.
    """
    try:
        from astrid.core.integrations.arnold.host.compat import compat as _compat
    except ImportError:
        return False
    return hasattr(_compat, "ParallelStage") and _compat.ParallelStage is not None


def lower_pattern_select(
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    pattern_names: tuple[str, ...],
    metadata: dict[str, Any] | None = None,
) -> StageSpec:
    """Emit a synthetic adapter-backed stage for media ``pattern_select``.

    The stage carries ``synthetic.media.pattern_select`` as its executor id
    and records *pattern_names* in the stage metadata so a downstream
    adapter can enumerate the available patterns.  This is intentionally a
    synthetic primitive — it does not touch any real media orchestrator.
    """
    extra_meta: dict[str, Any] = {
        "pattern_names": list(pattern_names),
        "synthetic_kind": "pattern_select",
    }
    if metadata:
        extra_meta.update(metadata)
    return adapter_stage_spec(
        stage_id=stage_id,
        label=label,
        executor_id=f"{_MEDIA_EXECUTOR_PREFIX}pattern_select",
        segment_id=segment_id,
        project=project,
        run_root_path=run_root_path,
        state=state,
        capability_kind="media",
        metadata=extra_meta,
    )


def lower_vote_judge(
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    vote_mode: str = "majority",
    candidates: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> StageSpec:
    """Emit a synthetic adapter-backed stage for ``vote`` / ``judge``.

    The stage carries ``synthetic.judge.vote`` as its executor id and
    records *vote_mode* and *candidates* in metadata.  This is a synthetic
    primitive — it does not touch any real judge orchestrator.
    """
    extra_meta: dict[str, Any] = {
        "vote_mode": vote_mode,
        "candidates": list(candidates),
        "synthetic_kind": "vote_judge",
    }
    if metadata:
        extra_meta.update(metadata)
    return adapter_stage_spec(
        stage_id=stage_id,
        label=label,
        executor_id=f"{_JUDGE_EXECUTOR_PREFIX}vote",
        segment_id=segment_id,
        project=project,
        run_root_path=run_root_path,
        state=state,
        capability_kind="judge",
        metadata=extra_meta,
    )


def lower_dynamic_fanout(
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    project: str,
    run_root_path: Path,
    state: dict[str, Any],
    fanout_branches: tuple[dict[str, Any], ...],
    metadata: dict[str, Any] | None = None,
) -> tuple[StageSpec, ...]:
    """Emit a synthetic fan-out structure for ``dynamic_fanout``.

    When the Arnold public surface exposes ``ParallelStage`` the returned
    tuple contains a single ``StageSpec`` whose metadata records the
    fan-out shape and carries a ``parallel_stage_hint`` marker for
    downstream builders that can construct a real ``ParallelStage``.

    When ``ParallelStage`` is not available the function returns one
    adapter-backed ``StageSpec`` per *fanout_branches* entry (sequential
    fan-out).  Each branch stage is labelled ``{stage_id}/{index}`` and
    carries the branch payload in its metadata.

    This is a synthetic primitive — it does not touch any real
    orchestrator.
    """
    extra_meta: dict[str, Any] = {
        "fanout_branch_count": len(fanout_branches),
        "synthetic_kind": "dynamic_fanout",
    }
    if metadata:
        extra_meta.update(metadata)

    if _arnold_has_parallel_stage():
        # Emit a single StageSpec with the parallel hint — downstream
        # builder can construct a ParallelStage from it.
        branch_meta = []
        for idx, branch in enumerate(fanout_branches):
            branch_meta.append({"index": idx, "payload": dict(branch)})
        extra_meta["fanout_branches"] = branch_meta
        extra_meta["parallel_stage_hint"] = True
        return (
            adapter_stage_spec(
                stage_id=stage_id,
                label=label,
                executor_id=f"{_FANOUT_EXECUTOR_PREFIX}fanout",
                segment_id=segment_id,
                project=project,
                run_root_path=run_root_path,
                state=state,
                capability_kind="fanout",
                metadata=extra_meta,
            ),
        )

    # Fallback: one adapter-backed stage per branch (sequential fan-out).
    specs: list[StageSpec] = []
    for idx, branch in enumerate(fanout_branches):
        branch_meta: dict[str, Any] = {
            "fanout_index": idx,
            "fanout_total": len(fanout_branches),
            "branch_payload": dict(branch),
            "synthetic_kind": "dynamic_fanout",
        }
        if metadata:
            branch_meta.update(metadata)
        specs.append(
            adapter_stage_spec(
                stage_id=f"{stage_id}/{idx}",
                label=f"{label}/{idx}",
                executor_id=f"{_FANOUT_EXECUTOR_PREFIX}fanout",
                segment_id=segment_id,
                project=project,
                run_root_path=run_root_path,
                state=state,
                capability_kind="fanout",
                metadata=branch_meta,
            )
        )
    return tuple(specs)


def join_parallel_results(stage: Any, results: list[Any]) -> Any:
    """Join results from parallel stages by delegating to the Arnold stage.

    When *stage* exposes a callable ``join`` attribute (e.g. the
    ``ParallelStage.join`` method in the Arnold public contract), this
    function delegates to ``stage.join(results)`` and returns the result.

    When *stage* does **not** expose a callable ``join``, this function
    raises ``CompileUnsupportedFeature`` with a diagnostic that names the
    stage and explains that the parallel join path requires the Arnold
    ``ParallelStage.join`` contract.  Astrid never attempts to implement
    its own join logic.
    """
    join_method = getattr(stage, "join", None)
    if callable(join_method):
        return join_method(results)
    stage_repr = getattr(stage, "stage_id", None) or repr(stage)
    raise CompileUnsupportedFeature(
        f"Parallel join is not supported for stage {stage_repr!r}. "
        f"The Arnold public surface does not expose a callable 'join' "
        f"method on this stage object.  Parallel fan-out join requires "
        f"``ParallelStage.join`` in the Arnold contract."
    )


__all__ = [
    "CompileResult",
    "CompileUnsupportedFeature",
    "CompiledNode",
    "EdgeSpec",
    "GROUP_ENTRY_SUFFIX",
    "GROUP_EXIT_SUFFIX",
    "HALT_STAGE_ID",
    "LoweredSegment",
    "StageSpec",
    "TASK_ADAPTER_EXECUTOR_PREFIX",
    "add_wrapper_stage",
    "adapter_stage_spec",
    "build_pipeline",
    "compile_plan_segment",
    "compile_sequence",
    "compile_step",
    "group_boundary_stage",
    "group_boundary_stage_id",
    "halt_stage",
    "index_port_declarations",
    "join_parallel_results",
    "leaf_stage_spec",
    "lower_dynamic_fanout",
    "lower_pattern_select",
    "lower_plan_segment",
    "lower_vote_judge",
    "pipeline_manifest",
    "plan_hash",
    "resolve_port_edge",
    "resolve_decision_vocabulary",
    "resolve_repeat_until_metadata",
    "resolved_re_export_metadata",
    "stage_id_for_path",
    "supersede_metadata",
    "task_executor_id",
]
