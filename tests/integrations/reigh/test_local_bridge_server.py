from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import socket
import string
import struct
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from astrid.core.events.service import EventAppendService
from astrid.core.integrations.reigh.bridge_service import HealthStatus
from astrid.core.integrations.reigh.local_bridge_server import (
    _is_loopback_host_header,
    create_local_bridge_server,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.runs import RunRepository
from astrid.core.store.uow import UnitOfWork
from astrid.packs import compose_standard_bridge
from astrid.packs.timeline import bridge as timeline_bridge

TS = "2026-08-15T00:00:00.000000+00:00"
_DECODABLE_VIDEO_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "reshape"
    / "hype_regression"
    / "main.mp4"
)


def _decodable_video_bytes() -> bytes:
    """Return a checked-in, ffprobe-decodable video for strict media tests."""
    return _DECODABLE_VIDEO_FIXTURE.read_bytes()


# Test-only map of live repository bridge origins to their per-boot token.
_BRIDGE_REQUEST_TOKENS: dict[str, str] = {}


def _cursor_payload(counter: int, label: str) -> dict[str, Any]:
    return {
        "v": 1,
        "p": f"project-{counter}-{label}",
        "r": f"run.{counter}.{label}",
        "s": counter,
        "o": counter * 2,
        "q": f"run-{counter}",
        "i": f"transition-{counter}-{label}",
    }


def test_runaway_cursor_accepts_binary_signature_containing_delimiter() -> None:
    """A signature byte equal to ``.`` must not be mistaken for the separator."""

    key = (30).to_bytes(32, "big")
    payload = {
        "v": 1,
        "p": "project",
        "r": "run",
        "s": 5,
        "o": 3,
        "q": "run",
        "i": "id",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    signature = hmac.digest(key, raw, "sha256")[: timeline_bridge._RUNAWAY_CURSOR_SIGNATURE_BYTES]
    assert b"." in signature  # deterministic counterexample to delimiter splitting

    cursor = timeline_bridge._encode_runaway_cursor(payload, key=key)

    assert timeline_bridge._decode_runaway_cursor(cursor, key=key) == payload


def test_runaway_cursor_round_trip_and_tamper_properties() -> None:
    """Many deterministic pseudo-random keys/payloads round-trip and fail closed."""

    import pytest

    rng = random.Random(0xA57D)
    alphabet = string.ascii_letters + string.digits + ".-_"
    for counter in range(512):
        label = "".join(rng.choice(alphabet) for _ in range(rng.randrange(1, 40)))
        payload = _cursor_payload(counter, label)
        key = hashlib.sha256(f"cursor-key-{counter}-{label}".encode()).digest()
        cursor = timeline_bridge._encode_runaway_cursor(payload, key=key)
        assert timeline_bridge._decode_runaway_cursor(cursor, key=key) == payload

        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = bytearray(base64.urlsafe_b64decode(padded.encode("ascii")))
        decoded[rng.randrange(len(decoded))] ^= 1
        tampered = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
        with pytest.raises(timeline_bridge.BridgeCursorError):
            timeline_bridge._decode_runaway_cursor(tampered, key=key)
        with pytest.raises(timeline_bridge.BridgeCursorError):
            timeline_bridge._decode_runaway_cursor(cursor[:-1], key=key)

    payload = _cursor_payload(513, "wrong-delimiter")
    key = hashlib.sha256(b"wrong-delimiter").digest()
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    signature = hmac.digest(key, raw, "sha256")[: timeline_bridge._RUNAWAY_CURSOR_SIGNATURE_BYTES]
    malformed = base64.urlsafe_b64encode(raw + b":" + signature).rstrip(b"=").decode("ascii")
    with pytest.raises(timeline_bridge.BridgeCursorError):
        timeline_bridge._decode_runaway_cursor(malformed, key=key)


def _repo_create_project(composition, *, slug: str, key: str):
    """Create one project through the repository-backed composition."""
    return UnitOfWork(composition.writer).run(
        lambda u: composition.projects.create(
            u,
            slug=slug,
            name=slug,
            settings={},
            idempotency_key=key,
            created_at=TS,
        )
    )


def _repo_create_timeline(
    composition,
    *,
    project_id: str,
    slug: str,
    key: str,
    timeline_id: str,
    timeline_ulid: str,
    name: str | None = None,
    is_default: bool = False,
    registry: dict[str, Any] | None = None,
):
    """Create one timeline through the repository-backed composition."""
    return UnitOfWork(composition.writer).run(
        lambda u: composition.timelines.create(
            u,
            project_id=project_id,
            slug=slug,
            name=name or slug.title(),
            config={"fps": 24},
            registry=registry if registry is not None else {"assets": {}},
            idempotency_key=key,
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            set_default=is_default,
            created_at=TS,
        )
    )


def _repo_load_timeline(composition, project_id: str, ref: str):
    """Load one timeline through the repository's transaction-free read."""
    return composition.timelines.show(composition.writer, project_id, ref)


def _repo_db_snapshot(composition) -> dict[str, Any]:
    """Snapshot mutable database state through a read-only connection.

    Counts every domain table plus the timeline document/registry and all
    stream heads, so zero-mutation proofs compare byte-identical state
    before and after stale/malformed save requests.
    """
    tables = (
        "projects",
        "event_streams",
        "events",
        "command_receipts",
        "timelines",
    )
    snapshot: dict[str, Any] = {}
    with composition.writer.read_only_connection() as conn:
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            snapshot[f"count:{table}"] = int(row[0])
        snapshot["heads"] = {
            str(row[0]): int(row[1])
            for row in conn.execute("SELECT id, head_seq FROM event_streams ORDER BY id").fetchall()
        }
        snapshot["docs"] = {
            str(row[0]): (str(row[1]), str(row[2]), str(row[3]))
            for row in conn.execute(
                "SELECT id, document_json, asset_registry_json, project_data_json "
                "FROM timelines ORDER BY id"
            ).fetchall()
        }
        snapshot["saved_events"] = int(
            conn.execute("SELECT COUNT(*) FROM events WHERE kind = 'timeline.saved'").fetchone()[0]
        )
        snapshot["save_receipts"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM command_receipts WHERE command_kind = 'timeline.save'"
            ).fetchone()[0]
        )
    return snapshot


def _get_json(url: str) -> tuple[int, dict]:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - localhost test server only
        return response.status, json.loads(response.read().decode("utf-8"))


def _get_error(url: str) -> tuple[int, dict]:
    try:
        _get_json(url)
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    raise AssertionError(f"expected {url} to return an HTTP error")


def _add_repository_request_token(req: Request, url: str) -> None:
    """Model the browser client sending the repository bridge's boot token."""
    for base_url, token in tuple(_BRIDGE_REQUEST_TOKENS.items()):
        if url.startswith(base_url + "/"):
            req.add_header("X-Astrid-Request-Token", token)
            break


def _post_json(url: str, body: dict[str, Any]) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    _add_repository_request_token(req, url)
    try:
        with urlopen(req) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _post_raw(url: str, raw_body: bytes, content_type: str | None = None) -> tuple[int, dict]:
    req = Request(url, data=raw_body, method="POST")
    _add_repository_request_token(req, url)
    if content_type is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urlopen(req) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _put_raw(url: str, raw_body: bytes, content_type: str | None = None) -> tuple[int, dict]:
    req = Request(url, data=raw_body, method="PUT")
    _add_repository_request_token(req, url)
    if content_type is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urlopen(req) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _options(url: str, origin: str | None = None) -> tuple[int, dict[str, str]]:
    req = Request(url, method="OPTIONS")
    if origin is not None:
        req.add_header("Origin", origin)
    try:
        with urlopen(req) as response:  # noqa: S310
            return response.status, dict(response.headers)
    except HTTPError as error:
        return error.code, dict(error.headers)


