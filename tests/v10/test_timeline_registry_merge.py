"""Timeline registry-merge tests: the internal completion-time asset
visibility path (27-build-spec section 5 step 7).

This suite proves :meth:`TimelineRepository.merge_registry`:

- additive merge: new entry keys land in ``asset_registry_json``, existing
  keys are never clobbered, and ``document_json`` stays byte-identical;
- head semantics: no caller ``expected_version`` exists — the merge reads
  the current head inside the transaction, appends one hash-chained
  ``timeline.registry_merged`` event carrying ``{assets, added_keys,
  base_head}`` with a defense-in-depth ``expected_head_seq`` CAS, and
  returns the new stream head a subsequent editor save must pass;
- fences: an archived timeline rejects the merge before any change, a
  foreign/unknown timeline id is typed, and a fully-redundant merge (all
  keys already present) changes zero rows and appends nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.timeline.repository import (
    TIMELINE_REGISTRY_MERGED_EVENT_KIND,
    TimelineArchivedError,
    TimelineNotFoundError,
    TimelineRepository,
    TimelineVersionConflictError,
)

TS = "2026-08-22T00:00:00.000000+00:00"
TS2 = "2026-08-22T01:00:00.000000+00:00"
TS3 = "2026-08-22T02:00:00.000000+00:00"

CONFIG = {"fps": 24, "resolution": "1920x1080", "nested": {"scene": "s01"}}
ASSETS = {"hero": {"path": "hero.png", "kind": "image"}}


@pytest.fixture
def env(tmp_path: Path, standard_registry):
    """Fresh writer, project/timeline repositories, and a seeded timeline."""
    writer = DatabaseWriter(tmp_path / "merge.sqlite3", standard_registry)
    events = EventAppendService(standard_registry)
    project_repo = ProjectRepository(events=events, receipts=ReceiptService())
    repo = TimelineRepository(
        events=events, receipts=ReceiptService(), projects=project_repo
    )
    project = UnitOfWork(writer).run(
        lambda u: project_repo.create(
            u,
            slug="pilot",
            name="Pilot",
            settings={"fps": 24},
            idempotency_key="create-pilot-k",
            created_at=TS,
        )
    )
    timeline = UnitOfWork(writer).run(
        lambda u: repo.create(
            u,
            project_id=project.id,
            slug="main",
            name="Main",
            config=dict(CONFIG),
            registry={"assets": dict(ASSETS)},
            idempotency_key="tl-create-1",
            created_at=TS,
        )
    )
    try:
        yield SimpleNamespace(
            writer=writer,
            repo=repo,
            project=project,
            timeline=timeline,
        )
    finally:
        writer.close()


def _merge(env, entries, **overrides):
    args = {
        "project_id": env.project.id,
        "timeline_id": env.timeline.timeline_id,
        "entries": entries,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.repo.merge_registry(u, **args)
    )


def _timeline_row(writer: DatabaseWriter, timeline_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
        )
    )


def _stream_events(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT seq, kind, payload_json FROM events "
            "WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )


def test_merge_adds_entries_and_keeps_document_byte_identical(env) -> None:
    before = _timeline_row(env.writer, env.timeline.timeline_id)
    document_before = before["document_json"]

    new_head = _merge(
        env,
        {"clip-1": {"media_id": "m1", "kind": "image"}},
    )

    assert new_head == 2  # created (head 1) + one merged event

    row = _timeline_row(env.writer, env.timeline.timeline_id)
    assert row["document_json"] == document_before  # byte-identical
    assets = json.loads(row["asset_registry_json"])
    assert assets == {
        "hero": ASSETS["hero"],
        "clip-1": {"media_id": "m1", "kind": "image"},
    }

    events = _stream_events(
        env.writer, f"{env.timeline.timeline_id}:timeline.timeline"
    )
    merged = [e for e in events if e["kind"] == TIMELINE_REGISTRY_MERGED_EVENT_KIND]
    assert len(merged) == 1
    payload = json.loads(merged[0]["payload_json"])
    data = payload["data"]
    assert data["added_keys"] == ["clip-1"]
    assert data["base_head"] == 1
    assert data["assets"] == assets
    assert payload["_integrity"]["previous_event_hash"] is not None


def test_merge_never_clobbers_existing_keys_and_reports_added_only(env) -> None:
    _merge(env, {"clip-1": {"media_id": "m1"}})
    row = _timeline_row(env.writer, env.timeline.timeline_id)

    # A second merge re-proposing hero and clip-1 adds nothing new except
    # the genuinely fresh key; existing values stay exactly as they were.
    new_head = _merge(
        env,
        {
            "hero": {"path": "CLOBBERED", "kind": "image"},
            "clip-1": {"media_id": "CHANGED"},
            "clip-2": {"media_id": "m2"},
        },
        created_at=TS3,
    )
    assert new_head == 3

    row = _timeline_row(env.writer, env.timeline.timeline_id)
    assets = json.loads(row["asset_registry_json"])
    assert assets["hero"] == ASSETS["hero"]  # editor authority wins
    assert assets["clip-1"] == {"media_id": "m1"}
    assert assets["clip-2"] == {"media_id": "m2"}

    events = _stream_events(env.writer, f"{env.timeline.timeline_id}:timeline.timeline")
    merged = [e for e in events if e["kind"] == TIMELINE_REGISTRY_MERGED_EVENT_KIND]
    assert len(merged) == 2
    second = json.loads(merged[1]["payload_json"])["data"]
    assert second["added_keys"] == ["clip-2"]
    assert second["base_head"] == 2


def test_redundant_merge_changes_zero_rows_and_appends_nothing(env) -> None:
    first_head = _merge(env, {"clip-1": {"media_id": "m1"}})
    row_before = _timeline_row(env.writer, env.timeline.timeline_id)
    events_before = _stream_events(
        env.writer, f"{env.timeline.timeline_id}:timeline.timeline"
    )

    repeat_head = _merge(
        env,
        {"clip-1": {"media_id": "anything"}},
        created_at=TS3,
    )

    assert repeat_head == first_head
    row_after = _timeline_row(env.writer, env.timeline.timeline_id)
    assert row_after["asset_registry_json"] == row_before["asset_registry_json"]
    assert row_after["updated_at"] == row_before["updated_at"]
    assert _stream_events(
        env.writer, f"{env.timeline.timeline_id}:timeline.timeline"
    ) == events_before


def test_merge_honors_archive_fence_and_typed_misses(env) -> None:
    with pytest.raises(TimelineNotFoundError):
        _merge(env, {"clip-1": {"media_id": "m1"}}, timeline_id="missing-tl")
    # Archive through the public command, then merge must reject.
    UnitOfWork(env.writer).run(
        lambda u: env.repo.archive(
            u,
            project_id=env.project.id,
            ref=env.timeline.timeline_id,
            idempotency_key="tl-archive-1",
            created_at=TS3,
        )
    )
    before = _timeline_row(env.writer, env.timeline.timeline_id)
    with pytest.raises(TimelineArchivedError):
        _merge(env, {"clip-9": {"media_id": "m9"}})
    after = _timeline_row(env.writer, env.timeline.timeline_id)
    assert after["asset_registry_json"] == before["asset_registry_json"]
    assert after["document_json"] == before["document_json"]


def test_merged_head_is_the_next_editor_save_version(env) -> None:
    new_head = _merge(env, {"clip-1": {"media_id": "m1"}})

    # The frozen load shape's config_version equals the merged head, and an
    # optimistic editor save at the stale pre-merge version conflicts.

    loaded = env.repo.show(env.writer, env.project.id, "main")
    assert loaded.config_version == new_head
    with pytest.raises(TimelineVersionConflictError):
        UnitOfWork(env.writer).run(
            lambda u: env.repo.save(
                u,
                project_id=env.project.id,
                ref=env.timeline.slug,
                config={"fps": 25},
                registry={"assets": {}},
                expected_version=new_head - 1,
                created_at=TS3,
            )
        )
