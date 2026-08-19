"""Executable timeline SDK service tests (m4 plan step 8, task T9).

Proves ``astrid.sdk.timelines.TimelinesService`` exposes repository-backed,
envelope-shaped ``create``/``list``/``show``/``save``/``archive``/``history``/
``diff`` over the Steps 6–7 timeline repository:

- the five-key envelope shape with the committed nine-key receipt on
  mutations and a null receipt on pure reads;
- caller keys preserved, generated keys returned and fresh, empty keys
  rejected as ``validation_error``;
- deterministic timeline ids derived from the idempotency key (project
  scope), so an identical retry replays the committed result with zero new
  rows and a changed request under the same key returns
  ``idempotency_mismatch`` before any mutation;
- UUID/ULID/slug addressing through the repository (project-scoped);
- whole-document CAS save: a stale ``expected_version`` maps to
  ``stale_version`` and changes zero rows; an archived timeline rejects a
  later save with ``terminal_state``;
- archive hides a timeline from ordinary lists; history/diff are
  deterministic reads; and every committed mutation survives restart.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import build_standard_registry
from astrid.packs.timeline.repository import (
    TIMELINE_ARCHIVED_EVENT_KIND,
    TIMELINE_CREATE_COMMAND_KIND,
    TIMELINE_SAVED_EVENT_KIND,
    TimelineRepository,
)
from astrid.sdk.contracts import derive_stable_id
from astrid.sdk.timelines import TimelinesService

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}
RECEIPT_KEYS = {
    "receipt_id",
    "command_kind",
    "idempotency_key",
    "request_hash",
    "project_id",
    "project_seq",
    "event_ids",
    "result",
    "created_at",
}

CONFIG = {"duration": 10, "fps": 24}
ASSETS = {"a1": {"kind": "image", "src": "a1.png"}}
SAVED_CONFIG = {"duration": 20, "fps": 30}
SAVED_ASSETS = {"a1": {"kind": "image", "src": "a1.png"}, "a2": {"kind": "image", "src": "a2.png"}}
SAVED_ASSETS_V2 = {"a1": {"kind": "image", "src": "a1-v2.png"}}


@pytest.fixture
def env(tmp_path: Path):
    """A fresh standard writer, repositories, and timeline service."""
    registry = build_standard_registry()
    writer = DatabaseWriter(tmp_path / "timelines.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        timelines = TimelineRepository(
            events=events, receipts=receipts, projects=projects
        )
        yield SimpleNamespace(
            service=TimelinesService(writer, projects, timelines, receipts),
            writer=writer,
            projects=projects,
            timelines=timelines,
            root=tmp_path,
        )
    finally:
        writer.close()


def _create_project(env: SimpleNamespace, *, slug: str = "pilot") -> str:
    model = UnitOfWork(env.writer).run(
        lambda uow: env.projects.create(
            uow,
            slug=slug,
            name=slug.title(),
            settings={"fps": 24},
            idempotency_key=f"create-{slug}-k",
        )
    )
    return model.id


def _timeline_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM timelines")[0]
    )


def _event_and_receipt_counts(env: SimpleNamespace) -> tuple[int, int]:
    return env.writer.submit(
        lambda s: (
            s.query_one("SELECT COUNT(*) FROM events")[0],
            s.query_one("SELECT COUNT(*) FROM command_receipts")[0],
        )
    )


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_create_envelope_has_exactly_five_keys(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    result = env.service.create(
        project=project_id, slug="main", name="Main", config=CONFIG
    )
    assert result.ok is True
    assert set(result.as_dict().keys()) == ENVELOPE_KEYS
    assert result.error is None
    assert result.receipt is not None
    assert set(result.receipt.as_dict().keys()) == RECEIPT_KEYS
    assert result.receipt.command_kind == TIMELINE_CREATE_COMMAND_KIND


def test_read_envelopes_carry_null_receipt_and_empty_key(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    env.service.create(
        project=project_id, slug="main", name="Main", config=CONFIG
    )
    for result in (
        env.service.list(project_id),
        env.service.show(project_id, "main"),
        env.service.history(project_id, "main"),
        env.service.diff(project_id, "main"),
    ):
        assert result.ok is True
        assert result.receipt is None
        assert result.idempotency_key == ""


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic ids
# ---------------------------------------------------------------------------


def test_caller_key_preserved_and_generated_key_is_fresh(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    first = env.service.create(
        project=project_id,
        slug="one",
        name="One",
        config=CONFIG,
        idempotency_key="caller-1",
    )
    second = env.service.create(
        project=project_id, slug="two", name="Two", config=CONFIG
    )
    assert first.idempotency_key == "caller-1"
    assert second.ok is True
    assert second.idempotency_key
    assert second.idempotency_key != first.idempotency_key


def test_generated_key_is_returned_when_project_resolution_fails(
    env: SimpleNamespace,
) -> None:
    results = (
        env.service.create(project="missing", slug="main", name="Main"),
        env.service.save(
            "missing",
            "main",
            config=CONFIG,
            registry={"assets": ASSETS},
            expected_version=1,
        ),
        env.service.archive("missing", "main"),
    )
    keys = []
    for result in results:
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "not_found"
        assert result.idempotency_key
        keys.append(result.idempotency_key)
    assert len(set(keys)) == len(keys)


def test_empty_key_returns_validation_error_before_mutation(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    result = env.service.create(
        project=project_id,
        slug="main",
        name="Main",
        config=CONFIG,
        idempotency_key="",
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"
    assert _timeline_count(env) == 0


def test_create_derives_deterministic_id_from_key(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    expected = derive_stable_id(
        command_kind=TIMELINE_CREATE_COMMAND_KIND,
        scope=project_id,
        idempotency_key="k-deterministic",
        ordinal=0,
    )
    result = env.service.create(
        project=project_id,
        slug="det",
        name="Det",
        config=CONFIG,
        idempotency_key="k-deterministic",
    )
    assert result.ok is True
    assert result.data["timeline_id"] == expected


# ---------------------------------------------------------------------------
# Replay and mismatch-before-mutation
# ---------------------------------------------------------------------------


def test_identical_retry_replays_with_zero_new_rows(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    first = env.service.create(
        project=project_id,
        slug="main",
        name="Main",
        config=CONFIG,
        idempotency_key="k1",
    )
    assert first.ok is True
    first_receipt_id = first.receipt.receipt_id
    assert _timeline_count(env) == 1

    second = env.service.create(
        project=project_id,
        slug="main",
        name="Main",
        config=CONFIG,
        idempotency_key="k1",
    )
    assert second.ok is True
    assert second.data["timeline_id"] == first.data["timeline_id"]
    assert second.receipt.receipt_id == first_receipt_id
    assert second.receipt == first.receipt
    assert _timeline_count(env) == 1


def test_mismatch_returns_idempotency_mismatch_before_mutation(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    first = env.service.create(
        project=project_id,
        slug="main",
        name="Main",
        config=CONFIG,
        idempotency_key="k1",
    )
    assert first.ok is True

    changed = env.service.create(
        project=project_id,
        slug="main",
        name="Different",
        config=CONFIG,
        idempotency_key="k1",
    )
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert changed.idempotency_key == "k1"
    assert _timeline_count(env) == 1
    shown = env.service.show(project_id, "main")
    assert shown.data["name"] == "Main"


# ---------------------------------------------------------------------------
# List and show with UUID/ULID/slug addressing
# ---------------------------------------------------------------------------


def test_list_returns_slug_sorted_rows(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="zeta", name="Zeta", config=CONFIG)
    env.service.create(project=project_id, slug="alpha", name="Alpha", config=CONFIG)
    result = env.service.list(project_id)
    assert result.ok is True
    assert [row["slug"] for row in result.data] == ["alpha", "zeta"]
    assert [row["name"] for row in result.data] == ["Alpha", "Zeta"]


def test_show_resolves_by_id_ulid_and_slug(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(
        project=project_id, slug="main", name="Main", config=CONFIG
    )
    timeline_id = created.data["timeline_id"]
    timeline_ulid = created.data["timeline_ulid"]
    by_id = env.service.show(project_id, timeline_id)
    by_ulid = env.service.show(project_id, timeline_ulid)
    by_slug = env.service.show(project_id, "main")
    for result in (by_id, by_ulid, by_slug):
        assert result.ok is True
        assert result.data == created.data


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    result = env.service.show(project_id, "missing-timeline")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_show_missing_project_returns_not_found(env: SimpleNamespace) -> None:
    result = env.service.show("no-such-project", "main")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


# ---------------------------------------------------------------------------
# Whole-document CAS save
# ---------------------------------------------------------------------------


def test_save_updates_document_and_returns_receipt(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(
        project=project_id, slug="main", name="Main", config=CONFIG
    )
    assert created.data["config_version"] == 1

    saved = env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=1,
    )
    assert saved.ok is True
    assert saved.receipt is not None
    assert saved.data["config_version"] == 2
    assert saved.data["config"] == SAVED_CONFIG
    assert saved.data["registry"] == {"assets": SAVED_ASSETS}


def test_save_stale_version_returns_stale_version(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="main", name="Main", config=CONFIG)
    before_events, before_receipts = _event_and_receipt_counts(env)

    saved = env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=0,  # stale: current head is 1
    )
    assert saved.ok is False
    assert saved.error is not None
    assert saved.error.code == "stale_version"
    # Zero mutation: no new event, no new receipt, document unchanged.
    assert _event_and_receipt_counts(env) == (before_events, before_receipts)
    shown = env.service.show(project_id, "main")
    assert shown.data["config"] == CONFIG


def test_save_replays_and_mismatches(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="main", name="Main", config=CONFIG)

    first = env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=1,
        idempotency_key="save-k1",
    )
    assert first.ok is True
    replay = env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=1,
        idempotency_key="save-k1",
    )
    assert replay.ok is True
    assert replay.receipt.receipt_id == first.receipt.receipt_id

    mismatch = env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS_V2},
        expected_version=1,
        idempotency_key="save-k1",
    )
    assert mismatch.ok is False
    assert mismatch.error.code == "idempotency_mismatch"


# ---------------------------------------------------------------------------
# Archive and history/diff
# ---------------------------------------------------------------------------


def test_archive_returns_receipt_and_hides_from_list(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="main", name="Main", config=CONFIG)
    env.service.create(project=project_id, slug="other", name="Other", config=CONFIG)

    archived = env.service.archive(project_id, "main")
    assert archived.ok is True
    assert archived.receipt is not None

    # Archived timeline disappears from ordinary lists.
    listed = env.service.list(project_id)
    assert [row["slug"] for row in listed.data] == ["other"]
    # Direct historical lookup still works.
    shown = env.service.show(project_id, "main")
    assert shown.ok is True


def test_save_after_archive_returns_terminal_state(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="main", name="Main", config=CONFIG)
    env.service.archive(project_id, "main")
    before_events, before_receipts = _event_and_receipt_counts(env)

    saved = env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=1,
    )
    assert saved.ok is False
    assert saved.error is not None
    assert saved.error.code == "terminal_state"
    assert _event_and_receipt_counts(env) == (before_events, before_receipts)


def test_archive_replays(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="main", name="Main", config=CONFIG)
    first = env.service.archive(project_id, "main", idempotency_key="arch-1")
    assert first.ok is True
    replay = env.service.archive(project_id, "main", idempotency_key="arch-1")
    assert replay.ok is True
    assert replay.receipt.receipt_id == first.receipt.receipt_id


def test_history_returns_ordered_lifecycle_events(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(project=project_id, slug="main", name="Main", config=CONFIG)
    env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=1,
    )
    env.service.archive(project_id, "main")

    result = env.service.history(project_id, "main")
    assert result.ok is True
    kinds = [entry["kind"] for entry in result.data]
    assert kinds == [
        "timeline.created",
        TIMELINE_SAVED_EVENT_KIND,
        TIMELINE_ARCHIVED_EVENT_KIND,
    ]
    versions = [entry["version"] for entry in result.data]
    assert versions == [1, 2, 3]


def test_diff_returns_deterministic_adjacent_diffs(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    env.service.create(
        project=project_id,
        slug="main",
        name="Main",
        config=CONFIG,
        registry={"assets": ASSETS},
    )
    env.service.save(
        project_id,
        "main",
        config=SAVED_CONFIG,
        registry={"assets": SAVED_ASSETS},
        expected_version=1,
    )

    result = env.service.diff(project_id, "main")
    assert result.ok is True
    assert len(result.data) == 1
    entry = result.data[0]
    assert entry["from_version"] == 1
    assert entry["to_version"] == 2
    assert entry["document"]["changed"] == ["duration", "fps"]
    assert entry["registry"]["added"] == ["a2"]


# ---------------------------------------------------------------------------
# Restart durability
# ---------------------------------------------------------------------------


def test_restart_reloads_committed_timeline(tmp_path: Path) -> None:
    registry = build_standard_registry()
    db_path = tmp_path / "restart.sqlite3"
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )

    writer = DatabaseWriter(db_path, registry)
    try:
        service = TimelinesService(writer, projects, timelines, receipts)
        project_id = UnitOfWork(writer).run(
            lambda uow: projects.create(
                uow,
                slug="pilot",
                name="Pilot",
                settings={},
                idempotency_key="proj-k",
            )
        ).id
        created = service.create(
            project=project_id, slug="main", name="Main", config=CONFIG
        )
        assert created.ok is True
        timeline_id = created.data["timeline_id"]
    finally:
        writer.close()

    reopened = DatabaseWriter(db_path, registry)
    try:
        service = TimelinesService(
            writer=reopened,
            projects=projects,
            timelines=timelines,
            receipts=receipts,
        )
        shown = service.show(project_id, timeline_id)
        assert shown.ok is True
        assert shown.data == created.data
        assert shown.data["config"] == CONFIG
    finally:
        reopened.close()