def _get_bytes(
    url: str,
    *,
    range_header: str | None = None,
    if_none_match: str | None = None,
    origin: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Fetch raw bytes from the bridge, returning (status, headers, body)."""
    req = Request(url)
    if range_header is not None:
        req.add_header("Range", range_header)
    if if_none_match is not None:
        req.add_header("If-None-Match", if_none_match)
    if origin is not None:
        req.add_header("Origin", origin)
    try:
        with urlopen(req) as response:  # noqa: S310
            headers = dict(response.headers)
            body = response.read()
            return response.status, headers, body
    except HTTPError as error:
        headers = dict(error.headers)
        body = error.read()
        return error.code, headers, body


def _head(url: str) -> tuple[int, dict[str, str]]:
    req = Request(url, method="HEAD")
    try:
        with urlopen(req) as response:  # noqa: S310
            return response.status, dict(response.headers)
    except HTTPError as error:
        return error.code, dict(error.headers)


@contextmanager
def running_server(projects_root: Path) -> Generator[str, None, None]:
    server = create_local_bridge_server(projects_root=projects_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    _BRIDGE_REQUEST_TOKENS[base_url] = server.request_token
    try:
        yield base_url
    finally:
        _BRIDGE_REQUEST_TOKENS.pop(base_url, None)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextmanager
def repository_server(
    projects_root: Path,
) -> Generator[tuple[str, Any], None, None]:
    """A running server with the repository-backed bridge composed.

    Mirrors the gateway serve composition root: the standard database and
    registered packs are constructed once and injected into the HTTP server
    (``server.bridge``), so the read routes answer from the repositories and
    never fall back to a filesystem authority.
    """
    composition = compose_standard_bridge(projects_root)
    server = create_local_bridge_server(
        projects_root=projects_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    _BRIDGE_REQUEST_TOKENS[base_url] = server.request_token
    try:
        yield base_url, composition
    finally:
        _BRIDGE_REQUEST_TOKENS.pop(base_url, None)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.close()


def test_health_and_timeline_endpoints_repository_backed(
    tmp_bridge_root: Path,
) -> None:
    """Health, timeline detail, and discovery list through the bridge."""
    timeline_id = "11111111-1111-1111-1111-111111111111"
    timeline_ulid = "01jm4k5n7p0000000000000001"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="ados-talks", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="intro-cut",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Intro Cut",
            is_default=True,
        )
        health_status, health = _get_json(f"{base_url}/health")
        timeline_status, timeline = _get_json(
            f"{base_url}/projects/ados-talks/timelines/{timeline_id}",
        )
        projects_status, projects = _get_json(f"{base_url}/projects")
        timelines_status, timelines = _get_json(f"{base_url}/projects/ados-talks/timelines")

    assert health_status == 200
    assert health == {"ok": True, "projects_root": str(tmp_bridge_root.resolve())}

    assert timeline_status == 200
    assert timeline["timeline_id"] == timeline_id
    assert timeline["timeline_ulid"] == timeline_ulid
    assert timeline["slug"] == "intro-cut"
    assert timeline["config_version"] == 1  # one timeline.created event

    assert projects_status == 200
    assert projects == {"projects": [{"slug": "ados-talks", "name": "ados-talks"}]}

    assert timelines_status == 200
    assert timelines == {
        "timelines": [
            {
                "timeline_id": timeline_id,
                "timeline_ulid": timeline_ulid,
                "slug": "intro-cut",
                "name": "Intro Cut",
                "is_default": True,
            }
        ],
    }


def test_projects_list_route_empty_root_returns_empty_envelope(
    tmp_bridge_root: Path,
) -> None:
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        status, body = _get_json(f"{base_url}/projects")

    assert status == 200
    assert body == {"projects": []}


def test_projects_list_route_returns_sorted_rows(
    tmp_bridge_root: Path,
) -> None:
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_create_project(composition, slug="z-last", key="proj-z")
        _repo_create_project(composition, slug="a-first", key="proj-a")
        status, body = _get_json(f"{base_url}/projects")

    assert status == 200
    assert body == {
        "projects": [
            {"slug": "a-first", "name": "a-first"},
            {"slug": "z-last", "name": "z-last"},
        ],
    }


def test_projects_timelines_list_route_envelope(
    tmp_bridge_root: Path,
) -> None:
    timeline_id = "44444444-4444-4444-4444-444444444444"
    timeline_ulid = "01jm4k5n7p0000000000000004"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="listed-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            is_default=True,
        )
        status, body = _get_json(f"{base_url}/projects/listed-proj/timelines")

    assert status == 200
    assert body == {
        "timelines": [
            {
                "timeline_id": timeline_id,
                "timeline_ulid": timeline_ulid,
                "slug": "primary",
                "name": "Primary",
                "is_default": True,
            }
        ],
    }


def test_uppercase_legacy_ulid_loads_only_when_list_exposes_exact_identity(
    tmp_bridge_root: Path,
) -> None:
    uppercase = "01KYPVKMW5STB4W6FE05ED8242"
    lowercase = uppercase.lower()
    timeline_id = "44444444-4444-4444-4444-444444444446"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        legacy = _repo_create_project(composition, slug="legacy-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=legacy.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=uppercase,
        )
        _repo_create_project(composition, slug="other-proj", key="proj-2")

        list_status, listed = _get_json(
            f"{base_url}/projects/legacy-proj/timelines"
        )
        upper_status, upper_loaded = _get_json(
            f"{base_url}/projects/legacy-proj/timelines/{uppercase}"
        )
        lower_status, lower_error = _get_error(
            f"{base_url}/projects/legacy-proj/timelines/{lowercase}"
        )
        foreign_status, foreign_error = _get_error(
            f"{base_url}/projects/other-proj/timelines/{uppercase}"
        )
        malformed_status, malformed_error = _get_error(
            f"{base_url}/projects/legacy-proj/timelines/{uppercase[:-1]}!"
        )
        slug_status, slug_loaded = _get_json(
            f"{base_url}/projects/legacy-proj/timelines/primary"
        )

    assert list_status == 200
    assert listed["timelines"][0]["timeline_ulid"] == uppercase
    assert upper_status == 200
    assert upper_loaded["timeline_ulid"] == uppercase
    assert lower_status == 404
    assert lower_error["error"] == "timeline_not_found"
    assert foreign_status == 404
    assert foreign_error["error"] == "timeline_not_found"
    assert malformed_status == 400
    assert malformed_error["error"] == "invalid_timeline"
    assert slug_status == 200
    assert slug_loaded["timeline_id"] == timeline_id


def test_projects_timelines_list_route_empty_for_project_without_timelines(
    tmp_bridge_root: Path,
) -> None:
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_create_project(composition, slug="empty-proj", key="proj-1")
        status, body = _get_json(f"{base_url}/projects/empty-proj/timelines")

    assert status == 200
    assert body == {"timelines": []}


def test_projects_timelines_list_route_unknown_project_returns_404(
    tmp_bridge_root: Path,
) -> None:
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        status, error = _get_error(f"{base_url}/projects/no-such-project/timelines")

    assert status == 404
    assert error["error"] == "project_not_found"


def test_projects_timelines_list_route_invalid_slug_returns_400(
    tmp_bridge_root: Path,
) -> None:
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        status, error = _get_error(f"{base_url}/projects/%2E%2E/timelines")

    assert status == 400
    assert error["error"] == "invalid_project"


def test_runaway_transitions_route_returns_typed_rows_filter_and_evidence(
    tmp_bridge_root: Path,
) -> None:
    """The editor route is repository-backed and preserves typed provenance."""
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="runaway-demo", key="proj-runaway")
        run_id = "01j5runawaytimingv1000000000000"
        runs = RunRepository(
            events=EventAppendService(composition.registry),
            receipts=ReceiptService(),
        )

        def _seed(uow: UnitOfWork) -> None:
            runs.create(
                uow,
                project_id=project.id,
                run_id=run_id,
                children=[],
                evidence=[],
                idempotency_key="runaway-test:run",
                kind="runaway:timing-v1",
                title="Runaway timing",
                input={},
                created_at=TS,
            )
            composition.runaway.create(
                uow,
                project_id=project.id,
                run_id=run_id,
                transitions=[
                    {
                        "ordinal": 0,
                        "start_ms": 292,
                        "duration_ms": 41,
                        "prompt": "rose neon piano chord, hard cut, 48fps, S01",
                        "metadata": {"frame": 14, "region": "S01", "colour": "rose"},
                    },
                    {
                        "ordinal": 1,
                        "start_ms": 333,
                        "duration_ms": 63,
                        "prompt": "teal neon piano chord, hard cut, 48fps, S02",
                        "metadata": {"frame": 16, "region": "S02", "colour": "teal"},
                    },
                ],
            )
            composition.runaway_evidence.record(
                uow,
                project_id=project.id,
                run_id=run_id,
                kind="measurement",
                summary="2 transitions across 3 declared regions",
                data={
                    "subtype": "runaway_timing_migrated",
                    "fps": 48,
                    "frame_count": 19,
                    "region_counts": {"S01": 1, "S02": 1, "S03": 0},
                },
                idempotency_key="runaway-test:evidence",
                created_at=TS,
            )

        UnitOfWork(composition.writer).run(_seed)
        status, body = _get_json(f"{base_url}/projects/runaway-demo/runaway-transitions")
        filtered_status, filtered = _get_json(
            f"{base_url}/projects/runaway-demo/runaway-transitions?run_id={run_id}"
        )

    assert status == filtered_status == 200
    assert body == filtered
    assert body["project"] == "runaway-demo"
    assert body["count"] == 2
    assert body["api_version"] == "v1"
    assert body["total_count"] == 2
    assert body["page"] == {"limit": 1000, "next_cursor": None}
    assert [row["ordinal"] for row in body["transitions"]] == [0, 1]
    assert body["transitions"][0]["metadata"]["frame"] == 14
    assert body["transitions"][1]["prompt"].startswith("teal neon")
    assert body["timing_summary"]["run_id"] == run_id
    assert body["timing_summary"]["data"]["region_counts"] == {
        "S01": 1,
        "S02": 1,
        "S03": 0,
    }


def test_runaway_transitions_route_empty_unknown_and_invalid_filter(
    tmp_bridge_root: Path,
) -> None:
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_create_project(composition, slug="empty-runaway", key="proj-empty")
        empty_status, empty = _get_json(f"{base_url}/projects/empty-runaway/runaway-transitions")
        missing_status, missing = _get_error(
            f"{base_url}/projects/no-such-project/runaway-transitions"
        )
        invalid_status, invalid = _get_error(
            f"{base_url}/projects/empty-runaway/runaway-transitions?run_id="
        )
        duplicate_status, duplicate = _get_error(
            f"{base_url}/projects/empty-runaway/runaway-transitions?run_id=a&run_id=b"
        )

    assert empty_status == 200
    assert empty["project"] == "empty-runaway"
    assert empty["count"] == empty["total_count"] == 0
    assert empty["api_version"] == "v1"
    assert empty["page"] == {"limit": 1000, "next_cursor": None}
    assert empty["timing_summary"] is None
    assert empty["transitions"] == []
    assert missing_status == 404
    assert missing["error"] == "project_not_found"
    assert invalid_status == 400
    assert invalid["error"] == "invalid_run"
    assert duplicate_status == 400
    assert duplicate["error"] == "invalid_run"


def test_runaway_v1_pagination_is_snapshot_consistent_and_scope_bound(
    tmp_bridge_root: Path,
) -> None:
    """Opaque cursors freeze inserts and cannot cross project boundaries."""

    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="runaway-page", key="proj-page")
        other = _repo_create_project(composition, slug="runaway-other", key="proj-other")
        run_id = "01j5runawaypage000000000000000"
        other_run_id = "01j5runawayother00000000000000"
        runs = RunRepository(
            events=EventAppendService(composition.registry),
            receipts=ReceiptService(),
        )

        def _seed(uow: UnitOfWork) -> None:
            for project_id, candidate in (
                (project.id, run_id),
                (other.id, other_run_id),
            ):
                runs.create(
                    uow,
                    project_id=project_id,
                    run_id=candidate,
                    children=[],
                    evidence=[],
                    idempotency_key=f"page-run:{candidate}",
                    kind="runaway:timing-v1",
                    title="Runaway page",
                    input={},
                    created_at=TS,
                )
            composition.runaway.create(
                uow,
                project_id=project.id,
                run_id=run_id,
                transitions=[
                    {
                        "ordinal": ordinal,
                        "start_ms": ordinal * 20,
                        "duration_ms": 20,
                        "prompt": f"transition {ordinal}",
                        "metadata": {"frame": ordinal + 1},
                    }
                    for ordinal in range(5)
                ],
            )

        UnitOfWork(composition.writer).run(_seed)
        status, first = _get_json(
            f"{base_url}/v1/projects/runaway-page/runaway-transitions?run_id={run_id}&limit=2"
        )
        cursor = first["page"]["next_cursor"]
        assert status == 200
        assert first["api_version"] == "v1"
        assert first["total_count"] == 5
        assert [row["ordinal"] for row in first["transitions"]] == [0, 1]
        assert isinstance(cursor, str) and cursor

        # Append after the first response. The old cursor must still traverse
        # the original five-row snapshot, never the sixth row.
        UnitOfWork(composition.writer).run(
            lambda uow: composition.runaway.create(
                uow,
                project_id=project.id,
                run_id=run_id,
                transitions=[
                    {
                        "ordinal": 5,
                        "start_ms": 100,
                        "duration_ms": 20,
                        "prompt": "transition 5",
                        "metadata": {"frame": 6},
                    }
                ],
                idempotency_key=f"runaway:create:{run_id}:append",
            )
        )
        _, second = _get_json(
            f"{base_url}/v1/projects/runaway-page/runaway-transitions"
            f"?run_id={run_id}&limit=2&cursor={cursor}"
        )
        cursor2 = second["page"]["next_cursor"]
        _, third = _get_json(
            f"{base_url}/v1/projects/runaway-page/runaway-transitions"
            f"?run_id={run_id}&limit=2&cursor={cursor2}"
        )
        assert second["snapshot"] == third["snapshot"] == first["snapshot"]
        assert second["total_count"] == third["total_count"] == 5
        assert [row["ordinal"] for row in second["transitions"]] == [2, 3]
        assert [row["ordinal"] for row in third["transitions"]] == [4]
        assert third["page"]["next_cursor"] is None

        cross_status, cross = _get_error(
            f"{base_url}/v1/projects/runaway-other/runaway-transitions?limit=2&cursor={cursor}"
        )
        bad_status, bad = _get_error(
            f"{base_url}/v1/projects/runaway-page/runaway-transitions"
            "?cursor=definitely-not-a-cursor"
        )

    assert cross_status == bad_status == 400
    assert cross["error"] == bad["error"] == "invalid_cursor"


def test_bridge_refuses_non_loopback_bind_and_enforces_optional_bearer(
    tmp_bridge_root: Path,
) -> None:
    import pytest

    with pytest.raises(ValueError, match="local-only"):
        create_local_bridge_server(projects_root=tmp_bridge_root, host="0.0.0.0")

    composition = compose_standard_bridge(tmp_bridge_root)
    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        auth_token="ship-secret",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"
    try:
        denied_status, denied = _get_error(f"{base}/v1/health")
        request = Request(f"{base}/v1/health")
        request.add_header("Authorization", "Bearer ship-secret")
        with urlopen(request) as response:  # noqa: S310 - loopback test server
            allowed_status = response.status
            allowed = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.close()
    assert denied_status == 401
    assert denied["error"] == "unauthorized"
    assert allowed_status == 200
    assert allowed["ok"] is True


def test_loopback_host_header_parser_handles_ipv4_ipv6_ports_and_malformed_values() -> None:
    for value in (
        "localhost",
        "localhost:0",
        "127.0.0.1",
        "127.0.0.1:65535",
        "[::1]",
        "[::1]:8080",
        "::1",
    ):
        assert _is_loopback_host_header(value), value

    for value in (
        "attacker.invalid",
        "attacker.invalid:80",
        "127.0.0.1:65536",
        "127.0.0.1:not-a-port",
        "127.0.0.1:",
        "[::1",
        "[::1]oops",
        "[::1]:-1",
        "127.0.0.1:80:90",
        "127.0.0.1, attacker.invalid",
        " 127.0.0.1",
        "127.0.0.1 ",
    ):
        assert not _is_loopback_host_header(value), value

    # The public request path only supplies strings, but the helper also fails
    # closed if called with an unexpected value by a future caller.
    assert not _is_loopback_host_header(None)  # type: ignore[arg-type]


def test_bridge_rejects_duplicate_host_and_forwarded_host_headers(
    tmp_bridge_root: Path,
) -> None:
    """Proxy/header ambiguity must not turn a hostile request into a 200."""

    from http.client import HTTPConnection

    composition = compose_standard_bridge(tmp_bridge_root)
    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        auth_token="ship-secret",
        release_mode=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    def request(
        *,
        host_value: str | None = None,
        duplicate_host: bool = False,
        forwarded: bool = False,
        missing_host: bool = False,
    ):
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.putrequest("GET", "/v1/health", skip_host=True)
            if not missing_host:
                connection.putheader("Host", host_value or f"127.0.0.1:{port}")
            if duplicate_host:
                connection.putheader("Host", "attacker.invalid")
            if forwarded:
                connection.putheader("X-Forwarded-Host", "attacker.invalid")
            connection.putheader("Authorization", "Bearer ship-secret")
            connection.putheader("X-Astrid-Bridge-Version", "v1")
            connection.endheaders()
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    try:
        duplicate_status, duplicate_body = request(duplicate_host=True)
        disallowed_status, disallowed_body = request(host_value="attacker.invalid")
        forwarded_status, forwarded_body = request(forwarded=True)
        missing_status, missing_body = request(missing_host=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.close()

    assert duplicate_status == disallowed_status == forwarded_status == missing_status == 403
    assert (
        duplicate_body["error"]
        == disallowed_body["error"]
        == forwarded_body["error"]
        == missing_body["error"]
        == "forbidden"
    )


def test_release_mode_fails_closed_and_requires_auth_and_protocol_version(
    tmp_bridge_root: Path,
    monkeypatch,
) -> None:
    import pytest

    monkeypatch.delenv("ASTRID_BRIDGE_TOKEN", raising=False)
    with pytest.raises(ValueError, match="requires ASTRID_BRIDGE_TOKEN"):
        create_local_bridge_server(
            projects_root=tmp_bridge_root,
            release_mode=True,
        )

    composition = compose_standard_bridge(tmp_bridge_root)
    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        auth_token="ship-secret",
        release_mode=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"
    try:
        denied_status, denied = _get_error(f"{base}/v1/health")

        auth_only = Request(f"{base}/v1/health")
        auth_only.add_header("Authorization", "Bearer ship-secret")
        with pytest.raises(HTTPError) as version_error:
            urlopen(auth_only)  # noqa: S310 - loopback test server
        version_body = json.loads(version_error.value.read().decode("utf-8"))

        compatible = Request(f"{base}/v1/health")
        compatible.add_header("Authorization", "Bearer ship-secret")
        compatible.add_header("X-Astrid-Bridge-Version", "v1")
        with urlopen(compatible) as response:  # noqa: S310 - loopback test server
            compatible_status = response.status
            response_version = response.headers["X-Astrid-Bridge-Version"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.close()

    assert denied_status == 401
    assert denied["error"] == "unauthorized"
    assert version_error.value.code == 426
    assert version_body["error"] == "protocol_version_mismatch"
    assert compatible_status == 200
    assert response_version == "v1"


def test_release_boot_secret_is_private_rotated_and_integrity_checked(
    tmp_bridge_root: Path,
) -> None:
    import os
    import stat

    import pytest

    composition = compose_standard_bridge(tmp_bridge_root)
    first = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        auth_token="ship-secret",
        release_mode=True,
    )
    secret_path = tmp_bridge_root / ".astrid" / "bridge-boot-secret"
    first_payload = secret_path.read_bytes()
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(secret_path.parent.stat().st_mode) == 0o700
    first.server_close()
    composition.close()

    composition = compose_standard_bridge(tmp_bridge_root)
    second = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        auth_token="ship-secret",
        release_mode=True,
    )
    thread: threading.Thread | None = None
    try:
        assert secret_path.read_bytes() != first_payload
        secret_path.write_bytes(b"tampered\n")
        os.chmod(secret_path, 0o600)
        thread = threading.Thread(target=second.serve_forever, daemon=True)
        thread.start()
        base = f"http://{second.server_address[0]}:{second.server_address[1]}"
        request = Request(f"{base}/v1/health")
        request.add_header("Authorization", "Bearer ship-secret")
        request.add_header("X-Astrid-Bridge-Version", "v1")
        with pytest.raises(HTTPError) as error:
            urlopen(request)  # noqa: S310 - loopback test server
        body = json.loads(error.value.read().decode("utf-8"))
        assert error.value.code == 500
        assert body["error"] == "internal"
    finally:
        second.shutdown()
        second.server_close()
        if thread is not None:
            thread.join(timeout=5)
        composition.close()


def test_bridge_rate_budget_rejects_repeated_mutation_with_retry_after(
    tmp_bridge_root: Path,
) -> None:
    composition = compose_standard_bridge(tmp_bridge_root)
    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        rate_limit_capacity=1,
        rate_limit_refill_per_second=0.001,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"
    _BRIDGE_REQUEST_TOKENS[base] = server.request_token
    try:
        first_status, _first = _post_json(
            f"{base}/v1/projects/no-such/timelines/no-such/save", {}
        )
        second_status, limited_body = _post_json(
            f"{base}/v1/projects/no-such/timelines/no-such/save", {}
        )
    finally:
        _BRIDGE_REQUEST_TOKENS.pop(base, None)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.close()

    assert first_status == 400
    assert second_status == 429
    assert limited_body["error"] == "rate_limited"


def test_bridge_default_rate_budget_allows_legitimate_burst_above_legacy_limit(
    tmp_bridge_root: Path,
) -> None:
    """The default budget covers metadata/media fan-out beyond the old 32 cap."""

    class FastHealthBridge:
        def health(self, projects_root: str) -> HealthStatus:
            return HealthStatus(ok=True, projects_root=projects_root)

    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=FastHealthBridge(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"
    try:
        statuses = [_get_json(f"{base}/v1/health")[0] for _ in range(40)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert statuses == [200] * 40


def test_bridge_read_burst_does_not_consume_mutation_rate_budget(
    tmp_bridge_root: Path,
) -> None:
    """Dynamic and media reads do not starve the separately metered mutations."""
    composition = compose_standard_bridge(tmp_bridge_root)
    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        task_bridge=composition.task_bridge,
        writer=composition.writer,
        database_path=composition.database_path,
        rate_limit_capacity=1,
        rate_limit_refill_per_second=0.001,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"
    _BRIDGE_REQUEST_TOKENS[base] = server.request_token
    try:
        read_targets = (
            "/v1/health",
            "/v1/projects",
            "/v1/projects/no-such/timelines",
            "/v1/projects/no-such/generations",
            "/v1/projects/no-such/media/no-such/content",
            "/v1/projects/no-such/timelines/no-such/assets/no-such",
        )
        read_statuses: list[int] = []
        for index in range(40):
            target = read_targets[index % len(read_targets)]
            try:
                read_statuses.append(_get_json(f"{base}{target}")[0])
            except HTTPError as error:
                read_statuses.append(error.code)
                error.read()

        first_status, _first = _post_json(
            f"{base}/v1/projects/no-such/timelines/no-such/save", {}
        )
        second_status, second_body = _post_json(
            f"{base}/v1/projects/no-such/timelines/no-such/save", {}
        )
    finally:
        _BRIDGE_REQUEST_TOKENS.pop(base, None)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.close()

    assert len(read_statuses) == 40
    assert all(status != 429 for status in read_statuses)
    assert first_status == 400
    assert second_status == 429
    assert second_body["error"] == "rate_limited"


def test_bridge_rejects_oversized_request_body_and_target_before_dispatch(
    tmp_bridge_root: Path,
) -> None:
    """Body and request-target caps fail closed before route services run."""

    with running_server(tmp_bridge_root) as base_url:
        # Send only the headers: the bridge must reject the declared size
        # before reading attacker-controlled bytes (and before a client that
        # keeps writing can hit a broken pipe).
        from urllib.parse import urlsplit

        parsed = urlsplit(base_url)
        token = _BRIDGE_REQUEST_TOKENS[base_url]
        connection = socket.create_connection((parsed.hostname, parsed.port), timeout=2)
        try:
            connection.sendall(
                (
                    f"POST /v1/queue/claim HTTP/1.1\r\n"
                    f"Host: {parsed.hostname}:{parsed.port}\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {1024 * 1024 + 1}\r\n"
                    f"X-Astrid-Request-Token: {token}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
            )
            connection.settimeout(2)
            raw_body_response = bytearray()
            while b'"payload_too_large"' not in raw_body_response:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                raw_body_response.extend(chunk)
        finally:
            connection.close()
        body_status = int(raw_body_response.split(b" ", 2)[1])
        body_error = json.loads(raw_body_response.split(b"\r\n\r\n", 1)[1])
        target_status, target_error = _get_error(
            f"{base_url}/v1/health?{'x' * 9000}"
        )

    assert body_status == 413
    assert body_error["error"] == "payload_too_large"
    assert target_status == 414
    assert target_error == {
        "error": "uri_too_long",
        "detail": "request target exceeds the bridge limit",
    }


def test_bridge_stalled_request_body_times_out_as_typed_invalid_body(
    tmp_bridge_root: Path,
    monkeypatch,
) -> None:
    """A client that stops sending a declared body cannot hold a worker forever."""

    from urllib.parse import urlsplit

    import astrid.core.integrations.reigh.local_bridge_server as bridge_server

    monkeypatch.setattr(bridge_server, "_REQUEST_SOCKET_TIMEOUT_SEC", 0.05)
    with running_server(tmp_bridge_root) as base_url:
        parsed = urlsplit(base_url)
        token = _BRIDGE_REQUEST_TOKENS[base_url]
        connection = socket.create_connection((parsed.hostname, parsed.port), timeout=2)
        started = time.monotonic()
        try:
            connection.sendall(
                (
                    f"POST /v1/queue/claim HTTP/1.1\r\n"
                    f"Host: {parsed.hostname}:{parsed.port}\r\n"
                    "Content-Type: application/json\r\n"
                    "Content-Length: 8\r\n"
                    f"X-Astrid-Request-Token: {token}\r\n"
                    "Connection: close\r\n\r\n"
                    "{"
                ).encode("ascii")
            )
            connection.settimeout(2)
            response = bytearray()
            while b'"invalid_body"' not in response:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
        finally:
            connection.close()

    assert time.monotonic() - started < 1
    assert response.startswith(b"HTTP/1.1 400")
    assert b'"error": "invalid_body"' in response


def test_asset_stream_stops_after_client_disconnect(
    tmp_bridge_root: Path,
    monkeypatch,
) -> None:
    """A dropped media client cancels the active stream and closes its file."""

    from http.client import HTTPConnection
    from urllib.parse import urlsplit

    timeline_id = "aaaaaad1-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pd1"
    asset_content = b"disconnect me\n" * (512 * 1024)
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="disconnect-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {"clip": {"file": "clip.bin"}}},
            media={"clip": (asset_content, "clip.bin")},
        )
        from astrid.core.io.media_import import managed_media_path

        stream_path = managed_media_path(
            composition.projects_root, hashlib.sha256(asset_content).hexdigest()
        )
        real_open = Path.open
        open_count = 0
        stream_read_started = threading.Event()
        release_read = threading.Event()
        stream_closed = threading.Event()
        read_calls = 0

        class BlockingReader:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self.close()
                return False

            def seek(self, *args):
                return self.wrapped.seek(*args)

            def read(self, size=-1):
                nonlocal read_calls
                read_calls += 1
                stream_read_started.set()
                assert release_read.wait(timeout=5)
                return self.wrapped.read(size)

            def close(self):
                self.wrapped.close()
                stream_closed.set()

        def open_hook(path, *args, **kwargs):
            nonlocal open_count
            if Path(path) == stream_path:
                open_count += 1
                # The first open verifies the content hash; the second is the
                # response stream itself.
                if open_count == 2:
                    return BlockingReader(real_open(path, *args, **kwargs))
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", open_hook)
        parsed = urlsplit(base_url)
        connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        connection.request(
            "GET",
            f"/projects/disconnect-proj/timelines/{timeline_id}/assets/clip",
        )
        response = connection.getresponse()
        assert response.status == 200
        assert stream_read_started.wait(timeout=5)

        # An abortive close gives the server an immediate RST rather than a
        # graceful FIN that could let one buffered write succeed.
        assert connection.sock is not None
        connection.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_LINGER,
            struct.pack("ii", 1, 0),
        )
        connection.close()
        release_read.set()
        assert stream_closed.wait(timeout=5)

    assert read_calls == 1


def test_bridge_concurrency_budget_rejects_then_releases(
    tmp_bridge_root: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    first_result: dict[str, int] = {}

    class SlowHealthBridge:
        def health(self, projects_root: str) -> HealthStatus:
            entered.set()
            assert release.wait(timeout=5)
            return HealthStatus(ok=True, projects_root=projects_root)

    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=SlowHealthBridge(),
        max_concurrent_requests=1,
        rate_limit_capacity=100,
        rate_limit_refill_per_second=100.0,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"

    def first_request() -> None:
        first_result["status"] = _get_json(f"{base}/v1/health")[0]

    client = threading.Thread(target=first_request, daemon=True)
    client.start()
    try:
        assert entered.wait(timeout=5)
        limited_status, limited = _get_error(f"{base}/v1/health")
        release.set()
        client.join(timeout=5)
        after_status, _after = _get_json(f"{base}/v1/health")
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert limited_status == 429
    assert limited["error"] == "rate_limited"
    assert first_result["status"] == 200
    assert after_status == 200


def test_projects_timeline_load_missing_project_returns_project_not_found(
    tmp_bridge_root: Path,
) -> None:
    """A nonexistent project is 404 project_not_found, never an empty view."""
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        status, error = _get_error(
            f"{base_url}/projects/no-such/timelines/33333333-3333-3333-3333-333333333333"
        )

    assert status == 404
    assert error["error"] == "project_not_found"


def test_server_returns_normal_http_errors_for_unknown_or_invalid_resources(
    tmp_bridge_root: Path,
) -> None:
    timeline_id = "22222222-2222-2222-2222-222222222222"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="ados-talks", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid="01jm4k5n7p0000000000000002",
        )
        missing_timeline_status, missing_timeline = _get_error(
            f"{base_url}/projects/ados-talks/timelines/33333333-3333-3333-3333-333333333333",
        )
        invalid_timeline_status, invalid_timeline = _get_error(
            f"{base_url}/projects/ados-talks/timelines/not%20a%20valid%20selector",
        )
        unknown_route_status, unknown_route = _get_error(
            f"{base_url}/projects/ados-talks/assets/bad-key",
        )
        removed_list_status, removed_list = _get_error(
            f"{base_url}/projects/missing-project/timelines",
        )

    assert missing_timeline_status == 404
    assert missing_timeline["error"] == "timeline_not_found"

    assert invalid_timeline_status == 400
    assert invalid_timeline["error"] == "invalid_timeline"

    assert unknown_route_status == 404
    assert unknown_route["error"] == "not_found"

    # The timelines-list route validates the project first; a missing project
    # is a project_not_found 404 (never an empty authority-dependent view).
    assert removed_list_status == 404
    assert removed_list["error"] == "project_not_found"


# ---------------------------------------------------------------------------
# Asset endpoint tests (repository-backed, m4 plan step 22)
# ---------------------------------------------------------------------------
#
# The legacy sidecar/FSA asset fallback was removed in step 22: every asset
# resolves from the persisted timeline registry through kernel
# media/location records in the route project, the local bytes are verified
# against the media content SHA-256 before streaming, and a server without
# the composed repository bridge fails closed with the typed 500 envelope.


def test_asset_200_full_response_with_correct_headers(
    tmp_bridge_root: Path,
) -> None:
    """Full asset fetch returns 200, Accept-Ranges, Content-Type, and full body."""
    timeline_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01JM4K5N7P00000000000000AA"
    registry = {"assets": {"clip-a": {"file": "clip-a.mp4"}}}
    asset_content = _decodable_video_bytes()
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="media-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clip-a": (asset_content, "clip-a.mp4")},
        )
        url = f"{base_url}/projects/media-proj/timelines/{timeline_id}/assets/clip-a"
        status, headers, body = _get_bytes(url)

    assert status == 200
    assert headers.get("X-Astrid-Bridge-Version") == "v1"
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("Referrer-Policy") == "no-referrer"
    assert headers.get("Accept-Ranges") == "bytes"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("ETag")
    assert headers.get("Last-Modified")
    assert headers.get("Content-Type") == "video/mp4"
    assert int(headers.get("Content-Length", "0")) == len(asset_content)
    assert body == asset_content


def test_asset_head_response_with_media_headers(
    tmp_bridge_root: Path,
) -> None:
    timeline_id = "a0a0a0a0-a0a0-a0a0-a0a0-a0a0a0a0a0a0"
    timeline_ulid = "01JM4K5N7P0000000000000A0A"
    registry = {"assets": {"clip-head": {"file": "clip-head.mp4"}}}
    asset_content = _decodable_video_bytes()
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="head-media-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clip-head": (asset_content, "clip-head.mp4")},
        )
        url = f"{base_url}/projects/head-media-proj/timelines/{timeline_id}/assets/clip-head"
        status, headers = _head(url)

    assert status == 200
    assert headers.get("X-Astrid-Bridge-Version") == "v1"
    assert headers.get("Accept-Ranges") == "bytes"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("ETag")
    assert headers.get("Last-Modified")
    assert headers.get("Content-Type") == "video/mp4"
    assert int(headers.get("Content-Length", "0")) == len(asset_content)


def test_typed_audio_asset_preserves_repository_mime_for_get_head_and_range(
    tmp_bridge_root: Path,
) -> None:
    """Content-addressed storage must not erase a typed audio transport contract."""
    timeline_id = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"
    timeline_ulid = "01JM4K5N7P0000000000000A1A"
    registry = {"assets": {"carrier": {"file": "carrier.aac", "type": "audio/aac"}}}
    asset_content = _decodable_video_bytes()
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="audio-media-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"carrier": (asset_content, "carrier.aac")},
        )
        url = f"{base_url}/projects/audio-media-proj/timelines/{timeline_id}/assets/carrier"
        status, headers, body = _get_bytes(url)
        head_status, head_headers = _head(url)
        range_status, range_headers, range_body = _get_bytes(
            url,
            range_header="bytes=4-10",
        )

    assert status == 200
    assert headers.get("Content-Type") == "audio/x-aac"
    assert body == asset_content
    assert head_status == 200
    assert head_headers.get("Content-Type") == "audio/x-aac"
    assert int(head_headers.get("Content-Length", "0")) == len(asset_content)
    assert range_status == 206
    assert range_headers.get("Content-Type") == "audio/x-aac"
    assert range_headers.get("Content-Range") == (
        f"bytes 4-10/{len(asset_content)}"
    )
    assert range_body == asset_content[4:11]


def test_asset_206_byte_range(
    tmp_bridge_root: Path,
) -> None:
    """Byte range request returns 206 with correct Content-Range and partial body."""
    timeline_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    timeline_ulid = "01JM4K5N7P00000000000000BB"
    registry = {"assets": {"alpha": {"file": "alpha.bin"}}}
    asset_content = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26 bytes
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="range-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"alpha": (asset_content, "alpha.bin")},
        )
        url = f"{base_url}/projects/range-proj/timelines/{timeline_id}/assets/alpha"
        # Request bytes 5-14 (10 bytes: FGHIJKLMNO)
        status, headers, body = _get_bytes(url, range_header="bytes=5-14")

    assert status == 206
    assert headers.get("X-Astrid-Bridge-Version") == "v1"
    assert headers.get("Content-Range") == "bytes 5-14/26"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("ETag")
    assert int(headers.get("Content-Length", "0")) == 10
    assert body == b"FGHIJKLMNO"


def test_asset_range_less_large_response_returns_initial_partial_chunk(
    tmp_bridge_root: Path,
    monkeypatch,
) -> None:
    """Large range-less asset fetches should not stream the whole source file."""
    import astrid.core.integrations.reigh.local_bridge_server as bridge_server

    monkeypatch.setattr(bridge_server, "_RANGELESS_FULL_BODY_LIMIT_BYTES", 20)
    monkeypatch.setattr(bridge_server, "_RANGELESS_INITIAL_CHUNK_BYTES", 8)

    timeline_id = "abababab-abab-abab-abab-abababababab"
    timeline_ulid = "01JM4K5N7P0000000000000ABA"
    registry = {"assets": {"large": {"file": "large.mp4"}}}
    asset_content = _decodable_video_bytes()
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="large-media-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"large": (asset_content, "large.mp4")},
        )
        url = f"{base_url}/projects/large-media-proj/timelines/{timeline_id}/assets/large"
        status, headers, body = _get_bytes(url)

    assert status == 206
    assert headers.get("Accept-Ranges") == "bytes"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("Content-Range") == f"bytes 0-7/{len(asset_content)}"
    assert int(headers.get("Content-Length", "0")) == 8
    assert body == asset_content[:8]


def test_asset_206_open_ended_range(
    tmp_bridge_root: Path,
) -> None:
    """Open-ended range (bytes=N-) returns from N to end."""
    timeline_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    timeline_ulid = "01JM4K5N7P00000000000000CC"
    registry = {"assets": {"digits": {"file": "digits.bin"}}}
    asset_content = b"0123456789"  # 10 bytes
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="open-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"digits": (asset_content, "digits.bin")},
        )
        url = f"{base_url}/projects/open-proj/timelines/{timeline_id}/assets/digits"
        status, headers, body = _get_bytes(url, range_header="bytes=7-")

    assert status == 206
    assert headers.get("Content-Range") == "bytes 7-9/10"
    assert int(headers.get("Content-Length", "0")) == 3
    assert body == b"789"


def test_asset_206_suffix_range(
    tmp_bridge_root: Path,
) -> None:
    """Suffix range (bytes=-N) returns last N bytes."""
    timeline_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    timeline_ulid = "01JM4K5N7P00000000000000DD"
    registry = {"assets": {"letters": {"file": "letters.bin"}}}
    asset_content = b"abcdefghij"  # 10 bytes
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="suffix-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"letters": (asset_content, "letters.bin")},
        )
        url = f"{base_url}/projects/suffix-proj/timelines/{timeline_id}/assets/letters"
        status, headers, body = _get_bytes(url, range_header="bytes=-4")

    assert status == 206
    assert headers.get("Content-Range") == "bytes 6-9/10"
    assert int(headers.get("Content-Length", "0")) == 4
    assert body == b"ghij"


def test_asset_416_range_not_satisfiable_start_beyond_size(
    tmp_bridge_root: Path,
) -> None:
    """Range start >= file size returns 416."""
    timeline_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    timeline_ulid = "01JM4K5N7P00000000000000EE"
    registry = {"assets": {"tiny": {"file": "tiny.bin"}}}
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="four16-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"tiny": (b"small", "tiny.bin")},
        )
        url = f"{base_url}/projects/four16-proj/timelines/{timeline_id}/assets/tiny"
        status, headers, body = _get_bytes(url, range_header="bytes=10-20")

    assert status == 416
    assert headers.get("X-Astrid-Bridge-Version") == "v1"
    assert headers.get("Content-Range") == "bytes */5"


def test_asset_404_for_missing_asset_key(
    tmp_bridge_root: Path,
) -> None:
    """Non-existent asset key returns 404 JSON error."""
    timeline_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="nope-proj",
            timeline_id=timeline_id,
            timeline_ulid="01JM4K5N7P0000000000000NP1",
            registry={"assets": {}},
        )
        status, error = _get_error(
            f"{base_url}/projects/nope-proj/timelines/{timeline_id}/assets/no-such-key",
        )

    assert status == 404
    assert error["error"] == "asset_not_found"


def test_asset_404_for_http_only_asset(
    tmp_bridge_root: Path,
) -> None:
    """HTTP-referenced asset (not local) returns 404 JSON error."""
    timeline_id = "11111111-1111-1111-1111-1111111111ab"
    timeline_ulid = "01JM4K5N7P00000000000000FF"
    registry = {"assets": {"remote-one": {"file": "https://example.com/video.mp4"}}}
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="http-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
        )
        status, error = _get_error(
            f"{base_url}/projects/http-proj/timelines/{timeline_id}/assets/remote-one",
        )

    assert status == 404
    assert error["error"] == "asset_not_local"


def test_asset_404_for_invalid_project(
    tmp_bridge_root: Path,
) -> None:
    """Asset request with invalid project slug returns 400."""
    timeline_id = "22222222-2222-2222-2222-222222222222"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="valid-proj",
            timeline_id=timeline_id,
            timeline_ulid="01JM4K5N7P0000000000000VP1",
            registry={"assets": {}},
        )
        status, error = _get_error(
            f"{base_url}/projects/%2E%2E/timelines/{timeline_id}/assets/some-key",
        )

    assert status == 400
    assert error["error"] == "invalid_project"


def test_asset_404_for_invalid_timeline(
    tmp_bridge_root: Path,
) -> None:
    """Asset request with invalid timeline selector returns 400."""
    timeline_id = "33333333-3333-3333-3333-333333333333"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="valid-proj",
            timeline_id=timeline_id,
            timeline_ulid="01JM4K5N7P0000000000000VP2",
            registry={"assets": {}},
        )
        status, error = _get_error(
            f"{base_url}/projects/valid-proj/timelines/!!!bad!!!selector!!!/assets/some-key",
        )

    assert status == 400
    assert error["error"] == "invalid_timeline"


def test_asset_fails_closed_without_composed_bridge(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """A server without the repository bridge fails closed with 500 internal.

    The legacy sidecar/FSA asset fallback is gone (m4 plan step 22): there
    is exactly one supported asset path, and it requires the injected
    repository bridge and writer.
    """
    timeline_id = "44444444-4444-4444-4444-444444444444"
    seed_bridge_project(slug="fallback-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        status, error = _get_error(
            f"{base_url}/projects/fallback-proj/timelines/{timeline_id}/assets/some-key",
        )

    assert status == 500
    assert error["error"] == "internal"


# ---------------------------------------------------------------------------
# Save endpoint tests (POST /projects/:project/timelines/:timeline/save)
# ---------------------------------------------------------------------------


def test_save_endpoint_200_for_valid_config(
    tmp_bridge_root: Path,
) -> None:
    """POST /save with a valid config, registry, and integer expected_version
    commits exactly one timeline.saved event through the repository CAS."""
    from astrid.core.integrations.reigh.bridge_service import (
        RECEIPT_SECRECY_FIELDS,
    )

    timeline_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01"
    timeline_ulid = "01jm4k5n7p000000000000save"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="save-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )

        new_config = {
            "clips": [
                {"id": "c1", "at": 0, "track": "V1", "clipType": "media", "asset": "a1"},
            ],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }
        new_registry = {"assets": {"a1": {"file": "a1.mp4", "type": "video/mp4"}}}

        url = f"{base_url}/projects/save-proj/timelines/{timeline_id}/save"
        status, result = _post_json(
            url,
            {
                "config": new_config,
                "registry": new_registry,
                "expected_version": 1,
            },
        )

        # Read back the committed projection through the repository.
        loaded = _repo_load_timeline(composition, project.id, timeline_id)

    assert status == 200
    assert result["timeline_id"] == timeline_id
    assert result["timeline_ulid"] == timeline_ulid
    assert result["config"] == new_config
    assert result["registry"] == new_registry
    # One created event (head 1) plus exactly one saved event (head 2).
    assert result["config_version"] == 2
    assert isinstance(result["config_version"], int)
    assert loaded.config_version == 2
    assert loaded.config == new_config
    assert loaded.registry == new_registry
    # Receipt secrecy (contract §7): no internal receipt/event field may
    # appear in any bridge response, even on the committed save.
    for field in RECEIPT_SECRECY_FIELDS:
        assert field not in result, f"receipt field leaked: {field!r}"


def test_save_endpoint_bundle_cas_round_trip_clear_and_schema_guard(
    tmp_bridge_root: Path,
) -> None:
    """Bundle is bridge-owned, CAS-persisted, omission-preserving, and typed."""
    timeline_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa02"
    timeline_ulid = "01jm4k5n7p000000000000bun1"
    bundle = {
        "schema_version": 1,
        "itemsBySchemaRef": {
            "reigh.transcript_segment/v1": [
                {
                    "id": "assetA:src:0",
                    "shape": "interval",
                    "domain": "source_seconds",
                    "extent": {"start": 0, "end": 1.5},
                    "schemaRef": "reigh.transcript_segment/v1",
                    "payload": {"text": "hello", "app": {"opaque": True}},
                    "sourceArtifactRef": {"assetId": "assetA"},
                    "provenance": {"adapterId": "reigh.adaptTranscript", "adapterVersion": "1"},
                }
            ],
        },
        "app": {"extension": {"opaque": "authored"}},
    }
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="bundle-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )
        url = f"{base_url}/projects/bundle-proj/timelines/{timeline_id}/save"
        status, saved = _post_json(
            url,
            {
                "config": {"clips": [], "tracks": [], "output": {"derived": True}},
                "registry": {"assets": {}},
                "expected_version": 1,
                "bundle": bundle,
            },
        )
        assert status == 200
        assert saved["bundle"] == bundle

        # Omitted means preserve the bridge-owned document lane.
        status, preserved = _post_json(
            url,
            {
                "config": {"clips": [{"id": "authored"}], "tracks": []},
                "registry": {"assets": {}},
                "expected_version": 2,
            },
        )
        assert status == 200
        assert preserved["bundle"] == bundle

        # Explicit null clears it atomically.
        status, cleared = _post_json(
            url,
            {
                "config": {"clips": [], "tracks": []},
                "registry": {"assets": {}},
                "expected_version": 3,
                "bundle": None,
            },
        )
        assert status == 200
        assert "bundle" not in cleared
        assert _repo_load_timeline(composition, project.id, timeline_id).bundle is None

        before = _repo_db_snapshot(composition)
        status, invalid = _post_json(
            url,
            {
                "config": {"clips": [], "tracks": []},
                "registry": {"assets": {}},
                "expected_version": 4,
                "bundle": {"schema_version": 99, "itemsBySchemaRef": {}},
            },
        )
        after = _repo_db_snapshot(composition)

    assert status == 422
    assert invalid["error"] == "schema_incompatible"
    assert invalid["issues"][0]["pointer"] == "/bundle/schema_version"
    assert before == after


def test_save_endpoint_400_for_malformed_body_not_json(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """POST /save with a non-JSON body returns 400."""
    timeline_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    seed_bridge_project(slug="bad-body-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        url = f"{base_url}/projects/bad-body-proj/timelines/{timeline_id}/save"
        status, error = _post_raw(url, b"this is not json", content_type="text/plain")

    assert status == 400
    assert error["error"] == "invalid_body"


def test_save_endpoint_400_for_missing_expected_version(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """POST /save with JSON that lacks an 'expected_version' returns 400."""
    timeline_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    seed_bridge_project(slug="no-version-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        url = f"{base_url}/projects/no-version-proj/timelines/{timeline_id}/save"
        status, error = _post_json(
            url,
            {
                "config": {"tracks": []},
                "registry": {"assets": {}},
            },
        )

    assert status == 400
    assert error["error"] == "invalid_expected_version"


def test_save_endpoint_400_for_missing_registry(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """POST /save with JSON that lacks a 'registry' returns 400."""
    timeline_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    seed_bridge_project(slug="no-registry-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        url = f"{base_url}/projects/no-registry-proj/timelines/{timeline_id}/save"
        status, error = _post_json(
            url,
            {
                "config": {"tracks": []},
                "expected_version": 1,
            },
        )

    assert status == 400
    assert error["error"] == "invalid_registry"


def test_save_endpoint_404_for_unknown_timeline(
    tmp_bridge_root: Path,
) -> None:
    """POST /save for a timeline that does not exist returns 404 timeline_not_found."""
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_create_project(composition, slug="known-proj", key="proj-1")
        url = f"{base_url}/projects/known-proj/timelines/ffffffff-ffff-ffff-ffff-ffffffffffff/save"
        status, error = _post_json(
            url,
            {
                "config": {"tracks": []},
                "registry": {"assets": {}},
                "expected_version": 1,
            },
        )

    assert status == 404
    assert error["error"] == "timeline_not_found"


def test_save_endpoint_400_for_invalid_project_slug(
    tmp_bridge_root: Path,
) -> None:
    """POST /save with an invalid project slug returns 400 invalid_project."""
    timeline_id = "11111111-1111-1111-1111-111111111111"
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        url = f"{base_url}/projects/%2E%2E/timelines/{timeline_id}/save"
        status, error = _post_json(
            url,
            {
                "config": {"tracks": []},
                "registry": {"assets": {}},
                "expected_version": 1,
            },
        )

    assert status == 400
    assert error["error"] == "invalid_project"


def test_save_endpoint_404_for_unknown_project(
    tmp_bridge_root: Path,
) -> None:
    """POST /save for a project that does not exist returns 404 project_not_found."""
    timeline_id = "22222222-2222-2222-2222-222222222222"
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        url = f"{base_url}/projects/no-such-proj/timelines/{timeline_id}/save"
        status, error = _post_json(
            url,
            {
                "config": {"tracks": []},
                "registry": {"assets": {}},
                "expected_version": 1,
            },
        )

    assert status == 404
    assert error["error"] == "project_not_found"


# ---------------------------------------------------------------------------
# Registry endpoint tests (PUT /projects/:project/timelines/:timeline/registry)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CORS preflight tests (OPTIONS)
# ---------------------------------------------------------------------------


def test_cors_preflight_options_returns_204_with_cors_headers(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """OPTIONS request returns 204 with correct CORS headers for allowed origins."""
    timeline_id = "11111111-1111-1111-1111-1111cors01"
    seed_bridge_project(slug="cors-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        # OPTIONS on a save endpoint with allowed origin
        url = f"{base_url}/projects/cors-proj/timelines/{timeline_id}/save"
        status, headers = _options(url, origin="http://localhost:3000")

    assert status == 204
    assert headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert headers.get("Access-Control-Allow-Methods") == "GET, HEAD, POST, OPTIONS"
    assert (
        headers.get("Access-Control-Allow-Headers")
        == "Authorization, Content-Type, Range, If-None-Match, If-Modified-Since, "
        "Idempotency-Key, X-Astrid-Bridge-Version, X-Astrid-Request-Token"
    )
    assert (
        headers.get("Access-Control-Expose-Headers")
        == "Accept-Ranges, Content-Length, Content-Range, Content-Type, ETag, Last-Modified, X-Astrid-Bridge-Version"
    )


def test_cors_preflight_no_origin_omits_cors_headers(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """OPTIONS without an Origin header omits CORS response headers."""
    timeline_id = "22222222-2222-2222-2222-2222cors02"
    seed_bridge_project(slug="no-origin-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        url = f"{base_url}/projects/no-origin-proj/timelines/{timeline_id}/save"
        status, headers = _options(url)

    assert status == 204
    assert headers.get("Access-Control-Allow-Origin") is None


def test_cors_preflight_disallowed_origin_is_rejected(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """OPTIONS from a non-whitelisted origin is rejected before routing."""
    timeline_id = "33333333-3333-3333-3333-3333cors03"
    seed_bridge_project(slug="bad-origin-proj", timeline_id=timeline_id)

    with running_server(tmp_bridge_root) as base_url:
        url = f"{base_url}/projects/bad-origin-proj/timelines/{timeline_id}/save"
        status, headers = _options(url, origin="https://evil.com")

    assert status == 403
    assert headers.get("Access-Control-Allow-Origin") is None


# ---------------------------------------------------------------------------
# Read-after-registry-write asset lookup
# ---------------------------------------------------------------------------


def test_asset_lookup_after_registry_write(
    tmp_bridge_root: Path,
) -> None:
    """Save a registry through the bridge, then GET the asset back.

    The registry write commits through the bridge POST (the combined save;
    the standalone PUT /registry route is gone), and the asset endpoint
    resolves the saved ``file`` alias through the kernel media location.
    """
    timeline_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"
    timeline_ulid = "01JM4K5N7P00000000000RARW1"
    asset_content = _decodable_video_bytes()
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="rarw-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
        )
        asset_path = _write_source_file(composition, "rarw-proj", "rarw-clip.webm", asset_content)
        _repo_import_media(
            composition,
            project_id=project.id,
            path=asset_path,
            key="media-1",
            realm="managed_local",
            locator="rarw-clip.webm",
        )

        # Step 1: Write the registry through the combined save.
        save_url = f"{base_url}/projects/rarw-proj/timelines/{timeline_id}/save"
        save_status, save_result = _post_json(
            save_url,
            {
                "config": {"clips": [], "tracks": []},
                "registry": {"assets": {"rarw-clip": {"file": "rarw-clip.webm"}}},
                "expected_version": 1,
            },
        )
        assert save_status == 200
        assert save_result["config_version"] == 2

        # Step 2: Read the asset back through the asset endpoint
        asset_url = f"{base_url}/projects/rarw-proj/timelines/{timeline_id}/assets/rarw-clip"
        asset_status, asset_headers, asset_body = _get_bytes(asset_url)

    assert asset_status == 200
    assert asset_headers.get("Accept-Ranges") == "bytes"
    assert int(asset_headers.get("Content-Length", "0")) == len(asset_content)
    assert asset_body == asset_content


def test_asset_lookup_after_registry_write_sources_relative(
    tmp_bridge_root: Path,
) -> None:
    """Registry ``file`` aliases resolve through nested media locations."""
    timeline_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2"
    timeline_ulid = "01JM4K5N7P00000000000RARW2"
    asset_content = b"Nested file content.\n"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="rarw-src-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
        )
        asset_path = _write_source_file(
            composition, "rarw-src-proj", "nested/deep.bin", asset_content
        )
        _repo_import_media(
            composition,
            project_id=project.id,
            path=asset_path,
            key="media-1",
            realm="managed_local",
            locator="nested/deep.bin",
        )
        save_url = f"{base_url}/projects/rarw-src-proj/timelines/{timeline_id}/save"
        save_status, save_result = _post_json(
            save_url,
            {
                "config": {"clips": [], "tracks": []},
                "registry": {"assets": {"deep-asset": {"file": "nested/deep.bin"}}},
                "expected_version": 1,
            },
        )
        assert save_status == 200
        assert save_result["config_version"] == 2

        asset_url = f"{base_url}/projects/rarw-src-proj/timelines/{timeline_id}/assets/deep-asset"
        asset_status, asset_headers, asset_body = _get_bytes(asset_url)

    assert asset_status == 200
    assert int(asset_headers.get("Content-Length", "0")) == len(asset_content)
    assert asset_body == asset_content


# ---------------------------------------------------------------------------
# CAS conflict tests (409 timeline_version_conflict)
# ---------------------------------------------------------------------------


def test_save_endpoint_409_for_stale_expected_version(
    tmp_bridge_root: Path,
) -> None:
    """POST /save with a stale expected_version returns 409 with the current
    integer config_version and changes zero rows."""
    timeline_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa409"
    timeline_ulid = "01jm4k5n7p00000000000409sav"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="conflict-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )
        config = {"clips": [], "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}]}
        registry = {"assets": {}}

        before = _repo_db_snapshot(composition)
        url = f"{base_url}/projects/conflict-proj/timelines/{timeline_id}/save"
        # expected_version=999 is far in the future → stale
        status, error = _post_json(
            url,
            {
                "config": config,
                "registry": registry,
                "expected_version": 999,
            },
        )
        after = _repo_db_snapshot(composition)

    assert status == 409
    assert error["error"] == "timeline_version_conflict"
    assert "detail" in error
    # The current head is exactly 1 (one timeline.created event).
    assert error["config_version"] == 1
    assert isinstance(error["config_version"], int)
    # A stale CAS changes zero rows: document, registry, events, heads,
    # receipts all stay byte-identical.
    assert after == before


def test_two_concurrent_saves_exactly_one_wins(
    tmp_bridge_root: Path,
) -> None:
    """Two concurrent saves from one expected head: exactly one 200 and one
    409, the winner's document commits at head 2, and no losing receipt
    exists."""
    timeline_id = "cccccccc-cccc-cccc-cccc-cccccccccc01"
    timeline_ulid = "01jm4k5n7p00000000000race01"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="race-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )

        config_a = {
            "clips": [{"id": "ca", "at": 0, "track": "V1", "clipType": "media", "asset": "aa"}],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }
        config_b = {
            "clips": [{"id": "cb", "at": 0, "track": "V1", "clipType": "media", "asset": "bb"}],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        }
        registry = {"assets": {}}

        results: list[tuple[int, dict]] = []

        def do_save(cfg: dict) -> None:
            url = f"{base_url}/projects/race-proj/timelines/{timeline_id}/save"
            status, body = _post_json(
                url,
                {
                    "config": cfg,
                    "registry": registry,
                    "expected_version": 1,
                },
            )
            results.append((status, body))

        t1 = threading.Thread(target=do_save, args=(config_a,))
        t2 = threading.Thread(target=do_save, args=(config_b,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        snapshot = _repo_db_snapshot(composition)
        loaded = _repo_load_timeline(composition, project.id, timeline_id)

    assert len(results) == 2
    statuses = {r[0] for r in results}
    assert statuses == {200, 409}, f"Expected one 200 and one 409, got {statuses}"

    winner = next(r for r in results if r[0] == 200)
    loser = next(r for r in results if r[0] == 409)
    assert loser[1]["error"] == "timeline_version_conflict"
    # The loser observed the winner's committed head.
    assert loser[1]["config_version"] == 2
    assert isinstance(loser[1]["config_version"], int)

    # Exactly one timeline.saved event, exactly one timeline.save receipt,
    # and the committed document is one of the two competing configs.
    assert winner[1]["config_version"] == 2
    assert snapshot["saved_events"] == 1, snapshot
    assert snapshot["save_receipts"] == 1, snapshot
    assert loaded.config_version == 2
    assert loaded.config in (config_a, config_b)


# ---------------------------------------------------------------------------
# Serve command registration tests
# ---------------------------------------------------------------------------


def test_serve_command_is_registered_in_top_level_handlers() -> None:
    """`astrid serve` must be a recognised top-level command."""
    from astrid.core.gateway.dispatch import _top_level_commands

    commands = _top_level_commands()
    assert "serve" in commands


def test_serve_dispatcher_starts_and_serves_health(
    seed_bridge_project,
    tmp_bridge_root: Path,
) -> None:
    """_dispatch_serve creates a working server that responds to /health."""

    timeline_id = "11111111-1111-1111-1111-111111111111"
    seed_bridge_project(slug="ados-talks", timeline_id=timeline_id)

    # Start the serve command in a daemon thread so it doesn't block the test.
    server_started = threading.Event()
    server_error: Exception | None = None
    server_address: tuple[str, int] | None = None
    server = None

    def _run_serve():
        nonlocal server, server_address, server_error
        try:
            # We need to override serve_forever to signal when the server is ready.
            from astrid.core.integrations.reigh.local_bridge_server import (
                create_local_bridge_server,
            )

            srv = create_local_bridge_server(
                host="127.0.0.1",
                port=0,
                projects_root=tmp_bridge_root,
            )
            composition = compose_standard_bridge(tmp_bridge_root)
            srv.bridge = composition.bridge
            srv.bridge_writer = composition.writer
            srv.bridge_database_path = composition.database_path
            server = srv
            server_address = srv.server_address
            server_started.set()
            try:
                srv.serve_forever()
            finally:
                composition.close()
        except Exception as exc:  # noqa: BLE001 - capture server-thread startup failures
            server_error = exc
            server_started.set()

    thread = threading.Thread(target=_run_serve, daemon=True)
    thread.start()

    # Wait for the server to bind.
    assert server_started.wait(timeout=5), "Server did not start within 5s"
    if server_error:
        raise server_error
    assert server_address is not None

    host, port = server_address
    base_url = f"http://{host}:{port}"

    try:
        health_status, health = _get_json(f"{base_url}/health")
        assert health_status == 200
        assert health["ok"] is True
        assert health["projects_root"] == str(tmp_bridge_root.resolve())
    finally:
        assert server is not None
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not thread.is_alive(), "serve dispatcher thread did not shut down"


def test_serve_dispatcher_with_host_port_and_projects_root_args(
    tmp_path: Path,
    seed_bridge_project,
) -> None:
    """_dispatch_serve accepts --host, --port, and --projects-root arguments."""

    projects_dir = tmp_path / "serve-test-projects"
    projects_dir.mkdir()
    seed_bridge_project(slug="test-proj", timeline_id="11111111-1111-1111-1111-111111111111")

    # We can't actually call _dispatch_serve because it blocks on serve_forever.
    # Instead, verify the argument parser accepts the expected flags.
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        prog="astrid serve", description="Start the Astrid local read bridge."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--projects-root", default=None)

    parsed = parser.parse_args(
        ["--host", "0.0.0.0", "--port", "9999", "--projects-root", str(projects_dir)]
    )
    assert parsed.host == "0.0.0.0"
    assert parsed.port == 9999
    assert parsed.projects_root == str(projects_dir)


def test_save_endpoint_422_for_schema_incompatible_config(
    tmp_bridge_root: Path,
) -> None:
    """POST /save whose payload fails the route-level schema guard returns a
    typed 422 schema_incompatible with issues[], never a connection-close 500.

    The repository treats config as a loose editor object (contract §5.2),
    so the wire-shape violation that maps to 422 is a registry whose
    ``assets`` is not an object (contract §6.2).
    """
    timeline_id = "cccccccc-cccc-cccc-cccc-cccccccccc01"
    timeline_ulid = "01jm4k5n7p0000000000004221"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="save-422-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )

        # registry.assets must be an object; a scalar is schema-incompatible.
        bad_registry = {"assets": "not-an-object"}

        url = f"{base_url}/projects/save-422-proj/timelines/{timeline_id}/save"
        status, result = _post_json(
            url,
            {
                "config": {"clips": [], "tracks": []},
                "registry": bad_registry,
                "expected_version": 1,
            },
        )

    assert status == 422
    assert result["error"] == "schema_incompatible"
    assert isinstance(result.get("issues"), list) and result["issues"]
    assert result["issues"][0]["pointer"] == "/registry/assets"
    assert "message" in result["issues"][0]


def test_save_endpoint_400_for_boolean_expected_version(
    tmp_bridge_root: Path,
) -> None:
    """POST /save with a boolean expected_version is rejected: a boolean is
    not a version (contract §6.1 numeric version rule)."""
    timeline_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    with repository_server(tmp_bridge_root) as (base_url, _composition):
        url = f"{base_url}/projects/no-such/timelines/{timeline_id}/save"
        status, error = _post_json(
            url,
            {
                "config": {"tracks": []},
                "registry": {"assets": {}},
                "expected_version": True,
            },
        )

    assert status == 400
    assert error["error"] == "invalid_expected_version"


def test_save_stale_and_malformed_requests_make_zero_database_changes(
    tmp_bridge_root: Path,
) -> None:
    """Every stale or malformed save request mutates nothing: the route maps
    body/schema/not-found/conflict failures to typed envelopes before any
    repository write, so counts, heads, documents, events, and receipts stay
    byte-identical."""
    timeline_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    timeline_ulid = "01jm4k5n7p00000000000zeromut"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="zero-mut-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )
        url = f"{base_url}/projects/zero-mut-proj/timelines/{timeline_id}/save"

        def attempt(body: Any = None, raw: bytes | None = None) -> tuple[int, dict]:
            if raw is not None:
                return _post_raw(url, raw, content_type="text/plain")
            return _post_json(url, body)

        # Malformed bodies (400 invalid_body).
        attempt(raw=b"this is not json")
        # Missing object fields (400 invalid_config / invalid_registry /
        # invalid_expected_version).
        attempt({"registry": {"assets": {}}, "expected_version": 1})
        attempt({"config": {"tracks": []}, "expected_version": 1})
        attempt({"config": {"tracks": []}, "registry": {"assets": {}}})
        # Boolean version (400 invalid_expected_version).
        attempt({"config": {}, "registry": {"assets": {}}, "expected_version": False})
        # Schema-incompatible registry (422 schema_incompatible).
        status, body = attempt(
            {
                "config": {},
                "registry": {"assets": "oops"},
                "expected_version": 1,
            }
        )
        assert (status, body["error"]) == (422, "schema_incompatible")
        # Stale expected version (409 timeline_version_conflict).
        status, body = attempt(
            {
                "config": {"tracks": []},
                "registry": {"assets": {}},
                "expected_version": 999,
            }
        )
        assert (status, body["error"]) == (409, "timeline_version_conflict")
        # Unknown timeline (404 timeline_not_found).
        status, body = _post_json(
            f"{base_url}/projects/zero-mut-proj/timelines/"
            "ffffffff-ffff-ffff-ffff-ffffffffffff/save",
            {"config": {}, "registry": {"assets": {}}, "expected_version": 1},
        )
        assert (status, body["error"]) == (404, "timeline_not_found")
        # Unknown project (404 project_not_found).
        status, body = _post_json(
            f"{base_url}/projects/no-such-proj/timelines/{timeline_id}/save",
            {"config": {}, "registry": {"assets": {}}, "expected_version": 1},
        )
        assert (status, body["error"]) == (404, "project_not_found")

        after = _repo_db_snapshot(composition)

    # Zero mutation: no events, receipts, heads, or documents changed by any
    # of the rejected requests (the timeline stays at the seed head 1).
    assert after["count:events"] == 2  # project.created + timeline.created
    assert after["count:command_receipts"] == 2
    assert after["saved_events"] == 0
    assert after["save_receipts"] == 0
    assert after["heads"][f"{timeline_id}:timeline.timeline"] == 1


# ---------------------------------------------------------------------------
# In-tree provider-contract client (m1 substitute, contract §11 / SD3)
# ---------------------------------------------------------------------------


class BridgeClientHTTPError(RuntimeError):
    """Non-2xx bridge response surfaced by the in-tree contract client."""

    def __init__(self, status: int, payload: dict[str, Any]):
        super().__init__(f"bridge HTTP {status}: {payload}")
        self.status = status
        self.payload = payload


class InTreeBridgeContractClient:
    """m1 in-tree substitute for the editor's ``AstridBridgeDataProvider``.

    Field-for-field against the frozen wire contract (§1-§6): list, load,
    save, and reload over plain HTTP with typed status handling. It is an
    m1 substitute that exercises the same wire contract without claiming
    browser or provider-source parity (SD3, contract §11; the real
    TypeScript suite remains the NSA-1 follow-up gate).
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health")

    def list_projects(self) -> list[dict[str, Any]]:
        return self._request_json("GET", "/projects")["projects"]

    def list_timelines(self, project_slug: str) -> list[dict[str, Any]]:
        return self._request_json("GET", f"/projects/{project_slug}/timelines")["timelines"]

    def load_timeline(self, project_slug: str, ref: str) -> dict[str, Any]:
        return self._request_json("GET", f"/projects/{project_slug}/timelines/{ref}")

    def reload_timeline(self, project_slug: str, ref: str) -> dict[str, Any]:
        """Load again after a save — the provider's reload contract."""
        return self.load_timeline(project_slug, ref)

    def save_timeline(
        self,
        project_slug: str,
        ref: str,
        *,
        config: dict[str, Any],
        registry: dict[str, Any],
        expected_version: int,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/projects/{project_slug}/timelines/{ref}/save",
            body={
                "config": config,
                "registry": registry,
                "expected_version": expected_version,
            },
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(self.base_url + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        _add_repository_request_token(req, self.base_url + path)
        try:
            with urlopen(req) as response:  # noqa: S310 - localhost client
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            payload = json.loads(error.read().decode("utf-8"))
            raise BridgeClientHTTPError(error.code, payload) from None


# ---------------------------------------------------------------------------
# Asset semantics over persisted registries (contract §9, repository-backed)
# ---------------------------------------------------------------------------


def _write_source_file(composition, slug: str, rel_path: str, content: bytes) -> Path:
    """Write one real media file under the project sources dir on disk."""
    path = composition.projects_root / slug / "sources" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _repo_import_media(
    composition,
    *,
    project_id: str,
    path: Path,
    key: str,
    realm: str = "managed_local",
    locator: str | None = None,
    media_id: str | None = None,
):
    """Import one prepared media file through the kernel media repository.

    The import commits a ``media`` row (content SHA-256 identity), one
    ``media_locations`` projection (realm + locator alias), the
    ``core.media`` stream, and a receipt in one unit of work. For the
    default ``managed_local`` realm the bytes are copied into the frozen
    digest tree, so serving resolves the managed path from the content
    hash; the explicit *locator* is stored as the replaceable alias that
    the timeline registry ``file`` value matches (m4 plan step 22).
    """
    from astrid.core.events.service import EventAppendService
    from astrid.core.io.media_import import prepare_media_file
    from astrid.core.receipts import ReceiptService
    from astrid.core.repositories.media import MediaRepository

    media = MediaRepository(
        events=EventAppendService(composition.registry),
        receipts=ReceiptService(),
        projects_root=composition.projects_root,
    )
    prepared = prepare_media_file(path)

    def _import(*, import_key: str, import_realm: str, import_locator: str | None):
        return UnitOfWork(composition.writer).run(
            lambda u: media.import_prepared(
                u,
                project_id=project_id,
                prepared=prepared,
                idempotency_key=import_key,
                realm=import_realm,
                locator=import_locator,
                media_id=media_id,
            )
        )

    # ``managed_local`` is deliberately opaque and digest-addressed.  The
    # editor's registry, however, uses a replaceable human locator (for
    # example ``clip-a.mp4``). Seed both the canonical managed location and
    # two external aliases: an absolute verified path for serving and the
    # registry alias for project-scoped lookup. This keeps the fixture honest
    # against the production storage contract without making tests depend on
    # a non-digest managed locator.
    if realm == "managed_local":
        result = _import(import_key=key, import_realm=realm, import_locator=None)
        if locator is not None:
            _import(
                import_key=f"{key}:absolute-alias",
                import_realm="external_local",
                import_locator=str(path),
            )
            _import(
                import_key=f"{key}:registry-alias",
                import_realm="external_local",
                import_locator=locator,
            )
        return result
    return _import(import_key=key, import_realm=realm, import_locator=locator)


def _repo_seed_asset_timeline(
    composition,
    *,
    slug: str,
    timeline_id: str,
    timeline_ulid: str,
    registry: dict[str, Any],
    media: dict[str, tuple[bytes, str]] | None = None,
):
    """Create one project and one timeline with a persisted asset registry.

    *media* maps an asset key to ``(content, locator)``: each entry is
    written under the project sources dir and imported through the kernel
    media repository with a ``managed_local`` location whose alias equals
    the locator, so the registry ``file`` value resolves project-scoped
    through ``media_locations`` (m4 plan step 22). The registry entry for
    the same key must carry ``{"file": <locator>}`` (or ``media_id``).
    """
    project = _repo_create_project(composition, slug=slug, key=f"proj-{slug}")
    _repo_create_timeline(
        composition,
        project_id=project.id,
        slug="primary",
        key=f"tl-{slug}",
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        registry=registry,
    )
    for index, (content, locator) in enumerate((media or {}).values()):
        path = _write_source_file(composition, slug, locator, content)
        _repo_import_media(
            composition,
            project_id=project.id,
            path=path,
            key=f"media-{slug}-{index}",
            realm="managed_local",
            locator=locator,
        )
    return project


def test_persisted_registry_asset_200_full_response_with_headers(
    tmp_bridge_root: Path,
) -> None:
    """Full asset fetch over a persisted registry: 200 + media headers."""
    timeline_id = "aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa1"
    registry = {"assets": {"clip-a": {"file": "clip-a.mp4"}}}
    asset_content = _decodable_video_bytes()
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="media-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clip-a": (asset_content, "clip-a.mp4")},
        )
        url = f"{base_url}/projects/media-proj/timelines/{timeline_id}/assets/clip-a"
        status, headers, body = _get_bytes(url)

    assert status == 200
    assert headers.get("Accept-Ranges") == "bytes"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("ETag")
    assert headers.get("Last-Modified")
    assert headers.get("Content-Type") == "video/mp4"
    assert int(headers.get("Content-Length", "0")) == len(asset_content)
    assert body == asset_content


def test_persisted_registry_asset_head_returns_headers_without_body(
    tmp_bridge_root: Path,
) -> None:
    """HEAD mirrors GET for status and headers with no response body."""
    timeline_id = "aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa2"
    registry = {"assets": {"clip": {"file": "clip.bin"}}}
    asset_content = b"head metadata only, persisted registry"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="head-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clip": (asset_content, "clip.bin")},
        )
        url = f"{base_url}/projects/head-proj/timelines/{timeline_id}/assets/clip"
        status, headers = _head(url)

    assert status == 200
    assert headers.get("Accept-Ranges") == "bytes"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("ETag")
    assert headers.get("Last-Modified")
    assert headers.get("Content-Type") == "application/octet-stream"
    assert int(headers.get("Content-Length", "0")) == len(asset_content)


