"""B-3b orchestrator interleaving suite (plan task 7, batch B5).

Two halves, both driving the REAL composed bridge over HTTP:

**Checked transition table.** The admission table in
``orchestrator_transitions.py`` is proven total over its fact space,
precedence-checked arrow by arrow, fail-closed when a row goes missing.
Purity lints pin the two orchestration primitives: the deterministic
child key is spelled in exactly one module and never embeds an attempt
number; ``derive_children`` touches no RNG, clock, or filesystem.

**Adversary schedules.** A deterministic scheduler enumerates the crash /
retry / race space against one ``join_clips`` parent (3 segments + 1
stitch): lease expiry mid-fan-out, lost admission acks (per child),
crash between admissions i and i+1 (per i), cancel during replay, zombie
executor racing the reclaimed one, and executor restart during parent
settlement (per completed-prefix j). On every enumerated schedule the
same three invariants hold:

1. **child set == planned set** — exactly one row per ``(role, index)``
   of ``derive_children(parent_spec)``, zero duplicates;
2. **exactly-one parent-terminal** — one receipted terminal command,
   terminal status, settled once;
3. **no orphaned running children** — every child is terminal or safely
   unstarted, never running without an owner.

Deterministic: fixed inputs, enumerated parameters, no sleeps, no RNG;
lease expiry is forced through the recorded ``lease_expires_at`` column
and recovered through the receipt-protected ``core.task.expire`` sweep.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import threading
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest

from astrid.core.integrations.reigh.local_bridge_server import (
    TRUST_TOKEN_HEADER,
    create_local_bridge_server,
)
from astrid.core.integrations.reigh.orchestrator_transitions import (
    ADMISSION_TRANSITIONS,
    KEY_PREFIX,
    FenceFacts,
    OrchestratorPlanError,
    Verdict,
    classify_admission,
    derive_children,
    orch_child_key,
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
SLUG = "interleave"
EXEC_1 = "exec-alice"
EXEC_2 = "exec-bob"
CHILD_CAPABILITIES = ["reigh.join_clips_segment", "reigh.join_final_stitch"]

PLAN_SPEC: dict[str, Any] = {
    "family": "join_clips",
    "params": {"clip_source": "clips", "clips": ["a", "b", "c"]},
}
PLANNED = derive_children(PLAN_SPEC)


# ---------------------------------------------------------------------------
# Harness: composed bridge over HTTP (self-contained; runtime staging here
# mirrors tests/integrations/reigh/conftest.py's hermetic stub trees).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def staged_binding_runtimes(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path_factory.mktemp("orch-runtimes")
    vibecomfy = root / "VibeComfy"
    vibecomfy.mkdir()
    (vibecomfy / "pyproject.toml").write_text("", encoding="utf-8")
    wgp = root / "Wan2GP"
    wgp.mkdir()
    (wgp / "wgp.py").write_text("", encoding="utf-8")
    (wgp / "defaults").mkdir()
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

    def _timeline_repo_factory() -> object:
        from astrid.core.events.service import EventAppendService
        from astrid.core.receipts.service import ReceiptService
        from astrid.core.repositories.projects import ProjectRepository
        from astrid.packs.timeline.repository import TimelineRepository

        return TimelineRepository(
            events=EventAppendService(composition.registry),
            receipts=ReceiptService(),
            projects=ProjectRepository(events=None, receipts=None),
        )

    from astrid.core.integrations.reigh.bridge_service import ReighTaskBridge

    task_bridge = ReighTaskBridge(
        writer=composition.writer,
        registry=composition.registry,
        projects_root=composition.projects_root,
        generation_repo_factory=_generation_repo_factory,
        timeline_repo_factory=_timeline_repo_factory,
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


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", TRUST_TOKEN_HEADER: token}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _post(
    env: dict[str, Any], path: str, **kwargs: Any
) -> tuple[int, dict[str, Any]]:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    body = kwargs.get("body")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(env["base_url"] + path, data=data, method="POST")
    for name, value in _headers(env["token"], kwargs.get("key")).items():
        if name != "Content-Type" or data is not None:
            req.add_header(name, value)
    try:
        with urlopen(req) as response:  # noqa: S310 - localhost test only
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw) if raw else {}


def _multipart_body(
    manifest: dict[str, Any], files: dict[str, bytes]
) -> tuple[bytes, str]:
    boundary = "orchbnd1"
    parts: list[bytes] = []
    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="manifest"\r\n\r\n'
        ).encode()
        + json.dumps(manifest).encode()
        + b"\r\n"
    )
    for name, payload in files.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{name}.bin"\r\n\r\n'
            ).encode()
            + payload
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def _post_multipart(
    env: dict[str, Any],
    path: str,
    *,
    key: str,
    body: bytes,
    boundary: str,
) -> tuple[int, dict[str, Any]]:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    req = Request(env["base_url"] + path, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))
    req.add_header("Idempotency-Key", key)
    req.add_header(TRUST_TOKEN_HEADER, env["token"])
    try:
        with urlopen(req) as response:  # noqa: S310 - localhost test only
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


# ---------------------------------------------------------------------------
# Scenario drivers (the deterministic adversary scheduler's vocabulary)
# ---------------------------------------------------------------------------


class Scenario:
    """One orchestrated parent driven step by step through the bridge."""

    def __init__(self, env: dict[str, Any]) -> None:
        self.env = env
        self.composition = env["composition"]
        self._create_project()
        self.parent_id = self._admit_parent()

    def _create_project(self) -> None:
        def command(uow):
            return self.composition.projects.create(
                uow,
                slug=SLUG,
                name=SLUG.title(),
                settings={},
                idempotency_key=f"proj-{SLUG}",
                created_at=TS,
            )

        UnitOfWork(self.composition.writer).run(command)

    def _admit_parent(self) -> str:
        status, resp = _post(
            self.env,
            f"/projects/{SLUG}/tasks",
            key="k-parent",
            body={
                "family": PLAN_SPEC["family"],
                "input": dict(PLAN_SPEC["params"]),
            },
        )
        assert status == 201, resp
        return str(resp["task"]["id"])

    # -- executor side -----------------------------------------------------

    def claim(self, executor_id: str) -> dict[str, Any]:
        status, claim = _post(
            self.env,
            "/queue/claim",
            body={
                "executor_id": executor_id,
                "capabilities": ["reigh.join_clips_orchestrator"],
            },
        )
        assert status == 200, claim
        assert claim["task"]["id"] == self.parent_id
        return claim

    def adopt_live_attempt(self, executor_id: str) -> dict[str, Any]:
        """Rebuild the fence from persisted state alone (executor restart)."""
        row = self._live_attempt_row()
        assert row is not None
        assert str(row["executor_id"]) == executor_id
        return {
            "task": {"id": self.parent_id},
            "attempt": {
                "id": row["id"],
                "attempt_no": int(row["attempt_no"]),
                "lease_id": row["lease_id"],
                "status_version": int(row["status_version"]),
            },
        }

    def heartbeat(self, claim: dict[str, Any]) -> dict[str, Any]:
        attempt = claim["attempt"]
        status, beat = _post(
            self.env,
            (
                f"/tasks/{self.parent_id}/attempts/"
                f"{attempt['attempt_no']}/heartbeat"
            ),
            body={
                "attempt_id": attempt["id"],
                "lease_id": attempt["lease_id"],
                "status_version": attempt["status_version"],
            },
        )
        assert status == 200, beat
        return beat

    # -- child admission ---------------------------------------------------

    @staticmethod
    def _family(role: str) -> str:
        return (
            "join_clips_segment" if role == "segment" else "join_final_stitch"
        )

    def admit_child(
        self,
        claim: dict[str, Any],
        role: str,
        index: int,
        *,
        executor_id: str = EXEC_1,
    ) -> tuple[int, dict[str, Any]]:
        attempt = claim["attempt"]
        return _post(
            self.env,
            f"/projects/{SLUG}/tasks",
            key=orch_child_key(self.parent_id, role, index),
            body={
                "family": self._family(role),
                "input": {"segment_index": index},
                "child_admission": {
                    "parent_task_id": self.parent_id,
                    "parent_attempt_id": attempt["id"],
                    "executor_id": executor_id,
                    "lease_id": attempt["lease_id"],
                    "status_version": attempt["status_version"],
                    "role": role,
                    "index": index,
                },
            },
        )

    def fan_out(
        self, claim: dict[str, Any], *, executor_id: str = EXEC_1
    ) -> dict[tuple[str, int], str]:
        admitted: dict[tuple[str, int], str] = {}
        for role, index in PLANNED:
            status, body = self.admit_child(
                claim, role, index, executor_id=executor_id
            )
            assert status in (200, 201), body
            admitted[(role, index)] = str(body["task"]["id"])
        return admitted

    # -- settlement --------------------------------------------------------

    def complete(
        self,
        claim: dict[str, Any],
        task_id: str,
        key: str,
        *,
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
        body, boundary = _multipart_body(manifest, {"out0": payload})
        return _post_multipart(
            self.env,
            f"/tasks/{task_id}/attempts/{attempt['attempt_no']}/complete",
            key=key,
            body=body,
            boundary=boundary,
        )

    def settle_parent(
        self, claim: dict[str, Any], key: str = "k-parent-done"
    ) -> tuple[int, dict[str, Any]]:
        return self.complete(claim, self.parent_id, key)

    # -- adversary actions -------------------------------------------------

    def expire_leases(self) -> None:
        """Force every live lease into the past (deterministic clock)."""

        def command(uow):
            uow.execute(
                "UPDATE execution_attempts SET lease_expires_at = ? "
                "WHERE id IN (SELECT a.id FROM execution_attempts a "
                "JOIN tasks t ON a.task_id = t.id "
                "WHERE t.project_id = ? "
                "AND a.status IN ('claimed', 'running'))",
                (PAST, self.project_id()),
            )

        UnitOfWork(self.composition.writer).run(command)

    def sweep(self) -> None:
        """Run the receipt-protected expiry sweep until nothing is overdue."""
        from astrid.core.events.service import EventAppendService
        from astrid.core.receipts.service import ReceiptService

        tasks = TaskRepository(
            events=EventAppendService(self.composition.registry),
            receipts=ReceiptService(),
        )
        project_id = self.project_id()
        round_no = 0
        while True:
            round_no += 1

            def run(uow):
                return tasks.expire_overdue(
                    uow,
                    project_id=project_id,
                    idempotency_key=f"sweep-{project_id}-{round_no}",
                )

            result = UnitOfWork(self.composition.writer).run(run)
            if result is None:
                return

    def cancel(self, claim: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        attempt = claim["attempt"]
        return _post(
            self.env,
            f"/projects/{SLUG}/tasks/{self.parent_id}/cancel",
            body={
                "attempt_id": attempt["id"],
                "lease_id": attempt["lease_id"],
                "status_version": attempt["status_version"],
            },
        )

    @staticmethod
    def try_claim_child(scenario: "Scenario") -> tuple[int, dict[str, Any]]:
        return _post(
            scenario.env,
            "/queue/claim",
            body={
                "executor_id": EXEC_1,
                "capabilities": list(CHILD_CAPABILITIES),
            },
        )

    # -- persistence reads -------------------------------------------------

    def project_id(self) -> str:
        with self.composition.writer.read_only_connection() as conn:
            row = conn.execute(
                "SELECT project_id FROM tasks WHERE id = ?",
                (self.parent_id,),
            ).fetchone()
        assert row is not None
        return str(row[0])

    def _live_attempt_row(self) -> Any:
        with self.composition.writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            return conn.execute(
                "SELECT * FROM execution_attempts WHERE task_id = ? "
                "AND status IN ('claimed', 'running') "
                "ORDER BY attempt_no DESC LIMIT 1",
                (self.parent_id,),
            ).fetchone()


def _sqlite_row_factory(cursor: Any, row: Any) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Invariant checker: the three batch invariants over persisted state
# ---------------------------------------------------------------------------

TERMINAL_COMMAND_KINDS = (
    CORE_TASK_COMPLETE_COMMAND_KIND,
    CORE_TASK_CANCEL_COMMAND_KIND,
    CORE_TASK_FAIL_COMMAND_KIND,
)


def _child_rows(scenario: Scenario) -> dict[tuple[str, int], dict[str, Any]]:
    prefix = f"{KEY_PREFIX}:{scenario.parent_id}:"
    with scenario.composition.writer.read_only_connection() as conn:
        conn.row_factory = _sqlite_row_factory
        rows = conn.execute(
            "SELECT r.idempotency_key AS key, t.id AS task_id, "
            "t.status AS status, t.capability AS capability "
            "FROM command_receipts r "
            "JOIN tasks t ON t.event_stream_id = r.primary_stream_id "
            "WHERE r.idempotency_key LIKE ? "
            "AND r.command_kind = 'core.task.create'",
            (prefix + "%",),
        ).fetchall()
    parsed: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        parts = str(row["key"]).split(":")
        parsed[(parts[-2], int(parts[-1]))] = row
    return parsed


def _terminal_receipt_count(scenario: Scenario) -> int:
    with scenario.composition.writer.read_only_connection() as conn:
        stream = conn.execute(
            "SELECT event_stream_id FROM tasks WHERE id = ?",
            (scenario.parent_id,),
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM command_receipts "
            "WHERE primary_stream_id = ? "
            "AND command_kind IN (?, ?, ?)",
            (stream, *TERMINAL_COMMAND_KINDS),
        ).fetchone()[0]
    return int(count)


def assert_invariants(
    scenario: Scenario,
    *,
    expect_terminal: bool,
    expected_children: frozenset[tuple[str, int]] | None = None,
    expect_settlement_replay: tuple[dict[str, Any], str] | None = None,
) -> None:
    """Child set == planned set, zero duplicates, one parent terminal."""
    planned = frozenset(
        expected_children if expected_children is not None else PLANNED
    )
    rows = _child_rows(scenario)
    assert frozenset(rows) == planned, (sorted(rows), sorted(planned))
    child_ids = [str(row["task_id"]) for row in rows.values()]
    assert len(child_ids) == len(set(child_ids)) == len(planned)

    if expect_terminal:
        assert _terminal_receipt_count(scenario) == 1
        if expect_settlement_replay is not None:
            claim, key = expect_settlement_replay
            status, replay = scenario.settle_parent(claim, key=key)
            assert status == 200, replay
            # The replay returns the stored settlement: still exactly one.
            assert _terminal_receipt_count(scenario) == 1
    else:
        assert _terminal_receipt_count(scenario) == 0


def assert_parent_terminal(scenario: Scenario) -> None:
    with scenario.composition.writer.read_only_connection() as conn:
        status = conn.execute(
            "SELECT status FROM tasks WHERE id = ?",
            (scenario.parent_id,),
        ).fetchone()[0]
    assert status in ("succeeded", "failed", "cancelled"), status


def assert_no_orphaned_running_children(scenario: Scenario) -> None:
    running = [
        key
        for key, row in _child_rows(scenario).items()
        if row["status"] in ("claimed", "running")
    ]
    assert running == [], running


def drain_children(scenario: Scenario, key_prefix: str) -> int:
    """Claim and complete every queued child; return the completions."""
    counter = 0
    while True:
        status, claim = Scenario.try_claim_child(scenario)
        if status == 204:
            return counter
        assert status == 200, claim
        counter += 1
        done, body = scenario.complete(
            claim, str(claim["task"]["id"]), f"{key_prefix}-{counter}"
        )
        assert done == 200, body


# ---------------------------------------------------------------------------
# Part A — the checked transition table
# ---------------------------------------------------------------------------


class TestTransitionTable:
    def test_table_is_total_over_the_fact_space(self) -> None:
        combos = list(
            itertools.product((True, False), (True, False), (True, False), (True, False))
        )
        verdicts = [classify_admission(FenceFacts(*combo)) for combo in combos]
        assert all(isinstance(v, Verdict) for v in verdicts)
        census = Counter(verdicts)
        assert census == Counter(
            {
                Verdict.REPLAY_RECEIPTED: 8,
                Verdict.CONFLICT_PARENT_NOT_RUNNING: 4,
                Verdict.FORBIDDEN_FENCE_MISMATCH: 2,
                Verdict.CONFLICT_LEASE_EXPIRED: 1,
                Verdict.ADMIT_NEW: 1,
            }
        )

    def test_precedence_order_is_baked_into_the_rows(self) -> None:
        # A receipted key replays even with every other fact hostile.
        for combo in itertools.product((True, False), (True, False), (True, False)):
            assert classify_admission(FenceFacts(True, *combo)) is (
                Verdict.REPLAY_RECEIPTED
            )
        # Parent-running beats fence inspection; fence validity beats lease.
        assert classify_admission(FenceFacts(False, False, True, True)) is (
            Verdict.CONFLICT_PARENT_NOT_RUNNING
        )
        assert classify_admission(FenceFacts(False, True, False, False)) is (
            Verdict.FORBIDDEN_FENCE_MISMATCH
        )

    def test_missing_row_fails_closed_never_admits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from astrid.core.integrations.reigh import orchestrator_transitions as ot

        shrunk = dict(ADMISSION_TRANSITIONS)
        del shrunk[(False, True, True, True)]
        monkeypatch.setattr(ot, "ADMISSION_TRANSITIONS", shrunk)
        assert classify_admission(FenceFacts(False, True, True, True)) is (
            Verdict.FORBIDDEN_FENCE_MISMATCH
        )


class TestArrowsThroughTheRoute:
    """Each table arrow observed on the real HTTP surface."""

    @pytest.fixture
    def scenario(self, tmp_path: Path) -> Generator[Scenario, None, None]:
        with task_server(tmp_path) as env:
            yield Scenario(env)

    def test_arrow_admit_new_is_201(self, scenario: Scenario) -> None:
        claim = scenario.claim(EXEC_1)
        status, body = scenario.admit_child(claim, "segment", 0)
        assert status == 201, body
        assert_invariants(
            scenario,
            expect_terminal=False,
            expected_children=frozenset({("segment", 0)}),
        )

    def test_arrow_replay_receipted_is_200_same_row(
        self, scenario: Scenario
    ) -> None:
        claim = scenario.claim(EXEC_1)
        s1, first = scenario.admit_child(claim, "segment", 0)
        assert s1 == 201, first
        s2, replay = scenario.admit_child(claim, "segment", 0)
        assert s2 == 200, replay
        assert replay["task"]["id"] == first["task"]["id"]
        assert len(_child_rows(scenario)) == 1

    def test_arrow_conflict_parent_not_running_is_409(
        self, scenario: Scenario
    ) -> None:
        claim = scenario.claim(EXEC_1)
        cstatus, _ = scenario.cancel(claim)
        assert cstatus == 200
        status, body = scenario.admit_child(claim, "segment", 0)
        assert status == 409, body
        assert body["error"] == "conflict"

    def test_arrow_forbidden_fence_mismatch_is_403(
        self, scenario: Scenario
    ) -> None:
        claim = scenario.claim(EXEC_1)
        status, body = scenario.admit_child(
            claim, "segment", 0, executor_id="exec-zombie"
        )
        assert status == 403, body
        assert body["error"] == "child_admission_forbidden"
        assert_invariants(
            scenario, expect_terminal=False, expected_children=frozenset()
        )

    def test_arrow_conflict_lease_expired_is_409(
        self, scenario: Scenario
    ) -> None:
        claim = scenario.claim(EXEC_1)
        scenario.expire_leases()
        status, body = scenario.admit_child(claim, "segment", 0)
        assert status == 409, body
        assert body["error"] == "conflict"
        assert "expired" in body["detail"]
        assert_invariants(
            scenario, expect_terminal=False, expected_children=frozenset()
        )


# ---------------------------------------------------------------------------
# Part A — purity lints over the orchestration primitives
# ---------------------------------------------------------------------------

_BANNED_CALLEES = frozenset(
    {
        "random",
        "uuid",
        "uuid4",
        "datetime",
        "now",
        "time",
        "time_ns",
        "open",
        "Path",
        "socket",
        "urlopen",
        "generate_lowercase_ulid",
        "generate_ulid",
    }
)


def _function_node(name: str) -> ast.FunctionDef:
    import inspect

    from astrid.core.integrations.reigh import orchestrator_transitions as ot

    tree = ast.parse(inspect.getsource(ot))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


class TestPurityLints:
    def test_orch_key_namespace_has_exactly_one_authority(self) -> None:
        offenders = sorted(
            str(path)
            for path in Path("astrid").rglob("*.py")
            if "reigh.orch:v1" in path.read_text(encoding="utf-8")
            and path.name != "orchestrator_transitions.py"
        )
        assert offenders == [], offenders

    def test_primitives_are_syntactically_pure(self) -> None:
        for name in ("derive_children", "orch_child_key"):
            node = _function_node(name)
            for sub in ast.walk(node):
                assert not isinstance(sub, (ast.Import, ast.ImportFrom)), (
                    f"{name} imports inside its body"
                )
                if isinstance(sub, ast.Call):
                    func = sub.func
                    callee = (
                        getattr(func, "id", None)
                        if isinstance(func, ast.Name)
                        else getattr(func, "attr", None)
                        if isinstance(func, ast.Attribute)
                        else None
                    )
                    assert callee not in _BANNED_CALLEES, (name, callee)
                if isinstance(sub, ast.Attribute):
                    assert sub.attr not in _BANNED_CALLEES, (name, sub.attr)

    def test_derive_children_blind_to_rng_and_clock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import random
        import time

        def _forbidden(*_args: Any) -> None:
            raise AssertionError("purity violation: RNG/clock touched")

        monkeypatch.setattr(random, "random", _forbidden)
        monkeypatch.setattr(time, "time", _forbidden)
        expected = derive_children(PLAN_SPEC)
        assert derive_children(PLAN_SPEC) == expected

    def test_plan_is_deterministic_and_fail_closed(self) -> None:
        assert PLANNED == (
            ("segment", 0),
            ("segment", 1),
            ("segment", 2),
            ("stitch", 0),
        )
        travel = {
            "family": "travel_between_images",
            "params": {"image_urls": ["x", "y"]},
        }
        assert derive_children(travel) == (
            ("segment", 0),
            ("segment", 1),
            ("stitch", 0),
        )
        edit = {"family": "edit_video_orchestrator", "params": {}}
        assert derive_children(edit) == ()
        with pytest.raises(OrchestratorPlanError):
            derive_children({"family": "image_upscale", "params": {}})
        with pytest.raises(OrchestratorPlanError):
            derive_children({"params": {}})

    def test_key_never_embeds_an_attempt_number(self, tmp_path: Path) -> None:
        with task_server(tmp_path) as env:
            scenario = Scenario(env)
            claim = scenario.claim(EXEC_1)
            attempt_id = claim["attempt"]["id"]
            status, body = scenario.admit_child(claim, "segment", 0)
            assert status == 201, body
            key = orch_child_key(scenario.parent_id, "segment", 0)
            # The receipted identity is the (parent, role, index) triple:
            # neither the attempt id nor any lease/version material leaks
            # into the key space.
            assert attempt_id not in key
            assert key == f"reigh.orch:v1:{scenario.parent_id}:segment:0"
            # Retry under a NEW fence (heartbeat advanced the version)
            # resolves to the SAME row — attempt-independent identity.
            beat = scenario.heartbeat(claim)
            claim["attempt"]["status_version"] = int(
                beat["attempt"]["status_version"]
            )
            retry_status, retry = scenario.admit_child(claim, "segment", 0)
            assert retry_status == 200, retry
            assert retry["task"]["id"] == body["task"]["id"]
            assert len(_child_rows(scenario)) == 1


# ---------------------------------------------------------------------------
# Part B — the adversary schedules (deterministically enumerated)
# ---------------------------------------------------------------------------


class TestInterleavingSchedules:
    @pytest.fixture
    def scenario(self, tmp_path: Path) -> Generator[Scenario, None, None]:
        with task_server(tmp_path) as env:
            yield Scenario(env)

    def test_schedule_lease_expiry_mid_fan_out(
        self, scenario: Scenario
    ) -> None:
        claim1 = scenario.claim(EXEC_1)
        s0, first = scenario.admit_child(claim1, "segment", 0)
        s1, second = scenario.admit_child(claim1, "segment", 1)
        assert (s0, s1) == (201, 201), (first, second)
        admitted_before = {
            ("segment", 0): str(first["task"]["id"]),
            ("segment", 1): str(second["task"]["id"]),
        }

        # The lease dies mid-fan-out; the sweeper requeues the parent.
        scenario.expire_leases()
        scenario.sweep()
        claim2 = scenario.claim(EXEC_2)
        assert int(claim2["attempt"]["attempt_no"]) == 2

        # The reclaimed attempt replays the receipted keys and admits the
        # rest deterministically — no duplicates, no lost children.
        admitted = scenario.fan_out(claim2, executor_id=EXEC_2)
        for key, child_id in admitted_before.items():
            assert admitted[key] == child_id

        drain_children(scenario, "k-child-s1")
        status, body = scenario.settle_parent(claim2)
        assert status == 200, body
        assert_parent_terminal(scenario)
        assert_invariants(
            scenario,
            expect_terminal=True,
            expect_settlement_replay=(claim2, "k-parent-done"),
        )
        assert_no_orphaned_running_children(scenario)

    @pytest.mark.parametrize("acked_index", range(len(PLANNED)))
    def test_schedule_lost_admission_ack(
        self, scenario: Scenario, acked_index: int
    ) -> None:
        claim = scenario.claim(EXEC_1)
        role, index = PLANNED[acked_index]

        # The admission commits server-side but the ack is lost: the same
        # deterministic key is re-sent and MUST resolve to the same row.
        first_status, first = scenario.admit_child(claim, role, index)
        assert first_status == 201, first
        retry_status, retry = scenario.admit_child(claim, role, index)
        assert retry_status == 200, retry
        assert retry["task"]["id"] == first["task"]["id"]

        scenario.fan_out(claim)
        drain_children(scenario, f"k-child-lost-{acked_index}")
        status, body = scenario.settle_parent(claim)
        assert status == 200, body
        assert_parent_terminal(scenario)
        assert_invariants(scenario, expect_terminal=True)
        assert_no_orphaned_running_children(scenario)

    @pytest.mark.parametrize("crash_after", range(len(PLANNED)))
    def test_schedule_crash_between_admissions_i_and_i_plus_1(
        self, scenario: Scenario, crash_after: int
    ) -> None:
        claim1 = scenario.claim(EXEC_1)
        partial: dict[tuple[str, int], str] = {}
        for role, index in PLANNED[: crash_after + 1]:
            status, body = scenario.admit_child(claim1, role, index)
            assert status == 201, body
            partial[(role, index)] = str(body["task"]["id"])

        # Crash: no heartbeats, no completions, no clean shutdown. The
        # sweeper requeues; a fresh executor inherits the receipts.
        scenario.expire_leases()
        scenario.sweep()
        claim2 = scenario.claim(EXEC_2)

        admitted = scenario.fan_out(claim2, executor_id=EXEC_2)
        for key, child_id in partial.items():
            assert admitted[key] == child_id, key

        drain_children(scenario, f"k-child-crash-{crash_after}")
        status, body = scenario.settle_parent(claim2)
        assert status == 200, body
        assert_parent_terminal(scenario)
        # Orphan-or-replay, never mixed state: every pre-crash receipt
        # resolved to its original row post-crash.
        assert_invariants(
            scenario,
            expect_terminal=True,
            expect_settlement_replay=(claim2, "k-parent-done"),
        )
        assert_no_orphaned_running_children(scenario)

    def test_schedule_cancel_during_replay(self, scenario: Scenario) -> None:
        claim = scenario.claim(EXEC_1)
        status, first = scenario.admit_child(claim, "segment", 0)
        assert status == 201, first

        cstatus, cbody = scenario.cancel(claim)
        assert cstatus == 200, cbody

        # A lost-ack retry arriving AFTER cancellation replays the stored
        # receipt (identity is the key, not the fence) — same row, no
        # resurrection of the parent.
        replay_status, replay = scenario.admit_child(claim, "segment", 0)
        assert replay_status == 200, replay
        assert replay["task"]["id"] == first["task"]["id"]

        # A NEW child can never be admitted under a dead parent.
        new_status, new_body = scenario.admit_child(claim, "segment", 1)
        assert new_status == 409, new_body

        assert_parent_terminal(scenario)
        assert_invariants(
            scenario,
            expect_terminal=True,
            expected_children=frozenset({("segment", 0)}),
        )
        assert_no_orphaned_running_children(scenario)

    def test_schedule_zombie_executor_races_the_reclaimed_one(
        self, scenario: Scenario
    ) -> None:
        claim1 = scenario.claim(EXEC_1)
        zstatus, zombie_receipt = scenario.admit_child(claim1, "segment", 0)
        assert zstatus == 201, zombie_receipt

        scenario.expire_leases()
        scenario.sweep()
        claim2 = scenario.claim(EXEC_2)
        assert int(claim2["attempt"]["attempt_no"]) == 2

        # Zombie NEW admission: stale fence -> forbidden, zero writes.
        znew_status, znew = scenario.admit_child(claim1, "segment", 1)
        assert znew_status == 403, znew
        # Zombie REPLAY of the receipted key: harmless — the SAME row,
        # because identity is the key, never the caller's fence.
        zrep_status, zrep = scenario.admit_child(claim1, "segment", 0)
        assert zrep_status == 200, zrep
        assert zrep["task"]["id"] == zombie_receipt["task"]["id"]
        # Zombie parent settlement: fenced out, zero terminal rows.
        zs_status, zs_body = scenario.complete(
            claim1, scenario.parent_id, "k-zombie-settle"
        )
        assert zs_status == 409, zs_body

        # The reclaimed executor owns the future: full fan-out, drain,
        # settle exactly once.
        admitted = scenario.fan_out(claim2, executor_id=EXEC_2)
        assert admitted[("segment", 0)] == str(zombie_receipt["task"]["id"])
        drain_children(scenario, "k-child-zombie")
        status, body = scenario.settle_parent(claim2)
        assert status == 200, body
        assert_parent_terminal(scenario)
        assert_invariants(
            scenario,
            expect_terminal=True,
            expect_settlement_replay=(claim2, "k-parent-done"),
        )
        assert_no_orphaned_running_children(scenario)

    @pytest.mark.parametrize("completed_prefix", range(len(PLANNED) + 1))
    def test_schedule_executor_restart_during_parent_settlement(
        self, scenario: Scenario, completed_prefix: int
    ) -> None:
        claim = scenario.claim(EXEC_1)
        scenario.fan_out(claim)

        # Complete the first j children, then the executor restarts: all
        # in-memory state is gone; only persisted server state remains.
        for position in range(completed_prefix):
            cstatus, child_claim = Scenario.try_claim_child(scenario)
            assert cstatus == 200, child_claim
            done, body = scenario.complete(
                child_claim,
                str(child_claim["task"]["id"]),
                f"k-child-pre-{position}",
            )
            assert done == 200, body

        # A heartbeat before the crash advances status_version, so the
        # restarted executor MUST rebuild its fence from persisted state.
        scenario.heartbeat(claim)
        resumed = scenario.adopt_live_attempt(EXEC_1)
        assert resumed["attempt"]["id"] == claim["attempt"]["id"]
        assert resumed["attempt"]["status_version"] == (
            int(claim["attempt"]["status_version"]) + 1
        )

        # Remaining children are still queued (terminal children are
        # never claimable again), so a plain claim drain finishes them.
        position = completed_prefix
        while True:
            claim_status, child_claim = Scenario.try_claim_child(scenario)
            if claim_status == 204:
                break
            done, body = scenario.complete(
                child_claim,
                str(child_claim["task"]["id"]),
                f"k-child-post-{position}",
            )
            assert done == 200, body
            position += 1

        status, body = scenario.settle_parent(resumed)
        assert status == 200, body
        assert body["task"]["status"] == "succeeded"
        assert_parent_terminal(scenario)
        assert_invariants(
            scenario,
            expect_terminal=True,
            expect_settlement_replay=(resumed, "k-parent-done"),
        )
        assert_no_orphaned_running_children(scenario)
