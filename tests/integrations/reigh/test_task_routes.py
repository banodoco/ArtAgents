"""Acceptance fixtures for the Reigh bridge task routes (doc 27 §§3-5).

Covers the R1 admission trio, the T8 child-admission hard gate, the fenced
claim/heartbeat pair, atomic multipart completion (happy path, lost-ack
replay, wrong fence, poisoned bytes), fenced failure, and the bounded
parser-abuse suite.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest

from astrid.core.integrations.reigh.local_bridge_server import create_local_bridge_server
from astrid.core.store.uow import UnitOfWork
from astrid.packs import compose_standard_bridge

TS = "2026-08-15T00:00:00.000000+00:00"


@contextmanager
def task_server(
    projects_root: Path,
) -> Generator[dict[str, Any], None, None]:
    """A fully composed serve root: timeline bridge + task bridge."""
    composition = compose_standard_bridge(projects_root)
    server = create_local_bridge_server(
        projects_root=projects_root,
        host="127.0.0.1",
        port=0,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        task_bridge=composition.task_bridge,
        auth_token="test-token",
        release_mode=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield {
            "base_url": f"http://{host}:{port}",
            "token": "test-token",
            "composition": composition,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.writer.close()


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Astrid-Bridge-Version": "v1",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _request_json(
    env: dict[str, Any],
    method: str,
    path: str,
    *,
    key: str | None = None,
    body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(env["base_url"] + path, data=data, method=method)
    for name, value in _headers(env["token"], key).items():
        if name != "Content-Type" or data is not None:
            req.add_header(name, value)
    for name, value in (extra_headers or {}).items():
        req.add_header(name, value)
    try:
        with urlopen(req) as response:  # noqa: S310 - localhost test only
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw) if raw else {}


def _post(
    env: dict[str, Any], path: str, **kwargs: Any
) -> tuple[int, dict[str, Any]]:
    return _request_json(env, "POST", path, **kwargs)


def _get(
    env: dict[str, Any], path: str
) -> tuple[int, dict[str, Any]]:
    return _request_json(env, "GET", path)


def _create_project(composition, slug: str) -> str:
    from astrid.core.repositories.projects import ProjectRepository

    projects = ProjectRepository(events=None, receipts=None)

    def command(uow):
        return projects.create(
            uow,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"proj-{slug}",
            created_at=TS,
        )

    return UnitOfWork(composition.writer).run(command).id


def _create_project(composition, slug: str) -> str:
    def command(uow):
        return composition.projects.create(
            uow,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"proj-{slug}",
            created_at=TS,
        )

    return UnitOfWork(composition.writer).run(command).id


def _admit_simple(
    env: dict[str, Any],
    slug: str,
    key: str,
) -> tuple[int, dict[str, Any]]:
    return _post(
        env,
        f"/projects/{slug}/tasks",
        key=key,
        body={
            "family": "image_upscale",
            "input": {
                "image_url": "http://127.0.0.1:9/x.png",
                "scale_factor": 2,
            },
        },
    )


def _db_count(composition, sql: str, params: tuple = ()) -> int:
    with composition.writer.read_only_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row[0])


def _create_timeline(
    composition: Any, project_id: str, *, slug: str = "render-source"
) -> Any:
    return UnitOfWork(composition.writer).run(
        lambda uow: composition.timelines.create(
            uow,
            project_id=project_id,
            slug=slug,
            name="Render Source",
            config={"clips": []},
            registry={"assets": {}},
            idempotency_key=f"timeline-{slug}",
            created_at=TS,
        )
    )


def _multipart_body(
    manifest: dict[str, Any],
    files: dict[str, bytes],
) -> tuple[bytes, str]:
    boundary = "testbnd123"
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
    req.add_header("Authorization", f"Bearer {env['token']}")
    req.add_header("X-Astrid-Bridge-Version", "v1")
    try:
        with urlopen(req) as response:  # noqa: S310 - localhost test only
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


# ---------------------------------------------------------------------------
# T5: R1 admission trio + validation surface
# ---------------------------------------------------------------------------


class TestAdmission:
    def test_trio_201_then_200_replay_then_409_mismatch(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "admit-proj"
            _create_project(env["composition"], slug)
            status, first = _admit_simple(env, slug, "reigh.admit:k1")
            assert status == 201
            assert first["task"]["capability"] == "reigh.image_upscale"
            assert first["task"]["status"] == "queued"

            status, replay = _admit_simple(env, slug, "reigh.admit:k1")
            assert status == 200
            assert replay["task"]["id"] == first["task"]["id"]

            status, mismatch = _request_json(
                env,
                "POST",
                f"/projects/{slug}/tasks",
                key="reigh.admit:k1",
                body={
                    "family": "image_upscale",
                    "input": {"image_url": "http://127.0.0.1:9/other.png"},
                },
            )
            assert status == 409
            assert mismatch["error"] == "idempotency_mismatch"

    def test_missing_key_is_rejected(self, tmp_bridge_root: Path) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "nokey-proj"
            _create_project(env["composition"], slug)
            status, body = _post(
                env,
                f"/projects/{slug}/tasks",
                body={"family": "image_upscale", "input": {"image_url": "x"}},
            )
            assert status == 400
            assert "Idempotency-Key" in body["detail"]

    def test_unknown_and_dead_families_map_to_capability_unavailable(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "dead-proj"
            _create_project(env["composition"], slug)
            for family, payload in (
                ("no_such_family", {}),
                ("edit_video_segment", {}),
                ("wan_lora_training", {}),
            ):
                status, body = _post(
                    env,
                    f"/projects/{slug}/tasks",
                    key=f"k-{family}",
                    body={"family": family, "input": payload},
                )
                assert status == 422, (family, status, body)
                assert body["error"] == "capability_unavailable"

    def test_invalid_input_maps_to_400(self, tmp_bridge_root: Path) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "badinput-proj"
            _create_project(env["composition"], slug)
            status, body = _post(
                env,
                f"/projects/{slug}/tasks",
                key="k-bad",
                body={"family": "magic_edit", "input": {"prompt": "p"}},
            )
            assert status == 400

    def test_render_export_version_fence_is_atomic_and_replayable(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            composition = env["composition"]
            slug = "render-proj"
            project_id = _create_project(composition, slug)
            timeline = _create_timeline(composition, project_id)
            path = f"/projects/{slug}/tasks"

            def admit(key: str, expected_version: int) -> tuple[int, dict[str, Any]]:
                return _post(
                    env,
                    path,
                    key=key,
                    body={
                        "family": "render_export",
                        "input": {
                            "timeline_ref": timeline.slug,
                            "expected_version": expected_version,
                            "destination": "download",
                        },
                    },
                )

            # Creation commits the timeline at head 1. A stale fence must
            # leave both the task projection and its receipt absent.
            status, stale = admit("render-stale-0", 0)
            assert status == 409, stale
            assert stale["error"] == "conflict"
            assert stale["config_version"] == 1
            assert _db_count(composition, "SELECT COUNT(*) FROM tasks") == 0
            assert (
                _db_count(
                    composition,
                    "SELECT COUNT(*) FROM command_receipts "
                    "WHERE idempotency_key = ?",
                    ("render-stale-0",),
                )
                == 0
            )

            status, admitted = admit("render-at-head-1", 1)
            assert status == 201, admitted
            task_id = admitted["task"]["id"]

            next_head = UnitOfWork(composition.writer).run(
                lambda uow: composition.timelines.merge_registry(
                    uow,
                    project_id=project_id,
                    timeline_id=timeline.timeline_id,
                    entries={"new-asset": {"type": "image"}},
                    created_at="2026-08-15T00:00:01.000000+00:00",
                )
            )
            assert next_head == 2

            # A lost-ack replay remains a replay even after the timeline
            # advances, but the same old fence under a new key is rejected.
            status, replay = admit("render-at-head-1", 1)
            assert status == 200, replay
            assert replay["task"]["id"] == task_id
            status, now_stale = admit("render-stale-1", 1)
            assert status == 409, now_stale
            assert now_stale["config_version"] == 2
            assert _db_count(composition, "SELECT COUNT(*) FROM tasks") == 1

    def test_child_family_via_browser_path_is_forbidden(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "childforbid-proj"
            _create_project(env["composition"], slug)
            status, body = _post(
                env,
                f"/projects/{slug}/tasks",
                key="k-child-browser",
                body={"family": "travel_segment", "input": {}},
            )
            assert status == 403
            assert body["error"] == "child_admission_forbidden"


# ---------------------------------------------------------------------------
# T8: the child-admission hard gate
# ---------------------------------------------------------------------------


class TestChildGate:
    @pytest.fixture
    def claimed_parent(self, tmp_bridge_root: Path) -> dict[str, Any]:
        with task_server(tmp_bridge_root) as env:
            slug = "childgate-proj"
            _create_project(env["composition"], slug)
            status, task_resp = _post(
                env,
                f"/projects/{slug}/tasks",
                key="k-parent",
                body={
                    "family": "join_clips",
                    "input": {"clip_source": "clips", "clips": ["a", "b"]},
                },
            )
            assert status == 201, task_resp
            parent_id = task_resp["task"]["id"]
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "exec-1",
                    "capabilities": ["reigh.join_clips_orchestrator"],
                },
            )
            assert cstatus == 200, claim
            yield {
                "env": env,
                "slug": slug,
                "parent_id": parent_id,
                "claim": claim,
            }

    def _child_request(
        self, fixture: dict[str, Any], *, overrides: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        claim = fixture["claim"]
        attempt = claim["attempt"]
        envelope = {
            "parent_task_id": fixture["parent_id"],
            "parent_attempt_id": attempt["id"],
            "executor_id": "exec-1",
            "lease_id": attempt["lease_id"],
            "status_version": attempt["status_version"],
            "role": "segment",
            "index": 0,
        }
        envelope.update(overrides.get("envelope", {}))
        key = overrides.get(
            "key",
            f"reigh.orch:v1:{fixture['parent_id']}:segment:0",
        )
        body = {
            "family": "join_clips_segment",
            "input": {"segment_index": 0},
            "child_admission": envelope,
        }
        return _post(
            fixture["env"],
            f"/projects/{fixture['slug']}/tasks",
            key=key,
            body=body,
        )

    def test_valid_envelope_admits_child(
        self, claimed_parent: dict[str, Any]
    ) -> None:
        status, body = self._child_request(claimed_parent, overrides={})
        assert status == 201, body
        assert body["task"]["capability"] == "reigh.join_clips_segment"
        assert body["task"]["project_id"] == (
            claimed_parent["claim"]["task"]["project_id"]
        )

    def test_forged_executor_or_lease_rejected(
        self, claimed_parent: dict[str, Any]
    ) -> None:
        for field in ("executor_id", "lease_id"):
            status, body = self._child_request(
                claimed_parent,
                overrides={"envelope": {field: "forged-value"}},
            )
            assert status == 403, (field, body)
            assert body["error"] == "child_admission_forbidden"

    def test_stale_fence_rejected(
        self, claimed_parent: dict[str, Any]
    ) -> None:
        attempt = claimed_parent["claim"]["attempt"]
        status, body = self._child_request(
            claimed_parent,
            overrides={
                "envelope": {"status_version": attempt["status_version"] + 5}
            },
        )
        assert status == 403, body

    def test_nondeterministic_key_rejected(
        self, claimed_parent: dict[str, Any]
    ) -> None:
        status, body = self._child_request(
            claimed_parent,
            overrides={"key": "browser-chosen-arbitrary-key"},
        )
        assert status == 403
        assert body["error"] == "child_admission_forbidden"

    def test_non_child_capability_never_passes_gate(
        self, claimed_parent: dict[str, Any]
    ) -> None:
        claim = claimed_parent["claim"]
        attempt = claim["attempt"]
        env = claimed_parent["env"]
        body = {
            "family": "join_clips_segment",
            "input": {},
            "child_admission": {
                "parent_task_id": claimed_parent["parent_id"],
                "parent_attempt_id": attempt["id"],
                "executor_id": "exec-1",
                "lease_id": attempt["lease_id"],
                "status_version": attempt["status_version"],
                "role": "segment",
                "index": 0,
            },
        }
        # A public-only family through the gate: unknown child -> rejected.
        body2 = dict(body, family="wan_2_2_t2i")
        status, resp = _post(
            env,
            f"/projects/{claimed_parent['slug']}/tasks",
            key=f"reigh.orch:v1:{claimed_parent['parent_id']}:t2i:0",
            body=body2,
        )
        assert status == 403


# ---------------------------------------------------------------------------
# T6: claim ordering + heartbeat semantics
# ---------------------------------------------------------------------------


class TestClaimAndHeartbeat:
    def test_empty_queue_returns_keyless_204(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            status, body = _post(
                env,
                "/queue/claim",
                body={"executor_id": "e1", "capabilities": ["reigh.wan_2_2_t2i"]},
            )
            assert status == 204
            assert body == {}

    def test_claim_creates_running_attempt_with_fence_fields(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "claim-proj"
            _create_project(env["composition"], slug)
            status, resp = _admit_simple(env, slug, "k1")
            assert status == 201
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert cstatus == 200
            attempt = claim["attempt"]
            task = claim["task"]
            for field in (
                "id",
                "attempt_no",
                "lease_id",
                "lease_expires_at",
                "status_version",
            ):
                assert field in attempt
            assert attempt["attempt_no"] == 1
            assert task["status"] == "running"
            assert task["spec"]["family"] == "image_upscale"
            # A second claim finds no more work.
            status2, _ = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert status2 == 204

    def test_claim_respects_priority_ordering(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "order-proj"
            _create_project(env["composition"], slug)
            low_first = _post(
                env,
                f"/projects/{slug}/tasks",
                key="k-low",
                body={
                    "family": "image_upscale",
                    "priority": 0,
                    "input": {"image_url": "low"},
                },
            )
            high_second = _post(
                env,
                f"/projects/{slug}/tasks",
                key="k-high",
                body={
                    "family": "image_upscale",
                    "priority": 7,
                    "input": {"image_url": "high"},
                },
            )
            assert low_first[0] == 201 and high_second[0] == 201
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert cstatus == 200
            assert claim["task"]["priority"] == 7
            assert claim["task"]["id"] == high_second[1]["task"]["id"]

    def test_heartbeat_extends_lease_and_appends_nothing(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "beat-proj"
            composition = env["composition"]
            _create_project(composition, slug)
            _admit_simple(env, slug, "k1")
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert cstatus == 200
            attempt = claim["attempt"]
            task_id = claim["task"]["id"]
            stream_id = f"{task_id}:core.task"
            before = _db_count(
                composition,
                "SELECT COUNT(*) FROM events WHERE stream_id = ?",
                (stream_id,),
            )

            receipts_before = _db_count(
                composition,
                "SELECT COUNT(*) FROM command_receipts WHERE "
                "primary_stream_id = ?",
                (stream_id,),
            )

            hstatus, beat = _post(
                env,
                f"/tasks/{task_id}/attempts/{attempt['attempt_no']}/heartbeat",
                body={
                    "attempt_id": attempt["id"],
                    "lease_id": attempt["lease_id"],
                    "status_version": attempt["status_version"],
                    "progress": {"pct": 50},
                },
            )
            fresh = beat["attempt"]
            assert fresh["status_version"] == attempt["status_version"] + 1
            assert fresh["lease_expires_at"] >= attempt["lease_expires_at"]
            after = _db_count(
                composition,
                "SELECT COUNT(*) FROM events WHERE stream_id = ?",
                (stream_id,),
            )
            receipts_after = _db_count(
                composition,
                "SELECT COUNT(*) FROM command_receipts WHERE "
                "primary_stream_id = ?",
                (stream_id,),
            )
            assert after == before  # appends nothing
            assert receipts_after == receipts_before  # receipts nothing

            # Stale fence is rejected.
            sstatus, stale = _post(
                env,
                f"/tasks/{task_id}/attempts/{attempt['attempt_no']}/heartbeat",
                body={
                    "attempt_id": attempt["id"],
                    "lease_id": attempt["lease_id"],
                    "status_version": attempt["status_version"],
                },
            )
            assert sstatus == 409
            assert stale["error"] == "conflict"

    def test_cancel_terminal_state_is_idempotent(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "cancel-proj"
            _create_project(env["composition"], slug)
            status, resp = _admit_simple(env, slug, "k1")
            task_id = resp["task"]["id"]
            cstatus, cancel = _post(
                env, f"/projects/{slug}/tasks/{task_id}/cancel", body={}
            )
            assert cstatus == 200
            assert cancel["task"]["status"] == "cancelled"
            # Repeated cancel reports the current terminal state.
            rstatus, repeat = _post(
                env, f"/projects/{slug}/tasks/{task_id}/cancel", body={}
            )
            assert rstatus == 200
            assert repeat["task"]["status"] == "cancelled"


class TestTaskReads:
    def test_list_and_detail_reads(self, tmp_bridge_root: Path) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "reads-proj"
            _create_project(env["composition"], slug)
            _admit_simple(env, slug, "k1")
            lstatus, listing = _get(env, f"/projects/{slug}/tasks")
            assert lstatus == 200
            assert len(listing["tasks"]) == 1
            summary = listing["tasks"][0]
            assert summary["capability"] == "reigh.image_upscale"
            dstatus, detail = _get(
                env, f"/projects/{slug}/tasks/{summary['task_id']}"
            )
            assert dstatus == 200
            assert detail["task"]["attempts"] == []
            assert detail["task"]["outputs"] == []


# ---------------------------------------------------------------------------
# T7: atomic multipart completion + fenced failure
# ---------------------------------------------------------------------------


def _complete_multipart(
    env: dict[str, Any],
    claim: dict[str, Any],
    task_id: str,
    *,
    key: str,
    files: dict[str, bytes] | None = None,
    fence_override: dict[str, Any] | None = None,
    declare_sha: bool = True,
    sha_override: str | None = None,
    outputs: list[dict[str, Any]] | None = None,
) -> tuple[int, dict[str, Any]]:
    attempt = claim["attempt"]
    files = files if files is not None else {"out0": b"rendered-bytes"}
    manifest = {
        "lease_id": attempt["lease_id"],
        "status_version": attempt["status_version"],
        "attempt_id": attempt["id"],
        "outputs": outputs,
    }
    if outputs is None:
        out0 = files["out0"]
        spec = {
            "key": "out0",
            "is_primary": True,
            "size": len(out0),
        }
        if declare_sha:
            spec["sha256"] = (
                sha_override
                if sha_override is not None
                else hashlib.sha256(out0).hexdigest()
            )
        manifest["outputs"] = [spec]
    manifest.update(fence_override or {})
    body, boundary = _multipart_body(manifest, files)
    return _post_multipart(
        env,
        f"/tasks/{task_id}/attempts/{attempt['attempt_no']}/complete",
        key=key,
        body=body,
        boundary=boundary,
    )


class TestCompletion:
    @pytest.fixture
    def claimed(self, tmp_bridge_root: Path) -> dict[str, Any]:
        with task_server(tmp_bridge_root) as env:
            slug = "complete-proj"
            composition = env["composition"]
            _create_project(composition, slug)
            status, resp = _admit_simple(env, slug, "k1")
            assert status == 201, resp
            task_id = resp["task"]["id"]
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert cstatus == 200, claim
            yield {"env": env, "task_id": task_id, "claim": claim}

    def test_happy_path_commits_media_and_cleans_staging(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        status, result = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-1"
        )
        assert status == 200, result
        assert result["task"]["status"] == "succeeded"
        # Authoritative rows: exactly one media + one output.
        assert (
            _db_count(composition, "SELECT COUNT(*) FROM task_outputs") == 1
        )
        assert _db_count(composition, "SELECT COUNT(*) FROM media") == 1
        # Staged bytes are cleaned up.
        assert not list((composition.projects_root / ".astrid").rglob("*out0*"))

    def _set_task_spec(self, composition, task_id: str, spec: dict) -> None:
        def command(uow):
            uow.execute(
                "UPDATE tasks SET spec_json = ? WHERE id = ?",
                (json.dumps(spec), task_id),
            )

        UnitOfWork(composition.writer).run(command)

    def _create_timeline(self, composition, project_id: str) -> str:
        from astrid.core.events.service import EventAppendService
        from astrid.core.receipts.service import ReceiptService
        from astrid.core.repositories.projects import ProjectRepository
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
                idempotency_key="timeline-primary",
            )

        return UnitOfWork(composition.writer).run(command).timeline_id

    def test_completion_creates_generation_per_output_policy(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        status, result = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-gen"
        )
        assert status == 200, result
        # reigh.image_upscale admits create_generation=True (doc 16 §1.1).
        assert result["generation"] is not None
        generation = result["generation"]
        assert generation["task_id"] == claimed["task_id"]
        assert _db_count(
            composition, "SELECT COUNT(*) FROM generations"
        ) == 1
        assert _db_count(
            composition, "SELECT COUNT(*) FROM generation_variants"
        ) == 1
        with composition.writer.read_only_connection() as conn:
            variant = conn.execute(
                "SELECT is_primary, variant_type FROM generation_variants"
            ).fetchone()
        assert variant[0] == 1
        assert variant[1] == "original"

    def test_registry_visibility_merge_updates_timeline_head(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        with composition.writer.read_only_connection() as conn:
            project_id = conn.execute(
                "SELECT project_id FROM tasks WHERE id = ?",
                (claimed["task_id"],),
            ).fetchone()[0]
            spec = json.loads(
                conn.execute(
                    "SELECT spec_json FROM tasks WHERE id = ?",
                    (claimed["task_id"],),
                ).fetchone()[0]
            )
        timeline_id = self._create_timeline(composition, project_id)
        spec["output_policy"]["timeline_visibility"] = {
            "timeline_id": timeline_id,
            "asset_key": "gen:upscaled",
        }
        self._set_task_spec(composition, claimed["task_id"], spec)
        digest = hashlib.sha256(b"rendered-bytes").hexdigest()
        status, result = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-vis"
        )
        assert status == 200, result
        with composition.writer.read_only_connection() as conn:
            registry_row = conn.execute(
                "SELECT asset_registry_json FROM timelines WHERE id = ?",
                (timeline_id,),
            ).fetchone()
        registry = json.loads(registry_row[0])
        assert registry["gen:upscaled"]["content_sha256"] == digest

    def test_completion_without_visibility_skips_merge(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        status, result = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-skip"
        )
        assert status == 200, result
        assert result["timeline_head"] is None

    def test_lost_ack_replay_returns_stored_completion(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        status, first = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-1"
        )
        assert status == 200
        media_before = _db_count(composition, "SELECT COUNT(*) FROM media")
        outputs_before = _db_count(
            composition, "SELECT COUNT(*) FROM task_outputs"
        )
        status2, replay = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-1"
        )
        assert status2 == 200
        assert replay["task"]["id"] == first["task"]["id"]
        assert (
            _db_count(composition, "SELECT COUNT(*) FROM media")
            == media_before
        )
        assert (
            _db_count(composition, "SELECT COUNT(*) FROM task_outputs")
            == outputs_before
        )

    def test_wrong_fence_conflicts_with_zero_rows(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        attempt = claimed["claim"]["attempt"]
        media_before = _db_count(composition, "SELECT COUNT(*) FROM media")
        status, body = _complete_multipart(
            env,
            claimed["claim"],
            claimed["task_id"],
            key="done-stale",
            fence_override={
                "status_version": attempt["status_version"] + 3
            },
        )
        assert status == 409
        assert body["error"] == "conflict"
        assert _db_count(composition, "SELECT COUNT(*) FROM media") == (
            media_before
        )

    def test_poisoned_bytes_rejected_with_zero_rows(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        media_before = _db_count(composition, "SELECT COUNT(*) FROM media")
        outputs_before = _db_count(
            composition, "SELECT COUNT(*) FROM task_outputs"
        )
        status, body = _complete_multipart(
            env,
            claimed["claim"],
            claimed["task_id"],
            key="done-poison",
            files={"out0": b"tampered"},
            sha_override=hashlib.sha256(b"honest-bytes").hexdigest(),
        )
        assert status == 400
        assert "sha256" in body["detail"]
        assert _db_count(composition, "SELECT COUNT(*) FROM media") == (
            media_before
        )
        assert (
            _db_count(composition, "SELECT COUNT(*) FROM task_outputs")
            == outputs_before
        )
        # Task is still running and completable with honest bytes.
        status2, result = _complete_multipart(
            env, claimed["claim"], claimed["task_id"], key="done-honest"
        )
        assert status2 == 200
        assert result["task"]["status"] == "succeeded"


class TestFail:
    def test_fail_requeues_then_exhausts_budget(
        self, tmp_bridge_root: Path
    ) -> None:
        with task_server(tmp_bridge_root) as env:
            slug = "fail-proj"
            composition = env["composition"]
            _create_project(composition, slug)
            status, resp = _admit_simple(env, slug, "k1")
            task_id = resp["task"]["id"]
            capabilities = ["reigh.image_upscale"]

            def claim():
                cstatus, c = _post(
                    env,
                    "/queue/claim",
                    body={"executor_id": "e1", "capabilities": capabilities},
                )
                assert cstatus == 200
                return c

            def fail(claim: dict[str, Any], key: str):
                attempt = claim["attempt"]
                return _post(
                    env,
                    f"/tasks/{task_id}/attempts/"
                    f"{attempt['attempt_no']}/fail",
                    key=key,
                    body={
                        "attempt_id": attempt["id"],
                        "lease_id": attempt["lease_id"],
                        "status_version": attempt["status_version"],
                        "error": {
                            "code": "executor_crash",
                            "message": "boom",
                            "retryable": True,
                        },
                    },
                )


            first = claim()
            fstatus, fbody = fail(first, "fail-1")
            assert fstatus == 200, fbody
            assert fbody["task"]["status"] == "queued"
            assert fbody["outcome"] == "requeued"

            second = claim()
            assert second["attempt"]["attempt_no"] == 2
            fstatus, fbody = fail(second, "fail-2")
            assert fstatus == 200
            assert fbody["outcome"] == "requeued"

            third = claim()
            assert third["attempt"]["attempt_no"] == 3
            fstatus, fbody = fail(third, "fail-3")
            assert fstatus == 200
            assert fbody["task"]["status"] == "failed"
            assert fbody["outcome"] == "failed"
            # Budget exhausted: nothing left to claim.
            dstatus, _ = _post(
                env,
                "/queue/claim",
                body={"executor_id": "e1", "capabilities": capabilities},
            )
            assert dstatus == 204


# ---------------------------------------------------------------------------
# Bounded parser-abuse suite (route level)
# ---------------------------------------------------------------------------


class TestParserAbuse:
    @pytest.fixture
    def claimed(self, tmp_bridge_root: Path) -> dict[str, Any]:
        with task_server(tmp_bridge_root) as env:
            slug = "abuse-proj"
            _create_project(env["composition"], slug)
            status, resp = _admit_simple(env, slug, "k1")
            task_id = resp["task"]["id"]
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert cstatus == 200
            yield {"env": env, "task_id": task_id, "claim": claim}

    def test_bad_boundary_is_400_with_zero_rows(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        composition = env["composition"]
        body, boundary = _multipart_body(
            {"lease_id": "x", "status_version": 1}, {}
        )
        status, resp = _post_multipart(
            env,
            f"/tasks/{claimed['task_id']}/attempts/1/complete",
            key="abuse-1",
            body=body,
            boundary="completely-different",
        )
        assert status == 400
        assert resp["error"] == "invalid_body"
        assert _db_count(composition, "SELECT COUNT(*) FROM media") == 0

    def test_truncated_body_is_400(self, claimed: dict[str, Any]) -> None:
        env = claimed["env"]
        attempt = claimed["claim"]["attempt"]
        out = b"payload"
        manifest = {
            "lease_id": attempt["lease_id"],
            "status_version": attempt["status_version"],
            "attempt_id": attempt["id"],
            "outputs": [
                {
                    "key": "out0",
                    "is_primary": True,
                    "sha256": hashlib.sha256(out).hexdigest(),
                    "size": len(out),
                }
            ],
        }
        body, boundary = _multipart_body(manifest, {"out0": out})
        status, resp = _post_multipart(
            env,
            f"/tasks/{claimed['task_id']}/attempts/1/complete",
            key="abuse-2",
            body=body[: len(body) // 2],  # truncated mid-part
            boundary=boundary,
        )
        assert status == 400
        assert resp["error"] == "invalid_body"

    def test_oversize_cap_rejects_with_fresh_server(
        self, tmp_bridge_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASTRID_BRIDGE_MAX_STAGING_REQUEST_BYTES", "1024")
        with task_server(tmp_bridge_root) as env:
            slug = "cap-proj"
            _create_project(env["composition"], slug)
            status, resp = _admit_simple(env, slug, "k1")
            task_id = resp["task"]["id"]
            cstatus, claim = _post(
                env,
                "/queue/claim",
                body={
                    "executor_id": "e1",
                    "capabilities": ["reigh.image_upscale"],
                },
            )
            assert cstatus == 200
            attempt = claim["attempt"]
            body, boundary = _multipart_body(
                {
                    "lease_id": attempt["lease_id"],
                    "status_version": attempt["status_version"],
                    "attempt_id": attempt["id"],
                    "outputs": [{"key": "big", "is_primary": True}],
                },
                {"big": b"x" * 4096},
            )
            status, resp = _post_multipart(
                env,
                f"/tasks/{task_id}/attempts/1/complete",
                key="abuse-cap",
                body=body,
                boundary=boundary,
            )
            assert status == 413
            assert resp["error"] == "payload_too_large"
            assert (
                _db_count(
                    env["composition"], "SELECT COUNT(*) FROM media"
                )
                == 0
            )
            # No staging leftovers.
            staging = env["composition"].projects_root / ".astrid" / "staging"
            if staging.exists():
                assert list(staging.iterdir()) == []

    def test_unknown_part_reference_is_400(
        self, claimed: dict[str, Any]
    ) -> None:
        env = claimed["env"]
        out = b"payload"
        attempt = claimed["claim"]["attempt"]
        manifest = {
            "lease_id": attempt["lease_id"],
            "status_version": attempt["status_version"],
            "attempt_id": attempt["id"],
            "outputs": [
                {
                    "key": "ghost",
                    "is_primary": True,
                    "sha256": hashlib.sha256(out).hexdigest(),
                }
            ],
        }
        body, boundary = _multipart_body(manifest, {"out0": out})
        status, resp = _post_multipart(
            env,
            f"/tasks/{claimed['task_id']}/attempts/1/complete",
            key="abuse-4",
            body=body,
            boundary=boundary,
        )
        assert status == 400
        assert "ghost" in resp["detail"]