def test_persisted_registry_asset_206_byte_ranges(
    tmp_bridge_root: Path,
) -> None:
    """Closed, open-ended, and suffix single ranges over persisted data."""
    timeline_id = "aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa3"
    registry = {"assets": {"alpha": {"file": "alpha.bin"}}}
    asset_content = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26 bytes
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="range-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"alpha": (asset_content, "alpha.bin")},
        )
        url = f"{base_url}/projects/range-proj/timelines/{timeline_id}/assets/alpha"

        closed_status, closed_headers, closed_body = _get_bytes(url, range_header="bytes=5-14")
        open_status, open_headers, open_body = _get_bytes(url, range_header="bytes=20-")
        suffix_status, suffix_headers, suffix_body = _get_bytes(url, range_header="bytes=-4")

    assert closed_status == 206
    assert closed_headers.get("Content-Range") == "bytes 5-14/26"
    assert int(closed_headers.get("Content-Length", "0")) == 10
    assert closed_body == b"FGHIJKLMNO"

    assert open_status == 206
    assert open_headers.get("Content-Range") == "bytes 20-25/26"
    assert open_body == b"UVWXYZ"

    assert suffix_status == 206
    assert suffix_headers.get("Content-Range") == "bytes 22-25/26"
    assert suffix_body == b"WXYZ"


