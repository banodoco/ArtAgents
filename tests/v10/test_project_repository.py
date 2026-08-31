"""Project repository tests: project-create validation, replay, and atomic state.

(m1 plan step 11, T24.) This suite proves the first complete repository
vertical end to end:

- lowercase ULIDs: the kernel's canonical project identifiers are
  26-character lowercase Crockford-base32 ULIDs (no I/L/O/U), generated
  monotonically within a millisecond, and the repository uses them whenever
  the caller omits ``project_id``;
- slug validation and uniqueness: the immutable slug grammar
  (``[a-z0-9]+(-[a-z0-9]+)*``) is enforced before any mutation, and a slug or
  project id that is already in use is rejected with the typed error before
  the UNIQUE constraints fire, changing zero rows;
- stable project-scoped replay: an identical retry keyed on the caller's
  stable project id returns exactly the stored complete result with zero new
  rows, and the same idempotency key under a *different* project creates a
  new project (replay never leaks across projects);
- mismatched-key rejection before mutation: reusing an idempotency key with a
  different request raises :class:`ReceiptMismatchError` while every
  persisted object (projects, streams, events, receipts, both heads) stays
  unchanged;
- stream association: one ``core.project`` stream per project whose aggregate
  id equals the project id, one registered ``core.project.created`` event on
  that stream carrying the canonical SD2 payload envelope, and the receipt
  pointing at that stream with the exact sequence range;
- full receipt contents: transaction id, request hash (recomputed from the
  semantic request), command kind, primary stream and resulting sequence,
  exact project sequence range, ordered event ids, complete result JSON, and
  created_at;
- no filesystem project authority: the read model lives only in the kernel
  database — no project file appears beside the SQLite file, and after a
  close/reopen the read model is reconstructed from the database alone.

Plan step 12 (T25) extends the suite with the read surface and the eventful
update path:

- sorted read-only list and typed show queries that never open a writer
  transaction, plus typed project-not-found behavior;
- eventful, idempotent name/settings updates through the same command path
  (projection + ``core.project.updated`` event + both heads + complete
  receipt in one ``BEGIN IMMEDIATE``), with update replay and
  mismatch-before-mutation;
- repository-owned default-timeline metadata persisted in ``settings_json``
  and preserved across caller settings updates;
- restart durability: after a clean close/reopen, transaction-free reads
  reconstruct the full updated state from the database alone.

Every command runs inside the caller's one ``BEGIN IMMEDIATE`` unit of work
(:class:`astrid.core.store.uow.UnitOfWork`), exactly as the repository
contract requires; every read runs on a separate read-only connection.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import (
    ULID_LENGTH,
    generate_lowercase_ulid,
    is_lowercase_ulid,
)
from astrid.core.receipts import ReceiptMismatchError, ReceiptService, request_hash
from astrid.core.repositories import (
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ProjectReadModel,
    ProjectRepository,
    ProjectSlugConflictError,
    ProjectValidationError,
)
from astrid.core.repositories.projects import ProjectSummary
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter, WriterSession

TS = "2026-08-15T00:00:00.000000+00:00"
TS2 = "2026-08-15T01:00:00.000000+00:00"

_CROCKFORD_ULID_RE = re.compile(r"^[0123456789abcdefghjkmnpqrstvwxyz]{26}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_UUID4_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def writer(tmp_path: Path, core_registry):
    """A fresh kernel-only writer at ``<tmp>/kernel.sqlite3``."""
    db_path = tmp_path / "kernel.sqlite3"
    w = DatabaseWriter(db_path, core_registry)
    try:
        yield w
    finally:
        w.close()


@pytest.fixture
def repo(core_registry) -> ProjectRepository:
    """A stateless project repository over the kernel event/receipt services."""
    return ProjectRepository(
        events=EventAppendService(core_registry),
        receipts=ReceiptService(),
    )


def _create(repo: ProjectRepository, writer: DatabaseWriter, **overrides):
    """Run one project-create command inside its own unit of work."""
    args = {
        "slug": "pilot",
        "name": "Pilot",
        "settings": {"fps": 24},
        "idempotency_key": "create-k-1",
        "project_id": generate_lowercase_ulid(),
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(writer).run(lambda u: repo.create(u, **args))


def _row_counts(writer: DatabaseWriter) -> tuple[int, int, int, int]:
    """(projects, event_streams, events, command_receipts) row counts."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM projects")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )


