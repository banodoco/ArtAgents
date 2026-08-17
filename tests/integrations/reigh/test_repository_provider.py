"""Adapter-level tests for the repository-backed bridge (m1 plan step 18).

These tests sit below the HTTP routing layer: they exercise the frozen
bridge DTOs and typed errors, the database path derivation, the timeline
bridge adapter over the project/timeline repositories, and the
persisted-registry-only asset classification with safe local-path rules.
They also prove the adapter never falls back to the legacy
file/JSONL/FSA/Supabase authorities: no ``LocalFsBackend``, sidecar
projection, or Supabase call exists anywhere in the adapter surface.

The provider-contract HTTP journey (list/load/save/reload over a real
server) is added by the later provider-journey task; this module is the
adapter-level baseline that journey builds on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService
from astrid.core.integrations.reigh.bridge_service import (
    ASTROID_DATABASE_NAME,
    ASTROID_DIR_NAME,
    RECEIPT_SECRECY_FIELDS,
    BridgeBodyError,
    BridgeConfigError,
    BridgeError,
    BridgeExpectedVersionError,
    BridgeInvalidProjectError,
    BridgeInvalidTimelineError,
    BridgeProjectNotFoundError,
    BridgeRegistryError,
    BridgeSchemaIncompatibleError,
    BridgeTimelineNotFoundError,
    BridgeVersionConflictError,
    HealthStatus,
    ProjectRow,
    TimelineLoad,
    TimelineRow,
    TimelineSaveRequest,
    derive_database_path,
)
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import register_standard_schema_packs
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from astrid.packs.timeline.repository import TimelineRepository

TS = "2026-08-15T00:00:00.000000+00:00"
CONFIG = {"fps": 24, "tracks": [{"id": "V1", "kind": "visual"}]}
SAVED_CONFIG = {"fps": 30, "tracks": [{"id": "V1", "kind": "visual"}]}


def _build_registry():
    """Compose core + exactly timeline, shots, and references, then freeze."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


@pytest.fixture
def writer(tmp_path: Path):
    """A fresh standard-Astrid writer at ``<tmp>/astrid.sqlite3``."""
    w = DatabaseWriter(tmp_path / "astrid.sqlite3", _build_registry())
    try:
        yield w
    finally:
        w.close()


def _make_adapter(writer: DatabaseWriter) -> TimelineBridgeAdapter:
    """Build the standard timeline bridge adapter over one writer."""
    registry = _build_registry()
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )
    return TimelineBridgeAdapter(
        writer=writer, projects=projects, timelines=timelines
    )


@pytest.fixture
def adapter(writer: DatabaseWriter) -> TimelineBridgeAdapter:
    """The standard timeline bridge adapter over real repositories."""
    return _make_adapter(writer)


def _create_project(
    adapter: TimelineBridgeAdapter,
    writer: DatabaseWriter,
    *,
    slug: str,
    key: str,
):
    """Create one project through the real repository command."""
    return UnitOfWork(writer).run(
        lambda u: adapter._projects.create(
            u,
            slug=slug,
            name=slug,
            settings={},
            idempotency_key=key,
            created_at=TS,
        )
    )


def _create_timeline(
    adapter: TimelineBridgeAdapter,
    writer: DatabaseWriter,
    *,
    project_id: str,
    slug: str,
    key: str,
    timeline_id: str,
    timeline_ulid: str,
    registry: dict[str, Any] | None = None,
):
    """Create one timeline through the real repository command."""
    return UnitOfWork(writer).run(
        lambda u: adapter._timelines.create(
            u,
            project_id=project_id,
            slug=slug,
            name=slug.title(),
            config=dict(CONFIG),
            registry=dict(registry or {"assets": {}}),
            idempotency_key=key,
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            created_at=TS,
        )
    )


# ---------------------------------------------------------------------------
# DTO serialization and request parsing
# ---------------------------------------------------------------------------


def test_health_and_project_row_dtos_serialize_exact_fields() -> None:
    assert HealthStatus(ok=True, projects_root="/root").to_dict() == {
        "ok": True,
        "projects_root": "/root",
    }
    assert ProjectRow(slug="pilot", name="Pilot").to_dict() == {
        "slug": "pilot",
        "name": "Pilot",
    }


