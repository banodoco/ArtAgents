"""Operator rendering for Arnold host snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from astrid.core.integrations.arnold.host.registry import ArnoldOperationSnapshot
from astrid.core.task.operator.render import NEXT_JSON_SCHEMA

ARNOLD_NEXT_JSON_SCHEMA: dict[str, str] = dict(NEXT_JSON_SCHEMA)


@dataclass(frozen=True)
class ArnoldRenderView:
    """Rendered Arnold next/status view in text and shared lifecycle JSON."""

    text: str
    lifecycle_json: dict[str, Any]


def render_operation_snapshot(snapshot: ArnoldOperationSnapshot) -> ArnoldRenderView:
    """Render an Arnold operation snapshot without task ``PeekResult`` data."""
    stage_id = snapshot.next_stage_id
    stage_label = snapshot.next_stage_label or stage_id
    events = tuple(event for event in snapshot.events_tail if isinstance(event, dict))
    blocked = _blocked_produces(events)
    rewritten = _rewrite_reack(events)
    state = "blocked" if blocked else "ready"
    action = None if blocked or stage_id is None else "ack"
    reason = _blocked_reason(blocked) if blocked else None
    command = None
    if action == "ack" and stage_id is not None:
        command = _ack_template(snapshot)

    lifecycle_json = _lifecycle_json(
        snapshot=snapshot,
        state=state,
        action=action,
        command=command,
        blocked=bool(blocked),
        reason=reason,
    )

    sections = [
        _stage_header(snapshot.workflow_id, stage_id, stage_label),
        _ready_ack_section(command, blocked=bool(blocked)),
        _blocked_produces_section(blocked),
        _feedback_ledger_section(events),
        _item_checklist_section(events, stage_id),
        _rewrite_reack_section(rewritten),
    ]
    return ArnoldRenderView(
        text="\n".join(section for section in sections if section).rstrip() + "\n",
        lifecycle_json=lifecycle_json,
    )


def render_operation_snapshot_text(snapshot: ArnoldOperationSnapshot) -> str:
    return render_operation_snapshot(snapshot).text


def render_operation_snapshot_json(snapshot: ArnoldOperationSnapshot) -> dict[str, Any]:
    return render_operation_snapshot(snapshot).lifecycle_json


def render_operation_snapshot_json_line(snapshot: ArnoldOperationSnapshot) -> str:
    return json.dumps(render_operation_snapshot_json(snapshot), sort_keys=True)


def _lifecycle_json(
    *,
    snapshot: ArnoldOperationSnapshot,
    state: str,
    action: str | None,
    command: str | None,
    blocked: bool,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project": snapshot.project_slug,
        "run_id": snapshot.run_id,
        "state": state,
        "action": action,
        "command": command,
        "step": snapshot.next_stage_id,
        "blocked": blocked,
        "reason": reason,
    }


def _stage_header(workflow_id: str, stage_id: str | None, stage_label: str | None) -> str:
    if stage_id is None:
        return f"Arnold workflow {workflow_id}: no pending stage"
    return f"Arnold workflow {workflow_id}\nstage: {stage_label or stage_id} ({stage_id})"


def _ready_ack_section(command: str | None, *, blocked: bool) -> str:
    if blocked:
        return ""
    if command is None:
        return "Run complete. Nothing to acknowledge."
    return f"ready for acknowledgement:\n{command}"


def _ack_template(snapshot: ArnoldOperationSnapshot) -> str:
    stage_id = snapshot.next_stage_id or "<stage>"
    return (
        "astrid ack --engine arnold "
        f"--project {snapshot.project_slug} "
        f"--stage {stage_id} "
        "--decision approve|reject "
        "--notes <notes>"
    )


def _blocked_produces(events: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    found: list[dict[str, Any]] = []
    for event in events:
        if event.get("kind") not in {
            "produces_check_failed",
            "arnold_produces_check_failed",
            "blocked_produces",
        }:
            continue
        found.append(
            {
                "name": event.get("produces_name")
                or event.get("output_name")
                or event.get("name")
                or "produces",
                "reason": event.get("reason") or "produces verification failed",
                "path": event.get("artifact_path") or event.get("expected_path"),
            }
        )
    return tuple(found)


def _blocked_reason(blocked: tuple[dict[str, Any], ...]) -> str | None:
    if not blocked:
        return None
    first = blocked[-1]
    return f"{first['name']}: {first['reason']}"


def _blocked_produces_section(blocked: tuple[dict[str, Any], ...]) -> str:
    if not blocked:
        return ""
    lines = ["blocked produces failure:"]
    for entry in blocked:
        line = f"  - {entry['name']}: {entry['reason']}"
        if entry.get("path"):
            line += f" ({entry['path']})"
        lines.append(line)
    lines.append("Re-write the artifact and re-ack.")
    return "\n".join(lines)


def _feedback_ledger_section(events: tuple[dict[str, Any], ...]) -> str:
    entries = [
        event
        for event in events
        if event.get("kind") in {"human_feedback", "arnold_feedback", "decision"}
        or "feedback" in event
        or "notes" in event
    ]
    if not entries:
        return "feedback ledger:\n  (no feedback yet)"
    lines = ["feedback ledger:"]
    for index, event in enumerate(entries, start=1):
        action = event.get("action") or event.get("decision") or event.get("kind")
        notes = event.get("notes") or event.get("feedback") or ""
        stage = event.get("stage_id") or event.get("stage") or ""
        suffix = f" [{stage}]" if stage else ""
        lines.append(f"  [{index}] {action}{suffix}")
        if notes:
            lines.append(f"      {notes}")
    return "\n".join(lines)


def _item_checklist_section(
    events: tuple[dict[str, Any], ...],
    stage_id: str | None,
) -> str:
    items = _latest_checklist(events)
    if not items:
        return "items:\n  (no checklist items)"
    lines = ["items:"]
    for item in items:
        item_id = str(item.get("id") or item.get("label") or "?")
        status = str(item.get("status") or "pending")
        marker = "x" if status in {"done", "pass", "passed", "complete", "completed"} else " "
        next_marker = "  <- next" if stage_id and item.get("stage_id") == stage_id else ""
        lines.append(f"  [{marker}] {item_id}{next_marker}")
    return "\n".join(lines)


def _latest_checklist(events: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    for event in reversed(events):
        raw = event.get("items") or event.get("checklist")
        if not isinstance(raw, list):
            continue
        items = [dict(item) for item in raw if isinstance(item, dict)]
        return tuple(items)
    return ()


def _rewrite_reack(events: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("kind") not in {"stage_rewritten", "plan_mutated", "arnold_stage_rewritten"}:
            continue
        if event.get("requires_reack") is False:
            continue
        return event
    return None


def _rewrite_reack_section(event: dict[str, Any] | None) -> str:
    if event is None:
        return ""
    stage = event.get("stage_id") or event.get("stage") or event.get("plan_step_id") or "stage"
    decision = event.get("previous_decision") or event.get("decision") or "previous decision"
    return (
        f"Stage '{stage}' was rewritten since your last acknowledgement.\n"
        f"Previous decision '{decision}' is no longer valid.\n"
        "Please review the updated stage and re-acknowledge."
    )


__all__ = [
    "ARNOLD_NEXT_JSON_SCHEMA",
    "ArnoldRenderView",
    "render_operation_snapshot",
    "render_operation_snapshot_json",
    "render_operation_snapshot_json_line",
    "render_operation_snapshot_text",
]