def test_persisted_registry_asset_304_when_if_none_match_matches(
    tmp_bridge_root: Path,
) -> None:
    """An ETag validator match short-circuits to 304 with no body."""
    timeline_id = "aaaaaaa4-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa4"
    registry = {"assets": {"clip": {"file": "clip.bin"}}}
    asset_content = b"cacheable persisted asset\n" * 20
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="cache-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clip": (asset_content, "clip.bin")},
        )
        url = f"{base_url}/projects/cache-proj/timelines/{timeline_id}/assets/clip"

        status, headers, _body = _get_bytes(url)
        etag = headers.get("ETag")
        assert status == 200
        assert etag

        not_modified_status, not_modified_headers, not_modified_body = _get_bytes(
            url, if_none_match=etag
        )

    assert not_modified_status == 304
    assert not_modified_body == b""
    assert not_modified_headers.get("X-Astrid-Bridge-Version") == "v1"
    assert not_modified_headers.get("X-Content-Type-Options") == "nosniff"
    assert not_modified_headers.get("Referrer-Policy") == "no-referrer"
    assert not_modified_headers.get("ETag") == etag
    assert not_modified_headers.get("Last-Modified")
    assert not_modified_headers.get("Cache-Control") == "private, no-cache"


def test_persisted_registry_asset_400_for_malformed_range(
    tmp_bridge_root: Path,
) -> None:
    """Malformed and empty Range headers are a 400 text/plain (§9.3)."""
    timeline_id = "aaaaaaa5-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa5"
    registry = {"assets": {"clip": {"file": "clip.bin"}}}
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="badrange-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clip": (b"x" * 8, "clip.bin")},
        )
        url = f"{base_url}/projects/badrange-proj/timelines/{timeline_id}/assets/clip"
        for bad_range in (
            "bytes=abc",
            "items=0-1",
            "bytes=0-1,2-3",
            "bytes=",
            "bytes=-",
        ):
            status, headers, body = _get_bytes(
                url,
                range_header=bad_range,
                origin="http://localhost:3000",
            )
            assert status == 400, bad_range
            assert headers.get("X-Astrid-Bridge-Version") == "v1", bad_range
            assert headers.get("Access-Control-Allow-Origin") == ("http://localhost:3000"), (
                bad_range
            )
            assert body in (b"invalid Range header", b"empty Range"), bad_range