def test_timeline_dtos_serialize_exact_fields() -> None:
    row = TimelineRow(
        timeline_id="t1",
        timeline_ulid="ulid1",
        slug="main",
        name="Main",
        is_default=True,
    )
    assert row.to_dict() == {
        "timeline_id": "t1",
        "timeline_ulid": "ulid1",
        "slug": "main",
        "name": "Main",
        "is_default": True,
    }
    load = TimelineLoad(
        timeline_id="t1",
        timeline_ulid="ulid1",
        slug="main",
        name="Main",
        is_default=False,
        config={"fps": 24},
        registry={"assets": {"hero": {"file": "hero.png"}}},
        config_version=3,
    )
    assert load.to_dict() == {
        "timeline_id": "t1",
        "timeline_ulid": "ulid1",
        "slug": "main",
        "name": "Main",
        "is_default": False,
        "config": {"fps": 24},
        "registry": {"assets": {"hero": {"file": "hero.png"}}},
        "config_version": 3,
    }


@pytest.mark.parametrize(
    ("body", "error_type"),
    [
        (None, BridgeBodyError),
        ([], BridgeBodyError),
        ({"registry": {}, "expected_version": 1}, BridgeConfigError),
        ({"config": [], "registry": {}, "expected_version": 1},
         BridgeConfigError),
        ({"config": {}, "expected_version": 1}, BridgeRegistryError),
        ({"config": {}, "registry": [], "expected_version": 1},
         BridgeRegistryError),
        ({"config": {}, "registry": {}}, BridgeExpectedVersionError),
        ({"config": {}, "registry": {}, "expected_version": True},
         BridgeExpectedVersionError),
        ({"config": {}, "registry": {}, "expected_version": 1.5},
         BridgeExpectedVersionError),
    ],
)
def test_timeline_save_request_parse_route_level_validation(
    body: Any, error_type: type[BridgeError]
) -> None:
    """Parse rejects non-object bodies, config, registry, and versions."""
    with pytest.raises(error_type):
        TimelineSaveRequest.parse(body)


def test_timeline_save_request_parse_accepts_valid_body() -> None:
    request = TimelineSaveRequest.parse(
        {"config": {"fps": 24}, "registry": {"assets": {}},
         "expected_version": 1}
    )
    assert request.config == {"fps": 24}
    assert request.registry == {"assets": {}}
    assert request.expected_version == 1
    assert isinstance(request.expected_version, int)


# ---------------------------------------------------------------------------
# Typed bridge errors
# ---------------------------------------------------------------------------


def test_typed_bridge_error_envelope_and_status_codes() -> None:
    cases = [
        (BridgeBodyError("bad body"), 400, "invalid_body"),
        (BridgeConfigError("bad config"), 400, "invalid_config"),
        (BridgeRegistryError("bad registry"), 400, "invalid_registry"),
        (BridgeExpectedVersionError("bad version"), 400,
         "invalid_expected_version"),
        (BridgeInvalidProjectError("bad slug"), 400, "invalid_project"),
        (BridgeInvalidTimelineError("bad ref"), 400, "invalid_timeline"),
        (BridgeProjectNotFoundError("missing"), 404, "project_not_found"),
        (BridgeTimelineNotFoundError("missing"), 404, "timeline_not_found"),
    ]
    for error, status, code in cases:
        assert error.status_code == status
        assert error.code == code
        assert error.to_dict() == {"error": code, "detail": error.detail}


def test_version_conflict_error_carries_config_version() -> None:
    error = BridgeVersionConflictError(
        "stale", config_version=4
    )
    assert error.status_code == 409
    assert error.to_dict() == {
        "error": "timeline_version_conflict",
        "detail": "stale",
        "config_version": 4,
    }


def test_schema_incompatible_error_carries_issues() -> None:
    error = BridgeSchemaIncompatibleError("invalid")
    assert error.status_code == 422
    payload = error.to_dict()
    assert payload["error"] == "schema_incompatible"
    assert isinstance(payload["issues"], list) and payload["issues"]
    assert "message" in payload["issues"][0]


