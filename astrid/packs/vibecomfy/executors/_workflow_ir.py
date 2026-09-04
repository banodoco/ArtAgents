"""Offline VibeComfy IR inspection and typed-delta edit bridge.

The source UI graph is the door input and remains the authority. This adapter
delegates projection and mutation to VibeComfy's public IR APIs; it never
evaluates a Python projection or maintains an Astrid-side graph model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

_ALLOWED_EDIT_TOOLS = frozenset(
    {
        "add_node",
        "edit_node",
        "remove_link",
        "remove_node",
        "set_node_mode",
        "upsert_link",
    }
)


class WorkflowIrBridgeError(ValueError):
    """A workflow or typed edit document cannot be admitted."""


def _read_json_object(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowIrBridgeError(f"{label} must be a readable JSON file: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowIrBridgeError(f"{label} must contain a JSON object")
    return value, raw


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def inspect_workflow(workflow_path: Path, out_dir: Path) -> dict[str, Path]:
    """Project one admitted UI graph through VibeComfy's readable IR lenses."""
    workflow, source_bytes = _read_json_object(workflow_path, label="workflow")
    from vibecomfy.porting.render import render

    rendered = render(workflow, lenses=("census", "surface", "topology"))
    if not isinstance(rendered, Mapping):  # defensive boundary over the dependency
        raise WorkflowIrBridgeError("VibeComfy returned an invalid IR projection")

    out_dir.mkdir(parents=True, exist_ok=True)
    projection_path = out_dir / "workflow-ir.py"
    projection_path.write_text(str(rendered["surface"]), encoding="utf-8")
    inspection_path = out_dir / "inspection.json"
    _write_json(
        inspection_path,
        {
            "schema_version": 1,
            "authority": "input_ui_graph",
            "source_sha256": _sha256(source_bytes),
            "projection": "read_only_python_like_ir",
            "lenses": {
                "census": rendered["census"],
                "surface": rendered["surface"],
                "topology": rendered["topology"],
                "topology_source": rendered.get("topology_source", "computed"),
            },
        },
    )
    return {"projection": projection_path, "inspection": inspection_path}


def _parse_edit_document(path: Path) -> tuple[list[dict[str, Any]], int]:
    document, _ = _read_json_object(path, label="operations")
    allowed_keys = {"schema_version", "expected_revision", "ops"}
    unknown = sorted(set(document) - allowed_keys)
    if unknown:
        raise WorkflowIrBridgeError(
            "operations does not accept keys: " + ", ".join(unknown)
        )
    if document.get("schema_version", 1) != 1:
        raise WorkflowIrBridgeError("operations.schema_version must be 1")
    expected_revision = document.get("expected_revision", 0)
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise WorkflowIrBridgeError("operations.expected_revision must be an integer")
    ops = document.get("ops")
    if not isinstance(ops, list) or not ops:
        raise WorkflowIrBridgeError("operations.ops must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(ops):
        if not isinstance(item, dict):
            raise WorkflowIrBridgeError(f"operations.ops[{index}] must be an object")
        normalized.append(dict(item))
    return normalized, expected_revision


def _diagnostic_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return {
        "code": str(getattr(value, "code", "unknown")),
        "message": str(getattr(value, "message", value)),
        "severity": str(getattr(value, "severity", "error")),
    }


def edit_workflow(
    workflow_path: Path,
    operations_path: Path,
    out_dir: Path,
) -> dict[str, Path]:
    """Apply one atomic typed-tool batch and emit a new UI graph artifact."""
    workflow, source_bytes = _read_json_object(workflow_path, label="workflow")
    ops, expected_revision = _parse_edit_document(operations_path)

    from vibecomfy.porting.edit import (
        EditSession,
        EditToolError,
        apply_edit_tool_call,
        op_to_dict,
    )

    for index, op in enumerate(ops):
        name = op.get("op")
        if not isinstance(name, str) or name not in _ALLOWED_EDIT_TOOLS:
            allowed = ", ".join(sorted(_ALLOWED_EDIT_TOOLS))
            raise WorkflowIrBridgeError(
                f"operations.ops[{index}].op must be one of: {allowed}"
            )

    session = EditSession(workflow)
    try:
        result = apply_edit_tool_call(
            session,
            "edit_batch",
            {"ops": ops},
            expected_revision=expected_revision,
        )
    except EditToolError as exc:
        raise WorkflowIrBridgeError(
            f"typed edit rejected ({exc.code}): {exc}"
        ) from exc
    diagnostics = [_diagnostic_payload(item) for item in result.diagnostics]
    if not result.ok or result.graph is None:
        detail = diagnostics[0]["message"] if diagnostics else result.reason
        raise WorkflowIrBridgeError(f"typed edit rejected ({result.reason}): {detail}")

    out_dir.mkdir(parents=True, exist_ok=True)
    workflow_out = out_dir / "workflow.ui.json"
    _write_json(workflow_out, result.graph)

    projection_out = out_dir / "workflow-ir.py"
    projection_out.write_text(session.render(), encoding="utf-8")

    report_out = out_dir / "edit-report.json"
    canonical_ops = [op_to_dict(op) for op in result.landed_ops]
    _write_json(
        report_out,
        {
            "schema_version": 1,
            "authority": "input_ui_graph_plus_typed_delta",
            "source_sha256": _sha256(source_bytes),
            "edited_sha256": _sha256(workflow_out.read_bytes()),
            "expected_revision": expected_revision,
            "revision": result.revision,
            "delta_id": result.delta_id,
            "requested_tools": [str(op["op"]) for op in ops],
            "canonical_delta": canonical_ops,
            "diagnostics": diagnostics,
        },
    )
    return {
        "workflow": workflow_out,
        "projection": projection_out,
        "report": report_out,
    }
