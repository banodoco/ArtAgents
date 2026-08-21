from __future__ import annotations

import argparse
import contextlib
import io
import json

from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.schema import ExecutorValidationError, validate_executor_definition
from astrid.core.execution.orchestrator.schema import (
    OrchestratorValidationError,
    validate_orchestrator_definition,
)

import pytest


def _executor_manifest(**overrides):
    data = {
        "id": "builtin.demo",
        "name": "Demo",
        "kind": "built_in",
        "version": "1.0",
        "description": "Demo executor.",
    }
    data.update(overrides)
    return data


def _orchestrator_manifest(**overrides):
    data = {
        "id": "video_editing.demo",
        "name": "Demo",
        "kind": "built_in",
        "version": "1.0",
        "runtime": {"kind": "python", "function": "main"},
        "description": "Demo orchestrator.",
    }
    data.update(overrides)
    return data


def test_executor_isolation_env_passthrough_round_trips_and_inspect_exposes_it() -> None:
    executor = validate_executor_definition(
        _executor_manifest(isolation={"env_passthrough": ["CUSTOM_PUBLIC_FLAG"]})
    )

    assert executor.isolation.env_passthrough == ("CUSTOM_PUBLIC_FLAG",)
    assert executor.to_dict()["isolation"]["env_passthrough"] == ["CUSTOM_PUBLIC_FLAG"]

    payload = executor.to_dict()
    assert payload["isolation"]["env_passthrough"] == ["CUSTOM_PUBLIC_FLAG"]


def test_orchestrator_isolation_env_passthrough_round_trips() -> None:
    orchestrator = validate_orchestrator_definition(
        _orchestrator_manifest(isolation={"env_passthrough": ["CUSTOM_PUBLIC_FLAG"]})
    )

    assert orchestrator.isolation.env_passthrough == ("CUSTOM_PUBLIC_FLAG",)
    assert orchestrator.to_dict()["isolation"]["env_passthrough"] == ["CUSTOM_PUBLIC_FLAG"]


def test_executor_isolation_env_passthrough_rejects_invalid_or_duplicate_names() -> None:
    for names in (["1BAD"], ["CUSTOM_PUBLIC_FLAG", "CUSTOM_PUBLIC_FLAG"]):
        with pytest.raises(ExecutorValidationError, match="env_passthrough"):
            validate_executor_definition(_executor_manifest(isolation={"env_passthrough": names}))


def test_orchestrator_isolation_env_passthrough_rejects_invalid_or_duplicate_names() -> None:
    for names in (["1BAD"], ["CUSTOM_PUBLIC_FLAG", "CUSTOM_PUBLIC_FLAG"]):
        with pytest.raises(OrchestratorValidationError, match="env_passthrough"):
            validate_orchestrator_definition(_orchestrator_manifest(isolation={"env_passthrough": names}))