def test_database_path_derivation(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    path = derive_database_path(root)
    assert path == root / ASTROID_DIR_NAME / ASTROID_DATABASE_NAME
    assert path.parent.name == ".astrid"
    assert path.name == "astrid.sqlite3"


# ---------------------------------------------------------------------------
# Adapter reads over the repositories
# ---------------------------------------------------------------------------


def test_adapter_health_and_sorted_project_list(
    adapter, writer: DatabaseWriter
) -> None:
    _create_project(adapter, writer, slug="z-last", key="proj-z")
    _create_project(adapter, writer, slug="a-first", key="proj-a")

    health = adapter.health("/projects")
    assert health.to_dict() == {"ok": True, "projects_root": "/projects"}

    rows = adapter.list_projects()
    assert [row.to_dict() for row in rows] == [
        {"slug": "a-first", "name": "a-first"},
        {"slug": "z-last", "name": "z-last"},
    ]


def test_adapter_timeline_list_rows_sorted_by_slug(
    adapter, writer: DatabaseWriter
) -> None:
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    _create_timeline(
        adapter, writer, project_id=project.id, slug="zeta",
        key="tl-1", timeline_id="11111111-1111-1111-1111-111111111111",
        timeline_ulid="01jm4k5n7p0000000000000001",
        registry={"assets": {"hero": {"file": "hero.png"}}},
    )
    _create_timeline(
        adapter, writer, project_id=project.id, slug="alpha",
        key="tl-2", timeline_id="22222222-2222-2222-2222-222222222222",
        timeline_ulid="01jm4k5n7p0000000000000002",
        registry={"assets": {}},
    )
    rows = adapter.list_timelines(project.slug)
    assert [row.slug for row in rows] == ["alpha", "zeta"]
    assert rows[0].to_dict() == {
        "timeline_id": "22222222-2222-2222-2222-222222222222",
        "timeline_ulid": "01jm4k5n7p0000000000000002",
        "slug": "alpha",
        "name": "Alpha",
        "is_default": False,
    }


def test_adapter_load_by_all_three_address_forms(
    adapter, writer: DatabaseWriter
) -> None:
    timeline_id = "33333333-3333-3333-3333-333333333333"
    timeline_ulid = "01jm4k5n7p0000000000000003"
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    _create_timeline(
        adapter, writer, project_id=project.id, slug="main",
        key="tl-1", timeline_id=timeline_id, timeline_ulid=timeline_ulid,
        registry={"assets": {"hero": {"file": "hero.png"}}},
    )
    for ref in (timeline_id, timeline_ulid, "main"):
        load = adapter.load_timeline(project.slug, ref)
        assert load.timeline_id == timeline_id
        assert load.timeline_ulid == timeline_ulid
        assert load.slug == "main"
        assert load.registry == {"assets": {"hero": {"file": "hero.png"}}}
        assert isinstance(load.config_version, int)
        assert load.config_version >= 1


def test_adapter_typed_not_found_and_validation_errors(
    adapter, writer: DatabaseWriter
) -> None:
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    _create_timeline(
        adapter, writer, project_id=project.id, slug="main",
        key="tl-1", timeline_id="44444444-4444-4444-4444-444444444444",
        timeline_ulid="01jm4k5n7p0000000000000004",
    )
    with pytest.raises(BridgeProjectNotFoundError):
        adapter.load_timeline("no-such-project", "main")
    with pytest.raises(BridgeInvalidProjectError):
        adapter.load_timeline("..", "main")
    with pytest.raises(BridgeTimelineNotFoundError):
        adapter.load_timeline(
            project.slug, "55555555-5555-5555-5555-555555555555"
        )
    with pytest.raises(BridgeInvalidTimelineError):
        adapter.load_timeline(project.slug, "not a valid ref")


def test_adapter_save_commits_and_stale_cas_conflict(
    adapter, writer: DatabaseWriter
) -> None:
    timeline_id = "66666666-6666-6666-6666-666666666666"
    timeline_ulid = "01jm4k5n7p0000000000000006"
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    _create_timeline(
        adapter, writer, project_id=project.id, slug="main",
        key="tl-1", timeline_id=timeline_id, timeline_ulid=timeline_ulid,
    )
    saved = adapter.save_timeline(
        project.slug,
        timeline_id,
        TimelineSaveRequest.parse(
            {"config": SAVED_CONFIG, "registry": {"assets": {}},
             "expected_version": 1}
        ),
    )
    assert saved.timeline_id == timeline_id
    assert saved.config == SAVED_CONFIG
    assert saved.config_version == 2

    # A *changed* payload under the same stale expected head derives a
    # different idempotency key, so the CAS check must run and conflict.
    conflicting_config = {"fps": 60, "tracks": [{"id": "V1"}]}
    with pytest.raises(BridgeVersionConflictError) as excinfo:
        adapter.save_timeline(
            project.slug,
            timeline_id,
            TimelineSaveRequest.parse(
                {"config": conflicting_config, "registry": {"assets": {}},
                 "expected_version": 1}
            ),
        )
    assert excinfo.value.config_version == 2


# ---------------------------------------------------------------------------
# Receipt secrecy (contract section 7)
# ---------------------------------------------------------------------------


def test_receipt_secrecy_never_leaks_internal_fields(
    adapter, writer: DatabaseWriter
) -> None:
    timeline_id = "77777777-7777-7777-7777-777777777777"
    timeline_ulid = "01jm4k5n7p0000000000000007"
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    _create_timeline(
        adapter, writer, project_id=project.id, slug="main",
        key="tl-1", timeline_id=timeline_id, timeline_ulid=timeline_ulid,
    )
    saved = adapter.save_timeline(
        project.slug,
        timeline_id,
        TimelineSaveRequest.parse(
            {"config": SAVED_CONFIG, "registry": {"assets": {}},
             "expected_version": 1}
        ),
    )
    loaded = adapter.load_timeline(project.slug, "main")

    # A complete receipt really exists in the database...
    with writer.read_only_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM command_receipts"
        ).fetchone()[0]
    assert count >= 1

    # ...but every wire payload is free of internal receipt fields.
    for payload in (saved.to_dict(), loaded.to_dict()):
        assert RECEIPT_SECRECY_FIELDS.isdisjoint(payload.keys())


