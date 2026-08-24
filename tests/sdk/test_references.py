"""Executable reference SDK service tests (m4 plan step 15, task T16).

Proves ``astrid.sdk.references.ReferencesService`` exposes repository-backed,
envelope-shaped ``create``/``update``/``archive``/``associate``/``set_primary``/
``link``/``list``/``show`` over the references pack repository:

- the five-key envelope shape with the committed nine-key receipt on
  mutations and a null receipt on pure reads;
- deterministic reference ids derived from the idempotency key, so an
  identical retry replays with zero new rows and a changed request under the
  same key returns ``idempotency_mismatch`` before any mutation;
- ``update`` mutates only name/description/metadata; ``archive`` hides a
  reference from ordinary lists while ``show`` still returns it, and any
  later mutation is a typed ``terminal_state``;
- ``associate`` and ``set_primary`` delegate exact-media/same-project and
  primary-replacement rules to the repository; ``link`` converges symmetric
  ``related_to`` requests on one canonical row;
- cross-project and missing references are typed ``not_found``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import build_standard_registry
from astrid.packs.references.repository import (
    REFERENCE_CREATE_COMMAND_KIND,
    REFERENCE_LINKED_EVENT_KIND,
    REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND,
    REFERENCE_PRIMARY_CHANGED_EVENT_KIND,
    REFERENCE_STREAM_TYPE,
    ReferenceRepository,
)
from astrid.sdk.contracts import derive_stable_id
from astrid.sdk.references import ReferencesService

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

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def env(tmp_path: Path):
    """A fresh standard writer, repositories, and reference service."""
    registry = build_standard_registry()
    writer = DatabaseWriter(tmp_path / "references.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        media = MediaRepository(
            events=events, receipts=receipts, projects_root=tmp_path
        )
        references = ReferenceRepository(events=events, receipts=receipts)
        yield SimpleNamespace(
            service=ReferencesService(writer, projects, references, receipts),
            writer=writer,
            projects=projects,
            media=media,
            references=references,
            root=tmp_path,
        )
    finally:
        writer.close()


def _create_project(env: SimpleNamespace, slug: str = "pilot") -> str:
    project_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.projects.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"create-{slug}-k",
            project_id=project_id,
        )
    )
    return project_id


_IMPORT_SEQ = 0


def _import_media(
    env: SimpleNamespace,
    project_id: str,
    *,
    data: bytes | None = None,
) -> str:
    global _IMPORT_SEQ
    _IMPORT_SEQ += 1
    # Media is content-addressed: distinct bytes guarantee a distinct media
    # row, so callers importing several media in one test never collide.
    content = data if data is not None else PNG_BYTES + str(_IMPORT_SEQ).encode()
    path = env.root / f"media-{generate_lowercase_ulid()}.png"
    path.write_bytes(content)
    prepared = prepare_media_file(path)
    media_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.media.import_prepared(
            u,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=f"import-{media_id}",
            media_id=media_id,
            realm="external_local",
        )
    )
    return media_id


def _reference_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM project_references")[0]
    )


def _create_reference(
    env: SimpleNamespace,
    project: str,
    *,
    media_id: str,
    kind: str = "character",
    name: str = "Aria",
    idempotency_key: str | None = None,
    **overrides,
):
    return env.service.create(
        project=project,
        kind=kind,
        name=name,
        media_id=media_id,
        idempotency_key=idempotency_key,
        **overrides,
    )


def _stream_id(ref_id: str) -> str:
    return f"{ref_id}:{REFERENCE_STREAM_TYPE}"


def _stream_head(env: SimpleNamespace, ref_id: str) -> int:
    row = env.writer.submit(
        lambda s: s.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ?", (_stream_id(ref_id),)
        )
    )
    assert row is not None, f"no event stream for reference {ref_id}"
    return int(row["head_seq"])


def _stream_event(env: SimpleNamespace, ref_id: str, event_kind: str) -> Any:
    """Return the most recent event of *event_kind* on a reference stream."""
    return env.writer.submit(
        lambda s: s.query_one(
            "SELECT event_id, kind, subject_type, subject_id, seq FROM events "
            "WHERE stream_id = ? AND kind = ? ORDER BY seq DESC LIMIT 1",
            (_stream_id(ref_id), event_kind),
        )
    )


def _event_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM events")[0]
    )


def _media_reference_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM media_references")[0]
    )


def _media_reference_is_primary(
    env: SimpleNamespace, ref_id: str, media_id: str
) -> bool:
    row = env.writer.submit(
        lambda s: s.query_one(
            "SELECT is_primary FROM media_references "
            "WHERE reference_id = ? AND media_id = ?",
            (ref_id, media_id),
        )
    )
    assert row is not None, f"no media_reference for {ref_id}/{media_id}"
    return int(row["is_primary"]) == 1


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_create_envelope_has_exactly_five_keys(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    result = _create_reference(env, project, media_id=media_id)
    assert result.ok is True
    assert set(result.as_dict().keys()) == ENVELOPE_KEYS
    assert result.error is None
    assert result.receipt is not None
    assert set(result.receipt.as_dict().keys()) == RECEIPT_KEYS
    assert result.receipt.command_kind == REFERENCE_CREATE_COMMAND_KIND


def test_read_envelopes_carry_null_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_id)
    ref_id = created.data["id"]
    for result in (
        env.service.list(project),
        env.service.show(project, ref_id),
    ):
        assert result.ok is True
        assert result.receipt is None
        assert result.idempotency_key == ""


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic ids
# ---------------------------------------------------------------------------


def test_create_derives_deterministic_id_from_key(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    expected = derive_stable_id(
        command_kind=REFERENCE_CREATE_COMMAND_KIND,
        scope=project,
        idempotency_key="k-deterministic",
        ordinal=0,
    )
    result = _create_reference(
        env, project, media_id=media_id, idempotency_key="k-deterministic"
    )
    assert result.ok is True
    assert result.data["id"] == expected


def test_identical_retry_replays_with_zero_new_rows(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    first = _create_reference(
        env, project, media_id=media_id, idempotency_key="k1"
    )
    assert first.ok is True
    first_receipt_id = first.receipt.receipt_id
    assert _reference_count(env) == 1

    second = _create_reference(
        env, project, media_id=media_id, idempotency_key="k1"
    )
    assert second.ok is True
    assert second.data["id"] == first.data["id"]
    assert second.receipt.receipt_id == first_receipt_id
    assert _reference_count(env) == 1


def test_mismatch_returns_idempotency_mismatch_before_mutation(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    first = _create_reference(
        env, project, media_id=media_id, idempotency_key="k1"
    )
    assert first.ok is True

    changed = _create_reference(
        env, project, media_id=media_id, name="Changed", idempotency_key="k1"
    )
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert _reference_count(env) == 1


# ---------------------------------------------------------------------------
# Update and archive lifecycle
# ---------------------------------------------------------------------------


def test_update_mutates_name_and_returns_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_id)
    ref_id = created.data["id"]

    updated = env.service.update(
        project, ref_id, name="Aria (v2)", metadata={"tone": "warm"}
    )
    assert updated.ok is True
    assert updated.receipt is not None
    assert updated.data["name"] == "Aria (v2)"
    assert updated.data["metadata"] == {"tone": "warm"}
    assert updated.data["kind"] == created.data["kind"]
    assert updated.data["project_id"] == project

    shown = env.service.show(project, ref_id)
    assert shown.ok is True
    assert shown.data["name"] == "Aria (v2)"


def test_archive_hides_from_list_but_show_still_works(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_id)
    ref_id = created.data["id"]

    archived = env.service.archive(project, ref_id, idempotency_key="archive-1")
    assert archived.ok is True
    assert archived.receipt is not None
    assert archived.data["reference_id"] == ref_id
    assert archived.data["archived_at"] is not None

    listed = env.service.list(project)
    assert listed.ok is True
    assert [row["id"] for row in listed.data] == []

    shown = env.service.show(project, ref_id)
    assert shown.ok is True
    assert shown.data["archived_at"] is not None


def test_update_after_archive_returns_terminal_state(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_id)
    ref_id = created.data["id"]

    assert env.service.archive(project, ref_id).ok is True
    result = env.service.update(project, ref_id, name="Nope")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "terminal_state"


def test_associate_after_archive_returns_recovery_details(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_id)
    ref_id = created.data["id"]

    assert env.service.archive(project, ref_id).ok is True
    result = env.service.associate(
        project, ref_id, media_id=media_id, role="depicts"
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "terminal_state"
    assert result.error.details["reference_id"] == ref_id
    assert "unarchive" in result.error.details["recovery"]


# ---------------------------------------------------------------------------
# Association and primary replacement
# ---------------------------------------------------------------------------


def test_associate_adds_exact_media_and_show_reflects(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    result = env.service.associate(
        project,
        ref_id,
        media_id=media_b,
        role="depicts",
        idempotency_key="associate-1",
    )
    assert result.ok is True
    assert result.receipt is not None
    assert [a["media_id"] for a in result.data["associations"]] == [media_b]

    shown = env.service.show(project, ref_id)
    assert shown.ok is True
    media_ids = [a["media_id"] for a in shown.data["media"]]
    assert media_a in media_ids
    assert media_b in media_ids


def test_set_primary_replaces_primary(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    associated = env.service.associate(
        project,
        ref_id,
        media_id=media_b,
        role="canonical",
        idempotency_key="associate-b",
    )
    assert associated.ok is True
    media_reference_id = associated.data["associations"][0]["id"]

    changed = env.service.set_primary(
        project,
        ref_id,
        media_reference_id=media_reference_id,
        idempotency_key="set-primary-1",
    )
    assert changed.ok is True
    assert changed.receipt is not None
    assert changed.data["previous_primary"]["media_id"] == media_a
    assert changed.data["new_primary"]["media_id"] == media_b

    shown = env.service.show(project, ref_id)
    assert shown.ok is True
    primary = [a for a in shown.data["media"] if a["is_primary"]]
    assert len(primary) == 1
    assert primary[0]["media_id"] == media_b


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def test_link_creates_typed_link_and_returns_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    ref_a = _create_reference(env, project, media_id=media_a).data["id"]
    ref_b = _create_reference(
        env, project, media_id=media_b, name="Bryn"
    ).data["id"]

    result = env.service.link(
        project,
        from_reference_id=ref_a,
        to_reference_id=ref_b,
        kind="belongs_to",
        idempotency_key="link-1",
    )
    assert result.ok is True
    assert result.receipt is not None
    assert result.data["from_reference_id"] == ref_a
    assert result.data["to_reference_id"] == ref_b
    assert result.data["kind"] == "belongs_to"


def test_link_symmetric_related_to_converges(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    ref_a = _create_reference(env, project, media_id=media_a).data["id"]
    ref_b = _create_reference(
        env, project, media_id=media_b, name="Bryn"
    ).data["id"]

    forward = env.service.link(
        project,
        from_reference_id=ref_a,
        to_reference_id=ref_b,
        kind="related_to",
        idempotency_key="link-forward",
    )
    assert forward.ok is True

    # ``related_to`` is symmetric and canonicalized: the reversed request
    # converges on the same stored edge and is rejected as a duplicate.
    reversed_result = env.service.link(
        project,
        from_reference_id=ref_b,
        to_reference_id=ref_a,
        kind="related_to",
        idempotency_key="link-reverse",
    )
    assert reversed_result.ok is False
    assert reversed_result.error is not None
    assert reversed_result.error.code == "validation_error"


# ---------------------------------------------------------------------------
# Not-found and cross-project
# ---------------------------------------------------------------------------


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    project = _create_project(env)
    result = env.service.show(project, "missing-ref")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_show_resolves_unambiguous_name_and_reports_ambiguous_recovery(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    media_id = _import_media(env, project_id)
    first = _create_reference(env, project_id, media_id=media_id, name="Field note")

    by_name = env.service.show(project_id, "Field note")
    assert by_name.ok is True
    assert by_name.data["id"] == first.data["id"]

    second_media = _import_media(env, project_id, data=PNG_BYTES + b"second")
    second = _create_reference(
        env, project_id, media_id=second_media, name="Field note", idempotency_key="ref-second"
    )
    ambiguous = env.service.show(project_id, "Field note")
    assert ambiguous.ok is False
    assert ambiguous.error is not None
    assert ambiguous.error.code == "validation_error"
    assert ambiguous.error.details["reason"] == "ambiguous_display_name"
    assert ambiguous.error.details["candidate_ids"] == sorted(
        [first.data["id"], second.data["id"]]
    )

    missing = env.service.show(project_id, "No such field note")
    assert missing.ok is False
    assert missing.error is not None
    assert missing.error.code == "not_found"
    assert missing.error.details["entity"] == "reference"


def test_show_name_and_id_return_equivalent_enriched_associations(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    primary_media = _import_media(env, project_id)
    secondary_media = _import_media(env, project_id, data=PNG_BYTES + b"secondary")
    created = _create_reference(
        env, project_id, media_id=primary_media, name="Unique Hero"
    )
    reference_id = created.data["id"]
    associated = env.service.associate(
        project_id,
        reference_id,
        media_id=secondary_media,
        role="depicts",
        idempotency_key="unique-hero-secondary",
    )
    assert associated.ok is True

    by_id = env.service.show(project_id, reference_id)
    by_name = env.service.show(project_id, "Unique Hero")
    assert by_id.ok is True
    assert by_name.ok is True
    assert by_name.data == by_id.data
    assert [entry["media_id"] for entry in by_name.data["media"]] == [
        primary_media,
        secondary_media,
    ]


def test_show_cross_project_returns_not_found(env: SimpleNamespace) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_id = _import_media(env, project_a)
    created = _create_reference(env, project_a, media_id=media_id)

    result = env.service.show(project_b, created.data["id"])
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_create_with_foreign_media_returns_validation_error(
    env: SimpleNamespace,
) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_id = _import_media(env, project_a)

    result = _create_reference(env, project_b, media_id=media_id)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"
    assert result.error.details == {
        "entity": "reference_media",
        "reason": "foreign",
        "media_id": media_id,
        "project_id": project_b,
        "recovery": (
            "run `astrid media list --project <project>` and retry with "
            "a media id owned by that project"
        ),
    }


# ---------------------------------------------------------------------------
# Stream-head advancement, event registration, atomic projection+receipt
# ---------------------------------------------------------------------------
#
# These integration tests assert the committed post-conditions the SDK
# exposes for set_primary/associate/link: exactly one stream-head advance,
# one registered event whose subject points at the reference, and a receipt
# committed in the same transaction as the projection. Statement-boundary
# crash atomicity itself is proven at the repository level by
# ``tests/v10/test_reference_conformance.py``.


def test_set_primary_advances_stream_head_and_appends_registered_event(
    env: SimpleNamespace,
) -> None:
    """set_primary advances the stream head by one and appends a registered
    ``reference.primary_changed`` event whose subject is the reference."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    associated = env.service.associate(
        project, ref_id, media_id=media_b, role="canonical", idempotency_key="assoc-b"
    )
    assert associated.ok is True
    media_reference_id = associated.data["associations"][0]["id"]

    head_before = _stream_head(env, ref_id)
    changed = env.service.set_primary(
        project, ref_id, media_reference_id=media_reference_id, idempotency_key="sp-1"
    )
    assert changed.ok is True

    assert _stream_head(env, ref_id) == head_before + 1

    event = _stream_event(env, ref_id, REFERENCE_PRIMARY_CHANGED_EVENT_KIND)
    assert event is not None
    assert event["kind"] == REFERENCE_PRIMARY_CHANGED_EVENT_KIND
    assert event["subject_type"] == "reference"
    assert event["subject_id"] == ref_id
    assert event["event_id"] in changed.receipt.event_ids


