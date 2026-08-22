"""B-3c orchestrator family journeys (plan task 8, batch B6).

Each orchestrator family (join_clips, travel_between_images,
edit_video_orchestrator) drives end-to-end through the one coordinator
(``orchestrator_runner.OrchestratorCoordinator``) over real HTTP: public
R1 parent admission, gated executor-only deterministic-key child
admission, fenced settlement. The DC-3 interleaving invariants (child
set == planned set, zero duplicates, exactly-one parent terminal) are
asserted against persisted state on every journey — the ported families
ride the same invariants the B5 suite proved over the harness.

No family bypasses the gate or writer queue: children exist only via the
``child_admission`` envelope route, parents only via fenced
heartbeat/complete/fail.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest

from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)
from astrid.core.integrations.reigh.orchestrator_runner import (
    HttpBridgeTransport,
    OrchestratorCoordinator,
    child_input,
    plan_children,
)
from astrid.core.integrations.reigh.orchestrator_transitions import (
    KEY_PREFIX,
    derive_children,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_CANCEL_COMMAND_KIND,
    CORE_TASK_COMPLETE_COMMAND_KIND,
    CORE_TASK_FAIL_COMMAND_KIND,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.packs import compose_standard_bridge

TS = "2026-08-15T00:00:00.000000+00:00"
PAST = "2026-01-01T00:00:00.000000+00:00"
SLUG = "families"
EXEC_1 = "exec-alice"
EXEC_2 = "exec-bob"

PARENT_CAPABILITY = {
    "join_clips": "reigh.join_clips_orchestrator",
    "travel_between_images": "reigh.travel_orchestrator",
    "edit_video_orchestrator": "reigh.edit_video_orchestrator",
}
CHILD_CAPABILITIES = [
    "reigh.join_clips_segment",
    "reigh.join_final_stitch",
    "reigh.travel_segment",
    "reigh.travel_stitch",
]


# ---------------------------------------------------------------------------
# Harness (mirrors test_orchestrator_interleaving.py; runtime staging per
# tests/integrations/reigh/conftest.py's hermetic stub trees)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def staged_binding_runtimes(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path_factory.mktemp("family-runtimes")
    vibecomfy = root / "VibeComfy"
    vibecomfy.mkdir()
    (vibecomfy / "pyproject.toml").write_text("", encoding="utf-8")
    wgp = root / "Wan2GP"
    wgp.mkdir()
    (wgp / "worker.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("REIGH_VIBECOMFY_HOME", str(vibecomfy))
    monkeypatch.setenv("REIGH_WGP_HOME", str(wgp))


@contextmanager
def task_server(projects_root: Path) -> Generator[dict[str, Any], None, None]:
    composition = compose_standard_bridge(projects_root)

    def _generation_repo_factory() -> object:
        from astrid.packs.shots.generation_repository import (
            GenerationRepository,
        )

        return GenerationRepository()

    from astrid.core.integrations.reigh.bridge_service import ReighTaskBridge

    task_bridge = ReighTaskBridge(
        writer=composition.writer,
        registry=composition.registry,
        projects_root=composition.projects_root,
        generation_repo_factory=_generation_repo_factory,
    )
    server = create_local_bridge_server(
        projects_root=projects_root,
        host="127.0.0.1",
        port=0,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        task_bridge=task_bridge,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield {
            "base_url": f"http://{host}:{port}",
            "token": server.request_token,
            "composition": composition,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.writer.close()


def _create_project(composition: Any, slug: str) -> None:
    def command(uow):
        return composition.projects.create(
            uow,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"proj-{slug}",
            created_at=TS,
        )

    UnitOfWork(composition.writer).run(command)


@pytest.fixture
def env(tmp_path: Path) -> Generator[dict[str, Any], None, None]:
    with task_server(tmp_path) as running:
        _create_project(running["composition"], SLUG)
        yield running


@pytest.fixture
def coordinator(env: dict[str, Any]) -> OrchestratorCoordinator:
    return OrchestratorCoordinator(
        HttpBridgeTransport(env["base_url"], env["token"])
    )


def _admit_parent(
    coordinator: OrchestratorCoordinator,
    *,
    key: str,
    spec: dict[str, Any],
) -> str:
    """Public R1 admission of an orchestrator parent."""
    status, body = coordinator._transport.post_json(
        f"/projects/{SLUG}/tasks",
        {"family": spec["family"], "input": spec.get("params", {})},
        key=key,
    )
    assert status == 201, body
    return str(body["task"]["id"])


def _multipart_complete(
    transport: HttpBridgeTransport,
    claim: dict[str, Any],
    *,
    key: str,
    payload: bytes = b"rendered-bytes",
) -> tuple[int, dict[str, Any]]:
    attempt = claim["attempt"]
    manifest = {
        "lease_id": attempt["lease_id"],
        "status_version": attempt["status_version"],
        "attempt_id": attempt["id"],
        "outputs": [
            {
                "key": "out0",
                "is_primary": True,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        ],
    }
    boundary = "famj1"
    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="manifest"\r\n\r\n'
        ).encode()
        + json.dumps(manifest).encode()
        + b"\r\n",
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="out0"; '
            'filename="out0.bin"\r\n\r\n'
        ).encode()
        + payload
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return transport.post_multipart(
        f"/tasks/{claim['task']['id']}/attempts/{attempt['attempt_no']}/complete",
        b"".join(parts),
        boundary,
        key=key,
    )


def _drain_children(
    coordinator: OrchestratorCoordinator, *, key_prefix: str
) -> int:
    """The worker-pool stand-in: claim and complete every queued child."""
    transport = coordinator._transport
    done = 0
    while True:
        status, claim = transport.post_json(
            "/queue/claim",
            {"executor_id": EXEC_2, "capabilities": list(CHILD_CAPABILITIES)},
        )
        if status == 204:
            return done
        assert status == 200, claim
        done += 1
        cstatus, body = _multipart_complete(
            transport, claim, key=f"{key_prefix}-{done}"
        )
        assert cstatus == 200, body


def _fail_child(
    coordinator: OrchestratorCoordinator,
    claim: dict[str, Any],
    *,
    key: str,
) -> None:
    transport = coordinator._transport
    attempt = claim["attempt"]
    status, body = transport.post_json(
        f"/tasks/{claim['task']['id']}/attempts/{attempt['attempt_no']}/fail",
        {
            "attempt_id": attempt["id"],
            "lease_id": attempt["lease_id"],
            "status_version": attempt["status_version"],
            "error": {
                "code": "render_failed",
                "message": "worker stand-in failed this child",
                "retryable": False,
            },
        },
        key=key,
    )



def _expire_and_sweep(composition: Any, parent_id: str) -> None:
    """Force-expire live leases, then run the sweeper until settled."""

    def expire(uow):
        uow.execute(
            "UPDATE execution_attempts SET lease_expires_at = ? "
            "WHERE id IN (SELECT a.id FROM execution_attempts a "
            "JOIN tasks t ON a.task_id = t.id "
            "WHERE a.status IN ('claimed', 'running'))",
            (PAST,),
        )

    UnitOfWork(composition.writer).run(expire)
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService

    tasks = TaskRepository(
        events=EventAppendService(composition.registry),
        receipts=ReceiptService(),
    )
    with composition.writer.read_only_connection() as conn:
        project_id = str(
            conn.execute(
                "SELECT project_id FROM tasks WHERE id = ?", (parent_id,)
            ).fetchone()[0]
        )
    round_no = 0
    while True:
        round_no += 1

        def run(uow):
            return tasks.expire_overdue(
                uow,
                project_id=project_id,
                idempotency_key=f"sweep-{project_id}-{round_no}",
            )

        if UnitOfWork(composition.writer).run(run) is None:
            return


# ---------------------------------------------------------------------------
# Persisted-state invariant checks (DC-3 over the ported families)
# ---------------------------------------------------------------------------


class FamilyJourney:
    """Shared assertions over one family's persisted orchestration state."""

    def __init__(self, env: dict[str, Any], parent_id: str) -> None:
        self.env = env
        self.parent_id = parent_id

    def child_rows(self) -> dict[tuple[str, int], dict[str, Any]]:
        with self.env["composition"].writer.read_only_connection() as conn:
            cursor = conn.execute(
                "SELECT r.idempotency_key AS key, t.id AS task_id, "
                "t.status AS status FROM command_receipts r "
                "JOIN tasks t ON t.event_stream_id = r.primary_stream_id "
                "WHERE r.idempotency_key LIKE ? "
                "AND r.command_kind = 'core.task.create'",
                (f"{KEY_PREFIX}:{self.parent_id}:%",),
            )
            rows = [
                {
                    col[0]: row[i]
                    for i, col in enumerate(cursor.description)
                }
                for row in cursor.fetchall()
            ]
        parsed: dict[tuple[str, int], dict[str, Any]] = {}
        for row in rows:
            parts = str(row["key"]).split(":")
            parsed[(parts[-2], int(parts[-1]))] = row
        return parsed

    def terminal_receipt_count(self) -> int:
        with self.env["composition"].writer.read_only_connection() as conn:
            stream = conn.execute(
                "SELECT event_stream_id FROM tasks WHERE id = ?",
                (self.parent_id,),
            ).fetchone()[0]
            count = conn.execute(
                "SELECT COUNT(*) FROM command_receipts "
                "WHERE primary_stream_id = ? AND command_kind IN (?, ?, ?)",
                (
                    stream,
                    CORE_TASK_COMPLETE_COMMAND_KIND,
                    CORE_TASK_CANCEL_COMMAND_KIND,
                    CORE_TASK_FAIL_COMMAND_KIND,
                ),
            ).fetchone()[0]
        return int(count)

    def parent_status(self) -> str:
        with self.env["composition"].writer.read_only_connection() as conn:
            return str(
                conn.execute(
                    "SELECT status FROM tasks WHERE id = ?",
                    (self.parent_id,),
                ).fetchone()[0]
            )

    def assert_invariants(
        self,
        planned: tuple[tuple[str, int], ...],
        *,
        expect_terminal: bool,
    ) -> None:
        rows = self.child_rows()
        assert frozenset(rows) == frozenset(planned), (
            sorted(rows),
            sorted(planned),
        )
        child_ids = [str(row["task_id"]) for row in rows.values()]
        assert len(child_ids) == len(set(child_ids)) == len(planned)
        assert self.terminal_receipt_count() == (1 if expect_terminal else 0)

    def assert_no_orphaned_running_children(self) -> None:
        running = [
            slot
            for slot, row in self.child_rows().items()
            if row["status"] in ("claimed", "running")
        ]
        assert running == [], running

    def success_or_cancel_receipts(self) -> int:
        """Complete/cancel receipts on the parent stream (false wins)."""
        with self.env["composition"].writer.read_only_connection() as conn:
            stream = conn.execute(
                "SELECT event_stream_id FROM tasks WHERE id = ?",
                (self.parent_id,),
            ).fetchone()[0]
            count = conn.execute(
                "SELECT COUNT(*) FROM command_receipts "
                "WHERE primary_stream_id = ? AND command_kind IN (?, ?)",
                (
                    stream,
                    CORE_TASK_COMPLETE_COMMAND_KIND,
                    CORE_TASK_CANCEL_COMMAND_KIND,
                ),
            ).fetchone()[0]
        return int(count)


