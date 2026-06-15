"""Authoring facade for Arnold pipeline construction.

Provides a stable, testable API surface for building Arnold pipeline graphs
without coupling callers to the internal lowering module or compat layer.

Design constraints (settled — do not re-litigate):

* **AF1:** Every function returns either ``lowering.StageSpec`` or a pipeline
  object — never dicts or intermediate representations.
* **AF2:** ``port()`` and ``artifact_ref()`` are thin constructors — no
  validation or side effects.
* **AF3:** ``executor_step()`` normalizes typed ``consumes``/``produces``
  dicts into the adapter metadata shape that ``lowering.adapter_stage_spec``
  expects.
* **AF4:** ``wrapper_step()`` mirrors ``lowering.add_wrapper_stage``
  semantics with a positional-stage-list API for inline construction.
* **AF5:** ``build_workflow()`` is the single entry point for linear
  orchestrator pipelines — it accepts a flat list of executor_step results,
  stitches edges, appends halt, and returns a compiled Arnold pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Thin typed-port constructors (AF2) ────────────────────────────────────────


@dataclass(frozen=True)
class Port:
    """A typed input port declaration for an executor step."""

    name: str
    artifact_type: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def port(
    name: str,
    *,
    artifact_type: str | None = None,
    description: str | None = None,
    **metadata: Any,
) -> Port:
    """Create a typed input port declaration.

    >>> port("video", artifact_type="video/mp4")
    Port(name='video', artifact_type='video/mp4', ...)
    """
    return Port(
        name=name,
        artifact_type=artifact_type,
        description=description,
        metadata=dict(metadata),
    )


@dataclass(frozen=True)
class ArtifactRef:
    """A reference to a produced artifact from a previous step."""

    name: str
    path: str
    artifact_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def artifact_ref(
    name: str,
    path: str,
    *,
    artifact_type: str | None = None,
    **metadata: Any,
) -> ArtifactRef:
    """Create an artifact reference.

    >>> artifact_ref("template_output", "ados-sunday-template.json")
    ArtifactRef(name='template_output', path='ados-sunday-template.json', ...)
    """
    return ArtifactRef(
        name=name,
        path=path,
        artifact_type=artifact_type,
        metadata=dict(metadata),
    )


# ── Stage constructors (AF3, AF4) ─────────────────────────────────────────────


def executor_step(
    stage_id: str,
    *,
    segment_id: str,
    adapter: str = "local",
    command: str | None = None,
    produces: dict[str, str] | None = None,
    consumes: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Declare an executor-backed linear stage.

    Returns a lightweight descriptor dict (not a ``StageSpec``).  The dict is
    consumed by ``build_workflow()`` which lowers it through
    ``lowering.adapter_stage_spec``.

    Parameters
    ----------
    stage_id:
        Unique stage identifier within the workflow segment.
    segment_id:
        The orchestrator workflow id (e.g. ``"video_editing.event_talks"``).
    adapter:
        Adapter kind — ``"local"``, ``"manual"``, ``"remote-artifact"``, or
        an executor-backed capability id.
    command:
        Shell command string for the step (passed through to the invocation).
    produces:
        Mapping of ``{produces_name: output_path}`` (relative to produces_root).
        Populated as typed port metadata on the adapter stage.
    consumes:
        Mapping of ``{input_name: state_ref}`` for state binding.
    metadata:
        Additional stage metadata merged into the adapter config.
    label:
        Human-readable label (defaults to *stage_id* when ``None``).
    """
    return {
        "kind": "executor",
        "stage_id": stage_id,
        "segment_id": segment_id,
        "adapter": adapter,
        "command": command,
        "produces": dict(produces or {}),
        "consumes": dict(consumes or {}),
        "metadata": dict(metadata or {}),
        "label": label or stage_id,
    }