def test_associate_advances_stream_head_and_appends_registered_event(
    env: SimpleNamespace,
) -> None:
    """associate advances the stream head by one and appends a registered
    ``reference.media_associated`` event whose subject is the reference."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    head_before = _stream_head(env, ref_id)
    result = env.service.associate(
        project, ref_id, media_id=media_b, role="depicts", idempotency_key="assoc-1"
    )
    assert result.ok is True

    assert _stream_head(env, ref_id) == head_before + 1

    event = _stream_event(env, ref_id, REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND)
    assert event is not None
    assert event["kind"] == REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND
    assert event["subject_type"] == "reference"
    assert event["subject_id"] == ref_id
    assert event["event_id"] in result.receipt.event_ids


def test_link_advances_stream_head_and_appends_registered_event(
    env: SimpleNamespace,
) -> None:
    """link advances the from-stream head by one and appends a registered
    ``reference.linked`` event whose subject is the from-reference."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    ref_a = _create_reference(env, project, media_id=media_a).data["id"]
    ref_b = _create_reference(env, project, media_id=media_b, name="Bryn").data["id"]

    head_before = _stream_head(env, ref_a)
    result = env.service.link(
        project,
        from_reference_id=ref_a,
        to_reference_id=ref_b,
        kind="belongs_to",
        idempotency_key="link-1",
    )
    assert result.ok is True

    assert _stream_head(env, ref_a) == head_before + 1

    event = _stream_event(env, ref_a, REFERENCE_LINKED_EVENT_KIND)
    assert event is not None
    assert event["kind"] == REFERENCE_LINKED_EVENT_KIND
    assert event["subject_type"] == "reference"
    assert event["subject_id"] == ref_a
    assert event["event_id"] in result.receipt.event_ids


