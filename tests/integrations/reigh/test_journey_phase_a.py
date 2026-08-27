"""Phase-A journey harness (tasklist T12, batch C5).

End-to-end executor journeys over the real loopback bridge, in-process on
port 0: admit → claim → heartbeat → complete → CAS bytes in the tree →
media/task_outputs rows → gallery row → timeline registry visible; plus the
named failure journeys — duplicate-admission replay, poisoned-output
rejection, cancel queued + running, and the v3-N1 merge-skipped-completion
replayable-receipt scenario.

Reuses the ``task_server`` composition and route helpers from the T6-T8
acceptance fixtures; every scenario runs against one fully composed serve
root (timeline bridge + task bridge, one writer, real SQLite, real CAS tree).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tests.integrations.reigh.test_task_routes import (
    _admit_simple,
    _complete_multipart,
    _create_project,
    _db_count,
    _post,
    task_server,
)

PAYLOAD = b"journey-rendered-bytes"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def _claim(env: dict[str, Any], capability: str = "reigh.image_upscale"):
    status, claim = _post(
        env,
        "/queue/claim",
        body={"executor_id": "e1", "capabilities": [capability]},
    )
    assert status == 200, claim
    return claim


def _heartbeat(env: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    attempt = claim["attempt"]
    status, payload = _post(
        env,
        f"/tasks/{claim['task']['id']}/attempts/{attempt['attempt_no']}/heartbeat",
        body={
            "attempt_id": attempt["id"],
            "lease_id": attempt["lease_id"],
            "status_version": attempt["status_version"],
        },
    )
    assert status == 200, payload
    return payload


def _create_timeline(composition, project_id: str) -> str:
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs.timeline.repository import TimelineRepository

    timelines = TimelineRepository(
        events=EventAppendService(composition.registry),
        receipts=ReceiptService(),
        projects=ProjectRepository(events=None, receipts=None),
    )

    def command(uow):
        return timelines.create(
            uow,
            project_id=project_id,
            slug="primary",
            name="Primary",
            config={},
            idempotency_key="journey-timeline",
        )

    return UnitOfWork(composition.writer).run(command).timeline_id


def _set_task_spec(composition, task_id: str, spec: dict) -> None:
    from astrid.core.store.uow import UnitOfWork

    def command(uow):
        uow.execute(
            "UPDATE tasks SET spec_json = ? WHERE id = ?",
            (json.dumps(spec), task_id),
        )

    UnitOfWork(composition.writer).run(command)


def _task_spec(composition, task_id: str) -> dict:
    with composition.writer.read_only_connection() as conn:
        raw = conn.execute(
            "SELECT spec_json FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()[0]
    return json.loads(raw)


def _project_id(composition, task_id: str) -> str:
    with composition.writer.read_only_connection() as conn:
        return conn.execute(
            "SELECT project_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()[0]


class TestJourneyPhaseA:
    def test_full_journey_admit_to_registry_visible(
        self, tmp_bridge_root: Path
    ) -> None:
        """The whole executor journey ends with the output visible in the
        CAS tree, the media/task_outputs rows, the gallery, and the
        timeline asset registry."""
        with task_server(tmp_bridge_root) as env:
            composition = env["composition"]
            slug = "journey-proj"
            _create_project(composition, slug)
            status, admitted = _admit_simple(env, slug, "journey-admit")
            assert status == 201, admitted
            task_id = admitted["task"]["id"]

            claim = _claim(env)
            assert claim["task"]["id"] == task_id
            attempt = claim["attempt"]
            assert attempt["status"] == "claimed"
            assert attempt["lease_id"]

            beat = _heartbeat(env, claim)
            assert beat["attempt"]["status_version"] == (
                attempt["status_version"] + 1
            )
            # The heartbeat's returned fence is the next live fence: the
            # completion below must present it.
            attempt["status_version"] = beat["attempt"]["status_version"]
            # Request registry visibility for the completed generation.
            timeline_id = _create_timeline(
                composition, _project_id(composition, task_id)
            )
            spec = _task_spec(composition, task_id)
            spec["output_policy"]["timeline_visibility"] = {
                "timeline_id": timeline_id,
                "asset_key": "journey:upscaled",
            }
            _set_task_spec(composition, task_id, spec)

            status, result = _complete_multipart(
                env,
                claim,
                task_id,
                key="journey-complete",
                files={"out0": PAYLOAD},
            )
            # CAS bytes are in the tree at the frozen digest path:
            # .astrid/media/sha256/<d0d1>/<d2d3>/<digest>
            managed = (
                composition.projects_root
                / ".astrid"
                / "media"
                / "sha256"
                / DIGEST[:2]
                / DIGEST[2:4]
                / DIGEST
            )
            assert managed.is_file()
            assert managed.read_bytes() == PAYLOAD

            # Authoritative rows: one media, one task output, one attempt
            # terminal succeeded.
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM media") == 1
            )
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM task_outputs")
                == 1
            )

            # Gallery row with its primary variant summary.
            from astrid.packs.shots.generation_repository import (
                GenerationRepository,
            )

            generations = GenerationRepository()
            project_id = _project_id(composition, task_id)
            rows = generations.list(composition.writer, project_id)
            assert len(rows) == 1
            assert rows[0].task_id == task_id
            assert rows[0].primary_media_id is not None
            assert rows[0].variant_count == 1

            # Registry visibility: the merged asset key resolves to the
            # published digest.
            with composition.writer.read_only_connection() as conn:
                registry_raw = conn.execute(
                    "SELECT asset_registry_json FROM timelines WHERE id = ?",
                    (timeline_id,),
                ).fetchone()[0]
            registry = json.loads(registry_raw)
            assert registry["journey:upscaled"]["content_sha256"] == DIGEST

    def test_duplicate_admission_replays_same_task(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            composition = env["composition"]
            slug = "replay-proj"
            _create_project(composition, slug)
            status_first, first = _admit_simple(env, slug, "same-key")
            assert status_first == 201, first
            status_again, again = _admit_simple(env, slug, "same-key")
            assert status_again == 200, again
            assert again["task"]["id"] == first["task"]["id"]
            assert _db_count(composition, "SELECT COUNT(*) FROM tasks") == 1

    def test_poisoned_output_rejection_zero_rows(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            composition = env["composition"]
            slug = "poison-proj"
            _create_project(composition, slug)
            _status, admitted = _admit_simple(env, slug, "poison-admit")
            task_id = admitted["task"]["id"]
            claim = _claim(env)
            status, body = _complete_multipart(
                env,
                claim,
                task_id,
                key="poison-complete",
                sha_override="0" * 64,
            )
            assert status == 400, body
            assert body["error"] == "invalid_body"
            assert _db_count(composition, "SELECT COUNT(*) FROM media") == 0
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM task_outputs")
                == 0
            )
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM generations")
                == 0
            )
            # The task is untouched: still running, retryable.
            with composition.writer.read_only_connection() as conn:
                task_status = conn.execute(
                    "SELECT status FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()[0]
            assert task_status == "running"

    def test_cancel_queued_and_running(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            composition = env["composition"]
            slug = "cancel-journey"
            _create_project(composition, slug)

            # Queued cancel: no executor ever saw it.
            _status, queued = _admit_simple(env, slug, "cancel-q")
            qstatus, qcancel = _post(
                env,
                f"/projects/{slug}/tasks/{queued['task']['id']}/cancel",
                body={},
            )
            assert qstatus == 200, qcancel
            assert qcancel["task"]["status"] == "cancelled"
            # Idempotent repeat reports the current terminal state.
            rstatus, repeat = _post(
                env,
                f"/projects/{slug}/tasks/{queued['task']['id']}/cancel",
                body={},
            )
            assert rstatus == 200
            assert repeat["task"]["status"] == "cancelled"

            # A running task is owned by its live executor attempt.  An
            # unfenced operator cancellation must fail closed rather than
            # racing that executor's completion.
            _status, running = _admit_simple(env, slug, "cancel-r")
            running_id = running["task"]["id"]
            _claim(env)
            ustatus, unfenced = _post(
                env,
                f"/projects/{slug}/tasks/{running_id}/cancel",
                body={},
            )
            assert ustatus == 409, unfenced
            assert unfenced["error"] == "conflict"

            # Executor callers may still cancel with the complete strict
            # fence when they own it.
            _status, fenced_running = _admit_simple(env, slug, "cancel-r-fenced")
            fenced_id = fenced_running["task"]["id"]
            fenced_claim = _claim(env)
            attempt = fenced_claim["attempt"]
            fstatus, fenced = _post(
                env,
                f"/projects/{slug}/tasks/{fenced_id}/cancel",
                body={
                    "attempt_id": attempt["id"],
                    "lease_id": attempt["lease_id"],
                    "status_version": attempt["status_version"],
                },
            )
            assert fstatus == 200, fenced
            assert fenced["task"]["status"] == "cancelled"
            assert fenced["attempt"]["status"] == "cancelled"

            # Partial executor fences remain a typed body error and do not
            # weaken the strict transition contract.
            _status, partial_running = _admit_simple(env, slug, "cancel-r-partial")
            partial_id = partial_running["task"]["id"]
            partial_claim = _claim(env)
            pstatus, partial = _post(
                env,
                f"/projects/{slug}/tasks/{partial_id}/cancel",
                body={"attempt_id": partial_claim["attempt"]["id"]},
            )
            assert pstatus == 400, partial
            assert partial["error"] == "invalid_body"

    def test_merge_skipped_completion_receipt_is_replayable(
        self, tmp_bridge_root: Path
    ) -> None:
        """v3 N1 named test: a completion that skips the registry-visibility
        merge stays receipt-valid — the lost-ack replay returns exactly the
        stored result with zero new rows and no invented timeline head."""
        with task_server(tmp_bridge_root) as env:
            composition = env["composition"]
            slug = "skipmerge-proj"
            _create_project(composition, slug)
            _status, admitted = _admit_simple(env, slug, "skip-admit")
            task_id = admitted["task"]["id"]
            claim = _claim(env)
            status, first = _complete_multipart(
                env, claim, task_id, key="skip-complete"
            )
            assert status == 200, first
            assert first["timeline_head"] is None
            assert first["generation"] is not None

            media_before = _db_count(composition, "SELECT COUNT(*) FROM media")
            events_before = _db_count(
                composition, "SELECT COUNT(*) FROM events"
            )
            receipts_before = _db_count(
                composition, "SELECT COUNT(*) FROM command_receipts"
            )

            status2, replay = _complete_multipart(
                env, claim, task_id, key="skip-complete"
            )
            assert status2 == 200
            assert replay == first
            assert replay["timeline_head"] is None
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM media")
                == media_before
            )
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM events")
                == events_before
            )
            assert (
                _db_count(composition, "SELECT COUNT(*) FROM command_receipts")
                == receipts_before
            )
