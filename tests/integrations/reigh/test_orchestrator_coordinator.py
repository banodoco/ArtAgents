"""Focused coordinator journeys on the current bearer/versioned bridge."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from astrid.core.integrations.reigh.orchestrator_runner import (
    HttpBridgeTransport,
    OrchestratorCoordinator,
)
from astrid.core.integrations.reigh.orchestrator_transitions import (
    ADMISSION_TRANSITIONS,
    FenceFacts,
    Verdict,
    derive_children,
)
from astrid.core.store.uow import UnitOfWork
from tests.integrations.reigh.test_task_routes import (
    _create_project,
    _multipart_body,
    _post_multipart,
    task_server,
)


def _complete_child(env: dict[str, Any], claim: dict[str, Any], *, key: str) -> None:
    attempt = claim["attempt"]
    payload = b"child-output"
    manifest = {
        "attempt_id": attempt["id"],
        "lease_id": attempt["lease_id"],
        "status_version": attempt["status_version"],
        "outputs": [
            {
                "key": "out0",
                "is_primary": True,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        ],
    }
    body, boundary = _multipart_body(manifest, {"out0": payload})
    status, response = _post_multipart(
        env,
        f"/tasks/{claim['task']['id']}/attempts/{attempt['attempt_no']}/complete",
        key=key,
        body=body,
        boundary=boundary,
    )
    assert status == 200, response


def _drive_family(
    tmp_path: Path,
    *,
    family: str,
    input_data: dict[str, Any],
    parent_capability: str,
    child_capabilities: list[str],
) -> None:
    with task_server(tmp_path) as env:
        slug = f"orch-{family.replace('_', '-')}"
        _create_project(env["composition"], slug)
        transport = HttpBridgeTransport(env["base_url"], env["token"])
        coordinator = OrchestratorCoordinator(transport)
        status, response = transport.post_json(
            f"/projects/{slug}/tasks",
            {"family": family, "input": input_data},
            key=f"parent-{family}",
        )
        assert status == 201, response
        parent_id = str(response["task"]["id"])
        claim = coordinator.claim(
            slug=slug,
            executor_id="orchestrator-1",
            capabilities=[parent_capability],
        )
        assert claim is not None and claim.task_id == parent_id
        admitted = coordinator.fan_out(claim, executor_id="orchestrator-1")
        expected = derive_children({"family": family, "params": input_data})
        assert set(admitted) == set(expected)
        # Every replay resolves to the same child row, including after the
        # first response has already been consumed by the caller.
        assert coordinator.fan_out(claim, executor_id="orchestrator-1") == admitted

        for index in range(len(admitted)):
            child_claim = coordinator.claim(
                slug=slug,
                executor_id="worker-1",
                capabilities=child_capabilities,
            )
            assert child_claim is not None
            _complete_child(
                env,
                {
                    "task": {
                        "id": child_claim.task_id,
                    },
                    "attempt": {
                        "id": child_claim.attempt_id,
                        "attempt_no": child_claim.attempt_no,
                        "lease_id": child_claim.lease_id,
                        "status_version": child_claim.status_version,
                    },
                },
                key=f"child-{family}-{index}",
            )

        result = coordinator.settle_success(
            claim, settlement_key=f"settle-{family}", receipt=admitted
        )
        assert result["task"]["status"] == "succeeded"
        assert (
            coordinator.settle_success(claim, settlement_key=f"settle-{family}", receipt=admitted)[
                "task"
            ]["status"]
            == "succeeded"
        )


def test_transition_table_is_total_and_precedence_is_explicit() -> None:
    assert len(ADMISSION_TRANSITIONS) == 16
    assert sum(value is Verdict.REPLAY_RECEIPTED for value in ADMISSION_TRANSITIONS.values()) == 8
    classify = Verdict.ADMIT_NEW
    assert ADMISSION_TRANSITIONS[(False, False, True, True)] is Verdict.CONFLICT_PARENT_NOT_RUNNING
    assert ADMISSION_TRANSITIONS[(False, True, False, True)] is Verdict.FORBIDDEN_FENCE_MISMATCH
    assert ADMISSION_TRANSITIONS[(False, True, True, False)] is Verdict.CONFLICT_LEASE_EXPIRED
    assert ADMISSION_TRANSITIONS[(False, True, True, True)] is classify
    assert FenceFacts(True, False, False, False).key() in ADMISSION_TRANSITIONS


def test_join_family_is_replay_safe_and_settles(tmp_path: Path) -> None:
    _drive_family(
        tmp_path,
        family="join_clips",
        input_data={"clip_source": "clips", "clips": ["a", "b"]},
        parent_capability="reigh.join_clips_orchestrator",
        child_capabilities=["reigh.join_clips_segment", "reigh.join_final_stitch"],
    )


def test_travel_family_is_replay_safe_and_settles(tmp_path: Path) -> None:
    _drive_family(
        tmp_path,
        family="travel_between_images",
        input_data={"image_urls": ["a", "b"]},
        parent_capability="reigh.travel_orchestrator",
        child_capabilities=["reigh.travel_segment", "reigh.travel_stitch"],
    )


def test_edit_family_is_childless_and_settles_directly(tmp_path: Path) -> None:
    with task_server(tmp_path) as env:
        slug = "orch-edit"
        _create_project(env["composition"], slug)
        transport = HttpBridgeTransport(env["base_url"], env["token"])
        coordinator = OrchestratorCoordinator(transport)
        status, response = transport.post_json(
            f"/projects/{slug}/tasks",
            {
                "family": "edit_video_orchestrator",
                "input": {"clip_source": "clip.mp4", "prompt": "trim"},
            },
            key="parent-edit",
        )
        assert status == 201, response
        claim = coordinator.claim(
            slug=slug,
            executor_id="orchestrator-edit",
            capabilities=["reigh.edit_video_orchestrator"],
        )
        assert claim is not None
        assert coordinator.fan_out(claim, executor_id="orchestrator-edit") == {}
        result = coordinator.settle_success(claim, settlement_key="settle-edit", receipt={})
        assert result["task"]["status"] == "succeeded"


def test_parent_lease_replay_reuses_children_after_sweeper(tmp_path: Path) -> None:
    with task_server(tmp_path) as env:
        slug = "orch-replay"
        _create_project(env["composition"], slug)
        transport = HttpBridgeTransport(env["base_url"], env["token"])
        coordinator = OrchestratorCoordinator(transport)
        status, response = transport.post_json(
            f"/projects/{slug}/tasks",
            {
                "family": "join_clips",
                "input": {"clip_source": "clips", "clips": ["a"]},
            },
            key="parent-replay",
        )
        assert status == 201, response
        claim = coordinator.claim(
            slug=slug,
            executor_id="orchestrator-1",
            capabilities=["reigh.join_clips_orchestrator"],
        )
        assert claim is not None
        first = coordinator.fan_out(claim, executor_id="orchestrator-1")

        def expire(uow: Any) -> None:
            uow.execute(
                "UPDATE execution_attempts SET lease_expires_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00+00:00", claim.attempt_id),
            )

        UnitOfWork(env["composition"].writer).run(expire)
        assert env["composition"].expiry_sweeper._sweep_once() is True
        resumed = coordinator.claim(
            slug=slug,
            executor_id="orchestrator-2",
            capabilities=["reigh.join_clips_orchestrator"],
        )
        assert resumed is not None
        assert resumed.task_id == claim.task_id
        assert resumed.attempt_no == claim.attempt_no + 1
        assert coordinator.fan_out(resumed, executor_id="orchestrator-2") == first


def test_failure_settlement_consumes_parent_attempt_budget(tmp_path: Path) -> None:
    with task_server(tmp_path) as env:
        slug = "orch-failure"
        _create_project(env["composition"], slug)
        transport = HttpBridgeTransport(env["base_url"], env["token"])
        coordinator = OrchestratorCoordinator(transport)
        status, response = transport.post_json(
            f"/projects/{slug}/tasks",
            {
                "family": "join_clips",
                "input": {"clip_source": "clips", "clips": ["a"]},
            },
            key="parent-failure",
        )
        assert status == 201, response
        claim = coordinator.claim(
            slug=slug,
            executor_id="orchestrator-fail",
            capabilities=["reigh.join_clips_orchestrator"],
        )
        assert claim is not None
        result = coordinator.settle_failure(
            claim,
            settlement_key="settle-failure",
            code="child_failed",
            message="a child failed",
        )
        assert result["task"]["status"] == "failed"
