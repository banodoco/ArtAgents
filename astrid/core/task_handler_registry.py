"""Neutral registry for explicitly composed task-handler bindings.

The registry is deliberately outside both the kernel execution service and
the Reigh integration package. Concrete bindings can register themselves
without making ``astrid.core.integrations`` import the execution service;
the service only resolves factories already installed by composition.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from astrid.core.contracts.errors import AstridError


class TaskExecutorError(AstridError):
    """Base error for task-handler registration and resolution."""


_FACTORIES: dict[str, Callable[[], Any]] = {}


def register_task_handler(binding: str, factory: Callable[[], Any]) -> None:
    """Register one explicit handler factory, rejecting silent overrides."""

    if not isinstance(binding, str) or not binding:
        raise TaskExecutorError("binding must be a non-empty string")
    if not callable(factory):
        raise TaskExecutorError("factory must be callable")
    existing = _FACTORIES.get(binding)
    if existing is not None and existing is not factory:
        raise TaskExecutorError(
            f"binding {binding!r} already has a registered handler factory"
        )
    _FACTORIES[binding] = factory


def resolve_registered_task_handler(binding: str) -> Any | None:
    """Return a registered handler instance, or ``None`` when uncomposed."""

    factory = _FACTORIES.get(binding)
    return factory() if factory is not None else None
