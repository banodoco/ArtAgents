"""Executor runtime resolution and argv construction."""

from __future__ import annotations


def resolve_executor_runtime_module(executor_id: str) -> str:
    """Resolve one qualified executor id to its runtime module.

    Resolution remains uncached so registry edits and capability
    re-registration are observable by callers.
    """
    if not isinstance(executor_id, str) or executor_id.count(".") != 1:
        raise ValueError(
            f"executor id must be qualified as '<pack>.<executor>', got {executor_id!r}"
        )
    from astrid.core.execution.executor.registry import load_default_registry

    registry = load_default_registry()
    executor = registry.get(executor_id)
    runtime_module = executor.metadata.get("runtime_module")
    if not isinstance(runtime_module, str) or not runtime_module:
        raise ValueError(f"executor {executor.id!r} is missing metadata.runtime_module")
    return runtime_module


def executor_argv(executor_id: str, python_exec: str) -> list[str]:
    """Return argv tokens for a qualified executor's module entrypoint."""
    return [python_exec, "-m", resolve_executor_runtime_module(executor_id)]