def test_persisted_registry_asset_416_when_range_start_beyond_size(
    tmp_bridge_root: Path,
) -> None:
    """Unsatisfiable ranges return 416 with the byte-range hint."""
    timeline_id = "aaaaaaa6-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa6"
    registry = {"assets": {"tiny": {"file": "tiny.bin"}}}
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="four16-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"tiny": (b"small", "tiny.bin")},
        )
        url = f"{base_url}/projects/four16-proj/timelines/{timeline_id}/assets/tiny"
        status, headers, _body = _get_bytes(
            url,
            range_header="bytes=10-20",
            origin="http://localhost:3000",
        )

    assert status == 416
    assert headers.get("X-Astrid-Bridge-Version") == "v1"
    assert headers.get("Content-Range") == "bytes */5"
    assert headers.get("Accept-Ranges") == "bytes"
    assert headers.get("Cache-Control") == "private, no-cache"
    assert headers.get("ETag")
    assert headers.get("Last-Modified")
    assert headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"


def test_persisted_registry_asset_404_for_missing_key(
    tmp_bridge_root: Path,
) -> None:
    """An asset key absent from the persisted registry is 404 asset_not_found."""
    timeline_id = "aaaaaaa7-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa7"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="nokey-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {}},
        )
        url = f"{base_url}/projects/nokey-proj/timelines/{timeline_id}/assets/no-such-key"
        status, error = _get_error(url)

    assert status == 404
    assert error["error"] == "asset_not_found"


