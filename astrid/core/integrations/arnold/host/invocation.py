"""StepInvocation metadata helpers for the Arnold host.

These helpers define the canonical metadata wire format that the existing
Astrid StepInvocation adapter already consumes.  The host shapes build
their adapter-backed stages through these functions so the metadata
contract stays centralized and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STEP_INVOCATION_KIND = "model"
HUMAN_DECISION_ACTIONS: frozenset[str] = frozenset({"approve", "reject"})
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
    executor_id: str
    input_map: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    mode: str = "inline"
    requires_ack: bool = False
    extra_metadata: dict[str, Any] = field(default_factory=dict)


ALLOWLISTED_INVOCATION_TEMPLATES: dict[str, dict[str, InvocationTemplate]] = {
    "we.refine_image": {
        "generate": InvocationTemplate(
            workflow_id="we.refine_image",
            stage_id="generate",
            executor_id="image.generate",
            input_map={"prompt": "prompt"},
            inputs={"variant": "refine"},
            extra_metadata={"iteration_key": "iter"},
        ),
        "review": InvocationTemplate(
            workflow_id="we.refine_image",
            stage_id="review",
            executor_id="human.review",
            input_map={"candidate": "candidate"},
            requires_ack=True,
            extra_metadata={"human_gate": True},
        ),
    },
    "we.best_of_4": {
        "gen_0": InvocationTemplate(
            workflow_id="we.best_of_4",
            stage_id="gen_0",
            executor_id="image.generate",
            input_map={"prompt": "prompt"},
            inputs={"variant": "branch_0"},
            extra_metadata={"branch": 0},
        ),
        "gen_1": InvocationTemplate(
            workflow_id="we.best_of_4",
            stage_id="gen_1",
            executor_id="image.generate",
            input_map={"prompt": "prompt"},
            inputs={"variant": "branch_1"},
            extra_metadata={"branch": 1},
        ),
        "gen_2": InvocationTemplate(
            workflow_id="we.best_of_4",
            stage_id="gen_2",
            executor_id="image.generate",
            input_map={"prompt": "prompt"},
            inputs={"variant": "branch_2"},
            extra_metadata={"branch": 2},
        ),
        "gen_3": InvocationTemplate(
            workflow_id="we.best_of_4",
            stage_id="gen_3",
            executor_id="image.generate",
            input_map={"prompt": "prompt"},
            inputs={"variant": "branch_3"},
            extra_metadata={"branch": 3},
        ),
        "judge": InvocationTemplate(
            workflow_id="we.best_of_4",
            stage_id="judge",
            executor_id="judge.exec",
            input_map={"candidates": "candidates"},
            inputs={"strategy": "best_of_4"},
        ),
        "review": InvocationTemplate(
            workflow_id="we.best_of_4",
            stage_id="review",
            executor_id="human.review",
            input_map={"finalist": "finalist"},
            requires_ack=True,
            extra_metadata={"human_gate": True},
        ),
    },
    "text_analysis.summarize": {
        "summarize": InvocationTemplate(
            workflow_id="text_analysis.summarize",
            stage_id="summarize",
            executor_id="text.summarize",
            input_map={"text": "text"},
        ),
    },
}


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
    """Construct a real Arnold StepInvocation with canonical metadata."""
    from astrid.core.integrations.arnold.host.compat import compat

    return compat.StepInvocation(
        kind=kind,
        metadata=build_step_metadata(
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
        ),
    )


def build_workflow_step_invocation(
    workflow_id: str,
    stage_id: str,
    *,
    state: dict[str, Any] | None = None,
    project: str | None = None,
    run_root: str | None = None,
    artifact_root: str | None = None,
    cas_project_dir: str | None = None,
) -> Any:
    """Build the canonical StepInvocation template for an allowlisted stage."""
    try:
        template = ALLOWLISTED_INVOCATION_TEMPLATES[workflow_id][stage_id]
    except KeyError as exc:
        raise KeyError(
            f"unknown host invocation template {workflow_id!r}/{stage_id!r}"
        ) from exc

    return build_step_invocation(
        executor_id=template.executor_id,
        inputs=template.inputs,
        input_map=template.input_map,
        state=state,
        mode=template.mode,
        project=project,
        run_root=run_root,
        artifact_root=artifact_root,
        cas_project_dir=cas_project_dir,
        requires_ack=template.requires_ack,
        workflow_id=template.workflow_id,
        stage_id=template.stage_id,
        **template.extra_metadata,
    )


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
    "ALLOWLISTED_INVOCATION_TEMPLATES",
    "HUMAN_DECISION_ACTIONS",
    "HUMAN_RESUME_INPUT_SCHEMA",
    "HumanResumePayloadError",
    "InvocationTemplate",
    "STEP_INVOCATION_KIND",
    "build_adapter_metadata",
    "build_human_resume_input_schema",
    "build_human_resume_payload",
    "build_step_invocation",
    "build_step_metadata",
    "build_workflow_step_invocation",
    "parse_human_resume_payload",
]
