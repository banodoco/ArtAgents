"""Locked Arnold authoring facade for pack workflow.py builders.

This module provides the stable, versioned public API that ``workflow.py``
files in individual packs import to construct Arnold ``Pipeline`` objects.
It wraps the lower-level ``session.lowering`` primitives so pack authors do
not need to know about ``StageSpec``, ``EdgeSpec``, ``LoweredSegment``, or
``build_pipeline`` internals.

Design constraints (settled — do not re-litigate):
- Does NOT import ``arnold.pipelines.megaplan._pipeline`` or Megaplan-only
  pipeline symbols.
- All Arnold runtime symbols flow through
  ``astrid.core.integrations.arnold.host.compat``.
- ``build_workflow()`` returns an Arnold ``Pipeline``, never a TaskPlan dict.
- The facade may use ``session.lowering`` helper values internally, but
  callers never see them.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from astrid.core.integrations.arnold.session import lowering
from astrid.core.task.plan import _validate_plan


def executor_step(
    *,
    stage_id: str,
    label: str,
    executor_id: str,
    segment_id: str,
    project: str,
    run_root: str | Path,
    state: dict[str, Any] | None = None,
    command: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    decision_vocabulary: tuple[str, ...] = ("next",),
    requires_ack: bool = False,
    optional: bool = False,
) -> lowering.StageSpec:
    """Build a StageSpec for an executor-backed step.

    This is the primary building block for pack workflows.  Each call
    produces a ``StageSpec`` that will be compiled into an Arnold ``Stage``
    by ``build_pipeline``.

    Args:
        stage_id: Unique stage identifier within the pipeline.
        label: Human-readable label for the stage.
        executor_id: Qualified executor id (e.g. ``editorial.transcribe``).
        segment_id: Workflow / segment identifier (e.g. ``video_editing.hype``).
        project: Project slug.
        run_root: Run output directory.
        state: Current runtime state dict.
        command: Optional command override (for wrapper stages).
        inputs: Named input port declarations.
        outputs: Named output port declarations.
        metadata: Extra metadata sidecar.
        decision_vocabulary: Allowed decision labels (default ``("next",)``).
        requires_ack: Whether this step requires an explicit acknowledgement.
        optional: Whether this step can be skipped (affects decision vocabulary).

    Returns:
        A ``StageSpec`` ready for inclusion in a ``LoweredSegment``.
    """
    resolved_run_root = Path(run_root)
    active_state = dict(state or {})
    merged_metadata = dict(metadata or {})

    if optional:
        decision_vocabulary = ("proceed", "skip")
    if requires_ack:
        merged_metadata["requires_ack"] = True
    if command is not None:
        merged_metadata["command"] = command
    if outputs:
        merged_metadata.setdefault("produces", list(outputs.keys()))
    merged_metadata["decision_vocabulary"] = list(decision_vocabulary)
    merged_metadata["vocabulary"] = list(decision_vocabulary)

    # Convert named inputs/outputs to the shapes expected by lowering
    input_map: dict[str, str] = {}
    if inputs:
        for name, spec in inputs.items():
            if isinstance(spec, str):
                input_map[name] = spec
            elif isinstance(spec, dict):
                ref = spec.get("ref")
                if ref:
                    input_map[name] = ref

    return lowering.adapter_stage_spec(
        stage_id=stage_id,
        label=label,
        executor_id=executor_id,
        segment_id=segment_id,
        project=project,
        run_root_path=resolved_run_root,
        state=active_state,
        capability_kind="executor",
        input_map=input_map if input_map else None,
        inputs=None,
        metadata=merged_metadata,
    )


def human_gate(
    *,
    stage_id: str,
    label: str,
    segment_id: str,
    decision_routes: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> lowering.StageSpec:
    """Build a StageSpec for a human-review gate.

    Human gates suspend the pipeline and wait for an external decision
    (approve, reject, etc.).  The *decision_routes* dict maps each human
    decision value to a target edge label.

    Args:
        stage_id: Unique stage identifier.
        label: Human-readable label.
        segment_id: Workflow / segment identifier.
        decision_routes: Mapping of decision -> edge label (e.g.
            ``{"approve": "next", "reject": "repeat"}``).
        metadata: Extra metadata sidecar.

    Returns:
        A ``StageSpec`` representing a suspended human gate.
    """
    merged_metadata = dict(metadata or {})
    merged_metadata["human_gate"] = True
    merged_metadata["manual"] = True
    merged_metadata["requires_ack"] = True

    effective_routes = dict(decision_routes or {"approve": "next"})
    vocabulary = tuple(effective_routes.keys())

    merged_metadata["decision_vocabulary"] = list(vocabulary)
    merged_metadata["vocabulary"] = list(vocabulary)
    merged_metadata["decision_routes"] = effective_routes
    merged_metadata["human_gate"] = True

    return lowering.StageSpec(
        stage_id=stage_id,
        label=label,
        invocation=None,
        suspension=None,
        metadata=merged_metadata,
        decision_vocabulary=vocabulary,
    )


def halt(
    *,
    label: str = "Halt",
) -> lowering.StageSpec:
    """Build a terminal halt stage.

    Every pipeline must end with a halt stage.

    Args:
        label: Human-readable label (default ``"Halt"``).

    Returns:
        A ``StageSpec`` for the terminal halt stage.
    """
    return lowering.halt_stage()


def edge(
    *,
    source: str,
    target: str,
    label: str = "next",
    source_port: str | None = None,
    target_port: str | None = None,
    logical_type: str | None = None,
    artifact_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> lowering.EdgeSpec:
    """Build an edge connecting two stages.

    Args:
        source: Source stage id.
        target: Target stage id.
        label: Edge label (default ``"next"``).
        source_port: Named source port for typed data flow.
        target_port: Named target port for typed data flow.
        logical_type: Logical type of the edge payload (stored in metadata).
        artifact_type: Artifact MIME/extension type (stored in metadata).
        metadata: Extra metadata sidecar.

    Returns:
        An ``EdgeSpec`` ready for inclusion in a ``LoweredSegment``.
    """
    merged_metadata = dict(metadata or {})
    if logical_type is not None:
        merged_metadata["logical_type"] = logical_type
    if artifact_type is not None:
        merged_metadata["artifact_type"] = artifact_type
    return lowering.resolve_port_edge(
        source=source,
        target=target,
        label=label,
        source_port=source_port,
        target_port=target_port,
        metadata=merged_metadata if merged_metadata else None,
    )


def pipeline(
    *,
    entry_stage_id: str,
    stages: tuple[lowering.StageSpec, ...],
    edges: tuple[lowering.EdgeSpec, ...],
    plan_hash: str | None = None,
    diagnostics: tuple[str, ...] = (),
) -> Any:
    """Compile stage and edge specs into an Arnold Pipeline.

    This is the final step in every ``build_workflow()`` function.
    It takes the accumulated ``StageSpec`` and ``EdgeSpec`` tuples,
    wraps them in a ``LoweredSegment``, and calls ``build_pipeline``
    to produce the Arnold-native ``Pipeline`` object.

    Args:
        entry_stage_id: The id of the first stage in the pipeline.
        stages: Ordered tuple of ``StageSpec`` values.
        edges: Ordered tuple of ``EdgeSpec`` values.
        plan_hash: Opaque plan hash for identity tracking.
        diagnostics: Human-readable diagnostics tuple.

    Returns:
        An Arnold ``Pipeline`` object.
    """
    lowered = lowering.LoweredSegment(
        entry_stage_id=entry_stage_id,
        ordered_stage_specs=stages,
        ordered_edge_specs=edges,
        plan_hash=plan_hash or entry_stage_id,
        diagnostics=diagnostics,
    )

    try:
        from astrid.core.integrations.arnold.host.compat import compat
    except ImportError:
        return SimpleNamespace(
            entry_stage_id=entry_stage_id,
            stages={stage.stage_id: stage for stage in stages},
            edges=tuple(edges),
            _astrid_stage_specs=tuple(stages),
            _astrid_edge_specs=tuple(edges),
            _astrid_lowered_segment=lowered,
        )

    return lowering.build_pipeline(lowered, compat=compat)


def task_plan_workflow(
    *,
    plan_builder: Any,
    segment_id: str,
    project: str | None = None,
    run_root: str | Path | None = None,
    state: dict[str, Any] | None = None,
    plan_builder_kwargs: dict[str, Any] | None = None,
    allow_repeat_for_each: bool = False,
) -> Any:
    """Build an Arnold Pipeline from a pack TaskPlan builder.

    Pack ``workflow.py`` modules use this as the migration bridge from their
    existing TaskPlan template to a real Arnold ``Pipeline`` entrypoint.
    """
    from astrid.core.integrations.arnold.host.compat import compat

    resolved_run_root = Path(run_root or "/tmp/astrid-arnold-workflow")
    plan_dict = plan_builder(
        run_root=resolved_run_root,
        **dict(plan_builder_kwargs or {}),
    )
    task_plan = _validate_plan(plan_dict)
    lowered = lowering.lower_plan_segment(
        task_plan,
        project=project or "default",
        run_root=resolved_run_root,
        state=dict(state or {}),
        segment_id=segment_id,
        compat=compat,
        allow_repeat_for_each=allow_repeat_for_each,
    )
    return lowering.build_pipeline(lowered, compat=compat)


def coerce_workflow_inputs(
    *,
    raw_inputs: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Coerce and validate workflow inputs against a per-pack schema.

    This is a minimal typed-input helper.  Each pack declares a schema
    dict mapping input names to type/default/required specs.  Missing
    required inputs raise ``ValueError``; optional inputs fall back to
    their declared defaults.

    Args:
        raw_inputs: The raw keyword dict passed to ``build_workflow()``.
        schema: A per-pack schema dict of shape::

            {
                "input_name": {
                    "type": "str" | "int" | "float" | "bool" | "path",
                    "default": <fallback value>,
                    "required": True | False,
                },
                ...
            }

    Returns:
        A validated and default-filled inputs dict.
    """
    validated: dict[str, Any] = {}
    for name, spec in schema.items():
        required = spec.get("required", False)
        default = spec.get("default")
        type_name = spec.get("type", "str")

        if name in raw_inputs and raw_inputs[name] is not None:
            value = raw_inputs[name]
        elif default is not None:
            value = default
        elif required:
            raise ValueError(
                f"Missing required workflow input: {name!r}"
            )
        else:
            continue

        # Coerce types
        if type_name == "path":
            value = Path(value)
        elif type_name == "int":
            value = int(value)
        elif type_name == "float":
            value = float(value)
        elif type_name == "bool":
            if isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            else:
                value = bool(value)
        elif type_name == "str":
            value = str(value)

        validated[name] = value
    return validated


def build_executor_argv(
    *,
    python_exec: str = "python3",
    module: str,
    subcommand: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build a standard executor argv list.

    This centralises the ``python -m pack.subcommand`` pattern used
    across many pack workflow stages.

    Args:
        python_exec: Python executable (default ``"python3"``).
        module: Fully-qualified module name.
        subcommand: Optional subcommand to append after the module.
        extra_args: Additional CLI arguments.

    Returns:
        A list of argv tokens.
    """
    argv = [python_exec, "-m", module]
    if subcommand:
        argv.append(subcommand)
    if extra_args:
        argv.extend(extra_args)
    return argv


__all__ = [
    "build_executor_argv",
    "coerce_workflow_inputs",
    "edge",
    "executor_step",
    "halt",
    "human_gate",
    "pipeline",
    "task_plan_workflow",
]