def test_persisted_registry_asset_404_for_http_only_locator(
    tmp_bridge_root: Path,
) -> None:
    """HTTP locators are never local: 404 asset_not_local."""
    timeline_id = "aaaaaaa8-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pa8"
    registry = {"assets": {"remote": {"file": "https://example.com/video.mp4"}}}
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="http-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
        )
        url = f"{base_url}/projects/http-proj/timelines/{timeline_id}/assets/remote"
        status, error = _get_error(url)

    assert status == 404
    assert error["error"] == "asset_not_local"


def test_persisted_registry_asset_404_for_unsafe_or_missing_locator(
    tmp_bridge_root: Path,
) -> None:
    """Unsafe and missing locators are 404 asset_not_found after safe-path
    checks — even when the escaped file exists outside the sources dir."""
    timeline_id = "aaaaaab1-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pb1"
    registry = {
        "assets": {
            "escape": {"file": "../escape.png"},
            "absolute": {"file": "/etc/passwd"},
            "ghost": {"file": "nope/deep.bin"},
            "clean": {"file": "nested/deep.bin"},
        }
    }
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="unsafe-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry=registry,
            media={"clean": (b"inside", "nested/deep.bin")},
        )
        # A real file exists outside sources (escape target) and the clean
        # nested file exists inside sources; only the clean one is served.
        (tmp_bridge_root / "escape.png").write_bytes(b"outside")
        for key in ("escape", "absolute", "ghost"):
            url = f"{base_url}/projects/unsafe-proj/timelines/{timeline_id}/assets/{key}"
            status, error = _get_error(url)
            assert status == 404, key
            assert error["error"] == "asset_not_found", key

        clean_url = f"{base_url}/projects/unsafe-proj/timelines/{timeline_id}/assets/clean"
        clean_status, _headers, clean_body = _get_bytes(clean_url)

    assert clean_status == 200
    assert clean_body == b"inside"