def wrapper_step(
    stage_id: str,
    *,
    segment_id: str,
    path: tuple[str, ...],
    adapter: str = "orchestrator",
    command: str | None = None,
    produces: dict[str, str] | None = None,
    consumes: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Declare a wrapper-runtime stage (for orchestrator subcommands).

    Returns a descriptor dict consumed by ``build_workflow()`` for
    hybrid pipelines that mix executor and wrapper stages.

    Parameters
    ----------
    stage_id:
        Unique stage identifier within the workflow segment.
    segment_id:
        The orchestrator workflow id.
    path:
        Plan-style path tuple (e.g. ``("video_editing.event_talks", "render")``).
    adapter:
        Adapter kind — typically ``"orchestrator"`` for wrapper stages.
    command:
        Subcommand name for the wrapper runtime.
    produces:
        Mapping of ``{produces_name: output_path}``.
    consumes:
        Mapping of ``{input_name: state_ref}``.
    metadata:
        Additional stage metadata.
    label:
        Human-readable label (defaults to *stage_id*).
    """
    return {
        "kind": "wrapper",
        "stage_id": stage_id,
        "segment_id": segment_id,
        "path": path,
        "adapter": adapter,
        "command": command,
        "produces": dict(produces or {}),
        "consumes": dict(consumes or {}),
        "metadata": dict(metadata or {}),
        "label": label or stage_id,
    }


def opaque_stage_orchestrator(
    stage_id: str,
    *,
    segment_id: str,
    path: str | tuple[str, ...],
    adapter: str,
    command: str,
    produces: dict[str, str] | None = None,
    consumes: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
    label: str | None = None,
) -> "lowering.StageSpec":  # type: ignore[name-defined]  # noqa: F821
    """Create an opaque single-stage wrapper for legacy monolith orchestrators.

    Returns a fully-formed ``lowering.StageSpec`` that wraps a monolithic
    orchestrator command behind a single Arnold stage.  This is the
    escape hatch for training packs (dataset_build, training_run) that have
    not yet been broken into fine-grained executor steps.

    The returned StageSpec carries wrapper metadata identifying the adapter,
    command, and path — enough for the Arnold runtime to dispatch the legacy
    orchestrator as a single opaque step.

    Parameters
    ----------
    stage_id:
        Unique stage identifier (e.g. ``"dataset-build"``).
    segment_id:
        The orchestrator workflow id (e.g. ``"training.dataset_build"``).
    path:
        Plan-style path — a tuple or dot-separated string.
    adapter:
        Adapter kind (e.g. ``"orchestrator"``, ``"local"``).
    command:
        The monolithic command string to execute.
    produces:
        Mapping of ``{produces_name: output_path}``.
    consumes:
        Mapping of ``{input_name: state_ref}``.
    metadata:
        Additional metadata merged into the wrapper spec.
    label:
        Human-readable label (defaults to *stage_id*).
    """
    from astrid.core.integrations.arnold.session import lowering

    path_tuple: tuple[str, ...]
    if isinstance(path, str):
        path_tuple = tuple(path.split("."))
    else:
        path_tuple = tuple(path)

    wrapper_metadata: dict[str, Any] = {
        "segment_id": segment_id,
        "stage_id": stage_id,
        "source_plan_path": list(path_tuple),
        "adapter": adapter,
        "command": command,
        "wrapper_runtime": "command",
        "wrapper_orchestrator_id": segment_id,
        "wrapper_subcommand": stage_id,
    }
    if produces:
        wrapper_metadata["produces"] = list(produces.values())
    if consumes:
        wrapper_metadata["consumes"] = dict(consumes)
    if metadata:
        wrapper_metadata.update(metadata)
    wrapper_metadata.setdefault("vocabulary", ["next"])

    return lowering.StageSpec(
        stage_id=stage_id,
        label=label or stage_id,
        invocation=None,
        suspension=None,
        metadata=wrapper_metadata,
        decision_vocabulary=("next",),
    )


# ── Workflow compiler (AF5) ───────────────────────────────────────────────────


def build_workflow(
    stages: list[dict[str, Any]],
    *,
    segment_id: str,
    project: str = "default",
    run_root_path: str | Path = "/tmp/arnold-workflow-run",
    state: dict[str, Any] | None = None,
) -> Any:
    """Compile a list of executor/wrapper step descriptors into an Arnold pipeline.

    This is the single entry point for linear orchestrator pipelines.  It:

    1. Lowers each descriptor through ``lowering.adapter_stage_spec`` (executor)
       or ``lowering.add_wrapper_stage`` (wrapper).
    2. Stitches linear ``next`` edges between consecutive stages.
    3. Appends a ``halt`` stage.
    4. Builds and returns a compiled Arnold pipeline via ``lowering.build_pipeline``.

    Parameters
    ----------
    stages:
        Ordered list of step descriptors from ``executor_step()`` or
        ``wrapper_step()``.
    segment_id:
        The orchestrator workflow id.
    project:
        Project slug for adapter metadata.
    run_root_path:
        Run root directory for artifact placement.
    state:
        Initial state dict for adapter bindings.
    """
    from pathlib import Path

    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.session import lowering

    resolved_run_root = Path(run_root_path)
    active_state = dict(state or {})

    stage_specs: list[lowering.StageSpec] = []

    for desc in stages:
        kind = desc.get("kind", "executor")
        sid = desc["stage_id"]
        seg = desc.get("segment_id", segment_id)
        lbl = desc.get("label", sid)
        meta = dict(desc.get("metadata", {}))

        if kind == "wrapper":
            lowering.add_wrapper_stage(
                stage_specs,
                stage_id=sid,
                label=lbl,
                segment_id=seg,
                path=desc.get("path", (seg, sid)),
                runtime="command",
                adapter=desc.get("adapter", "orchestrator"),
                command=desc.get("command"),
                metadata=meta,
            )
        else:
            executor_id = desc.get("adapter", "local")
            if not executor_id.startswith("task.") and executor_id not in (
                "local",
                "manual",
                "remote-artifact",
            ):
                executor_id = f"task.{executor_id}" if "." not in executor_id else executor_id
            else:
                executor_id = f"task.{executor_id}"

            extra_meta: dict[str, Any] = {}
            if desc.get("produces"):
                extra_meta["produces"] = [
                    {"name": name, "path": path}
                    for name, path in desc["produces"].items()
                ]
            if desc.get("consumes"):
                extra_meta["consumes"] = dict(desc["consumes"])
            extra_meta.update(meta)
            extra_meta.setdefault("vocabulary", ["next"])

            stage_spec = lowering.adapter_stage_spec(
                stage_id=sid,
                label=lbl,
                executor_id=executor_id,
                segment_id=seg,
                project=project,
                run_root_path=resolved_run_root,
                state=active_state,
                capability_kind="executor",
                source_orchestrator_id=seg,
                metadata=extra_meta,
            )
            stage_specs.append(stage_spec)

    # Stitch linear edges
    edge_specs: list[lowering.EdgeSpec] = []
    for i in range(len(stage_specs) - 1):
        edge_specs.append(
            lowering.EdgeSpec(
                source=stage_specs[i].stage_id,
                target=stage_specs[i + 1].stage_id,
                label="next",
            )
        )

    # Append halt
    had_prior_stages = bool(stage_specs)
    if had_prior_stages:
        last_stage_id = stage_specs[-1].stage_id
    stage_specs.append(lowering.halt_stage())
    if had_prior_stages:
        edge_specs.append(
            lowering.EdgeSpec(
                source=last_stage_id,
                target=lowering.HALT_STAGE_ID,
                label="next",
            )
        )

    entry_id = stage_specs[0].stage_id if stage_specs else lowering.HALT_STAGE_ID

    lowered = lowering.LoweredSegment(
        entry_stage_id=entry_id,
        ordered_stage_specs=tuple(stage_specs),
        ordered_edge_specs=tuple(edge_specs),
        plan_hash=f"orchestrator:{segment_id}@1.0",
        diagnostics=(
            f"compiled linear orchestrator {segment_id}",
            f"stages={len(stage_specs)}",
            f"edges={len(edge_specs)}",
        ),
    )
    return lowering.build_pipeline(lowered, compat=compat)


__all__ = [
    "ArtifactRef",
    "Port",
    "artifact_ref",
    "build_workflow",
    "executor_step",
    "opaque_stage_orchestrator",
    "port",
    "wrapper_step",
]
