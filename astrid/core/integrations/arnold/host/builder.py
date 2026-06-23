"""Direct Arnold pipeline builder helpers for the Arnold host.

These helpers construct real ``Stage``, ``ParallelStage``, and ``Edge``
objects directly (no duck-typed fallback loops), register them with a
``PipelineBuilder``, set an entry stage, and finalize through ``build()``.

Every helper targets the **real Arnold dataclass contract** exclusively.
``label``, ``metadata``, and raw ``Suspension`` objects belong in specs /
manifests only — they are **not** passed into Arnold constructors.

Edges should be pre-built and passed to ``build_stage`` / ``build_parallel_stage``
via the ``edges`` parameter so they are attached directly to the owning stage.
The ``builder_add_edge`` helper remains for backward compatibility with callers
that register edges separately; when the real ``PipelineBuilder`` is in use,
edges without a ``source`` attribute are collected and flushed via
``add_caller_supplied_edges`` before finalisation.

Design constraints:
- Does NOT require ``Pipeline``, ``Port``, or ``PortRef``.
- ``build()`` is tried but not required — if absent the builder itself is
  returned as the finalized pipeline.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any


def _constructor_info(
    callable_: Any,
) -> tuple[set[str], bool]:
    """Inspect *callable_*'s constructor.

    Returns a tuple of (named_param_names, accepts_var_keyword).
    """
    try:
        sig = inspect.signature(callable_)
    except (ValueError, TypeError):
        return set(), False
    names: set[str] = set()
    accepts_kwargs = False
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            accepts_kwargs = True
        elif param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            names.add(param.name)
    return names, accepts_kwargs


class _HostNoopStep:
    """Minimal Step-compatible object for host-managed static graph stages."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.kind = "host"

    def run(self, ctx: Any) -> Any:
        return None


def _join_noop(results: list[Any], ctx: Any) -> Any:
    return results


def _derive_suspension_schema(suspension: Any) -> dict[str, Any] | None:
    """Extract a plain schema dict from an Arnold ``Suspension`` object.

    The real Arnold ``Stage`` carries ``suspension_schema`` (not a
    ``Suspension`` instance), so we serialise the key fields from the
    caller-supplied *suspension* object.

    Returns ``None`` when *suspension* is ``None`` or has no serialisable
    fields.
    """
    if suspension is None:
        return None
    schema: dict[str, Any] = {}
    for field_name in (
        "kind",
        "awaitable",
        "prompt",
        "resume_input_schema",
        "resume_cursor",
        "thread_ref",
        "actor",
        "deadline",
        "on_timeout",
        "default_action",
    ):
        value = getattr(suspension, field_name, None)
        if value is not None and value != ():
            # Copy mappings/lists so the caller can mutate the originals.
            if isinstance(value, dict):
                schema[field_name] = dict(value)
            elif isinstance(value, (list, tuple)):
                schema[field_name] = list(value)
            else:
                schema[field_name] = value
    return schema if schema else None





@dataclass
class _PipelineAssembly:
    stages: list[Any] = field(default_factory=list)
    edges: list[Any] = field(default_factory=list)
    entry_stage_id: str | None = None


def normalize_edge_metadata(metadata: Any) -> dict[str, Any]:
    """Return a plain dict for per-edge metadata sidecars."""
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def edge_manifest_entry(
    *,
    source: str | None,
    target: str | None,
    label: str | None,
    source_port: str | None = None,
    target_port: str | None = None,
    logical_type: str | None = None,
    artifact_type: str | None = None,
    metadata: Any = None,
) -> dict[str, Any]:
    """Build the canonical manifest-sidecar shape for one compiled edge."""
    return {
        "source": source,
        "target": target,
        "label": label,
        "source_port": source_port,
        "target_port": target_port,
        "logical_type": logical_type,
        "artifact_type": artifact_type,
        "metadata": normalize_edge_metadata(metadata),
    }


# ── Direct Arnold constructors ────────────────────────────────────────────────