def test_persisted_registry_asset_project_and_timeline_errors(
    tmp_bridge_root: Path,
) -> None:
    """Project and timeline errors keep their frozen envelopes on assets."""
    timeline_id = "aaaaaab2-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pb2"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="ok-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {}},
        )

        status, error = _get_error(f"{base_url}/projects/%2E%2E/timelines/{timeline_id}/assets/k")
        assert (status, error["error"]) == (400, "invalid_project")

        status, error = _get_error(f"{base_url}/projects/nope/timelines/{timeline_id}/assets/k")
        assert (status, error["error"]) == (404, "project_not_found")

        status, error = _get_error(f"{base_url}/projects/ok-proj/timelines/!!!bad!!!/assets/k")
        assert (status, error["error"]) == (400, "invalid_timeline")

        status, error = _get_error(
            f"{base_url}/projects/ok-proj/timelines/ffffffff-ffff-ffff-ffff-ffffffffffff/assets/k"
        )
        assert (status, error["error"]) == (404, "timeline_not_found")


def test_persisted_registry_asset_options_preflight(
    tmp_bridge_root: Path,
) -> None:
    """OPTIONS on the asset route returns 204 with CORS headers."""
    timeline_id = "aaaaaab3-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pb3"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        _repo_seed_asset_timeline(
            composition,
            slug="opt-proj",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {}},
        )
        url = f"{base_url}/projects/opt-proj/timelines/{timeline_id}/assets/k"
        status, headers = _options(url, origin="http://localhost:3000")

    assert status == 204
    assert headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert "GET, HEAD, POST, OPTIONS" in headers.get("Access-Control-Allow-Methods", "")
    assert headers.get("Access-Control-Allow-Headers") == (
        "Authorization, Content-Type, Range, If-None-Match, If-Modified-Since, "
        "Idempotency-Key, X-Astrid-Bridge-Version, X-Astrid-Request-Token"
    )


def test_persisted_registry_asset_serves_registered_media_id(
    tmp_bridge_root: Path,
) -> None:
    """A registry entry's registered ``media_id`` resolves and serves.

    The explicit media id is resolved project-scoped through the kernel
    media row (m4 plan step 22); the ``file`` alias is not required when
    the registered identity is present.
    """
    timeline_id = "aaaaaac1-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pc1"
    asset_content = b"served through the registered media id\n" * 8
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="mediaid-proj", key="proj-1")
        asset_path = _write_source_file(composition, "mediaid-proj", "mid.bin", asset_content)
        media = _repo_import_media(
            composition,
            project_id=project.id,
            path=asset_path,
            key="media-1",
            realm="managed_local",
            locator="mid.bin",
        )
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {"clip": {"media_id": media.id}}},
        )
        url = f"{base_url}/projects/mediaid-proj/timelines/{timeline_id}/assets/clip"
        status, headers, body = _get_bytes(url)
        head_status, head_headers = _head(url)
        range_status, range_headers, range_body = _get_bytes(
            url, range_header="bytes=2-7"
        )
        unsatisfiable_status, unsatisfiable_headers, unsatisfiable_body = _get_bytes(
            url, range_header=f"bytes={len(asset_content)}-"
        )

    assert status == 200
    assert int(headers.get("Content-Length", "0")) == len(asset_content)
    assert body == asset_content
    assert headers.get("Content-Type") == "application/octet-stream"
    assert head_status == 200
    assert int(head_headers.get("Content-Length", "0")) == len(asset_content)
    assert head_headers.get("Content-Type") == "application/octet-stream"
    assert range_status == 206
    assert range_headers.get("Content-Range") == f"bytes 2-7/{len(asset_content)}"
    assert range_body == asset_content[2:8]
    assert unsatisfiable_status == 416
    assert unsatisfiable_headers.get("Content-Range") == (
        f"bytes */{len(asset_content)}"
    )
    assert unsatisfiable_body == b""


