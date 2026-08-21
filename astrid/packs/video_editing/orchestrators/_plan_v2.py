"""Self-contained plan-v2 emission helpers for video_editing orchestrators.

The former task-mode orchestrator plan-template module (and the task-plan
schema it rendered) was retired with the task runtime. Pack orchestrators
execute their steps directly now; ``plan.json`` remains an informational
run-local artifact, so the builders live here instead of in core.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def cost_entry(amount: float, *, source: str) -> dict[str, Any]:
    """Cost sidecar entry matching the plan-v2 CostEntry shape."""

    return {"amount": float(amount), "currency": "USD", "source": source}


def file_output(name: str, path: str | Path, sentinel: bool = False) -> dict[str, Any]:
    """Named produced-file entry with the default file_nonempty check."""

    return {
        name: {
            "path": str(path),
            "check": {"check_id": "file_nonempty", "params": {}, "sentinel": sentinel},
        }
    }


def repeat_for_each_from(ref: str) -> dict[str, Any]:
    """Repeat a step once per item produced by an upstream step reference."""

    return {"for_each": {"from_ref": ref}}


def repeat_until(
    condition: str,
    *,
    max_iterations: int = 2,
    on_exhaust: str = "fail",
) -> dict[str, Any]:
    """Repeat a step until a produces condition holds, bounded."""

    return {
        "until": {
            "condition": condition,
            "max_iterations": max_iterations,
            "on_exhaust": on_exhaust,
        }
    }


def build_leaf_template(
    step_id: str,
    *,
    command: str,
    produces: list[dict[str, Any]] | None = None,
    cost: dict[str, Any] | None = None,
    adapter: str = "local",
    requires_ack: bool = False,
    ack_kind: str = "agent",
    instructions: str | None = None,
    assignee: str = "system",
    repeat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a plan-v2 leaf step dict."""

    step: dict[str, Any] = {"id": step_id, "adapter": adapter, "command": command}
    if produces:
        merged: dict[str, Any] = {}
        for entry in produces:
            merged.update(entry)
        step["produces"] = merged
    if cost is not None:
        step["cost"] = cost
    if requires_ack:
        step["requires_ack"] = True
        step["ack_kind"] = ack_kind
    if instructions is not None:
        step["instructions"] = instructions
    if requires_ack or assignee != "system":
        step["assignee"] = assignee
    if repeat is not None:
        step["repeat"] = repeat
    return step


def build_group_template(
    group_id: str,
    *,
    re_export: dict[str, str] | None = None,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a plan-v2 group step dict wrapping child steps."""

    group: dict[str, Any] = {"id": group_id, "adapter": "local", "command": f"group:{group_id}"}
    if re_export:
        group["re_export"] = re_export
    if children:
        group["children"] = children
    return group


def build_plan_template(
    *,
    plan_id: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a plan-v2 document dict."""

    return {"plan_id": plan_id, "version": 2, "steps": steps}


def emit_plan_json(plan: dict[str, Any], path: str | Path) -> None:
    """Write canonical plan JSON."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    output_path.write_text(payload, encoding="utf-8")


__all__ = [
    "build_group_template",
    "build_leaf_template",
    "build_plan_template",
    "cost_entry",
    "emit_plan_json",
    "file_output",
    "repeat_for_each_from",
    "repeat_until",
]
