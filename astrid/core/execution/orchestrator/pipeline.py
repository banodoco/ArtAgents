"""Arnold Pipeline lowering for manifest- and folder-based orchestrators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.execution.executor.registry import (
    ExecutorRegistry,
    load_default_registry as load_default_executor_registry,
)
from astrid.core.integrations.arnold.session import lowering

from .folder import load_folder_orchestrator
from .registry import OrchestratorRegistry, load_default_registry as load_default_orchestrator_registry
from .schema import OrchestratorDefinition, load_orchestrator_manifest


@dataclass(frozen=True)
class _ChildCapability:
    capability_id: str
    capability_kind: str
    definition: Any
    stage_id: str
    inputs_by_name: dict[str, Any]
    outputs_by_name: dict[str, Any]


def compile_orchestrator_definition(
    definition: OrchestratorDefinition,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any] | None = None,
    segment_id: str | None = None,
    executor_registry: ExecutorRegistry | None = None,
    orchestrator_registry: OrchestratorRegistry | None = None,
    mode: str = "graph",
) -> lowering.CompileResult:
    """Compile an orchestrator definition into an Arnold pipeline.

    *mode* selects the lowering strategy:

    - ``"graph"`` (default): resolve child executors/orchestrators and lower
      them as a linear graph of adapter-backed stages.  This is the standard
      path for orchestrators with a declared child graph.
    - ``"wrapper"``: emit a single wrapper stage that delegates to the
      orchestrator's ``runtime`` (command or python invocation).  Intended
      for synthetic A4a fixtures and runtime-only orchestrators without
      declared children.

    When *mode* is ``"graph"`` and the orchestrator has no declared children,
    the function defaults to wrapper lowering automatically (backwards-
    compatible behaviour for runtime-only orchestrators).
    """

    resolved_segment_id = segment_id or definition.id
    active_state = dict(state or {})
    lowered = lower_orchestrator_definition(
        definition,
        project=project,
        run_root=run_root,
        state=active_state,
        segment_id=resolved_segment_id,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        mode=mode,
    )
    from astrid.core.integrations.arnold.host.compat import compat

    pipeline = lowering.build_pipeline(lowered, compat=compat)
    return lowering.CompileResult(
        pipeline=pipeline,
        pipeline_manifest=lowering.pipeline_manifest(
            pipeline,
            edge_specs=lowered.ordered_edge_specs,
        ),
        plan_hash=lowered.plan_hash,
        entry_stage_id=lowered.entry_stage_id,
        diagnostics=lowered.diagnostics,
    )


def compile_orchestrator_manifest(
    manifest_path: str | Path,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any] | None = None,
    segment_id: str | None = None,
    executor_registry: ExecutorRegistry | None = None,
    orchestrator_registry: OrchestratorRegistry | None = None,
    mode: str = "graph",
) -> lowering.CompileResult:
    """Load ``orchestrator.yaml`` metadata and compile its child graph."""

    definition = load_orchestrator_manifest(manifest_path)
    return compile_orchestrator_definition(
        definition,
        project=project,
        run_root=run_root,
        state=state,
        segment_id=segment_id,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        mode=mode,
    )


def compile_folder_orchestrator(
    orchestrator_root: str | Path,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any] | None = None,
    segment_id: str | None = None,
    executor_registry: ExecutorRegistry | None = None,
    orchestrator_registry: OrchestratorRegistry | None = None,
    mode: str = "graph",
) -> lowering.CompileResult:
    """Load a folder orchestrator and compile its child graph."""

    definition = load_folder_orchestrator(orchestrator_root)
    return compile_orchestrator_definition(
        definition,
        project=project,
        run_root=run_root,
        state=state,
        segment_id=segment_id,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        mode=mode,
    )


def lower_orchestrator_definition(
    definition: OrchestratorDefinition,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any],
    segment_id: str,
    executor_registry: ExecutorRegistry | None = None,
    orchestrator_registry: OrchestratorRegistry | None = None,
    mode: str = "graph",
) -> lowering.LoweredSegment:
    """Lower an orchestrator definition to shared Arnold specs.

    Two strategies are supported:

    * **graph** (default): resolve child executors/orchestrators and emit one
      adapter-backed stage per child with linear port-inferred edges, plus a
      terminal halt stage.  Use this for orchestrators that declare a child
      graph.
    * **wrapper**: emit a single wrapper stage backed by the orchestrator's
      ``runtime`` (command or python invocation), wired straight to halt.
      This path is selected explicitly via *mode* or automatically when the
      orchestrator has no declared children.
    """

    if mode == "wrapper":
        return _lower_wrapper(definition, project=project, run_root=run_root, state=state, segment_id=segment_id)

    active_executor_registry = executor_registry or load_default_executor_registry()
    active_orchestrator_registry = orchestrator_registry or load_default_orchestrator_registry(
        executor_registry=active_executor_registry
    )
    children = _resolve_children(
        definition,
        executor_registry=active_executor_registry,
        orchestrator_registry=active_orchestrator_registry,
    )
    if not children:
        return _lower_wrapper(definition, project=project, run_root=run_root, state=state, segment_id=segment_id)

    run_root_path = Path(run_root)
    ordered_stage_specs: list[lowering.StageSpec] = []
    ordered_edge_specs: list[lowering.EdgeSpec] = []
    previous: _ChildCapability | None = None
    for child in children:
        stage = lowering.adapter_stage_spec(
            stage_id=child.stage_id,
            label=child.capability_id,
            executor_id=child.capability_id,
            segment_id=segment_id,
            project=project,
            run_root_path=run_root_path,
            state=state,
            capability_kind=child.capability_kind,
            source_orchestrator_id=definition.id,
            metadata={
                "child_capability_id": child.capability_id,
                f"child_{child.capability_kind}_id": child.capability_id,
            },
        )
        ordered_stage_specs.append(stage)
        if previous is not None:
            source_port, target_port = _infer_linear_ports(
                previous.capability_id,
                previous.outputs_by_name,
                child.capability_id,
                child.inputs_by_name,
            )
            ordered_edge_specs.append(
                lowering.resolve_port_edge(
                    source=previous.stage_id,
                    target=child.stage_id,
                    label="next",
                    source_port=source_port,
                    target_port=target_port,
                    producer_outputs=previous.outputs_by_name or None,
                    consumer_inputs=child.inputs_by_name or None,
                    metadata={
                        "source_capability_id": previous.capability_id,
                        "target_capability_id": child.capability_id,
                        "source_capability_kind": previous.capability_kind,
                        "target_capability_kind": child.capability_kind,
                    },
                )
            )
        previous = child

    halt_stage = lowering.halt_stage()
    ordered_stage_specs.append(halt_stage)
    ordered_edge_specs.append(
        lowering.EdgeSpec(
            source=children[-1].stage_id,
            target=halt_stage.stage_id,
            label="next",
            metadata={
                "source_capability_id": children[-1].capability_id,
                "target_capability_id": halt_stage.stage_id,
                "source_capability_kind": children[-1].capability_kind,
                "target_capability_kind": "terminal",
            },
        )
    )
    diagnostics = (
        f"compiled orchestrator {definition.id}",
        f"children={len(children)}",
        f"stages={len(ordered_stage_specs)}",
        f"edges={len(ordered_edge_specs)}",
    )
    return lowering.LoweredSegment(
        entry_stage_id=children[0].stage_id,
        ordered_stage_specs=tuple(ordered_stage_specs),
        ordered_edge_specs=tuple(ordered_edge_specs),
        plan_hash=f"orchestrator:{definition.id}@{definition.version}",
        diagnostics=diagnostics,
    )


def _lower_wrapper(
    definition: OrchestratorDefinition,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any],
    segment_id: str,
) -> lowering.LoweredSegment:
    """Lower a runtime-only orchestrator into a single wrapper stage + halt.

    Produces one adapter-backed wrapper stage that carries the orchestrator's
    runtime spec (command or python) in its metadata so the adapter can invoke
    it directly without a registered executor.  Uses the ``add_wrapper_stage``
    primitive established in T2.
    """
    wrapper_stage_id = f"wrapper_{definition.id.replace('.', '_')}"
    runtime = definition.runtime

    # Build extra metadata that describes the wrapper runtime.
    wrapper_meta: dict[str, Any] = {
        "wrapper_orchestrator_id": definition.id,
        "wrapper_runtime_kind": runtime.kind,
        "segment_id": segment_id,
        "stage_id": wrapper_stage_id,
        "source_plan_path": [definition.id],
    }
    if runtime.kind == "python":
        if runtime.module is not None:
            wrapper_meta["wrapper_module"] = runtime.module
        wrapper_meta["wrapper_function"] = runtime.function
    elif runtime.kind == "command" and runtime.command is not None:
        wrapper_meta["wrapper_command_argv"] = list(runtime.command.argv)
        if runtime.command.cwd:
            wrapper_meta["wrapper_command_cwd"] = runtime.command.cwd
        if runtime.command.env:
            wrapper_meta["wrapper_command_env"] = dict(runtime.command.env)

    stage_specs: list[lowering.StageSpec] = []
    stage = lowering.add_wrapper_stage(
        stage_specs,
        stage_id=wrapper_stage_id,
        label=definition.name,
        segment_id=segment_id,
        path=(definition.id,),
        runtime=runtime.kind,
        adapter="orchestrator",
        command=runtime.command.argv[0] if runtime.kind == "command" and runtime.command else None,
        metadata=wrapper_meta,
        decision_vocabulary=("next",),
    )

    halt_stage = lowering.halt_stage()
    stage_specs.append(halt_stage)
    halt_edge = lowering.EdgeSpec(
        source=wrapper_stage_id,
        target=halt_stage.stage_id,
        label="next",
        metadata={
            "source_capability_id": wrapper_stage_id,
            "target_capability_id": halt_stage.stage_id,
            "source_capability_kind": "wrapper",
            "target_capability_kind": "terminal",
        },
    )

    diagnostics = (
        f"compiled wrapper orchestrator {definition.id}",
        f"runtime={runtime.kind}",
        "stages=2",
        "edges=1",
    )
    return lowering.LoweredSegment(
        entry_stage_id=wrapper_stage_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=(halt_edge,),
        plan_hash=f"orchestrator:{definition.id}@{definition.version}",
        diagnostics=diagnostics,
    )


def _resolve_children(
    definition: OrchestratorDefinition,
    *,
    executor_registry: ExecutorRegistry,
    orchestrator_registry: OrchestratorRegistry,
) -> tuple[_ChildCapability, ...]:
    children: list[_ChildCapability] = []
    index = 0
    for capability_id in definition.child_executors:
        executor = executor_registry.get(capability_id)
        inputs_by_name, outputs_by_name = lowering.index_port_declarations(
            inputs=executor.inputs,
            outputs=executor.outputs,
        )
        children.append(
            _ChildCapability(
                capability_id=executor.id,
                capability_kind="executor",
                definition=executor,
                stage_id=_child_stage_id(index, executor.id),
                inputs_by_name=inputs_by_name,
                outputs_by_name=outputs_by_name,
            )
        )
        index += 1
    for capability_id in definition.child_orchestrators:
        orchestrator = orchestrator_registry.get(capability_id)
        inputs_by_name, outputs_by_name = lowering.index_port_declarations(
            inputs=orchestrator.inputs,
            outputs=orchestrator.outputs,
        )
        children.append(
            _ChildCapability(
                capability_id=orchestrator.id,
                capability_kind="orchestrator",
                definition=orchestrator,
                stage_id=_child_stage_id(index, orchestrator.id),
                inputs_by_name=inputs_by_name,
                outputs_by_name=outputs_by_name,
            )
        )
        index += 1
    return tuple(children)


def _infer_linear_ports(
    producer_capability_id: str,
    producer_outputs: dict[str, Any],
    consumer_capability_id: str,
    consumer_inputs: dict[str, Any],
) -> tuple[str | None, str | None]:
    if not producer_outputs or not consumer_inputs:
        return None, None

    if len(producer_outputs) == 1 and len(consumer_inputs) == 1:
        return next(iter(producer_outputs)), next(iter(consumer_inputs))

    shared_names = sorted(set(producer_outputs) & set(consumer_inputs))
    if len(shared_names) == 1:
        port_name = shared_names[0]
        return port_name, port_name

    raise lowering.CompileUnsupportedFeature(
        "could not infer a unique port mapping between "
        f"{producer_capability_id!r} outputs {sorted(producer_outputs)} and "
        f"{consumer_capability_id!r} inputs {sorted(consumer_inputs)}"
    )


def _child_stage_id(index: int, capability_id: str) -> str:
    safe_capability_id = capability_id.replace("/", "_")
    return f"child_{index:02d}_{safe_capability_id}"


__all__ = [
    "compile_folder_orchestrator",
    "compile_orchestrator_definition",
    "compile_orchestrator_manifest",
    "lower_orchestrator_definition",
]