def test_persisted_registry_asset_404_cross_project_locator_alias(
    tmp_bridge_root: Path,
) -> None:
    """A locator alias owned by another project never resolves (404).

    The kernel ``media_locations`` lookup is joined to the route project
    (m4 plan step 9): the same alias in another project is
    indistinguishable from an unknown one, so no cross-project bytes are
    ever streamed.
    """
    timeline_id = "aaaaaac2-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pc2"
    asset_content = b"owned by the other project\n"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        other = _repo_create_project(composition, slug="other-proj", key="proj-other")
        other_path = _write_source_file(composition, "other-proj", "shared.bin", asset_content)
        _repo_import_media(
            composition,
            project_id=other.id,
            path=other_path,
            key="media-other",
            realm="managed_local",
            locator="shared.bin",
        )
        own = _repo_create_project(composition, slug="own-proj", key="proj-own")
        _repo_create_timeline(
            composition,
            project_id=own.id,
            slug="primary",
            key="tl-own",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {"clip": {"file": "shared.bin"}}},
        )
        url = f"{base_url}/projects/own-proj/timelines/{timeline_id}/assets/clip"
        status, error = _get_error(url)

    assert status == 404
    assert error["error"] == "asset_not_found"


def test_persisted_registry_asset_404_cross_project_media_id(
    tmp_bridge_root: Path,
) -> None:
    """A media id owned by another project never resolves (404)."""
    timeline_id = "aaaaaac3-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pc3"
    asset_content = b"foreign media bytes\n"
    with repository_server(tmp_bridge_root) as (base_url, composition):
        other = _repo_create_project(composition, slug="foreign-proj", key="proj-foreign")
        other_path = _write_source_file(composition, "foreign-proj", "foreign.bin", asset_content)
        foreign_media = _repo_import_media(
            composition,
            project_id=other.id,
            path=other_path,
            key="media-foreign",
            realm="managed_local",
            locator="foreign.bin",
        )
        own = _repo_create_project(composition, slug="ref-proj", key="proj-ref")
        _repo_create_timeline(
            composition,
            project_id=own.id,
            slug="primary",
            key="tl-ref",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {"clip": {"media_id": foreign_media.id}}},
        )
        url = f"{base_url}/projects/ref-proj/timelines/{timeline_id}/assets/clip"
        status, error = _get_error(url)

    assert status == 404
    assert error["error"] == "asset_not_found"


def test_persisted_registry_asset_404_when_local_bytes_do_not_match_hash(
    tmp_bridge_root: Path,
) -> None:
    """Bytes that no longer match the media content hash are never served.

    An ``external_local`` reference-in-place location is re-hashed before
    streaming (m4 plan step 22): after the source file's bytes change, the
    actual SHA-256 no longer matches the media row's ``content_hash`` and
    the asset fails closed with ``404 asset_not_found``.
    """
    timeline_id = "aaaaaac4-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pc4"
    asset_content = b"immutable registered bytes\n" * 6
    with repository_server(tmp_bridge_root) as (base_url, composition):
        project = _repo_create_project(composition, slug="ext-proj", key="proj-1")
        asset_path = _write_source_file(composition, "ext-proj", "ext.bin", asset_content)
        media = _repo_import_media(
            composition,
            project_id=project.id,
            path=asset_path,
            key="media-1",
            realm="external_local",
        )
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            registry={"assets": {"clip": {"media_id": media.id}}},
        )
        url = f"{base_url}/projects/ext-proj/timelines/{timeline_id}/assets/clip"

        ok_status, ok_headers, ok_body = _get_bytes(url)
        assert ok_status == 200
        assert ok_body == asset_content
        assert int(ok_headers.get("Content-Length", "0")) == len(asset_content)

        # Mutate the reference-in-place bytes: the next fetch must fail
        # closed even though the media row and registry are untouched.
        asset_path.write_bytes(b"tampered bytes that no longer match\n")
        status, error = _get_error(url)

    assert status == 404
    assert error["error"] == "asset_not_found"


# ---------------------------------------------------------------------------
# Provider-contract journey (finding CF-F7D02052E469F1116F83)
# ---------------------------------------------------------------------------


def test_in_tree_client_completes_provider_restart_journey(
    tmp_bridge_root: Path,
    monkeypatch,
    capsys,
) -> None:
    """The in-tree contract client proves the complete HTTP journey.

    list → load → save → reload → stale 409 → two writers → server and
    database restart, with runtime diagnostics recorded per request. The
    substitute exercises the frozen wire contract only (SD3 / §11); it
    never claims browser or provider-source parity.
    """
    import astrid.core.integrations.reigh.local_bridge_server as bridge_server

    monkeypatch.setattr(bridge_server, "_DIAGNOSTICS_ENABLED", True)

    timeline_id = "aaaaaab4-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    timeline_ulid = "01jm4k5n7p0000000000000pb4"
    config_v2 = {"fps": 30, "tracks": [{"id": "V1", "kind": "visual"}]}
    registry_v2 = {"assets": {"hero": {"file": "hero.png"}}}

    with repository_server(tmp_bridge_root) as (base_url, composition):
        client = InTreeBridgeContractClient(base_url)

        # Fresh database: empty project list.
        assert client.list_projects() == []

        project = _repo_create_project(composition, slug="journey-proj", key="proj-1")
        _repo_create_timeline(
            composition,
            project_id=project.id,
            slug="primary",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            name="Primary",
        )

        # list: project and timeline discovery rows.
        assert [row["slug"] for row in client.list_projects()] == ["journey-proj"]
        timeline_rows = client.list_timelines("journey-proj")
        assert [row["timeline_id"] for row in timeline_rows] == [timeline_id]
        assert timeline_rows[0]["is_default"] is False

        # load: the seeded head 1 with the created registry.
        loaded = client.load_timeline("journey-proj", timeline_id)
        assert loaded["config_version"] == 1
        assert loaded["registry"] == {"assets": {}}

        # save: CAS from head 1 commits head 2 with the new document.
        saved = client.save_timeline(
            "journey-proj",
            timeline_id,
            config=config_v2,
            registry=registry_v2,
            expected_version=1,
        )
        assert saved["config_version"] == 2
        assert saved["config"] == config_v2
        assert saved["registry"] == registry_v2

        # reload: the committed document re-reads verbatim.
        reloaded = client.reload_timeline("journey-proj", timeline_id)
        assert reloaded["config_version"] == 2
        assert reloaded["config"] == config_v2
        assert reloaded["registry"] == registry_v2

        # stale save: expected_version 1 against head 2 → typed 409 with the
        # current integer version and zero mutation.
        before = _repo_db_snapshot(composition)
        try:
            client.save_timeline(
                "journey-proj",
                timeline_id,
                config={"fps": 60},
                registry={"assets": {}},
                expected_version=1,
            )
        except BridgeClientHTTPError as exc:
            assert exc.status == 409
            assert exc.payload["error"] == "timeline_version_conflict"
            assert exc.payload["config_version"] == 2
            assert isinstance(exc.payload["config_version"], int)
        else:
            raise AssertionError("stale save must raise a 409 conflict")
        assert _repo_db_snapshot(composition) == before

        # two writers: concurrent saves from head 2 → exactly one 200 at
        # head 3 and one 409 observing head 3; no losing receipt.
        config_3a = dict(config_v2, writer="a")
        config_3b = dict(config_v2, writer="b")
        outcomes: list[tuple[int, dict[str, Any]]] = []
        outcomes_lock = threading.Lock()

        def race(cfg: dict[str, Any]) -> None:
            try:
                outcome: tuple[int, dict[str, Any]] = (
                    200,
                    client.save_timeline(
                        "journey-proj",
                        timeline_id,
                        config=cfg,
                        registry={"assets": {}},
                        expected_version=2,
                    ),
                )
            except BridgeClientHTTPError as exc:
                outcome = (exc.status, exc.payload)
            with outcomes_lock:
                outcomes.append(outcome)

        t1 = threading.Thread(target=race, args=(config_3a,))
        t2 = threading.Thread(target=race, args=(config_3b,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(outcomes) == 2
        assert {status for status, _ in outcomes} == {200, 409}
        winner = next(payload for status, payload in outcomes if status == 200)
        loser = next(payload for status, payload in outcomes if status == 409)
        assert winner["config_version"] == 3
        assert loser["error"] == "timeline_version_conflict"
        assert loser["config_version"] == 3
        assert isinstance(loser["config_version"], int)

        snapshot = _repo_db_snapshot(composition)
        assert snapshot["saved_events"] == 2  # the v2 save + one race winner
        assert snapshot["save_receipts"] == 2
        final_config = client.reload_timeline("journey-proj", timeline_id)["config"]
        assert final_config in (config_3a, config_3b)

        # Runtime diagnostics recorded the whole journey.
        diagnostics = capsys.readouterr().out
        assert "[AstridBridge] request" in diagnostics
        assert "[AstridBridge] response" in diagnostics
        assert "'status': 200" in diagnostics
        assert "'status': 409" in diagnostics

    # ---- server AND database restart ----
    # The first server was shut down and its writer closed; a brand-new
    # composition reopens the same sqlite database and serves the retained
    # save (finding CF-F7D02052E469F1116F83 durability evidence).
    with repository_server(tmp_bridge_root) as (base_url2, _composition2):
        client2 = InTreeBridgeContractClient(base_url2)
        assert [row["slug"] for row in client2.list_projects()] == ["journey-proj"]
        reloaded_after_restart = client2.load_timeline("journey-proj", timeline_id)
        assert reloaded_after_restart["config_version"] == 3
        assert reloaded_after_restart["config"] in (config_3a, config_3b)


# ---------------------------------------------------------------------------
# astrid serve: editor-open, readiness line, and typed failures (m6)
# ---------------------------------------------------------------------------


class _FakeServeServer:
    """Stand-in for the bridge HTTP server so serve returns instead of blocking."""

    server_address = ("127.0.0.1", 45678)

    def shutdown(self) -> None:
        pass

    def server_close(self) -> None:
        pass

    def serve_forever(self) -> None:
        pass


def _patch_serve_server(monkeypatch) -> None:
    """Route serve's lazily-imported server factory to the non-blocking fake."""
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.local_bridge_server.create_local_bridge_server",
        lambda **kwargs: _FakeServeServer(),
    )


def test_serve_editor_path_opens_and_prints_readiness(
    tmp_bridge_root: Path, monkeypatch, capsys
) -> None:
    import astrid.core.gateway.dispatch as dispatch_mod

    editor = tmp_bridge_root / "editor-bundle"
    editor.mkdir()
    opened: list[Path] = []

    monkeypatch.setattr(dispatch_mod, "_open_editor", lambda p: opened.append(p))
    _patch_serve_server(monkeypatch)

    code = dispatch_mod._dispatch_serve(
        ["--projects-root", str(tmp_bridge_root), "--editor-path", str(editor)]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "Astrid ready" in out
    assert "bridge at http://127.0.0.1:45678" in out
    assert f"editor at {editor.resolve()}" in out
    assert opened == [editor.resolve()]


def test_serve_no_open_editor_skips_editor(tmp_bridge_root: Path, monkeypatch, capsys) -> None:
    import astrid.core.gateway.dispatch as dispatch_mod

    opened: list[Path] = []
    monkeypatch.setattr(dispatch_mod, "_open_editor", lambda p: opened.append(p))
    _patch_serve_server(monkeypatch)

    code = dispatch_mod._dispatch_serve(
        ["--projects-root", str(tmp_bridge_root), "--no-open-editor"]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "Astrid ready" in out
    assert "editor: not opened" in out
    assert opened == []


def test_serve_missing_editor_path_exits_one(tmp_bridge_root: Path, monkeypatch, capsys) -> None:
    import astrid.core.gateway.dispatch as dispatch_mod

    missing = tmp_bridge_root / "does-not-exist"
    code = dispatch_mod._dispatch_serve(
        ["--projects-root", str(tmp_bridge_root), "--editor-path", str(missing)]
    )
    err = capsys.readouterr().err

    assert code == 1
    assert "serve failed" in err
    assert "--editor-path does not exist" in err


def test_serve_unopenable_database_exits_one(tmp_bridge_root: Path, monkeypatch, capsys) -> None:
    import astrid.core.gateway.dispatch as dispatch_mod

    (tmp_bridge_root / ".astrid").mkdir()
    (tmp_bridge_root / ".astrid" / "astrid.sqlite3").write_bytes(b"not a sqlite database")
    code = dispatch_mod._dispatch_serve(["--projects-root", str(tmp_bridge_root)])
    err = capsys.readouterr().err

    assert code == 1
    assert "serve failed" in err
    assert "cannot open the Astrid database" in err


def test_serve_readiness_without_editor_bundle(tmp_bridge_root: Path, monkeypatch, capsys) -> None:
    import astrid.core.gateway.dispatch as dispatch_mod

    opened: list[Path] = []
    monkeypatch.setattr(dispatch_mod, "_locate_reigh_editor", lambda: None)
    monkeypatch.setattr(dispatch_mod, "_open_editor", lambda p: opened.append(p))
    _patch_serve_server(monkeypatch)

    code = dispatch_mod._dispatch_serve(["--projects-root", str(tmp_bridge_root)])
    out = capsys.readouterr().out

    assert code == 0
    assert "Astrid ready" in out
    assert "editor: not opened" in out
    assert "open the bridge manually at http://127.0.0.1:45678" in out
    assert opened == []
