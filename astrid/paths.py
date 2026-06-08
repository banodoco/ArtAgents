"""Canonical root-path constants and executor runtime resolution.

This module is the public surface for PACKAGE_ROOT, REPO_ROOT, WORKSPACE_ROOT,
and the executor-argv utilities.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
WORKSPACE_ROOT = REPO_ROOT.parent


@lru_cache(maxsize=None)
def resolve_executor_runtime_module(script_name: str) -> str:
    """Resolve an executor id or legacy pipeline step name to its runtime module.

    Qualified ids resolve through the registry so aliases land on the canonical
    executor definition. Bare names remain supported only for legacy pipeline
    step dispatch via ``metadata.pipeline_step``.
    """
    stem = script_name[:-3] if script_name.endswith(".py") else script_name
    from astrid.core.executor.registry import load_default_registry

    registry = load_default_registry()
    if "." in stem:
        executor = registry.get(stem)
    else:
        candidates = [
            executor
            for executor in registry.list()
            if executor.metadata.get("pipeline_step") == stem
        ]
        if len(candidates) != 1:
            matches = ", ".join(executor.id for executor in candidates) or "none"
            raise ValueError(f"could not resolve executor step {stem!r}; matches: {matches}")
        executor = candidates[0]
    runtime_module = executor.metadata.get("runtime_module")
    if not isinstance(runtime_module, str) or not runtime_module:
        raise ValueError(f"executor {executor.id!r} is missing metadata.runtime_module")
    return runtime_module


def executor_argv(script_name: str, python_exec: str) -> list[str]:
    """Return argv tokens that invoke a pipeline executor's module entrypoint."""
    return [python_exec, "-m", resolve_executor_runtime_module(script_name)]