# ---------------------------------------------------------------------------
# Asset classification from the persisted registry only
# ---------------------------------------------------------------------------


def _classify_locator(locator: str) -> str:
    """Mirror the frozen safe-path rules (legacy bridge semantics).

    ``http``/``https`` locators are HTTP-only; every other locator must be a
    relative path that stays inside the project sources root — absolute
    paths and ``..`` traversal are unsafe, never local. A locator is a
    *path reference*, never media identity.
    """
    if locator.startswith("http://") or locator.startswith("https://"):
        return "http"
    candidate = Path(locator)
    if candidate.is_absolute():
        return "unsafe"
    if any(part == ".." for part in candidate.parts):
        return "unsafe"
    return "local"


def _classify_assets(load: TimelineLoad) -> dict[str, str]:
    """Classify every asset key present in the persisted registry."""
    assets = load.registry.get("assets", {})
    classified: dict[str, str] = {}
    for key, entry in assets.items():
        if not isinstance(entry, dict):
            classified[key] = "missing"
            continue
        locator = entry.get("file")
        if not isinstance(locator, str) or not locator.strip():
            classified[key] = "missing"
            continue
        classified[key] = _classify_locator(locator.strip())
    return classified


def test_asset_classification_from_persisted_registry_only(
    adapter, writer: DatabaseWriter, tmp_path: Path
) -> None:
    """Locators classify as local/http/missing from registry data alone.

    The registry is persisted through the real repository and surfaced
    verbatim by the adapter; no file needs to exist on disk and no
    filesystem scan runs — the classification is a pure function of the
    persisted locators.
    """
    timeline_id = "88888888-8888-8888-8888-888888888888"
    timeline_ulid = "01jm4k5n7p0000000000000008"
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    registry = {
        "assets": {
            "hero": {"file": "hero.png"},
            "remote": {"file": "https://example.com/video.mp4"},
            "deep": {"file": "nested/deep.bin"},
        }
    }
    _create_timeline(
        adapter, writer, project_id=project.id, slug="main",
        key="tl-1", timeline_id=timeline_id, timeline_ulid=timeline_ulid,
        registry=registry,
    )

    load = adapter.load_timeline(project.slug, timeline_id)
    assert load.registry == registry  # persisted data, verbatim

    classified = _classify_assets(load)
    assert classified == {
        "hero": "local",
        "remote": "http",
        "deep": "local",
    }
    # A key absent from the persisted registry is missing — the registry is
    # the single source of truth, not the filesystem.
    assert "absent-key" not in load.registry["assets"]
    # No project directory exists on disk at all: reads came from the
    # database, never from a sidecar or file authority.
    assert not (tmp_path / "proj").exists()