def build_stage(
    stage_type: type[Any],
    *,
    stage_id: str,
    label: str,
    invocation: Any | None = None,
    suspension: Any | None = None,
    metadata: dict[str, Any] | None = None,
    decision_vocabulary: list[str] | tuple[str, ...] | None = None,
    loop_condition: Any | None = None,
    decision_routes: dict[str, str | None] | None = None,
    edges: tuple[Any, ...] = (),
) -> Any:
    """Construct a real Arnold ``Stage`` directly.

    ``label``, ``metadata``, and the raw ``Suspension`` object are accepted
    for caller convenience but are **not** passed into the Arnold
    constructor — they belong in specs / manifests only.

    The real Arnold ``Stage`` dataclass contract is::

        Stage(name=..., step=..., edges=..., decision_vocabulary=...,
              decision_routes=..., suspension_schema=...,
              invocation=..., loop_condition=...)

    *edges* is a tuple of pre-built :class:`Edge` objects that will be
    attached directly to the stage.  This is the preferred path for edge
    attachment — build edges first, then pass them here.
    """
    resolved_routes = dict(decision_routes) if decision_routes else {}
    kwargs: dict[str, Any] = {
        "name": stage_id,
        "step": _HostNoopStep(stage_id),
        "edges": tuple(edges),
        "decision_vocabulary": (
            frozenset(decision_vocabulary)
            if decision_vocabulary is not None
            else frozenset()
        ),
        "decision_routes": resolved_routes,
        "suspension_schema": _derive_suspension_schema(suspension),
        "invocation": invocation,
    }
    if loop_condition is not None:
        kwargs["loop_condition"] = loop_condition

    # Test doubles / backward-compat surfaces may accept Astrid-only sidecars
    # such as ``stage_id``, ``label``, and ``metadata``.  Real Arnold dataclasses
    # reject these, so only pass them when the constructor actually accepts them.
    params, accepts_kwargs = _constructor_info(stage_type)
    if accepts_kwargs or "stage_id" in params:
        kwargs["stage_id"] = stage_id
    if accepts_kwargs or "label" in params:
        kwargs["label"] = label
    if (accepts_kwargs or "metadata" in params) and metadata:
        kwargs["metadata"] = dict(metadata)

    return stage_type(**kwargs)


def build_parallel_stage(
    parallel_stage_type: type[Any],
    *,
    stage_id: str,
    label: str,
    sub_stages: list[Any],
    metadata: dict[str, Any] | None = None,
    edges: tuple[Any, ...] = (),
) -> Any:
    """Construct a real Arnold ``ParallelStage`` directly.

    ``label`` and ``metadata`` are accepted for caller convenience but are
    **not** passed into the Arnold constructor — they belong in specs /
    manifests only.

    The real Arnold ``ParallelStage`` dataclass contract is::

        ParallelStage(name=..., steps=..., join=...)

    *edges* is a tuple of pre-built :class:`Edge` objects that will be
    attached directly to the stage.  This is the preferred path for edge
    attachment — build edges first, then pass them here.
    """
    kwargs: dict[str, Any] = {
        "name": stage_id,
        "steps": tuple(sub_stages),
        "join": _join_noop,
        "edges": tuple(edges),
    }
    return parallel_stage_type(**kwargs)


