"""Kernel task-executor boundary: injected local handlers (m2 plan step 9, T16).

This package defines the kernel/pack execution boundary without importing
any pack and without adding remote or provider execution:

- :class:`~astrid.core.task_executor.service.TaskHandler` is the injected
  protocol a pack-owned adapter implements (e.g. the ``timeline_visualize``
  adapter of plan step 14). Kernel code only ever sees this protocol, never
  a concrete pack class.
- :class:`~astrid.core.task_executor.service.ExecutionService` orchestrates
  one attempt execution: it starts the fenced attempt and records its
  assigned staging transaction id through the **caller-owned** unit of work,
  invokes the handler **outside SQLite** (no transaction is open while the
  handler runs), strictly validates the universal result manifest
  (T15), prepares media descriptors for every validated concrete file
  output, and routes any handler/validation/preparation failure through the
  fenced repository failure command — again inside a short caller-owned
  unit of work. The service never opens its own writer or transaction.

The public surface is re-exported from :mod:`astrid.core.task_executor`.
"""

from __future__ import annotations

from astrid.core.task_executor.service import (
    STAGING_TXN_ID_KEY,
    ExecutionResult,
    ExecutionService,
    HandlerExecutionError,
    PreparedExecution,
    PreparedOutput,
    TaskExecutorError,
    TaskHandler,
    register_task_handler,
    resolve_task_handler,
)


def __getattr__(name: str):
    """Load the pack-facing handler only when that compatibility export is used."""

    if name == "CapabilityTaskHandler":
        from astrid.core.task_executor.capability_handler import CapabilityTaskHandler

        globals()[name] = CapabilityTaskHandler
        return CapabilityTaskHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "STAGING_TXN_ID_KEY",
    "CapabilityTaskHandler",
    "ExecutionResult",
    "ExecutionService",
    "HandlerExecutionError",
    "PreparedExecution",
    "PreparedOutput",
    "TaskExecutorError",
    "TaskHandler",
    "register_task_handler",
    "resolve_task_handler",
]