def _project_row(writer: DatabaseWriter, project_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
    )


def _stream_row(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
        )
    )


def _event_row(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq", (stream_id,)
        )
    )


def _receipt_row(writer: DatabaseWriter, project_id: str, key: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = ? AND idempotency_key = ?",
            (project_id, key),
        )
    )


def _get(repo: ProjectRepository, writer: DatabaseWriter, project_id: str):
    return UnitOfWork(writer).run(lambda u: repo.get(u, project_id))


def _update(
    repo: ProjectRepository, writer: DatabaseWriter, project_id: str, **overrides
):
    """Run one project-update command inside its own unit of work."""
    args = {
        "name": "Pilot Renamed",
        "settings": {"fps": 30},
        "idempotency_key": "update-k-1",
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(writer).run(lambda u: repo.update(u, project_id, **args))


def _set_default(
    repo: ProjectRepository,
    writer: DatabaseWriter,
    project_id: str,
    timeline_id: str,
    **overrides,
):
    """Run one repository-owned default-timeline update command."""
    args = {
        "idempotency_key": "default-k-1",
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(writer).run(
        lambda u: repo.set_default_timeline(u, project_id, timeline_id, **args)
    )


def _events(writer: DatabaseWriter, stream_id: str):
    """All events on one stream, ordered by seq."""
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq",
            (stream_id,),
        )
    )


def _install_begin_spy(monkeypatch) -> list[str]:
    """Record every BEGIN IMMEDIATE opened on the writer session.

    Test-only instrumentation: ``_begin_immediate`` is the single private
    method that opens a writer transaction, so a read path that never
    calls it proves it opens no writer transaction.
    """
    calls: list[str] = []
    original = WriterSession._begin_immediate

    def spy(self, *args, **kwargs):
        calls.append("begin_immediate")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(WriterSession, "_begin_immediate", spy)
    return calls


# ---------------------------------------------------------------------------
# Lowercase Crockford ULIDs
# ---------------------------------------------------------------------------


def test_generate_lowercase_ulid_shape_uniqueness_and_monotonicity() -> None:
    ulids = [generate_lowercase_ulid() for _ in range(100)]
    assert len(set(ulids)) == 100
    for ulid in ulids:
        assert len(ulid) == ULID_LENGTH == 26
        assert ulid == ulid.lower()
        assert _CROCKFORD_ULID_RE.fullmatch(ulid) is not None
        # Crockford base32 omits the visually ambiguous I, L, O, U.
        assert not any(ch in ulid for ch in "ilou")
    # Time-ordered: the 48-bit millisecond prefix makes consecutive ULIDs
    # strictly increasing (monotonic within a millisecond by construction).
    assert sorted(ulids) == ulids


def test_is_lowercase_ulid_accepts_generated_and_rejects_bad_shapes() -> None:
    assert is_lowercase_ulid(generate_lowercase_ulid()) is True
    valid = generate_lowercase_ulid()
    assert is_lowercase_ulid(valid.upper()) is False
    assert is_lowercase_ulid(valid[:25]) is False
    assert is_lowercase_ulid(valid + "0") is False
    # Ambiguous letters are excluded from the alphabet.
    for excluded in ("i", "l", "o", "u"):
        assert is_lowercase_ulid(excluded * 26) is False
    assert is_lowercase_ulid("") is False
    assert is_lowercase_ulid(123) is False
    assert is_lowercase_ulid(None) is False