def test_safe_local_path_rules_reject_unsafe_locators(
    adapter, writer: DatabaseWriter
) -> None:
    """Absolute and traversing locators are never classified as local."""
    timeline_id = "99999999-9999-9999-9999-999999999999"
    timeline_ulid = "01jm4k5n7p0000000000000009"
    project = _create_project(adapter, writer, slug="proj", key="proj-1")
    registry = {
        "assets": {
            "escape": {"file": "../escape.png"},
            "absolute": {"file": "/etc/passwd"},
            "clean": {"file": "clips/a.mp4"},
        }
    }
    _create_timeline(
        adapter, writer, project_id=project.id, slug="main",
        key="tl-1", timeline_id=timeline_id, timeline_ulid=timeline_ulid,
        registry=registry,
    )
    load = adapter.load_timeline(project.slug, "main")
    classified = _classify_assets(load)
    assert classified["escape"] == "unsafe"
    assert classified["absolute"] == "unsafe"
    assert classified["clean"] == "local"


# ---------------------------------------------------------------------------
# Authority boundaries: no legacy file/JSONL/FSA/Supabase fallback
# ---------------------------------------------------------------------------


_FORBIDDEN_AUTHORITY_MARKERS = (
    "LocalFsBackend",
    "astrid.core.timeline.eventlog",
    "supabase",
    "data_provider",
    "sidecar",
    "astrid.core.integrations.reigh.local_bridge",
)


def test_adapter_modules_never_import_legacy_authorities() -> None:
    """The adapter + DTO modules contain no legacy authority import."""
    import astrid.core.integrations.reigh.bridge_service as bridge_service
    import astrid.packs.timeline.bridge as timeline_bridge

    sources = [
        Path(bridge_service.__file__).read_text(encoding="utf-8"),
        Path(timeline_bridge.__file__).read_text(encoding="utf-8"),
    ]
    for source in sources:
        for marker in _FORBIDDEN_AUTHORITY_MARKERS:
            assert marker not in source, marker


# ---------------------------------------------------------------------------
# Provider-journey durability at the adapter level (finding CF-F7D02052E469F1116F83)
# ---------------------------------------------------------------------------


def test_adapter_save_survives_writer_restart_with_stale_conflict(
    tmp_path: Path,
) -> None:
    """A committed save survives a full writer/database restart.

    The provider journey must retain the successful save across server and
    database restart; at the adapter level this means a brand-new writer
    reopens the same sqlite file and the committed document, registry, and
    numeric head are re-read verbatim, while a stale CAS against the
    reopened head raises the typed conflict with the current version and
    changes nothing.
    """
    timeline_id = "abababab-abab-abab-abab-ababababab01"
    timeline_ulid = "01jm4k5n7p0000000000000aa1"
    db_path = tmp_path / "astrid.sqlite3"

    writer1 = DatabaseWriter(db_path, _build_registry())
    try:
        adapter1 = _make_adapter(writer1)
        project = _create_project(
            adapter1, writer1, slug="proj", key="proj-1"
        )
        _create_timeline(
            adapter1,
            writer1,
            project_id=project.id,
            slug="main",
            key="tl-1",
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
        )
        saved = adapter1.save_timeline(
            project.slug,
            timeline_id,
            TimelineSaveRequest.parse(
                {"config": SAVED_CONFIG, "registry": {"assets": {}},
                 "expected_version": 1}
            ),
        )
        assert saved.config_version == 2
    finally:
        writer1.close()

    # A brand-new writer reopens the same database file: the committed
    # document, registry, and head survive the restart.
    writer2 = DatabaseWriter(db_path, _build_registry())
    try:
        adapter2 = _make_adapter(writer2)
        loaded = adapter2.load_timeline(project.slug, timeline_id)
        assert loaded.config_version == 2
        assert loaded.config == SAVED_CONFIG

        # Stale CAS against the reopened head → typed conflict with the
        # current integer version and zero mutation.
        with pytest.raises(BridgeVersionConflictError) as excinfo:
            adapter2.save_timeline(
                project.slug,
                timeline_id,
                TimelineSaveRequest.parse(
                    {"config": {"fps": 60}, "registry": {"assets": {}},
                     "expected_version": 1}
                ),
            )
        assert excinfo.value.config_version == 2

        reloaded = adapter2.load_timeline(project.slug, timeline_id)
        assert reloaded.config_version == 2
        assert reloaded.config == SAVED_CONFIG
    finally:
        writer2.close()
