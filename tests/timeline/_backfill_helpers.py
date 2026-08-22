"""Shared helpers for the S1 backfill test suites.

Builds a real kernel database (standard registry), a real project row, and
real LocalFs source timeline directories (append-only JSONL written through
``LocalFsBackend``, so hashes/chains/heads are canonical), then runs the
backfill orchestrator over the single writer — the same composition the
bridge and SDK use.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor
from astrid.packs import register_standard_schema_packs
from astrid.packs.timeline.backfill import load_local_fs_source
from astrid.packs.timeline.repository import TimelineRepository

TS = "2026-08-15T00:00:00.000000+00:00"


def build_registry():
    """Compose core + exactly timeline, shots, and references, then freeze."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def make_writer(database_path: Path) -> DatabaseWriter:
    """A fresh standard-Astrid writer at ``database_path``."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return DatabaseWriter(database_path, build_registry())


def make_project(
    writer: DatabaseWriter,
    *,
    slug: str = "proj",
    key: str = "proj-1",
) -> tuple[str, ProjectRepository]:
    """Create one project row through the real repository command."""
    registry = build_registry()
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    UnitOfWork(writer).run(
        lambda u: projects.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=key,
            created_at=TS,
        )
    )
    project_id = projects.resolve(writer, slug)
    return project_id, projects


def make_backfill_deps(writer: DatabaseWriter):
    """Build the services the backfill orchestrator needs over *writer*."""
    registry = build_registry()
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )
    return projects, receipts, timelines


MINIMAL_CONFIG = {"tracks": [], "clips": []}
"""A valid raw TimelineConfig container (required keys clips/tracks)."""


def source_events_spec() -> list[tuple[str, dict[str, Any], str]]:
    """A mixed synthetic event spec: config + registry + registered mutation
    kinds + one UNREGISTERED kind (raw-dict pass-through) + three actor
    types. ``timeline.created`` first = full lifecycle (bridge-servable)."""
    return [
        (
            "timeline.created",
            {
                "timeline_id": "PLACEHOLDER",
                "slug": "main",
                "name": "Main",
            },
            "human",
        ),
        (
            "timeline.config_replaced",
            {"config": MINIMAL_CONFIG},
            "human",
        ),
        (
            "timeline.asset_registry_replaced",
            {"registry": {"assets": {"hero": {"file": "hero.png"}}}},
            "agent",
        ),
        (
            "clip.added",
            {
                "clip_id": "c1",
                "kind": "visual",
                "track_id": "V1",
                "asset_id": "hero",
                "position": {"mode": "index", "index": 0},
            },
            "agent",
        ),
        (
            "track.added",
            {"track_id": "V1", "kind": "visual", "label": "Video"},
            "system",
        ),
        (
            "timeline.custom_note",
            {"note": "raw dict pass-through"},
            "system",
        ),
    ]


def make_source_timeline(
    root: Path,
    *,
    timeline_id: str | None = None,
    timeline_ulid: str | None = None,
    slug: str = "main",
    name: str = "Main",
    events_spec: list[tuple[str, dict[str, Any], str]] | None = None,
) -> tuple[Path, str, str]:
    """Build a real LocalFs source timeline dir under *root*.

    Returns ``(timeline_home, timeline_id, timeline_ulid)``. The directory
    is named by the timeline ULID and carries identity/head sidecars
    written through the backend itself (canonical hashes, chain, head).
    """
    timeline_id = timeline_id or str(uuid.uuid4())
    timeline_ulid = timeline_ulid or "01J00000000000000000000001"
    home = root / timeline_ulid
    home.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        home / "assembly.identity.json",
        {
            "backend": "local_fs",
            "created_at": "2026-08-01T00:00:00Z",
            "display": {
                "is_default": True,
                "name": name,
                "schema_version": 1,
                "slug": slug,
            },
            "provenance": "created",
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": timeline_ulid,
        },
    )
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
    spec = events_spec if events_spec is not None else source_events_spec()
    for kind, payload, actor_type in spec:
        if kind == "timeline.created":
            payload = dict(payload)
            payload["timeline_id"] = timeline_id
        backend.append_event(
            timeline_id,
            kind,
            payload,
            actor=TimelineActor(type=actor_type, id=f"actor:{actor_type}"),
        )
    return home, timeline_id, timeline_ulid


def project_root_with_timeline(
    tmp_path: Path,
    *,
    project_slug: str = "proj",
    timeline_id: str | None = None,
    timeline_ulid: str | None = None,
    slug: str = "main",
    name: str = "Main",
    events_spec: list[tuple[str, dict[str, Any], str]] | None = None,
) -> tuple[Path, Path, str, str]:
    """Build ``<tmp>/projects/<slug>/timelines/<ULID>`` + the source dir.

    Returns ``(projects_root, timeline_home, timeline_id, timeline_ulid)``.
    """
    projects_root = tmp_path / "projects"
    timelines_dir = projects_root / project_slug / "timelines"
    timelines_dir.mkdir(parents=True, exist_ok=True)
    home, timeline_id, timeline_ulid = make_source_timeline(
        timelines_dir,
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        slug=slug,
        name=name,
        events_spec=events_spec,
    )
    write_json_atomic(
        projects_root / project_slug / "project.json",
        {"name": project_slug},
    )
    return projects_root, home, timeline_id, timeline_ulid


def load_source(home: Path) -> Any:
    """Load one source through the production importer (read-only)."""
    return load_local_fs_source(home)


def kernel_event_rows(writer: DatabaseWriter, stream_id: str) -> list[dict[str, Any]]:
    """Return ordered kernel event rows for one stream (read-only)."""
    from astrid.core.repositories.events import EventRepository

    return [
        model.as_dict()
        for model in EventRepository(writer).list_events(
            stream_id=stream_id, limit=10_000
        )
    ]


def head_seq(writer: DatabaseWriter, stream_id: str) -> int:
    import sqlite3

    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        ).fetchone()
    return int(row["head_seq"]) if row is not None else 0


def marker_state(projects_root: Path) -> dict[str, Any]:
    from astrid.packs.timeline.backfill import read_backfill_state

    return read_backfill_state(projects_root)


def marker_json(projects_root: Path) -> dict[str, Any]:
    import json as _json

    path = (
        projects_root
        / ".astrid"
        / "backfill-state.json"
    )
    if not path.is_file():
        return {}
    return _json.loads(path.read_text(encoding="utf-8"))


def resolve_project_id(writer: DatabaseWriter, *, slug: str = "proj") -> str:
    """Resolve the kernel project id for *slug* (read-only).

    The identity-column verifier (round-2 P2#1) compares the stored
    ``timelines.project_id`` against the project the import targets, so the
    reusable-checker tests need the resolved id here.
    """
    projects, _receipts, _timelines = make_backfill_deps(writer)
    return projects.resolve(writer, slug)


def tamper_event_payload_without_rehash(
    home: Path, *, index: int, mutate
) -> str:
    """Edit one event's payload in ``assembly.jsonl`` WITHOUT recomputing
    hashes (round-2 P3#5 laundering probe).

    Reproduces the panel scenario: the stored ``hash`` / ``prev_hash`` stay
    verbatim while the payload changes, so a source that skips chain
    verification would import the rewritten history as green. ``mutate``
    receives the parsed payload dict and edits it in place; the event is
    re-serialized as JSON (line formatting is not load-bearing). Returns the
    tampered ``event_id``.
    """
    import json as _json

    events_path = home / "assembly.jsonl"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    raw = _json.loads(lines[index])
    mutate(raw["payload"])
    lines[index] = _json.dumps(raw)
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(raw["event_id"])
