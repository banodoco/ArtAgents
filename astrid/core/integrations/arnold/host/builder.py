"""Duck-typed pipeline builder helpers for the Arnold host.

These helpers construct ``Stage``, ``ParallelStage``, ``Edge``, and
``Suspension`` objects, register them with a ``PipelineBuilder``, set
an entry stage where supported, and finalize through ``build()`` only
when present.

Every helper is duck-typed: it tries multiple kwarg shapes against the
imported Arnold type surface so that the caller does not need to know
which concrete attribute names the installed Arnold version uses.

Design constraints:
- Does NOT require ``Pipeline``, ``Port``, or ``PortRef``.
- Works with fake Arnold surfaces (e.g. test doubles injected into
  ``sys.modules['arnold.pipeline']``).
- ``build()`` is tried but not required — if absent the builder itself is
  returned as the finalized pipeline.
"""

from __future__ import annotations

from typing import Any


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
) -> Any:
    """Construct a Stage duck-typed against *stage_type*.

    Tries several kwarg shapes to accommodate different Arnold surface
    versions.  Raises ``TypeError`` if no shape succeeds.
    """
    kwargs_meta = dict(metadata or {})
    kwargs = {
        "stage_id": stage_id,
        "label": label,
        "invocation": invocation,
        "suspension": suspension,
        "metadata": kwargs_meta,
    }
    if decision_vocabulary is not None:
        kwargs["decision_vocabulary"] = tuple(decision_vocabulary)
    if loop_condition is not None:
        kwargs["loop_condition"] = loop_condition
    for candidate in (
        kwargs,
        {
            "id": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": kwargs_meta,
            **({"decision_vocabulary": tuple(decision_vocabulary)} if decision_vocabulary is not None else {}),
            **({"loop_condition": loop_condition} if loop_condition is not None else {}),
        },
        {
            "name": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": kwargs_meta,
            **({"decision_vocabulary": tuple(decision_vocabulary)} if decision_vocabulary is not None else {}),
            **({"loop_condition": loop_condition} if loop_condition is not None else {}),
        },
        {
            "stage_id": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": kwargs_meta,
        },
        {
            "id": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": kwargs_meta,
        },
        {
            "name": stage_id,
            "label": label,
            "invocation": invocation,
            "suspension": suspension,
            "metadata": kwargs_meta,
        },
    ):
        try:
            return stage_type(**candidate)
        except TypeError:
            continue
    raise TypeError(f"could not construct Stage for {stage_id!r}")


def build_parallel_stage(
    parallel_stage_type: type[Any],
    *,
    stage_id: str,
    label: str,
    sub_stages: list[Any],
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Construct a ParallelStage duck-typed against *parallel_stage_type*.

    Tries several attribute names for the sub-stage collection to
    accommodate different Arnold surface versions.  Raises ``TypeError``
    if no shape succeeds.
    """
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


def build_edge(
    edge_type: type[Any],
    *,
    source: str,
    target: str,
    label: str,
) -> Any:
    """Construct an Edge duck-typed against *edge_type*.

    Tries several kwarg shapes for source/target attribute names.
    Raises ``TypeError`` if no shape succeeds.
    """
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

    Tries common method names (``add_edge``, ``edge``, ``with_edge``,
    ``register_edge``) and falls back to appending to an ``edges`` list
    attribute.  Raises ``TypeError`` if no registration surface is found.
    """
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


def builder_finalize(builder: Any) -> Any:
    """Finalize *builder* into a built pipeline.

    Calls ``builder.build()`` if present; otherwise returns *builder*
    itself as the opaque finalized pipeline.  This supports fake Arnold
    surfaces that do not expose a ``build()`` method.
    """
    build = getattr(builder, "build", None)
    if callable(build):
        return build()
    return builder


__all__ = [
    "build_edge",
    "build_parallel_stage",
    "build_stage",
    "builder_add_edge",
    "builder_add_stage",
    "builder_finalize",
    "builder_set_entry_stage",
]