def test_set_primary_atomic_projection_association_receipt(
    env: SimpleNamespace,
) -> None:
    """set_primary commits the projection, association flip, and receipt in one
    transaction: the old primary is cleared, the new one is set, and the
    receipt's event id and resulting stream seq match the committed state."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    associated = env.service.associate(
        project, ref_id, media_id=media_b, role="canonical", idempotency_key="assoc-b"
    )
    assert associated.ok is True
    media_reference_id = associated.data["associations"][0]["id"]

    changed = env.service.set_primary(
        project, ref_id, media_reference_id=media_reference_id, idempotency_key="sp-1"
    )
    assert changed.ok is True

    # Projection: old primary cleared, new primary set.
    assert _media_reference_is_primary(env, ref_id, media_a) is False
    assert _media_reference_is_primary(env, ref_id, media_b) is True

    # The show read model reflects the new primary.
    shown = env.service.show(project, ref_id)
    primary = [a for a in shown.data["media"] if a["is_primary"]]
    assert len(primary) == 1
    assert primary[0]["media_id"] == media_b

    # The receipt row was committed alongside the projection.
    receipt_row = env.writer.submit(
        lambda s: s.query_one(
            "SELECT event_ids_json, result_json, resulting_stream_seq "
            "FROM command_receipts WHERE project_id = ? AND idempotency_key = ?",
            (project, "sp-1"),
        )
    )
    assert receipt_row is not None
    event_ids = json.loads(receipt_row["event_ids_json"])
    assert event_ids == list(changed.receipt.event_ids)
    assert event_ids[0] == _stream_event(
        env, ref_id, REFERENCE_PRIMARY_CHANGED_EVENT_KIND
    )["event_id"]
    stored_result = json.loads(receipt_row["result_json"])
    assert stored_result["new_primary"]["media_id"] == media_b
    assert receipt_row["resulting_stream_seq"] == _stream_head(env, ref_id)


def test_associate_replay_returns_stored_receipt_zero_new_rows(
    env: SimpleNamespace,
) -> None:
    """An identical associate retry replays the stored receipt with zero new
    media_references rows and zero new events."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    first = env.service.associate(
        project, ref_id, media_id=media_b, role="depicts", idempotency_key="assoc-r"
    )
    assert first.ok is True
    first_receipt_id = first.receipt.receipt_id

    media_count_before = _media_reference_count(env)
    event_count_before = _event_count(env)

    second = env.service.associate(
        project, ref_id, media_id=media_b, role="depicts", idempotency_key="assoc-r"
    )
    assert second.ok is True
    assert second.receipt.receipt_id == first_receipt_id
    assert _media_reference_count(env) == media_count_before
    assert _event_count(env) == event_count_before


