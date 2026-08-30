"""Canonical orchestrator framework APIs.

Runner helpers are lazy so manifest discovery does not import local project
run bookkeeping or the legacy in-process execution path.
"""

from __future__ import annotations

import importlib

from .api import OrchestratorSpec, orchestrator
from .folder import load_folder_orchestrator, load_folder_orchestrators
from .registry import (
    OrchestratorRegistry,
    OrchestratorRegistryError,
    load_default_registry,
    load_pack_orchestrators,
)
from .schema import (
    CachePolicy,
    CommandSpec,
    IsolationMetadata,
    OrchestratorDefinition,
    OrchestratorValidationError,
    Output,
    Port,
    RuntimeSpec,
    load_orchestrator_manifest,
    to_capability_handle,
    validate_orchestrator_definition,
)

__all__ = [
    "CachePolicy",
    "CommandSpec",
    "IsolationMetadata",
    "OrchestratorDefinition",
    "OrchestratorPlan",
    "OrchestratorPlanStep",
    "OrchestratorRegistry",
    "OrchestratorRegistryError",
    "OrchestratorRunError",
    "OrchestratorRunRequest",
    "OrchestratorRunResult",
    "OrchestratorRunnerError",
    "OrchestratorSpec",
    "OrchestratorValidationError",
    "Output",
    "Port",
    "RuntimeSpec",
    "build_orchestrator_command",
    "load_default_registry",
    "load_pack_orchestrators",
    "load_folder_orchestrator",
    "load_folder_orchestrators",
    "load_orchestrator_manifest",
    "orchestrator",
    "run_orchestrator",
    "to_capability_handle",
    "validate_orchestrator_definition",
]

_LAZY_EXPORTS = {
    "OrchestratorPlan": ("runner", "OrchestratorPlan"),
    "OrchestratorPlanStep": ("runner", "OrchestratorPlanStep"),
    "OrchestratorRunError": ("runner", "OrchestratorRunError"),
    "OrchestratorRunnerError": ("runner", "OrchestratorRunnerError"),
    "OrchestratorRunRequest": ("runner", "OrchestratorRunRequest"),
    "OrchestratorRunResult": ("runner", "OrchestratorRunResult"),
    "build_orchestrator_command": ("runner", "build_orchestrator_command"),
    "run_orchestrator": ("runner", "run_orchestrator"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    return getattr(importlib.import_module(f".{module_name}", __name__), attribute)
