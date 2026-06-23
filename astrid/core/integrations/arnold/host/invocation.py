"""StepInvocation metadata helpers for the Arnold host.

These helpers define the canonical metadata wire format that the existing
Astrid StepInvocation adapter already consumes.  The host shapes build
their adapter-backed stages through these functions so the metadata
contract stays centralized and testable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

STEP_INVOCATION_KIND = "model"
HOST_CONTROL_KINDS: frozenset[str] = frozenset(
    {"pattern_select", "dynamic_fanout", "vote_judge", "group_boundary", "halt"}
)
HUMAN_DECISION_ACTIONS: frozenset[str] = frozenset({"approve", "reject"})
HUMAN_DECISION_ROUTES: dict[str, str] = {"approve": "next", "reject": "repeat"}
HUMAN_RESUME_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": "string", "enum": sorted(HUMAN_DECISION_ACTIONS)},
                "notes": {"type": "string"},
                "state_patch": {"type": "object"},
            },
            "required": ["action"],
        },
        "produces_reverify": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "artifacts": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "inputs": {"type": "object"},
            },
        },
    },
    "required": ["decision"],
}


class HumanResumePayloadError(ValueError):
    """Raised when a human resume payload violates the documented wire format."""


@dataclass(frozen=True)
class InvocationTemplate:
    """Host-owned template for one adapter-backed workflow stage."""

    workflow_id: str
    stage_id: str
    executor_id: str | None = None
    adapter_invocation_id: str | None = None
    control_kind: str | None = None
    input_map: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    mode: str = "inline"
    requires_ack: bool = False
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_control(self) -> bool:
        return self.control_kind is not None

    @property
    def is_invocable(self) -> bool:
        return self.executor_id is not None or self.adapter_invocation_id is not None


@dataclass(frozen=True)
class StepInvocationMetadata:
    """Metadata-compatible fallback used when Arnold is not installed.

    Authoring and topology tests only need the invocation metadata sidecar.
    Real Arnold runtime paths still receive ``arnold.pipeline.StepInvocation``
    when the package is present.
    """

    kind: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


def build_adapter_metadata(
    *,
    executor_id: str,
    inputs: dict[str, Any] | None = None,
    input_map: dict[str, str] | None = None,
    state: dict[str, Any] | None = None,
    mode: str = "inline",
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
    requires_ack: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Build the canonical adapter_config payload for the Astrid adapter."""
    config: dict[str, Any] = {
        "executor_id": executor_id,
        "mode": mode,
        "requires_ack": requires_ack,
        **extra,
    }
    if inputs is not None:
        config["inputs"] = dict(inputs)
    if input_map is not None:
        config["input_map"] = dict(input_map)
    if state is not None:
        config["state"] = dict(state)
    if project is not None:
        config["project"] = project
    if run_root is not None:
        config["run_root"] = run_root
    if artifact_root is not None:
        config["artifact_root"] = artifact_root
    if cas_project_dir is not None:
        config["cas_project_dir"] = cas_project_dir
    return config


