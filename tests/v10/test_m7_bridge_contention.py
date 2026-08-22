"""M7 real-bridge contention and shared-writer evidence."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from astrid.application import compose_standard_application
from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from tests.v10._m7_fixture import build_m7_fixture


def _post_save(
    url: str,
    body: dict[str, Any],
    *,
    ready: threading.Barrier,
    log_path: Path,
    token: str,
) -> tuple[int, dict[str, Any]]:
    """One independent HTTP client, with a durable actor runtime log.

    *token* is the server's per-boot request token (doc 27 §4.7): the
    local-trust gate rejects token-less mutations with 403, so each
    contender presents the launcher-delivered boot token.
    """
    started = time.monotonic_ns()
    log_path.write_text(
        json.dumps({"actor": "http", "phase": "ready", "started_ns": started}) + "\n",
        encoding="utf-8",
    )
    ready.wait(timeout=10)
    request = Request(
        url,
        data=json.dumps(body, sort_keys=True).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Astrid-Request-Token": token,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - localhost
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        status = error.code
        payload = json.loads(error.read().decode("utf-8"))
    log_path.write_text(
        log_path.read_text(encoding="utf-8")
        + json.dumps(
            {
                "actor": "http",
                "phase": "complete",
                "status": status,
                "finished_ns": time.monotonic_ns(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return status, payload


def _queue_actor(
    *,
    name: str,
    log_path: Path,
    callback: Any,
    result_box: dict[str, Any],
    ready: threading.Barrier,
) -> None:
    started = time.monotonic_ns()
    log_path.write_text(
        json.dumps({"actor": name, "phase": "ready", "started_ns": started}) + "\n",
        encoding="utf-8",
    )
    ready.wait(timeout=10)
    try:
        result_box["result"] = callback()
    except BaseException as exc:  # retain actor evidence before failing below
        result_box["error"] = repr(exc)
    log_path.write_text(
        log_path.read_text(encoding="utf-8")
        + json.dumps(
            {
                "actor": name,
                "phase": "complete",
                "ok": "error" not in result_box,
                "finished_ns": time.monotonic_ns(),
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _database_snapshot(app: Any, project_id: str) -> dict[str, Any]:
    """Read immutable proof rows through the one writer's RO connection."""
    with app.writer.read_only_connection() as connection:
        tables = (
            "events",
            "command_receipts",
            "event_streams",
            "timelines",
            "tasks",
        )
        result: dict[str, Any] = {}
        for table in tables:
            result[table] = [
                tuple(row)
                for row in connection.execute(
                    f"SELECT * FROM {table} ORDER BY rowid"
                ).fetchall()
            ]
        result["project_events"] = [
            tuple(row)
            for row in connection.execute(
                "SELECT event_id, project_seq, stream_id, seq, kind, payload_json "
                "FROM events WHERE project_id = ? ORDER BY project_seq",
                (project_id,),
            ).fetchall()
        ]
        result["project_receipts"] = [
            tuple(row)
            for row in connection.execute(
                "SELECT idempotency_key, command_kind, first_project_seq, "
                "last_project_seq FROM command_receipts WHERE project_id = ? "
                "ORDER BY first_project_seq, idempotency_key",
                (project_id,),
            ).fetchall()
        ]
        result["heads"] = [
            tuple(row)
            for row in connection.execute(
                "SELECT id, head_seq FROM event_streams WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        ]
    return result


def _assert_event_hash_chains(app: Any, project_id: str) -> None:
    events = app.event_log.list_events(project_id=project_id)
    assert [event.project_seq for event in events] == list(
        range(1, len(events) + 1)
    )
    by_stream: dict[str, list[Any]] = {}
    for event in events:
        assert event.event_hash
        by_stream.setdefault(event.stream_id, []).append(event)
    for stream_events in by_stream.values():
        assert stream_events[0].previous_event_hash is None
        for previous, current in zip(stream_events, stream_events[1:]):
            assert current.previous_event_hash == previous.event_hash
    with app.writer.read_only_connection() as connection:
        for stream_id, head_seq in connection.execute(
            "SELECT id, head_seq FROM event_streams ORDER BY id"
        ).fetchall():
            stream = by_stream.get(str(stream_id), [])
            assert int(head_seq) == (stream[-1].seq if stream else 0)


def test_real_bridge_contention_has_one_cas_winner_and_shared_queue_progress(
    tmp_path: Path,
) -> None:
    """Two HTTP clients race while service/task writers drain the same queue."""
    root = tmp_path / "contention"
    fixture = build_m7_fixture(root)
    project_id = str(fixture.spec["project"]["id"])
    log_root = tmp_path / "runtime-logs"
    log_root.mkdir()

    with compose_standard_application(root) as app:
        bridge = TimelineBridgeAdapter(
            writer=app.writer,
            projects=app.projects_service,
            timelines=app.timelines_service,
        )
        server = create_local_bridge_server(
            projects_root=root,
            bridge=bridge,
            writer=app.writer,
            database_path=app.database_path,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        base_url = f"http://{host}:{port}"
        save_url = f"{base_url}/projects/m7-representative/timelines/main/save"
        initial = _database_snapshot(app, project_id)
        initial_load = json.loads(
            urlopen(  # noqa: S310 - localhost test server
                f"{base_url}/projects/m7-representative/timelines/main",
                timeout=10,
            ).read().decode("utf-8")
        )
        expected_version = int(initial_load["config_version"])
        ready = threading.Barrier(2)
        responses: list[tuple[int, dict[str, Any]] | None] = [None, None]
        errors: list[BaseException] = []

        def http_actor(index: int) -> None:
            try:
                responses[index] = _post_save(
                    save_url,
                    {
                        "config": {
                            **initial_load["config"],
                            "contender": f"http-{index}",
                        },
                        "registry": initial_load["registry"],
                        "expected_version": expected_version,
                    },
                    ready=ready,
                    log_path=log_root / f"http-{index}.jsonl",
                    token=server.request_token,
                )
            except BaseException as exc:
                errors.append(exc)

        clients = [threading.Thread(target=http_actor, args=(i,)) for i in range(2)]
        for client in clients:
            client.start()
        for client in clients:
            client.join(timeout=10)
        assert all(not client.is_alive() for client in clients)
        assert not errors
        assert all(response is not None for response in responses)
        completed = [response for response in responses if response is not None]
        assert sorted(status for status, _payload in completed) == [200, 409]
        winner = next(payload for status, payload in completed if status == 200)
        loser = next(payload for status, payload in completed if status == 409)
        assert loser["error"] == "timeline_version_conflict"
        assert loser["config_version"] == int(winner["config_version"])
        after_race = _database_snapshot(app, project_id)
        assert len(after_race["project_events"]) == len(initial["project_events"]) + 1
        assert len(after_race["project_receipts"]) == len(initial["project_receipts"]) + 1

        # Queue two additional public mutations after the CAS race. One is a
        # service-backed CLI save and one is executor-side task admission;
        # both are submitted to this same app.writer queue.
        queue_ready = threading.Barrier(2)
        service_box: dict[str, Any] = {}
        executor_box: dict[str, Any] = {}
        service_thread = threading.Thread(
            target=_queue_actor,
            kwargs={
                "name": "cli-service",
                "log_path": log_root / "cli-service.jsonl",
                "callback": lambda: app.timelines_service.save(
                    "m7-representative",
                    "main",
                    config={**winner["config"], "service_actor": True},
                    registry=winner["registry"],
                    expected_version=int(winner["config_version"]),
                    idempotency_key="m7-contention-service-save",
                ),
                "result_box": service_box,
                "ready": queue_ready,
            },
        )
        executor_thread = threading.Thread(
            target=_queue_actor,
            kwargs={
                "name": "executor",
                "log_path": log_root / "executor.jsonl",
                "callback": lambda: app.tasks_service.create(
                    project_id=project_id,
                    capability="generation.generate_image",
                    spec={"fixture": "m7-representative-v1", "actor": "executor"},
                    idempotency_key="m7-contention-executor-task",
                ),
                "result_box": executor_box,
                "ready": queue_ready,
            },
        )
        service_thread.start()
        executor_thread.start()
        service_thread.join(timeout=10)
        executor_thread.join(timeout=10)
        assert not service_thread.is_alive()
        assert not executor_thread.is_alive()
        assert "error" not in service_box
        assert "error" not in executor_box
        assert service_box["result"].ok
        assert executor_box["result"].ok

        final_load = json.loads(
            urlopen(save_url.replace("/save", ""), timeout=10)  # noqa: S310
            .read()
            .decode("utf-8")
        )
        assert final_load["config"]["service_actor"] is True
        assert int(final_load["config_version"]) == expected_version + 2
        final = _database_snapshot(app, project_id)
        assert len(final["project_events"]) == len(initial["project_events"]) + 3
        assert len(final["project_receipts"]) == len(initial["project_receipts"]) + 3
        assert len(final["tasks"]) == len(initial["tasks"]) + 1
        assert len(app.timeline_save_calls) == 3
        assert [call.expected_version for call in app.timeline_save_calls] == [
            expected_version,
            expected_version,
            expected_version + 1,
        ]
        _assert_event_hash_chains(app, project_id)

        for actor_log in sorted(log_root.glob("*.jsonl")):
            records = [json.loads(line) for line in actor_log.read_text().splitlines()]
            assert [record["phase"] for record in records] == ["ready", "complete"]
            assert records[1]["finished_ns"] >= records[0]["started_ns"]

        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
        assert not thread.is_alive()