def test_associate_mismatch_rejected_before_mutation(env: SimpleNamespace) -> None:
    """A changed associate request under the same key is rejected as
    ``idempotency_mismatch`` before any row is written."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    first = env.service.associate(
        project, ref_id, media_id=media_b, role="depicts", idempotency_key="assoc-m"
    )
    assert first.ok is True

    media_count_before = _media_reference_count(env)
    event_count_before = _event_count(env)

    changed = env.service.associate(
        project, ref_id, media_id=media_b, role="inspired_by", idempotency_key="assoc-m"
    )
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert _media_reference_count(env) == media_count_before
    assert _event_count(env) == event_count_before


def test_set_primary_mismatch_rejected_before_mutation(env: SimpleNamespace) -> None:
    """A changed set_primary request under the same key is rejected as
    ``idempotency_mismatch`` before the primary is moved or an event appended."""
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    media_c = _import_media(env, project)
    created = _create_reference(env, project, media_id=media_a)
    ref_id = created.data["id"]

    assoc_b = env.service.associate(
        project, ref_id, media_id=media_b, role="canonical", idempotency_key="assoc-b"
    )
    assoc_c = env.service.associate(
        project, ref_id, media_id=media_c, role="canonical", idempotency_key="assoc-c"
    )
    assert assoc_b.ok is True
    assert assoc_c.ok is True
    media_reference_b = assoc_b.data["associations"][0]["id"]
    media_reference_c = assoc_c.data["associations"][0]["id"]

    first = env.service.set_primary(
        project, ref_id, media_reference_id=media_reference_b, idempotency_key="sp-m"
    )
    assert first.ok is True

    event_count_before = _event_count(env)

    changed = env.service.set_primary(
        project, ref_id, media_reference_id=media_reference_c, idempotency_key="sp-m"
    )
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    # No mutation: media_b stays primary, media_c stays non-primary, and no
    # new event was appended.
    assert _media_reference_is_primary(env, ref_id, media_b) is True
    assert _media_reference_is_primary(env, ref_id, media_c) is False
    assert _event_count(env) == event_count_before