def build_step_metadata(
    *,
    executor_id: str,
    inputs: dict[str, Any] | None = None,
    input_map: dict[str, str] | None = None,
    state: dict[str, Any] | None = None,
    mode: str = "inline",
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
    requires_ack: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Build a StepInvocation metadata payload with nested adapter_config."""
    return {
        "adapter_config": build_adapter_metadata(
            executor_id=executor_id,
            inputs=inputs,
            input_map=input_map,
            state=state,
            mode=mode,
            project=project,
            run_root=run_root,
            artifact_root=artifact_root,
            cas_project_dir=cas_project_dir,
            requires_ack=requires_ack,
            **extra,
        )
    }


def build_step_invocation(
    *,
    executor_id: str,
    inputs: dict[str, Any] | None = None,
    input_map: dict[str, str] | None = None,
    state: dict[str, Any] | None = None,
    mode: str = "inline",
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
    requires_ack: bool = False,
    kind: str = STEP_INVOCATION_KIND,
    **extra: Any,
) -> Any:
    """Construct a StepInvocation-like object with canonical metadata."""
    metadata = build_step_metadata(
        executor_id=executor_id,
        inputs=inputs,
        input_map=input_map,
        state=state,
        mode=mode,
        project=project,
        run_root=run_root,
        artifact_root=artifact_root,
        cas_project_dir=cas_project_dir,
        requires_ack=requires_ack,
        **extra,
    )

    try:
        from astrid.core.integrations.arnold.host.compat import compat
    except ImportError:
        return StepInvocationMetadata(kind=kind, metadata=metadata)

    return compat.StepInvocation(
        kind=kind,
        metadata=metadata,
    )


class CompiledInvocationTemplateError(ValueError):
    """Raised when a compiled pipeline cannot produce host invocation templates."""


def invocation_templates_from_compiled_pipeline(
    workflow_id: str,
    pipeline: Any,
) -> dict[str, InvocationTemplate]:
    """Derive host invocation templates from an already-compiled Arnold pipeline.

    The function is intentionally duck-typed and does not import Arnold. It
    inspects compiled stage metadata, classifies synthetic/control stages as
    host controls, and requires every executable stage to expose either a real
    executor id or an adapter invocation id.
    """
    if not workflow_id:
        raise CompiledInvocationTemplateError("workflow_id must be non-empty")

    stages = _pipeline_stages(pipeline)
    if not stages:
        raise CompiledInvocationTemplateError(
            f"compiled pipeline for {workflow_id!r} has no stages"
        )

    templates: dict[str, InvocationTemplate] = {}
    for stage in stages:
        stage_id = _stage_id(stage)
        if not stage_id:
            raise CompiledInvocationTemplateError(
                f"compiled pipeline for {workflow_id!r} contains a stage without stage_id"
            )
        if stage_id in templates:
            raise CompiledInvocationTemplateError(
                f"compiled pipeline for {workflow_id!r} contains duplicate stage {stage_id!r}"
            )
        metadata = _stage_metadata(stage, pipeline)
        control_kind = _control_kind(stage_id, metadata)
        if control_kind is not None:
            templates[stage_id] = InvocationTemplate(
                workflow_id=workflow_id,
                stage_id=stage_id,
                control_kind=control_kind,
                extra_metadata=_control_metadata(metadata, control_kind),
            )
            continue

        adapter_config = _adapter_config(stage, metadata)
        executor_id = _string_value(adapter_config.get("executor_id"))
        adapter_invocation_id = _adapter_invocation_id(metadata)
        if executor_id is None and adapter_invocation_id is None:
            raise CompiledInvocationTemplateError(
                f"compiled pipeline for {workflow_id!r} stage {stage_id!r} is "
                "executable but exposes neither adapter_config.executor_id, "
                "metadata.executor_id, nor wrapper adapter invocation metadata"
            )

        templates[stage_id] = InvocationTemplate(
            workflow_id=workflow_id,
            stage_id=stage_id,
            executor_id=executor_id,
            adapter_invocation_id=adapter_invocation_id,
            input_map=dict(adapter_config.get("input_map") or {}),
            inputs=dict(adapter_config.get("inputs") or {}),
            mode=_string_value(adapter_config.get("mode")) or "inline",
            requires_ack=bool(adapter_config.get("requires_ack", False)),
            extra_metadata=_compiled_extra_metadata(metadata, adapter_config),
        )
    return templates


def _stage_id(stage: Any) -> str | None:
    return _string_value(
        getattr(stage, "stage_id", None)
        or getattr(stage, "id", None)
        or getattr(stage, "name", None)
    )


def _pipeline_stages(pipeline: Any) -> tuple[Any, ...]:
    stages = getattr(pipeline, "stages", ()) or ()
    if isinstance(stages, Mapping):
        return tuple(stages.values())
    return tuple(stages)


def _stage_metadata(stage: Any, pipeline: Any) -> dict[str, Any]:
    metadata = getattr(stage, "metadata", None)
    if isinstance(metadata, dict) and metadata:
        return dict(metadata)
    stage_id = _stage_id(stage)
    stage_specs = getattr(pipeline, "_astrid_stage_specs", None)
    if stage_specs is not None and stage_id:
        for spec in stage_specs:
            if spec.stage_id == stage_id and isinstance(spec.metadata, dict):
                return dict(spec.metadata)
    return {}


def _adapter_config(stage: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    config = metadata.get("adapter_config")
    if not isinstance(config, dict):
        invocation = getattr(stage, "invocation", None)
        invocation_metadata = getattr(invocation, "metadata", None)
        if isinstance(invocation_metadata, dict):
            config = invocation_metadata.get("adapter_config")
    normalized = dict(config) if isinstance(config, dict) else {}
    if "executor_id" not in normalized:
        executor_id = _string_value(metadata.get("executor_id"))
        if executor_id is not None:
            normalized["executor_id"] = executor_id
    return normalized


def _control_kind(stage_id: str, metadata: dict[str, Any]) -> str | None:
    synthetic_kind = _string_value(metadata.get("synthetic_kind"))
    if synthetic_kind in HOST_CONTROL_KINDS:
        return synthetic_kind
    group_boundary = _string_value(metadata.get("group_boundary"))
    if group_boundary is not None:
        return "group_boundary"
    if stage_id == "halt" or metadata.get("terminal") is True:
        return "halt"
    return None


def _control_metadata(metadata: dict[str, Any], control_kind: str) -> dict[str, Any]:
    control_metadata = dict(metadata)
    control_metadata["host_control_kind"] = control_kind
    control_metadata.pop("executor_id", None)
    adapter_config = control_metadata.get("adapter_config")
    if isinstance(adapter_config, dict):
        adapter_copy = dict(adapter_config)
        adapter_copy.pop("executor_id", None)
        control_metadata["adapter_config"] = adapter_copy
    return control_metadata


def _adapter_invocation_id(metadata: dict[str, Any]) -> str | None:
    adapter = _string_value(metadata.get("adapter"))
    command = _string_value(metadata.get("command"))
    if adapter is not None and command is not None:
        return f"{adapter}:{command}"
    wrapper_subcommand = _string_value(metadata.get("wrapper_subcommand"))
    wrapper_orchestrator_id = _string_value(metadata.get("wrapper_orchestrator_id"))
    if adapter is not None and wrapper_orchestrator_id is not None and wrapper_subcommand is not None:
        return f"{adapter}:{wrapper_orchestrator_id}:{wrapper_subcommand}"
    return None


def _compiled_extra_metadata(
    metadata: dict[str, Any],
    adapter_config: dict[str, Any],
) -> dict[str, Any]:
    extra = dict(metadata)
    extra.pop("adapter_config", None)
    extra.pop("executor_id", None)
    for key in ("workflow_id", "stage_id", "mode", "requires_ack"):
        extra.pop(key, None)
    extra["compiled_pipeline"] = True
    if "adapter_config" in metadata:
        extra["compiled_adapter_config"] = dict(adapter_config)
    return extra


def _string_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def build_human_resume_input_schema() -> dict[str, Any]:
    """Return a copy of the documented composite human resume schema."""
    return {
        "type": HUMAN_RESUME_INPUT_SCHEMA["type"],
        "additionalProperties": HUMAN_RESUME_INPUT_SCHEMA["additionalProperties"],
        "properties": {
            "decision": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(HUMAN_RESUME_INPUT_SCHEMA["properties"]["decision"]["properties"]["action"]["enum"]),
                    },
                    "notes": {"type": "string"},
                    "state_patch": {"type": "object"},
                },
                "required": ["action"],
            },
            "produces_reverify": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "artifacts": {"type": "array", "items": {"type": "string"}},
                    "inputs": {"type": "object"},
                },
            },
        },
        "required": ["decision"],
    }


def build_human_resume_payload(
    *,
    action: str,
    notes: str = "",
    state_patch: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized composite human resume payload."""
    if action not in HUMAN_DECISION_ACTIONS:
        raise HumanResumePayloadError(
            f"decision.action must be one of {sorted(HUMAN_DECISION_ACTIONS)!r}"
        )
    payload: dict[str, Any] = {
        "decision": {
            "action": action,
            "notes": notes,
            "state_patch": dict(state_patch or {}),
        }
    }
    if artifacts is not None or inputs is not None:
        payload["produces_reverify"] = {
            "artifacts": list(artifacts or []),
            "inputs": dict(inputs or {}),
        }
    return payload


def parse_human_resume_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and split the composite human resume payload."""
    if not isinstance(payload, dict):
        raise HumanResumePayloadError(
            f"human resume payload must be a dict, got {type(payload).__name__}"
        )

    decision = payload.get("decision")
    if not isinstance(decision, dict):
        raise HumanResumePayloadError("human resume payload requires a dict 'decision'")

    action = decision.get("action")
    if action not in HUMAN_DECISION_ACTIONS:
        raise HumanResumePayloadError(
            f"decision.action must be one of {sorted(HUMAN_DECISION_ACTIONS)!r}"
        )
    notes = decision.get("notes", "")
    if not isinstance(notes, str):
        raise HumanResumePayloadError("decision.notes must be a string when provided")
    state_patch = decision.get("state_patch", {})
    if not isinstance(state_patch, dict):
        raise HumanResumePayloadError("decision.state_patch must be a dict")

    produces_reverify = payload.get("produces_reverify", {})
    if not isinstance(produces_reverify, dict):
        raise HumanResumePayloadError("produces_reverify must be a dict when provided")

    artifacts = produces_reverify.get("artifacts", [])
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        raise HumanResumePayloadError("produces_reverify.artifacts must be a list of strings")
    inputs = produces_reverify.get("inputs", {})
    if not isinstance(inputs, dict):
        raise HumanResumePayloadError("produces_reverify.inputs must be a dict")

    return (
        {
            "action": action,
            "notes": notes,
            "state_patch": dict(state_patch),
        },
        {
            "artifacts": list(artifacts),
            "inputs": dict(inputs),
        },
    )


__all__ = [
    "HUMAN_DECISION_ACTIONS",
    "HUMAN_RESUME_INPUT_SCHEMA",
    "HOST_CONTROL_KINDS",
    "CompiledInvocationTemplateError",
    "HumanResumePayloadError",
    "InvocationTemplate",
    "STEP_INVOCATION_KIND",
    "StepInvocationMetadata",
    "build_adapter_metadata",
    "build_human_resume_input_schema",
    "build_human_resume_payload",
    "build_step_invocation",
    "build_step_metadata",
    "invocation_templates_from_compiled_pipeline",
    "parse_human_resume_payload",
]