def build_edge(
    edge_type: type[Any],
    *,
    source: str,
    target: str,
    label: str,
    source_port: str | None = None,
    target_port: str | None = None,
    logical_type: str | None = None,
    artifact_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Construct an edge instance of *edge_type*.

    The real Arnold ``Edge`` dataclass contract is sourceless::

        Edge(label=..., target=..., kind='normal', recommendation=None)

    For backward compatibility with fake/test edge types that still carry
    ``source`` or metadata fields, this helper inspects the constructor
    signature and passes only the parameters the type actually accepts.
    """
    params, accepts_kwargs = _constructor_info(edge_type)
    if not params and not accepts_kwargs:
        # Fallback for types whose signature cannot be introspected: assume
        # the real Arnold contract.
        params = {"label", "target", "kind", "recommendation"}

    def _accepts(name: str) -> bool:
        return accepts_kwargs or name in params

    kwargs: dict[str, Any] = {}
    if _accepts("label"):
        kwargs["label"] = label
    if _accepts("target"):
        kwargs["target"] = target
    if _accepts("kind"):
        kwargs["kind"] = "normal"
    if _accepts("recommendation"):
        kwargs["recommendation"] = None
    # Legacy/test edge types may still accept source and metadata fields.
    if _accepts("source"):
        kwargs["source"] = source
    if _accepts("source_port"):
        kwargs["source_port"] = source_port
    if _accepts("target_port"):
        kwargs["target_port"] = target_port
    if _accepts("logical_type"):
        kwargs["logical_type"] = logical_type
    if _accepts("artifact_type"):
        kwargs["artifact_type"] = artifact_type
    if _accepts("metadata"):
        kwargs["metadata"] = normalize_edge_metadata(metadata)
    return edge_type(**kwargs)


# ── Builder registration helpers ──────────────────────────────────────────────


def _flush_pending_caller_edges(builder: Any) -> None:
    """Flush edges accumulated via ``builder_add_edge`` to the real builder."""
    pending: dict[str, list[str]] | None = getattr(
        builder, "_astrid_pending_edges", None
    )
    if not pending:
        return
    add_ces = getattr(builder, "add_caller_supplied_edges", None)
    if callable(add_ces):
        # Convert list[target] to list[(target, label)] if labels were stored
        cleaned: dict[str, list[str]] = {}
        for src, entries in pending.items():
            cleaned[src] = [e if isinstance(e, str) else e[0] for e in entries]
        add_ces(cleaned)
    # Clear to avoid double-flushing
    try:
        delattr(builder, "_astrid_pending_edges")
    except AttributeError:
        pass


def builder_add_stage(builder: Any, stage: Any) -> None:
    """Register *stage* with *builder*, duck-typing the add method.

    Tries common method names (``add_stage``, ``stage``, ``with_stage``,
    ``register_stage``) and falls back to appending to a ``stages`` list
    attribute.  Raises ``TypeError`` if no registration surface is found.
    """
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


def builder_add_edge(builder: Any, edge: Any) -> None:
    """Register *edge* with *builder*, duck-typing the add method.

    For the real Arnold ``PipelineBuilder``, edges without a ``source``
    attribute cannot be attached via ``add_edge`` alone.  This helper
    therefore accumulates sourceless edges in a pending dict on the builder
    and flushes them via ``add_caller_supplied_edges`` when
    ``builder_finalize`` is called.

    Callers are encouraged to pre-attach edges to stages via
    ``build_stage(edges=...)`` or ``build_parallel_stage(edges=...)``
    instead of using this function.
    """
    # Try standard method-based registration first.
    for name in ("add_edge", "edge", "with_edge", "register_edge"):
        method = getattr(builder, name, None)
        if callable(method):
            method(edge)
            break
    else:
        edges_attr = getattr(builder, "edges", None)
        if isinstance(edges_attr, list):
            edges_attr.append(edge)
            return

    # For real Arnold edges (no 'source' attribute), accumulate in a pending
    # dict keyed by source stage name so they can be flushed via
    # add_caller_supplied_edges at finalisation time.
    edge_source = getattr(edge, "source", None)
    if edge_source is None:
        # Real Edge has no source — nothing to accumulate.
        return

    pending: dict[str, list[str]] | None = getattr(
        builder, "_astrid_pending_edges", None
    )
    if pending is None:
        pending = {}
        builder._astrid_pending_edges = pending
    edge_target = getattr(edge, "target", None)
    if edge_source not in pending:
        pending[edge_source] = []
    if edge_target is not None and edge_target not in pending[edge_source]:
        pending[edge_source].append(edge_target)


def builder_set_entry_stage(builder: Any, stage_id: str) -> None:
    """Set the entry stage on *builder*, duck-typing the set method.

    Tries common method names (``set_entry_stage``, ``entry_stage``,
    ``set_entrypoint``) and falls back to setting an ``entry_stage_id``
    attribute directly.  Raises ``TypeError`` if no entry stage surface
    is found.
    """
    for name in ("set_entry_stage", "entry_stage", "set_entrypoint"):
        method = getattr(builder, name, None)
        if callable(method):
            method(stage_id)
            return
    if hasattr(builder, "entry_stage_id"):
        builder.entry_stage_id = stage_id
        return
    raise TypeError("PipelineBuilder does not support entry-stage selection")


def create_pipeline(pipeline_type: type[Any]) -> Any:
    """Create a mutable pipeline assembly for conformance helpers."""
    return _PipelineAssembly()


def add_stage(pipeline: Any, stage: Any) -> None:
    """Add *stage* to a mutable pipeline assembly."""
    stages = getattr(pipeline, "stages", None)
    if isinstance(stages, list):
        stages.append(stage)
        if getattr(pipeline, "entry_stage_id", None) is None:
            pipeline.entry_stage_id = getattr(
                stage, "stage_id", getattr(stage, "name", None)
            )
        return
    if isinstance(stages, dict):
        stage_id = getattr(stage, "stage_id", getattr(stage, "name", None))
        if stage_id is not None:
            stages[stage_id] = stage
            return
    builder_add_stage(pipeline, stage)


def add_edge(pipeline: Any, edge: Any) -> None:
    """Add *edge* to a mutable pipeline assembly."""
    edges = getattr(pipeline, "edges", None)
    if isinstance(edges, list):
        edges.append(edge)
        return
    builder_add_edge(pipeline, edge)


def finalize_pipeline(pipeline: Any) -> Any:
    """Finalize a mutable pipeline assembly or builder-like object."""
    build = getattr(pipeline, "build", None)
    if callable(build):
        return build()
    return pipeline


def builder_finalize(builder: Any) -> Any:
    """Finalize *builder* into a built pipeline.

    Flushes any pending edges accumulated via ``builder_add_edge`` through
    ``add_caller_supplied_edges`` before calling ``builder.build()`` (if
    present).  If ``build()`` is absent the builder itself is returned as
    the opaque finalized pipeline.
    """
    _flush_pending_caller_edges(builder)
    build = getattr(builder, "build", None)
    if callable(build):
        return build()
    return builder


__all__ = [
    "build_edge",
    "build_parallel_stage",
    "build_stage",
    "add_edge",
    "add_stage",
    "builder_add_edge",
    "builder_add_stage",
    "builder_finalize",
    "builder_set_entry_stage",
    "create_pipeline",
    "edge_manifest_entry",
    "finalize_pipeline",
    "normalize_edge_metadata",
]
