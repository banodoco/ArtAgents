from __future__ import annotations

from pathlib import Path

from astrid.core.integrations.arnold.host.registry import ArnoldOperationSnapshot
from astrid.core.task.operator.render import NEXT_JSON_SCHEMA


def _snapshot(events: tuple[dict[str, object], ...] = ()) -> ArnoldOperationSnapshot:
    return ArnoldOperationSnapshot(
        project_slug="demo",
        workflow_id="we.refine_image",
        run_id="run-1",
        run_root=Path("/tmp/run-1"),
        lease={"writer_epoch": 0},
        cursor={"stage": "review"},
        events_tail=events,
        next_stage_id="review",
        next_stage_label="Review",
        envelope=object(),
    )


def test_arnold_next_json_schema_preserves_shared_task_fields() -> None:
    from astrid.core.integrations.arnold.host.render import ARNOLD_NEXT_JSON_SCHEMA

    assert ARNOLD_NEXT_JSON_SCHEMA == NEXT_JSON_SCHEMA


def test_render_snapshot_ready_ack_uses_snapshot_not_task_peek_result() -> None:
    from astrid.core.integrations.arnold.host.render import render_operation_snapshot

    rendered = render_operation_snapshot(_snapshot())

    assert rendered.lifecycle_json == {
        "schema_version": 1,
        "project": "demo",
        "run_id": "run-1",
        "state": "ready",
        "action": "ack",
        "command": (
            "astrid ack --engine arnold --project demo --stage review "
            "--decision approve|reject --notes <notes>"
        ),
        "step": "review",
        "blocked": False,
        "reason": None,
    }
    assert "Arnold workflow we.refine_image" in rendered.text
    assert "stage: Review (review)" in rendered.text
    assert "ready for acknowledgement:" in rendered.text


def test_render_snapshot_covers_blocked_produces_feedback_items_and_reack() -> None:
    from astrid.core.integrations.arnold.host.render import render_operation_snapshot

    rendered = render_operation_snapshot(
        _snapshot(
            (
                {
                    "kind": "human_feedback",
                    "stage_id": "review",
                    "action": "reject",
                    "notes": "too soft",
                },
                {
                    "kind": "item_checklist",
                    "items": [
                        {"id": "a", "status": "completed"},
                        {"id": "b", "status": "pending", "stage_id": "review"},
                    ],
                },
                {
                    "kind": "produces_check_failed",
                    "produces_name": "image",
                    "artifact_path": "out.png",
                    "reason": "missing file",
                },
                {
                    "kind": "stage_rewritten",
                    "stage_id": "review",
                    "previous_decision": "approve",
                },
            )
        )
    )

    assert rendered.lifecycle_json["state"] == "blocked"
    assert rendered.lifecycle_json["blocked"] is True
    assert rendered.lifecycle_json["action"] is None
    assert rendered.lifecycle_json["reason"] == "image: missing file"
    assert "blocked produces failure:" in rendered.text
    assert "Re-write the artifact and re-ack." in rendered.text
    assert "feedback ledger:" in rendered.text
    assert "too soft" in rendered.text
    assert "[x] a" in rendered.text
    assert "[ ] b  <- next" in rendered.text
    assert "Previous decision 'approve' is no longer valid." in rendered.text
