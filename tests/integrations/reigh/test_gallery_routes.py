"""Acceptance fixtures for the contracted gallery reads and the
managed-media content route (doc 27 §4.1): bounded paged gallery listing
with primary-variant summaries, full generation detail with document-native
placements, and verified managed bytes with Range/ETag/HEAD semantics.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)
from astrid.core.store.uow import UnitOfWork
from astrid.packs import compose_standard_bridge

TS = "2026-08-15T00:00:00.000000+00:00"


# ---------------------------------------------------------------------------
# Server fixture (mirrors the task-route serve root)
# ---------------------------------------------------------------------------


@contextmanager
def gallery_server(projects_root: Path) -> Generator[dict[str, Any], None, None]:
    """A fully composed serve root: timeline bridge + task bridge."""
    composition = compose_standard_bridge(projects_root)
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import ReighTaskBridge
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.packs.timeline.repository import TimelineRepository

    def _generation_repo_factory() -> object:
        from astrid.packs.shots.generation_repository import (
            GenerationRepository,
        )

        return GenerationRepository()

    task_bridge = ReighTaskBridge(
        writer=composition.writer,
        registry=composition.registry,
        projects_root=composition.projects_root,
        generation_repo_factory=_generation_repo_factory,
        timeline_repo_factory=lambda: TimelineRepository(
            events=EventAppendService(composition.registry),
            receipts=ReceiptService(),
            projects=ProjectRepository(events=None, receipts=None),
        ),
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
            "composition": composition,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.writer.close()


def _request(
    env: dict[str, Any],
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any, bytes]:
    """Raw request returning ``(status, response_headers, body)``."""
    req = Request(env["base_url"] + path, method=method)
    for name, value in (headers or {}).items():
        req.add_header(name, value)
    try:
        with urlopen(req) as response:  # noqa: S310 - localhost test only
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def _get_json(env: dict[str, Any], path: str) -> tuple[int, dict[str, Any]]:
    status, _, raw = _request(env, "GET", path)
    return status, json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


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


def _seed_media(composition, project_id: str, payload: bytes) -> str:
    """One kernel media row plus its installed managed-tree bytes."""
    from astrid.core.io.media_import import managed_media_path

    digest = hashlib.sha256(payload).hexdigest()
    path = managed_media_path(composition.projects_root, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    media_id = generate_lowercase_ulid()

    def command(uow):
        uow.execute(
            "INSERT INTO media (id, project_id, media_kind, mime_type, "
            "byte_size, content_hash, metadata_json, created_at) "
            "VALUES (?, ?, 'image', 'image/png', ?, ?, '{}', ?)",
            (media_id, project_id, len(payload), digest, TS),
        )
        uow.execute(
            "INSERT INTO media_locations (id, media_id, realm, locator, "
            "verified_at, created_at) VALUES (?, ?, 'managed_local', ?, ?, ?)",
            (
                generate_lowercase_ulid(),
                media_id,
                str(path),
                TS,
                TS,
            ),
        )
        return media_id

    return UnitOfWork(composition.writer).run(command)


def _seed_generation(
    composition,
    project_id: str,
    *,
    created_at: str,
    starred: bool = False,
    variants: list[dict[str, Any]] | None = None,
    name: str | None = None,
) -> str:
    """One generation row plus variant rows (primary flag per variant)."""
    generation_id = generate_lowercase_ulid()

    def command(uow):
        uow.execute(
            "INSERT INTO generations (id, project_id, type, name, "
            "params_json, starred, created_at, updated_at) "
            "VALUES (?, ?, 'image', ?, '{}', ?, ?, ?)",
            (generation_id, project_id, name, int(starred), created_at, created_at),
        )
        for index, variant in enumerate(variants or []):
            uow.execute(
                "INSERT INTO generation_variants (id, generation_id, media_id,"
                " variant_type, params_json, is_primary, starred, created_at)"
                " VALUES (?, ?, ?, ?, '{}', ?, 0, ?)",
                (
                    generate_lowercase_ulid(),
                    generation_id,
                    variant["media_id"],
                    variant.get("variant_type"),
                    int(variant.get("is_primary", False)),
                    variant["created_at"],
                ),
            )
        return generation_id

    return UnitOfWork(composition.writer).run(command)


def _seed_timeline_document(
    composition, project_id: str, document: dict[str, Any]
) -> str:
    """One timeline row carrying a document with placement nodes."""
    stream_id = generate_lowercase_ulid()
    timeline_id = generate_lowercase_ulid()

    def command(uow):
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, "
            "aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, 'timeline', ?, 0, ?)",
            (stream_id, project_id, timeline_id, TS),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, "
            "document_json, asset_registry_json, created_at, updated_at) "
            "VALUES (?, ?, ?, 'main', ?, '{}', ?, ?)",
            (
                timeline_id,
                project_id,
                stream_id,
                json.dumps(document),
                TS,
                TS,
            ),
        )
        return timeline_id

    return UnitOfWork(composition.writer).run(command)


@pytest.fixture()
def env(tmp_path: Path) -> Generator[dict[str, Any], None, None]:
    with gallery_server(tmp_path) as handle:
        yield handle

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


def test_gallery_list_order_primary_summary_and_count(env) -> None:
    composition = env["composition"]
    project_id = _create_project(composition, "gallery-proj")
    primary_payload = b"primary-bytes"
    other_payload = b"other-bytes"
    primary_media = _seed_media(composition, project_id, primary_payload)
    other_media = _seed_media(composition, project_id, other_payload)
    old_id = _seed_generation(
        composition,
        project_id,
        created_at="2026-01-01T00:00:00+00:00",
        name="old",
        variants=[
            {
                "media_id": other_media,
                "variant_type": "upscale",
                "is_primary": True,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "media_id": primary_media,
                "variant_type": "original",
                "created_at": "2026-01-02T00:00:00+00:00",
            },
        ],
    )
    new_id = _seed_generation(
        composition,
        project_id,
        created_at="2026-02-01T00:00:00+00:00",
        name="new",
        variants=[
            {
                "media_id": primary_media,
                "variant_type": "original",
                "is_primary": True,
                "created_at": "2026-02-01T00:00:00+00:00",
            }
        ],
    )

    status, body = _get_json(env, "/projects/gallery-proj/generations")
    assert status == 200, body
    items = body["generations"]
    assert [item["generation_id"] for item in items] == [new_id, old_id]
    newest, oldest = items
    assert newest["name"] == "new"
    assert newest["type"] == "image"
    assert newest["starred"] is False
    assert newest["variant_count"] == 1
    assert newest["primary"] == {
        "media_id": primary_media,
        "variant_type": "original",
    }
    assert oldest["variant_count"] == 2
    assert oldest["primary"]["variant_type"] == "upscale"
    assert body["next_cursor"] is None


def test_gallery_list_paging_with_opaque_cursor(env) -> None:
    composition = env["composition"]
    project_id = _create_project(composition, "page-proj")
    _seed_media(composition, project_id, b"shared")
    ids = [
        _seed_generation(
            composition,
            project_id,
            created_at=f"2026-03-0{index}T00:00:00+00:00",
        )
        for index in range(1, 6)
    ]

    status, first = _get_json(
        env, "/projects/page-proj/generations?limit=2"
    )
    assert status == 200
    assert [item["generation_id"] for item in first["generations"]] == ids[
        4:2:-1
    ]
    assert first["next_cursor"]

    status, second = _get_json(
        env,
        "/projects/page-proj/generations?limit=2&cursor="
        + first["next_cursor"],
    )
    assert status == 200
    assert [
        item["generation_id"] for item in second["generations"]
    ] == ids[2:0:-1]
    assert second["next_cursor"]

    status, third = _get_json(
        env,
        "/projects/page-proj/generations?limit=2&cursor="
        + second["next_cursor"],
    )
    assert status == 200
    assert [item["generation_id"] for item in third["generations"]] == [ids[0]]
    assert third["next_cursor"] is None

    # A tampered cursor is a typed 400, never a 500.
    status, bad = _get_json(
        env, "/projects/page-proj/generations?cursor=not-a-cursor"
    )
    assert status == 400
    assert bad["error"] == "invalid_body"

    # The limit is hard-bounded at 200.
    status, clamped = _get_json(
        env, "/projects/page-proj/generations?limit=100000"
    )
    assert status == 200, clamped


def test_gallery_list_starred_filter_and_unknown_project(env) -> None:
    composition = env["composition"]
    project_id = _create_project(composition, "star-proj")
    media = _seed_media(composition, project_id, b"starred")
    starred_id = _seed_generation(
        composition,
        project_id,
        created_at="2026-04-01T00:00:00+00:00",
        starred=True,
        variants=[
            {
                "media_id": media,
                "is_primary": True,
                "created_at": "2026-04-01T00:00:00+00:00",
            }
        ],
    )
    _seed_generation(
        composition, project_id, created_at="2026-04-02T00:00:00+00:00"
    )

    status, body = _get_json(
        env, "/projects/star-proj/generations?starred=true"
    )
    assert status == 200
    assert [item["generation_id"] for item in body["generations"]] == [
        starred_id
    ]

    status, body = _get_json(
        env, "/projects/star-proj/generations?starred=false"
    )
    assert status == 200
    assert len(body["generations"]) == 2

    status, bad = _get_json(
        env, "/projects/star-proj/generations?starred=yes"
    )
    assert status == 400
    assert bad["error"] == "invalid_body"

    status, missing = _get_json(env, "/projects/nope-proj/generations")
    assert status == 404
    assert missing["error"] == "project_not_found"

    status, invalid = _get_json(env, "/projects/Nope!/generations")
    assert status == 400
    assert invalid["error"] == "invalid_project"


# ---------------------------------------------------------------------------
# Generation detail
# ---------------------------------------------------------------------------


def test_generation_detail_variants_items_and_misses(env) -> None:
    composition = env["composition"]
    project_id = _create_project(composition, "detail-proj")
    media_a = _seed_media(composition, project_id, b"aaa")
    media_b = _seed_media(composition, project_id, b"bbb")
    generation_id = _seed_generation(
        composition,
        project_id,
        created_at="2026-05-01T00:00:00+00:00",
        name="detail",
        variants=[
            {
                "media_id": media_b,
                "variant_type": "upscale",
                "created_at": "2026-05-02T00:00:00+00:00",
            },
            {
                "media_id": media_a,
                "variant_type": "original",
                "is_primary": True,
                "created_at": "2026-05-01T00:00:00+00:00",
            },
        ],
    )
    _seed_timeline_document(
        composition,
        project_id,
        {
            "shots": [
                {
                    "shot_id": "shot-9",
                    "items": [
                        {
                            "generation_id": generation_id,
                            "shot_id": "shot-9",
                            "timeline_frame": 96,
                        },
                        {"generation_id": "01OTHERGEN"},
                    ],
                }
            ]
        },
    )

    status, body = _get_json(
        env, f"/projects/detail-proj/generations/{generation_id}"
    )
    assert status == 200, body
    detail = body["generation"]
    assert detail["generation_id"] == generation_id
    assert [v["media_id"] for v in detail["variants"]] == [media_b, media_a]
    assert detail["variants"][1]["is_primary"] is True
    assert detail["items"] == [{"shot_id": "shot-9", "timeline_frame": 96}]

    status, missing = _get_json(
        env, "/projects/detail-proj/generations/01UNKNOWNGENER"
    )
    assert status == 404
    assert missing["error"] == "generation_not_found"


def test_generation_detail_is_project_scoped(env) -> None:
    composition = env["composition"]
    project_a = _create_project(composition, "scope-a")
    _create_project(composition, "scope-b")
    media = _seed_media(composition, project_a, b"scoped")
    foreign_id = _seed_generation(
        composition,
        project_a,
        created_at="2026-06-01T00:00:00+00:00",
        variants=[
            {
                "media_id": media,
                "is_primary": True,
                "created_at": "2026-06-01T00:00:00+00:00",
            }
        ],
    )
    status, body = _get_json(
        env, f"/projects/scope-b/generations/{foreign_id}"
    )
    assert status == 404
    assert body["error"] == "generation_not_found"


# ---------------------------------------------------------------------------
# Managed-media content
# ---------------------------------------------------------------------------


def test_media_content_full_range_etag_head(env) -> None:
    composition = env["composition"]
    project_id = _create_project(composition, "media-proj")
    payload = b"0123456789abcdef"
    media_id = _seed_media(composition, project_id, payload)

    status, headers, body = _request(
        env, "GET", f"/projects/media-proj/media/{media_id}/content"
    )
    assert status == 200
    assert body == payload
    assert headers["Content-Type"] == "image/png"
    etag = headers["ETag"]
    assert headers["Accept-Ranges"] == "bytes"
    assert "Last-Modified" in headers

    status, headers_206, partial = _request(
        env,
        "GET",
        f"/projects/media-proj/media/{media_id}/content",
        headers={"Range": "bytes=4-9"},
    )
    assert status == 206
    assert partial == payload[4:10]
    assert headers_206["Content-Range"] == f"bytes 4-9/{len(payload)}"
    assert headers_206["Content-Length"] == "6"

    status, _, not_modified = _request(
        env,
        "GET",
        f"/projects/media-proj/media/{media_id}/content",
        headers={"If-None-Match": etag},
    )
    assert status == 304
    assert not_modified == b""

    status, suffix_headers, suffix = _request(
        env,
        "GET",
        f"/projects/media-proj/media/{media_id}/content",
        headers={"Range": "bytes=-4"},
    )
    assert status == 206
    assert suffix == payload[-4:]

    status, _, malformed = _request(
        env,
        "GET",
        f"/projects/media-proj/media/{media_id}/content",
        headers={"Range": "bytes=4-2"},
    )
    assert status == 416
    assert malformed == b""

    status, head_headers, head_body = _request(
        env, "HEAD", f"/projects/media-proj/media/{media_id}/content"
    )
    assert status == 200
    assert head_body == b""
    assert head_headers["Content-Length"] == str(len(payload))
    assert head_headers["ETag"] == etag


def test_media_content_unknown_foreign_and_missing_bytes(env) -> None:
    composition = env["composition"]
    project_a = _create_project(composition, "media-a")
    _create_project(composition, "media-b")
    media_id = _seed_media(composition, project_a, b"served-bytes")

    status, _, _ = _request(
        env, "GET", "/projects/media-a/media/01UNKNOWNMEDIA/content"
    )
    assert status == 404
    status, _, body = _request(
        env, "GET", f"/projects/media-b/media/{media_id}/content"
    )
    assert status == 404
    assert json.loads(body)["error"] == "media_not_found"

    # Known row whose managed bytes were lost from the tree.
    from astrid.core.io.media_import import managed_media_path

    managed_media_path(
        composition.projects_root,
        hashlib.sha256(b"served-bytes").hexdigest(),
    ).unlink()
    status, _, body = _request(
        env, "GET", f"/projects/media-a/media/{media_id}/content"
    )
    assert status == 404
    assert json.loads(body)["error"] == "media_bytes_missing"

    status, _, _ = _request(env, "GET", "/projects/media-a/media//content")
    assert status == 404
