"""Canonical executor framework APIs.

The package root is a discovery-safe facade.  Runner and dependency-install
helpers are loaded only when an explicit execution/install caller asks for
them; importing executor manifests must remain free of local project/run and
dynamic-install authority.
"""

from __future__ import annotations

import importlib

from .api import ExecutorSpec, executor
from .folder import (
    FolderExecutorError,
    discover_folder_executor_roots,
    load_folder_executor,
    load_folder_executors,
)
from .registry import (
    ExecutorRegistry,
    ExecutorRegistryError,
    load_default_registry,
    load_pack_executors,
)
from .schema import (
    CachePolicy,
    CommandSpec,
    ConditionSpec,
    ExecutorDefinition,
    ExecutorOutput,
    ExecutorPort,
    ExecutorValidationError,
    GraphMetadata,
    IsolationMetadata,
    load_executor_manifest,
    load_executor_manifest_definitions,
    to_capability_handle,
    validate_executor_definition,
)

__all__ = [
    "CachePolicy",
    "CommandSpec",
    "ConditionResult",
    "ConditionSpec",
    "ExecutorDefinition",
    "ExecutorInstallError",
    "ExecutorInstallPlan",
    "ExecutorInstallResult",
    "ExecutorOutput",
    "ExecutorPort",
    "ExecutorRegistry",
    "ExecutorRegistryError",
    "ExecutorRunRequest",
    "ExecutorRunResult",
    "ExecutorRunnerError",
    "ExecutorSpec",
    "ExecutorValidationError",
    "FolderExecutorError",
    "GraphMetadata",
    "IsolationMetadata",
    "build_executor_command",
    "build_executor_install_plan",
    "build_pipeline_context",
    "check_executor_binaries",
    "discover_folder_executor_roots",
    "evaluate_conditions",
    "executor",
    "executor_environment_path",
    "executor_python_path",
    "fetch_git_executor_manifest",
    "install_executor",
    "load_default_registry",
    "load_pack_executors",
    "load_executor_manifest",
    "load_executor_manifest_definitions",
    "load_folder_executor",
    "load_folder_executors",
    "run_executor",
    "to_capability_handle",
    "validate_executor_definition",
]

_LAZY_EXPORTS = {
    "ExecutorInstallError": ("install", "ExecutorInstallError"),
    "ExecutorInstallPlan": ("install", "ExecutorInstallPlan"),
    "ExecutorInstallResult": ("install", "ExecutorInstallResult"),
    "build_executor_install_plan": ("install", "build_executor_install_plan"),
    "executor_environment_path": ("install", "executor_environment_path"),
    "executor_python_path": ("install", "executor_python_path"),
    "fetch_git_executor_manifest": ("install", "fetch_git_executor_manifest"),
    "install_executor": ("install", "install_executor"),
    "ConditionResult": ("runner", "ConditionResult"),
    "ExecutorRunnerError": ("runner", "ExecutorRunnerError"),
    "ExecutorRunRequest": ("runner", "ExecutorRunRequest"),
    "ExecutorRunResult": ("runner", "ExecutorRunResult"),
    "build_executor_command": ("runner", "build_executor_command"),
    "build_pipeline_context": ("runner", "build_pipeline_context"),
    "check_executor_binaries": ("runner", "check_executor_binaries"),
    "evaluate_conditions": ("runner", "evaluate_conditions"),
    "run_executor": ("runner", "run_executor"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    return getattr(importlib.import_module(f".{module_name}", __name__), attribute)