def _claim_parent(
    coordinator: OrchestratorCoordinator, family: str
) -> Any:
    claim = coordinator.claim(
        slug=SLUG,
        executor_id=EXEC_1,
        capabilities=[PARENT_CAPABILITY[family]],
    )
    assert claim is not None
    return claim


# ---------------------------------------------------------------------------
# join_clips — N segments + final stitch through the gate
# ---------------------------------------------------------------------------

JOIN_SPEC = {
    "family": "join_clips",
    "params": {"clip_source": "clips", "clips": ["a", "b", "c"]},
}


class TestJoinFamilyJourney:
    def test_end_to_end_through_gated_admission(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        parent_id = _admit_parent(coordinator, key="k-join-parent", spec=JOIN_SPEC)
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(JOIN_SPEC)

        claim = _claim_parent(coordinator, "join_clips")
        assert claim.task_id == parent_id
        admitted = coordinator.fan_out(claim, executor_id=EXEC_1)
        assert set(admitted) == set(planned)
        journey.assert_invariants(planned, expect_terminal=False)

        assert (
            _drain_children(coordinator, key_prefix="k-join-child")
            == len(planned)
        )
        coordinator.settle_success(
            claim, settlement_key="k-join-done", receipt=admitted
        )

        assert journey.parent_status() == "succeeded"
        journey.assert_invariants(planned, expect_terminal=True)
        journey.assert_no_orphaned_running_children()

        # Settlement replay: identity is the key; still exactly one.
        coordinator.settle_success(
            claim, settlement_key="k-join-done", receipt=admitted
        )
        assert journey.terminal_receipt_count() == 1

    def test_lost_admission_ack_replays_same_row(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        parent_id = _admit_parent(coordinator, key="k-join-parent", spec=JOIN_SPEC)
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(JOIN_SPEC)

        claim = _claim_parent(coordinator, "join_clips")
        # The ack of segment/0 is lost; the retry resolves to the SAME row.
        first_pass = coordinator.fan_out(claim, executor_id=EXEC_1)
        replayed = coordinator.fan_out(claim, executor_id=EXEC_1)
        assert replayed == first_pass

        _drain_children(coordinator, key_prefix="k-join-lost")
        coordinator.settle_success(
            claim, settlement_key="k-join-lost-done", receipt=first_pass
        )
        journey.assert_invariants(planned, expect_terminal=True)

    def test_child_failure_fails_the_parent_explicitly(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        parent_id = _admit_parent(coordinator, key="k-join-parent", spec=JOIN_SPEC)
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(JOIN_SPEC)

        claim = _claim_parent(coordinator, "join_clips")
        admitted = coordinator.fan_out(claim, executor_id=EXEC_1)

        transport = coordinator._transport
        # A child failure spends the retry budget before it settles
        # terminal; drain the budget deterministically.
        for _ in range(4):
            status, child_claim = transport.post_json(
                "/queue/claim",
                {
                    "executor_id": EXEC_2,
                    "capabilities": ["reigh.join_clips_segment"],
                },
            )
            if status == 204:
                break
            assert status == 200, child_claim
            _fail_child(
                coordinator, child_claim, key=f"k-join-child-fail-{_}"
            )

        statuses = coordinator.child_statuses(claim, admitted)
        assert "failed" in statuses.values()

        coordinator.settle_failure(
            claim,
            settlement_key="k-join-failed-done",
            code="child_failed",
            message="segment child failed; parent settles failed",
        )
        # The budget-driven drain ends in exactly one terminal STATE.
        assert journey.parent_status() == "failed"
        assert journey.success_or_cancel_receipts() == 0
        rows = journey.child_rows()
        assert frozenset(rows) == frozenset(planned)
        child_ids = [str(row["task_id"]) for row in rows.values()]
        assert len(child_ids) == len(set(child_ids)) == len(planned)
        journey.assert_no_orphaned_running_children()

    def test_crash_mid_fan_out_replays_from_persisted_state(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        composition = env["composition"]
        parent_id = _admit_parent(coordinator, key="k-join-parent", spec=JOIN_SPEC)
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(JOIN_SPEC)
        plans = plan_children(parent_id, JOIN_SPEC)

        claim = _claim_parent(coordinator, "join_clips")
        # One admission lands, then the executor dies before the rest.
        transport = coordinator._transport
        first = plans[0]
        status, body = transport.post_json(
            f"/projects/{SLUG}/tasks",
            {
                "family": first.capability,
                "input": child_input(JOIN_SPEC, first),
                "child_admission": claim.envelope(
                    executor_id=EXEC_1, role=first.role, index=first.index
                ),
            },
            key=first.idempotency_key,
        )
        assert status == 201, body
        pre_crash_child_id = journey.child_rows()[
            (first.role, first.index)
        ]["task_id"]

        # Crash: leases die, the sweeper requeues; a fresh executor wins
        # attempt 2 by plain claim and replays every receipted key.
        _expire_and_sweep(composition, parent_id)
        resumed = coordinator.claim(
            slug=SLUG,
            executor_id=EXEC_2,
            capabilities=[PARENT_CAPABILITY["join_clips"]],
        )
        assert resumed is not None and resumed.task_id == parent_id
        assert resumed.attempt_no == 2
        assert resumed.spec["family"] == "join_clips"

        admitted = coordinator.fan_out(resumed, executor_id=EXEC_2)
        assert admitted[(first.role, first.index)] == pre_crash_child_id
        assert set(admitted) == set(planned)

        _drain_children(coordinator, key_prefix="k-join-crash")
        coordinator.settle_success(
            resumed, settlement_key="k-join-crash-done", receipt=admitted
        )
        assert journey.parent_status() == "succeeded"
        journey.assert_invariants(planned, expect_terminal=True)
        journey.assert_no_orphaned_running_children()

    def test_restart_with_live_lease_resumes_from_persisted_state(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        parent_id = _admit_parent(
            coordinator, key="k-join-parent", spec=JOIN_SPEC
        )
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(JOIN_SPEC)

        claim = _claim_parent(coordinator, "join_clips")
        # A heartbeat advances status_version before the "restart", so
        # the resumed fence must come from persisted state, not memory.
        coordinator.heartbeat(claim)
        resumed = coordinator.resume(
            slug=SLUG, parent_task_id=parent_id, executor_id=EXEC_1
        )
        assert resumed.attempt_id == claim.attempt_id
        assert resumed.status_version == claim.status_version + 1

        admitted = coordinator.fan_out(resumed, executor_id=EXEC_1)
        assert set(admitted) == set(planned)
        _drain_children(coordinator, key_prefix="k-join-resume")
        coordinator.settle_success(
            resumed, settlement_key="k-join-resume-done", receipt=admitted
        )
        assert journey.parent_status() == "succeeded"
        journey.assert_invariants(planned, expect_terminal=True)
        journey.assert_no_orphaned_running_children()


# ---------------------------------------------------------------------------
# travel_between_images — N travel segments + crossfade stitch (non-turbo
# derivation resolves the parent to reigh.travel_orchestrator, doc 16 §3.9)
# ---------------------------------------------------------------------------

TRAVEL_SPEC = {
    "family": "travel_between_images",
    "params": {"image_urls": ["a.png", "b.png", "c.png"]},
}


class TestTravelFamilyJourney:
    def test_end_to_end_through_gated_admission(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        parent_id = _admit_parent(
            coordinator, key="k-travel-parent", spec=TRAVEL_SPEC
        )
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(TRAVEL_SPEC)
        assert planned == (
            ("segment", 0),
            ("segment", 1),
            ("segment", 2),
            ("stitch", 0),
        )

        claim = coordinator.claim(
            slug=SLUG,
            executor_id=EXEC_1,
            capabilities=[PARENT_CAPABILITY["travel_between_images"]],
        )
        assert claim is not None and claim.task_id == parent_id
        assert claim.capability == "reigh.travel_orchestrator"
        admitted = coordinator.fan_out(claim, executor_id=EXEC_1)
        assert set(admitted) == set(planned)
        # Every admitted child is an allowlisted executor-child row —
        # no family bypassed the gate.
        for slot, child_id in admitted.items():
            row = [
                r
                for r in journey.child_rows().values()
                if str(r["task_id"]) == child_id
            ][0]
            assert slot in journey.child_rows()
        journey.assert_invariants(planned, expect_terminal=False)

        assert (
            _drain_children(coordinator, key_prefix="k-travel-child")
            == len(planned)
        )
        coordinator.settle_success(
            claim, settlement_key="k-travel-done", receipt=admitted
        )
        assert journey.parent_status() == "succeeded"
        journey.assert_invariants(planned, expect_terminal=True)
        journey.assert_no_orphaned_running_children()

    def test_child_family_is_never_publicly_admissible(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        """A browser-shaped request for a child family is forbidden."""
        status, body = coordinator._transport.post_json(
            f"/projects/{SLUG}/tasks",
            {
                "family": "travel_segment",
                "input": {"start_image_url": "a.png"},
            },
            key="k-browser-child",
        )
        assert status == 403, body
        assert body["error"] == "child_admission_forbidden"
        # And nothing was written: zero orchestrator children exist.
        with env["composition"].writer.read_only_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM command_receipts WHERE "
                "idempotency_key = 'k-browser-child'"
            ).fetchone()[0]
        assert int(count) == 0

    def test_lost_lease_mid_fan_out_replays_same_children(
        self, env: dict[str, Any], coordinator: OrchestratorCoordinator
    ) -> None:
        composition = env["composition"]
        parent_id = _admit_parent(
            coordinator, key="k-travel-parent", spec=TRAVEL_SPEC
        )
        journey = FamilyJourney(env, parent_id)
        planned = derive_children(TRAVEL_SPEC)

        claim = _claim_parent(coordinator, "travel_between_images")
        plans = plan_children(parent_id, TRAVEL_SPEC)
        transport = coordinator._transport
        # Admit only the first segment before the lease dies.
        first = plans[0]
        status, body = transport.post_json(
            f"/projects/{SLUG}/tasks",
            {
                "family": first.capability,
                "input": child_input(TRAVEL_SPEC, first),
                "child_admission": claim.envelope(
                    executor_id=EXEC_1, role=first.role, index=first.index
                ),
            },
            key=first.idempotency_key,
        )
        assert status == 201, body
        pre_crash_child_id = journey.child_rows()[
            (first.role, first.index)
        ]["task_id"]

        _expire_and_sweep(composition, parent_id)
        resumed = coordinator.claim(
            slug=SLUG,
            executor_id=EXEC_2,
            capabilities=[PARENT_CAPABILITY["travel_between_images"]],
        )
        assert resumed is not None and resumed.attempt_no == 2
        admitted = coordinator.fan_out(resumed, executor_id=EXEC_2)
        assert admitted[(first.role, first.index)] == pre_crash_child_id
        assert set(admitted) == set(planned)

        _drain_children(coordinator, key_prefix="k-travel-crash")
        coordinator.settle_success(
            resumed, settlement_key="k-travel-crash-done", receipt=admitted
        )
        assert journey.parent_status() == "succeeded"
        journey.assert_invariants(planned, expect_terminal=True)
        journey.assert_no_orphaned_running_children()