def test_create_generates_lowercase_ulid_when_project_id_omitted(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    created = _create(repo, writer, project_id=None)
    assert is_lowercase_ulid(created.id) is True
    row = _project_row(writer, created.id)
    assert row["id"] == created.id
    # The aggregate id of the core.project stream is the generated ULID.
    stream = _stream_row(writer, f"{created.id}:core.project")
    assert stream["aggregate_id"] == created.id


# ---------------------------------------------------------------------------
# Slug validation and uniqueness
# ---------------------------------------------------------------------------


def test_slug_validation_rejects_invalid_slugs_before_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    invalid_slugs = [
        "",
        "Pilot",
        "pilot project",
        "-pilot",
        "pilot-",
        "pi--lot",
        "pilot_1",
        None,
        123,
    ]
    for slug in invalid_slugs:
        with pytest.raises(ProjectValidationError, match="slug"):
            _create(repo, writer, slug=slug)
    # Every rejection happened before any row was written.
    assert _row_counts(writer) == (0, 0, 0, 0)


def test_slug_validation_accepts_valid_grammar(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    for index, slug in enumerate(
        ["pilot", "a", "my-project-2", "x1-y2", "abc123"]
    ):
        created = _create(
            repo,
            writer,
            slug=slug,
            idempotency_key=f"valid-k-{index}",
        )
        assert created.slug == slug
    assert _row_counts(writer) == (5, 5, 5, 5)


def test_name_settings_actor_and_key_validation_before_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    cases = [
        ({"name": ""}, "name"),
        ({"name": None}, "name"),
        ({"settings": [1, 2]}, "settings"),
        ({"settings": "not-an-object"}, "settings"),
        ({"settings": {"fps": float("nan")}}, "cannot canonicalize"),
        ({"actor_kind": "remote"}, "actor_kind"),
        ({"idempotency_key": ""}, "idempotency_key"),
        ({"idempotency_key": None}, "idempotency_key"),
    ]
    for overrides, match in cases:
        with pytest.raises(ProjectValidationError, match=match):
            _create(repo, writer, **overrides)
    assert _row_counts(writer) == (0, 0, 0, 0)


def test_slug_uniqueness_rejected_with_zero_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    first = _create(repo, writer)
    with pytest.raises(ProjectSlugConflictError, match="already in use"):
        _create(
            repo,
            writer,
            slug="pilot",
            idempotency_key="create-k-2",
            project_id=generate_lowercase_ulid(),
        )
    assert _row_counts(writer) == (1, 1, 1, 1)
    assert _project_row(writer, first.id)["slug"] == "pilot"


def test_duplicate_project_id_rejected_with_zero_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    first = _create(repo, writer)
    with pytest.raises(ProjectAlreadyExistsError, match="already exists"):
        _create(
            repo,
            writer,
            slug="another",
            idempotency_key="create-k-2",
            project_id=first.id,
        )
    assert _row_counts(writer) == (1, 1, 1, 1)
    assert _project_row(writer, first.id)["slug"] == "pilot"


# ---------------------------------------------------------------------------
# Stable project-scoped replay
# ---------------------------------------------------------------------------


def test_stable_project_scoped_replay_returns_exact_stored_result(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    args = {
        "slug": "pilot",
        "name": "Pilot",
        "settings": {"fps": 24, "nested": {"a": [1, 2]}},
        "idempotency_key": "stable-k-1",
        "project_id": stable_id,
    }
    first = _create(repo, writer, **args)
    assert _row_counts(writer) == (1, 1, 1, 1)

    # Identical retry with the same stable project id: exactly the stored
    # complete result, zero new rows, heads untouched.
    replayed = _create(repo, writer, **args)
    assert replayed == first
    assert replayed.to_dict() == first.to_dict()
    assert _row_counts(writer) == (1, 1, 1, 1)
    assert _project_row(writer, stable_id)["event_head_seq"] == 1

    # The replay result is exactly what was persisted as the receipt result.
    receipt = _receipt_row(writer, stable_id, "stable-k-1")
    assert json.loads(receipt["result_json"]) == first.to_dict()

    # The immutable read model reads back identically through get().
    assert _get(repo, writer, stable_id) == first


def test_replay_is_scoped_to_project(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    first = _create(repo, writer, idempotency_key="shared-k")
    # Same idempotency key under a different project id is a *new* command:
    # receipts are keyed on the (project_id, idempotency_key) pair.
    second = _create(
        repo,
        writer,
        idempotency_key="shared-k",
        project_id=generate_lowercase_ulid(),
        slug="second",
    )
    assert second.id != first.id
    assert _row_counts(writer) == (2, 2, 2, 2)
    # Each project has exactly its own stream, event, and receipt.
    for project_id in (first.id, second.id):
        stream = _stream_row(writer, f"{project_id}:core.project")
        assert stream["project_id"] == project_id
        assert _event_row(writer, stream["id"])["project_id"] == project_id
        assert _receipt_row(writer, project_id, "shared-k")["project_id"] == project_id


# ---------------------------------------------------------------------------
# Mismatched-key rejection before mutation
# ---------------------------------------------------------------------------


def test_mismatched_key_rejected_before_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(
        repo,
        writer,
        slug="pilot",
        name="Pilot",
        idempotency_key="mismatch-k",
        project_id=stable_id,
    )
    assert _row_counts(writer) == (1, 1, 1, 1)

    # Same project and key, changed request: rejected before any allocation.
    with pytest.raises(ReceiptMismatchError, match="different request"):
        _create(
            repo,
            writer,
            slug="changed",
            name="Pilot",
            idempotency_key="mismatch-k",
            project_id=stable_id,
        )

    # Zero mutation: row counts, both heads, and the stored slug are unchanged.
    assert _row_counts(writer) == (1, 1, 1, 1)
    assert _project_row(writer, stable_id)["event_head_seq"] == 1
    assert _stream_row(writer, f"{stable_id}:core.project")["head_seq"] == 1
    assert _project_row(writer, stable_id)["slug"] == "pilot"
    assert _get(repo, writer, stable_id).slug == "pilot"


# ---------------------------------------------------------------------------
# Stream association
# ---------------------------------------------------------------------------


def test_create_persists_stream_and_event_association(
    repo: ProjectRepository, writer: DatabaseWriter, core_registry
) -> None:
    stable_id = generate_lowercase_ulid()
    created = _create(
        repo,
        writer,
        project_id=stable_id,
        idempotency_key="stream-k",
    )
    stream_id = f"{stable_id}:core.project"
    assert created.event_head_seq == 1

    # Exactly one core.project stream per project, aggregate == project.
    stream = _stream_row(writer, stream_id)
    assert stream is not None
    assert stream["project_id"] == stable_id
    assert stream["stream_type"] == "core.project"
    assert stream["aggregate_id"] == stable_id
    assert stream["head_seq"] == 1
    assert stream["created_at"] == TS

    # Exactly one registered core.project.created event on that stream.
    event = _event_row(writer, stream_id)
    assert event is not None
    assert event["stream_id"] == stream_id
    assert event["project_id"] == stable_id
    assert event["project_seq"] == 1
    assert event["seq"] == 1
    assert event["kind"] == "core.project.created"
    assert event["subject_type"] == "project"
    assert event["subject_id"] == stable_id
    assert event["actor_kind"] == "local"
    assert event["schema_version"] == 1
    assert event["idempotency_key"] == "stream-k"
    assert event["created_at"] == TS
    assert _UUID4_HEX_RE.fullmatch(event["event_id"]) is not None
    assert json.loads(event["changes_json"]) == ["slug", "name", "settings"]

    # Canonical SD2 payload envelope with a genesis chain link.
    payload = json.loads(event["payload_json"])
    assert payload["data"] == {
        "slug": "pilot",
        "name": "Pilot",
        "settings": {"fps": 24},
    }
    integrity = payload["_integrity"]
    assert integrity["previous_event_hash"] is None
    assert _SHA256_HEX_RE.fullmatch(integrity["event_hash"]) is not None

    # Genesis-to-head verification recomputes the chain and agrees.
    verification = EventAppendService(core_registry).verify_stream(
        writer, stream_id
    )
    assert verification.event_count == 1
    assert verification.head_seq == 1
    assert verification.head_hash == integrity["event_hash"]


# ---------------------------------------------------------------------------
# Full receipt contents
# ---------------------------------------------------------------------------


def test_create_persists_complete_receipt_contents(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    settings = {"fps": 24, "labels": ["a", "b"]}
    created = _create(
        repo,
        writer,
        slug="pilot",
        name="Pilot",
        settings=settings,
        idempotency_key="receipt-k",
        project_id=stable_id,
    )
    stream_id = f"{stable_id}:core.project"
    event = _event_row(writer, stream_id)
    receipt = _receipt_row(writer, stable_id, "receipt-k")

    # The stored request hash recomputes from the semantic request.
    expected_hash = request_hash(
        "core.project.create",
        {
            "project_id": stable_id,
            "slug": "pilot",
            "name": "Pilot",
            "settings": settings,
        },
    )
    assert receipt["request_hash"] == expected_hash
    assert _SHA256_HEX_RE.fullmatch(receipt["request_hash"]) is not None

    assert receipt["project_id"] == stable_id
    assert receipt["idempotency_key"] == "receipt-k"
    assert receipt["command_kind"] == "core.project.create"
    assert _UUID4_HEX_RE.fullmatch(receipt["txn_id"]) is not None
    assert receipt["txn_id"] == event["txn_id"]
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 1
    assert receipt["first_project_seq"] == 1
    assert receipt["last_project_seq"] == 1
    assert receipt["created_at"] == TS

    # Ordered event ids name exactly the one committed event.
    assert json.loads(receipt["event_ids_json"]) == [event["event_id"]]

    # The complete result is the immutable read model's JSON-safe dict.
    assert json.loads(receipt["result_json"]) == created.to_dict()


# ---------------------------------------------------------------------------
# Absence of a filesystem project authority
# ---------------------------------------------------------------------------


def test_no_filesystem_project_authority(
    repo: ProjectRepository,
    writer: DatabaseWriter,
    core_registry,
    tmp_path: Path,
) -> None:
    created = _create(repo, writer, project_id=generate_lowercase_ulid())

    db_path = tmp_path / "kernel.sqlite3"
    assert db_path.is_file()

    def non_database_files() -> list[Path]:
        return [
            path
            for path in tmp_path.rglob("*")
            if path.is_file()
            and path.name
            not in {
                "kernel.sqlite3",
                "kernel.sqlite3-wal",
                "kernel.sqlite3-shm",
            }
        ]

    # While the writer is open the only artifacts are the database and its
    # WAL sidecars: no project JSON/JSONL/YAML or any other authority file.
    assert non_database_files() == []

    # After a clean close even the sidecars are checkpointed away.
    writer.close()
    assert non_database_files() == []

    # Restart durability: the read model is reconstructed from the database
    # alone — there is no filesystem project authority to consult.
    reopened = DatabaseWriter(db_path, core_registry)
    try:
        assert _get(repo, reopened, created.id) == created
    finally:
        reopened.close()
    assert non_database_files() == []


# ---------------------------------------------------------------------------
# Plan step 12: sorted read-only list/show, typed not-found, eventful update
# ---------------------------------------------------------------------------


def test_list_returns_sorted_read_only_rows(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    # A root with no projects is an empty list, never an authority view.
    assert repo.list(writer) == []

    for index, (slug, name) in enumerate(
        [
            ("zulu", "Zulu"),
            ("alpha", "Alpha"),
            ("mid-2", "Mid 2"),
            ("alpha-1", "Alpha 1"),
            ("beta", "Beta"),
        ]
    ):
        _create(
            repo,
            writer,
            slug=slug,
            name=name,
            idempotency_key=f"list-k-{index}",
        )

    rows = repo.list(writer)
    assert [row.slug for row in rows] == [
        "alpha",
        "alpha-1",
        "beta",
        "mid-2",
        "zulu",
    ]
    assert [row.name for row in rows] == [
        "Alpha",
        "Alpha 1",
        "Beta",
        "Mid 2",
        "Zulu",
    ]
    # The frozen runtime GET /projects row shape: exactly {slug, name}.
    assert [row.to_dict() for row in rows] == [
        {"slug": "alpha", "name": "Alpha"},
        {"slug": "alpha-1", "name": "Alpha 1"},
        {"slug": "beta", "name": "Beta"},
        {"slug": "mid-2", "name": "Mid 2"},
        {"slug": "zulu", "name": "Zulu"},
    ]
    # Reads never mutate: counts and heads are untouched.
    assert _row_counts(writer) == (5, 5, 5, 5)


def test_show_returns_typed_read_model_and_raises_not_found(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    created = _create(repo, writer, project_id=generate_lowercase_ulid())

    shown = repo.show(writer, created.id)
    assert shown == created
    # The transaction-free show agrees with the UoW-context get() path.
    assert shown == _get(repo, writer, created.id)

    missing = generate_lowercase_ulid()
    with pytest.raises(ProjectNotFoundError) as excinfo:
        repo.show(writer, missing)
    assert excinfo.value.project_id == missing
    # A missing project never becomes an empty authority-dependent view:
    # the list still shows exactly the one real project.
    assert repo.list(writer) == [
        ProjectSummary(slug=created.slug, name=created.name)
    ]

    with pytest.raises(ProjectValidationError, match="project_id"):
        repo.show(writer, "")
    assert _row_counts(writer) == (1, 1, 1, 1)


def test_list_and_show_open_no_writer_transactions(
    repo: ProjectRepository,
    writer: DatabaseWriter,
    monkeypatch,
) -> None:
    created = _create(repo, writer, project_id=generate_lowercase_ulid())
    begins = _install_begin_spy(monkeypatch)

    repo.list(writer)
    repo.show(writer, created.id)
    # No BEGIN IMMEDIATE (and therefore no commit/rollback) was opened.
    assert begins == []
    # The writer session itself is never inside a transaction after reads.
    assert writer.submit(lambda session: session.in_transaction) is False
    # Reads change nothing: counts, both heads, and stored bytes.
    assert _row_counts(writer) == (1, 1, 1, 1)
    assert _project_row(writer, created.id)["event_head_seq"] == 1
    assert _stream_row(writer, f"{created.id}:core.project")["head_seq"] == 1


def test_update_name_is_eventful_chained_and_receipted(
    repo: ProjectRepository, writer: DatabaseWriter, core_registry
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(
        repo,
        writer,
        project_id=stable_id,
        idempotency_key="create-k",
        created_at=TS,
    )
    stream_id = f"{stable_id}:core.project"
    create_event = _event_row(writer, stream_id)

    updated = _update(
        repo,
        writer,
        stable_id,
        name="Pilot Renamed",
        settings=None,
        idempotency_key="update-k-1",
        created_at=TS2,
    )
    assert updated.name == "Pilot Renamed"
    assert updated.settings == {"fps": 24}  # unchanged settings
    assert updated.event_head_seq == 2
    assert updated.created_at == TS
    assert updated.updated_at == TS2

    # The projection row reflects the new name and stamp.
    row = _project_row(writer, stable_id)
    assert row["name"] == "Pilot Renamed"
    assert json.loads(row["settings_json"]) == {"fps": 24}
    assert row["updated_at"] == TS2
    assert row["event_head_seq"] == 2

    # Exactly one core.project.updated event, chained from the create event.
    events = _events(writer, stream_id)
    assert [event["kind"] for event in events] == [
        "core.project.created",
        "core.project.updated",
    ]
    second = events[1]
    assert second["seq"] == 2
    assert second["project_seq"] == 2
    assert json.loads(second["changes_json"]) == ["name"]
    payload = json.loads(second["payload_json"])
    assert payload["data"] == {
        "name": "Pilot Renamed",
        "settings": {"fps": 24},
    }
    integrity = payload["_integrity"]
    first_payload = json.loads(create_event["payload_json"])
    assert (
        integrity["previous_event_hash"]
        == first_payload["_integrity"]["event_hash"]
    )
    assert integrity["event_hash"] != integrity["previous_event_hash"]

    # Both heads advanced; genesis-to-head verification recomputes the chain.
    assert _stream_row(writer, stream_id)["head_seq"] == 2
    verification = EventAppendService(core_registry).verify_stream(
        writer, stream_id
    )
    assert verification.event_count == 2
    assert verification.head_seq == 2
    assert verification.head_hash == integrity["event_hash"]

    # The complete update receipt.
    receipt = _receipt_row(writer, stable_id, "update-k-1")
    expected_hash = request_hash(
        "core.project.update",
        {"project_id": stable_id, "name": "Pilot Renamed", "settings": None},
    )
    assert receipt["request_hash"] == expected_hash
    assert _SHA256_HEX_RE.fullmatch(receipt["request_hash"]) is not None
    assert receipt["command_kind"] == "core.project.update"
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2
    assert receipt["first_project_seq"] == 2
    assert receipt["last_project_seq"] == 2
    assert json.loads(receipt["event_ids_json"]) == [second["event_id"]]
    assert json.loads(receipt["result_json"]) == updated.to_dict()


def test_update_settings_preserves_repository_owned_default_timeline(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(repo, writer, project_id=stable_id, idempotency_key="create-k")
    _set_default(repo, writer, stable_id, "tl-1", idempotency_key="default-k")

    # Caller settings merge over the current state; the owned key survives.
    updated = _update(
        repo,
        writer,
        stable_id,
        name=None,
        settings={"fps": 30, "labels": ["x"]},
        idempotency_key="update-settings-k",
    )
    assert updated.settings == {
        "fps": 30,
        "labels": ["x"],
        "default_timeline_id": "tl-1",
    }
    assert updated.default_timeline_id == "tl-1"

    # The projection stores the merged settings.
    row = _project_row(writer, stable_id)
    assert json.loads(row["settings_json"]) == updated.settings
    # create(1) + set_default(2) + update(3): both heads at 3.
    assert _stream_row(writer, f"{stable_id}:core.project")["head_seq"] == 3

    # A caller cannot write the repository-owned key directly.
    with pytest.raises(ProjectValidationError, match="repository-owned"):
        _update(
            repo,
            writer,
            stable_id,
            settings={"default_timeline_id": "tl-other"},
            idempotency_key="update-owned-k",
        )
    with pytest.raises(ProjectValidationError, match="repository-owned"):
        _create(
            repo,
            writer,
            slug="second",
            idempotency_key="create-owned-k",
            project_id=generate_lowercase_ulid(),
            settings={"default_timeline_id": "tl-x"},
        )
    assert _row_counts(writer) == (1, 1, 3, 3)


def test_set_default_timeline_is_eventful_and_idempotent_in_effect(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(repo, writer, project_id=stable_id, idempotency_key="create-k")
    stream_id = f"{stable_id}:core.project"

    updated = _set_default(repo, writer, stable_id, "tl-9")
    assert updated.settings == {"fps": 24, "default_timeline_id": "tl-9"}
    assert updated.default_timeline_id == "tl-9"
    assert updated.event_head_seq == 2

    events = _events(writer, stream_id)
    assert len(events) == 2
    assert events[1]["kind"] == "core.project.updated"
    assert json.loads(events[1]["changes_json"]) == ["settings"]
    payload = json.loads(events[1]["payload_json"])
    assert payload["data"] == {
        "name": "Pilot",
        "settings": {"fps": 24, "default_timeline_id": "tl-9"},
    }

    # Setting the same default again is a no-op: same model, zero new rows.
    again = _set_default(
        repo, writer, stable_id, "tl-9", idempotency_key="default-k-2"
    )
    assert again == updated
    assert _row_counts(writer) == (1, 1, 2, 2)
    assert _project_row(writer, stable_id)["event_head_seq"] == 2
    assert _stream_row(writer, stream_id)["head_seq"] == 2


def test_update_replay_returns_stored_result_and_mismatch_rejected(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(repo, writer, project_id=stable_id, idempotency_key="create-k")
    args = {
        "name": "Renamed",
        "settings": {"fps": 25},
        "idempotency_key": "update-replay-k",
        "created_at": TS2,
    }
    first = _update(repo, writer, stable_id, **args)
    assert _row_counts(writer) == (1, 1, 2, 2)

    # Identical retry: exactly the stored result, zero new rows.
    replayed = _update(repo, writer, stable_id, **args)
    assert replayed == first
    assert _row_counts(writer) == (1, 1, 2, 2)
    assert _project_row(writer, stable_id)["event_head_seq"] == 2

    # Changed request under the same key: rejected before mutation.
    with pytest.raises(ReceiptMismatchError, match="different request"):
        _update(
            repo,
            writer,
            stable_id,
            name="Different",
            settings={"fps": 25},
            idempotency_key="update-replay-k",
        )
    assert _row_counts(writer) == (1, 1, 2, 2)
    assert _project_row(writer, stable_id)["name"] == "Renamed"
    assert _get(repo, writer, stable_id).name == "Renamed"


def test_noop_update_rejected_before_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(repo, writer, project_id=stable_id, idempotency_key="create-k")
    with pytest.raises(ProjectValidationError, match="unchanged"):
        _update(
            repo,
            writer,
            stable_id,
            name="Pilot",
            settings={"fps": 24},
            idempotency_key="noop-k",
        )
    assert _row_counts(writer) == (1, 1, 1, 1)


def test_update_validation_and_not_found_before_mutation(
    repo: ProjectRepository, writer: DatabaseWriter
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(repo, writer, project_id=stable_id, idempotency_key="create-k")

    missing = generate_lowercase_ulid()
    with pytest.raises(ProjectNotFoundError) as excinfo:
        _update(repo, writer, missing, idempotency_key="missing-k")
    assert excinfo.value.project_id == missing

    cases = [
        ({"name": ""}, "name"),
        ({"settings": [1, 2]}, "settings"),
        ({"settings": "not-an-object"}, "settings"),
        ({"settings": {"fps": float("nan")}}, "cannot canonicalize"),
        ({"actor_kind": "remote"}, "actor_kind"),
        ({"idempotency_key": ""}, "idempotency_key"),
    ]
    for overrides, match in cases:
        with pytest.raises(ProjectValidationError, match=match):
            _update(repo, writer, stable_id, **overrides)
    assert _row_counts(writer) == (1, 1, 1, 1)


def test_restart_durability_with_transaction_free_reads(
    repo: ProjectRepository,
    writer: DatabaseWriter,
    core_registry,
    tmp_path: Path,
    monkeypatch,
) -> None:
    stable_id = generate_lowercase_ulid()
    _create(repo, writer, project_id=stable_id, idempotency_key="create-k")
    _set_default(
        repo, writer, stable_id, "tl-default", idempotency_key="default-k"
    )
    updated = _update(
        repo,
        writer,
        stable_id,
        name="Durable Name",
        settings={"fps": 60},
        idempotency_key="update-k",
        created_at=TS2,
    )
    assert updated.default_timeline_id == "tl-default"
    stream_id = f"{stable_id}:core.project"
    assert _stream_row(writer, stream_id)["head_seq"] == 3

    db_path = tmp_path / "kernel.sqlite3"

    def non_database_files() -> list[Path]:
        return [
            path
            for path in tmp_path.rglob("*")
            if path.is_file()
            and path.name
            not in {
                "kernel.sqlite3",
                "kernel.sqlite3-wal",
                "kernel.sqlite3-shm",
            }
        ]

    # Clean close checkpoints the WAL; no authority files ever appear.
    writer.close()
    assert non_database_files() == []

    # Restart: transaction-free reads reconstruct the full updated state.
    reopened = DatabaseWriter(db_path, core_registry)
    try:
        begins = _install_begin_spy(monkeypatch)
        shown = repo.show(reopened, stable_id)
        rows = repo.list(reopened)
        assert begins == []
        assert shown == updated
        assert shown.name == "Durable Name"
        assert shown.settings == {
            "fps": 60,
            "default_timeline_id": "tl-default",
        }
        assert shown.default_timeline_id == "tl-default"
        assert shown.event_head_seq == 3
        assert rows == [ProjectSummary(slug="pilot", name="Durable Name")]
        assert reopened.submit(lambda session: session.in_transaction) is False

        # The full event chain survives the restart.
        verification = EventAppendService(core_registry).verify_stream(
            reopened, stream_id
        )
        assert verification.event_count == 3
        assert verification.head_seq == 3
    finally:
        reopened.close()
    assert non_database_files() == []
