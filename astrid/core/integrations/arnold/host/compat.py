"""Arnold compatibility surface for the host package.

This module is the only host submodule allowed to import Arnold runtime
symbols. It validates the Arnold contract eagerly when this module is
imported, while the rest of Astrid remains Arnold-free until an explicit
``--engine arnold`` path reaches the host.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import is_dataclass
from typing import Any

_REQUIRED_SYMBOLS = (
    "RuntimeEnvelope",
    "ResumeCursorRef",
    "AdvanceOutcome",
    "CheckpointOutcome",
    "StepwiseDriver",
    "PipelineBuilder",
    "Stage",
    "ParallelStage",
    "Edge",
    "Suspension",
    "StepContext",
    "ExecutorHooks",
    "StepInvocation",
    "ContractResult",
    "ContractStatus",
    "PipelineVerdict",
    "persist_resume_cursor",
    "read_resume_cursor",
)

_OPTIONAL_SYMBOLS = (
    "EvidenceArtifactRef",
    "Provenance",
    "StepResult",
    "StepInvocationAdapter",
    "StepInvocationAdapterRegistry",
    "ContentValidatorRegistry",
    "no_op_content_validator",
)


def _has_field(obj: Any, field_name: str) -> bool:
    if is_dataclass(obj):
        return field_name in getattr(obj, "__dataclass_fields__", {})
    annotations = getattr(obj, "__annotations__", {})
    if field_name in annotations:
        return True
    return hasattr(obj, field_name)


def _field_type(obj: Any, field_name: str) -> Any:
    dataclass_fields = getattr(obj, "__dataclass_fields__", {})
    if field_name in dataclass_fields:
        return dataclass_fields[field_name].type
    annotations = getattr(obj, "__annotations__", {})
    if field_name in annotations:
        return annotations[field_name]
    value = getattr(obj, field_name, None)
    return None if value is None else type(value)


def _validate_driver_signature(driver_type: Any, method_name: str, expected: tuple[str, ...]) -> str | None:
    method = getattr(driver_type, method_name, None)
    if method is None:
        return f"StepwiseDriver missing method '{method_name}'"
    try:
        parameters = tuple(inspect.signature(method).parameters)
    except (TypeError, ValueError):
        return f"StepwiseDriver.{method_name} has no inspectable signature"
    if parameters[: len(expected)] != expected:
        return (
            f"StepwiseDriver.{method_name} signature starts with {parameters!r}; "
            f"expected prefix {expected!r}"
        )
    return None


def _load_contract() -> dict[str, Any]:
    try:
        pipeline = importlib.import_module("arnold.pipeline")
    except ImportError as exc:
        raise ImportError(
            "The Astrid Arnold host requires the 'arnold' package. "
            "Install it with: pip install arnold. "
            "The rest of Astrid remains fully functional without Arnold."
        ) from exc

    contract: dict[str, Any] = {}
    problems: list[str] = []

    for name in _REQUIRED_SYMBOLS:
        if not hasattr(pipeline, name):
            problems.append(f"missing symbol arnold.pipeline.{name}")
            continue
        contract[name] = getattr(pipeline, name)

    for name in _OPTIONAL_SYMBOLS:
        if hasattr(pipeline, name):
            contract[name] = getattr(pipeline, name)

    runtime_envelope = contract.get("RuntimeEnvelope")
    if runtime_envelope is not None:
        missing = [name for name in ("run_id", "artifact_root", "resume_cursor", "cross_cutting") if not _has_field(runtime_envelope, name)]
        if missing:
            problems.append(f"RuntimeEnvelope missing field(s): {', '.join(missing)}")
        cross_cutting_type = _field_type(runtime_envelope, "cross_cutting")
        if cross_cutting_type is None:
            problems.append("RuntimeEnvelope.cross_cutting has no inspectable type")
        else:
            cross_missing = [name for name in ("cost", "lineage") if not _has_field(cross_cutting_type, name)]
            if cross_missing:
                problems.append(
                    "RuntimeEnvelope.cross_cutting missing field(s): "
                    + ", ".join(cross_missing)
                )

    for type_name, required_fields in (
        ("StepContext", ("inputs", "hook_extensions")),
        ("ContractResult", ("suspension",)),
        ("Suspension", ("resume_input_schema",)),
    ):
        exported = contract.get(type_name)
        if exported is None:
            continue
        missing = [name for name in required_fields if not _has_field(exported, name)]
        if missing:
            problems.append(f"{type_name} missing field(s): {', '.join(missing)}")

    driver_type = contract.get("StepwiseDriver")
    if driver_type is not None:
        for method_name, expected in (
            ("advance", ("self", "envelope")),
            ("checkpoint", ("self", "envelope")),
            ("resume", ("self", "envelope", "cursor")),
        ):
            problem = _validate_driver_signature(driver_type, method_name, expected)
            if problem:
                problems.append(problem)

    if problems:
        details = "\n".join(f"- {problem}" for problem in problems)
        raise ImportError(
            "The installed 'arnold' package does not satisfy the Astrid Arnold "
            f"host contract:\n{details}\n"
            "Use a compatible Arnold package/worktree. Ordinary Astrid imports "
            "remain supported without Arnold."
        )

    return contract


_CONTRACT = _load_contract()


class ArnoldCompat:
    """Centralized namespace for validated Arnold host symbols."""


for _name, _value in _CONTRACT.items():
    setattr(ArnoldCompat, _name, _value)

compat = ArnoldCompat()

__all__ = ["ArnoldCompat", "compat", *_REQUIRED_SYMBOLS, *_OPTIONAL_SYMBOLS]

for _name in _REQUIRED_SYMBOLS + _OPTIONAL_SYMBOLS:
    if _name in _CONTRACT:
        globals()[_name] = _CONTRACT[_name]
