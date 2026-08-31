"""Executable m4 domain-contract tests (plan Step 3 / task T3).

Proves the frozen SDK platform contract is
implemented exactly by ``astrid.sdk.contracts``, ``astrid.sdk.exceptions``,
and ``astrid.core.receipts.service``:

- the domain result envelope is immutable, has exactly the five keys
  ``ok``/``data``/``error``/``receipt``/``idempotency_key``, enforces the
  frozen invariants (``ok`` true implies ``error`` null; ``ok`` false
  implies ``data`` null and a frozen error object), and serializes
  **losslessly** through ``to_json``/``from_json``;
- the error object has exactly ``code``/``message``/``details``, the nine
  frozen machine codes are the complete taxonomy, and details stay bounded;
- the command receipt is read-only, has exactly the nine exposed keys, and
  round-trips losslessly;
- caller-supplied idempotency keys are preserved, absent keys are generated
  before mutation, and stable derived ids depend only on
  (command kind, scope, key, ordinal);
- committed-receipt lookup is read-only (no transaction, no writes), an
  identical retry replays the stored result with zero new rows, and a
  changed request under the same key raises ``idempotency_mismatch``
  **before any mutation**;
- ``map_error`` centralizes the bounded mapping of kernel exceptions to the
  frozen taxonomy and redacts paths, secrets, and excess length from
  ``internal_error`` messages and details.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.receipts.contract import CommandReceipt
from astrid.core.receipts.canonical import canonical_json
from astrid.core.receipts.service import (
    ReceiptMismatchError,
    ReceiptService,
    ReceiptValidationError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk import exceptions as sdk_exceptions
from astrid.sdk.contracts import (
    ENVELOPE_KEYS,
    ERROR_OBJECT_KEYS,
    DomainResult,
    ErrorObject,
    derive_stable_id,
    generate_idempotency_key,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import (
    MAX_ERROR_MESSAGE_LENGTH,
    ServiceError,
    ServiceInternalError,
    ServiceNotFoundError,
    ServiceValidationError,
    map_error,
)

TS = "2026-08-18T00:00:00.000000+00:00"

ENVELOPE_KEY_SET = frozenset(ENVELOPE_KEYS)
ERROR_OBJECT_KEY_SET = frozenset(ERROR_OBJECT_KEYS)
ERROR_CODES = frozenset(
    {
        "validation_error",
        "not_found",
        "conflict",
        "stale_version",
        "terminal_state",
        "idempotency_mismatch",
        "integrity_error",
        "unavailable",
        "internal_error",
    }
)


def _receipt(**overrides: object) -> CommandReceipt:
    """Build a minimal valid immutable receipt for envelope tests."""
    values: dict[str, object] = {
        "receipt_id": "txn-1",
        "command_kind": "timeline.save",
        "idempotency_key": "k1",
        "request_hash": "h1",
        "project_id": "p1",
        "project_seq": (1, 2),
        "event_ids": ("e1", "e2"),
        "result": {"config_version": 3},
        "created_at": TS,
    }
    values.update(overrides)
    return CommandReceipt(**values)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Local writer fixture (kernel-only database, no packs)
# ---------------------------------------------------------------------------


@pytest.fixture
def writer(tmp_path: Path):
    """A fresh writer over a kernel-only database for receipt tests."""
    w = DatabaseWriter(tmp_path / "contracts.sqlite3", core_only_registry())
    try:
        yield w
    finally:
        w.close()


def _seed_project(writer: DatabaseWriter, project_id: str = "p1") -> None:
    UnitOfWork(writer).run(
        lambda uow: uow.execute(
            "INSERT INTO projects (id, slug, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, project_id, project_id, TS, TS),
        )
    )


def _record_receipt(
    writer: DatabaseWriter,
    *,
    project_id: str = "p1",
    idempotency_key: str = "k1",
    request_hash: str = "h1",
    command_kind: str = "core.project.create",
    result: object = {"project_id": "p1"},
    txn_id: str = "txn-1",
    event_ids: tuple[str, ...] = ("e1", "e2"),
) -> None:
    receipts = ReceiptService()
    UnitOfWork(writer).run(
        lambda uow: receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=1,
            last_project_seq=2,
            event_ids=event_ids,
            result=result,
        )
    )


# ---------------------------------------------------------------------------
# 1. Domain result envelope: exact keys, invariants, immutability
# ---------------------------------------------------------------------------


def test_envelope_serializes_to_exactly_five_keys() -> None:
    result = DomainResult.success(
        {"project_id": "p1"}, receipt=_receipt(), idempotency_key="k1"
    )
    assert set(result.as_dict().keys()) == ENVELOPE_KEY_SET
    assert set(json.loads(result.to_json()).keys()) == ENVELOPE_KEY_SET


def test_envelope_success_invariants() -> None:
    ok = DomainResult.success({"a": 1}, idempotency_key="k")
    assert ok.ok is True
    assert ok.data == {"a": 1}
    assert ok.error is None
    assert ok.receipt is None
    assert ok.idempotency_key == "k"
    with pytest.raises(ValueError, match="ok=True requires error=None"):
        DomainResult(ok=True, data=1, error=ErrorObject(
            code="not_found", message="x", details={}
        ), receipt=None, idempotency_key="k")


def test_envelope_failure_invariants() -> None:
    err = ErrorObject(code="not_found", message="missing", details={})
    failed = DomainResult.failure(err, idempotency_key="k")
    assert failed.ok is False
    assert failed.data is None
    assert failed.error == err
    assert failed.receipt is None
    with pytest.raises(ValueError, match="ok=False requires data=None"):
        DomainResult(ok=False, data=1, error=err, receipt=None, idempotency_key="k")
    with pytest.raises(ValueError, match="ok=False requires a frozen error object"):
        DomainResult(ok=False, data=None, error=None, receipt=None, idempotency_key="k")


def test_envelope_rejects_extra_or_missing_keys() -> None:
    base = {
        "ok": True,
        "data": {"a": 1},
        "error": None,
        "receipt": None,
        "idempotency_key": "k",
    }
    with pytest.raises(ValueError, match="exactly the keys"):
        DomainResult.from_dict({**base, "extra": 1})
    with pytest.raises(ValueError, match="exactly the keys"):
        DomainResult.from_dict({k: v for k, v in base.items() if k != "ok"})


def test_envelope_lossless_json_round_trip_with_receipt_and_error() -> None:
    ok = DomainResult.success(
        {"project_id": "p1", "nested": {"list": [1, 2, 3]}},
        receipt=_receipt(result={"config_version": 3, "registry": {"a": 1}}),
        idempotency_key="k1",
    )
    assert DomainResult.from_json(ok.to_json()) == ok
    failed = DomainResult.failure(
        ErrorObject(
            code="stale_version",
            message="stale head",
            details={"expected_version": 2, "current_version": 5},
        ),
        idempotency_key="k2",
    )
    assert DomainResult.from_json(failed.to_json()) == failed


def test_envelope_is_immutable() -> None:
    result = DomainResult.success({"a": 1}, idempotency_key="k")
    with pytest.raises(AttributeError):
        result.ok = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.data = {"changed": True}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. Error object and the closed nine-code taxonomy
# ---------------------------------------------------------------------------


def test_error_object_has_exactly_three_keys_and_round_trips() -> None:
    err = ErrorObject(
        code="conflict",
        message="duplicate",
        details={"project_id": "p1"},
    )
    assert set(err.as_dict().keys()) == ERROR_OBJECT_KEY_SET
    assert set(json.loads(err.to_json()).keys()) == ERROR_OBJECT_KEY_SET
    assert ErrorObject.from_json(err.to_json()) == err
    with pytest.raises(ValueError, match="exactly the keys"):
        ErrorObject.from_dict({"code": "conflict", "message": "x"})


def test_service_error_taxonomy_is_exactly_the_nine_frozen_codes() -> None:
    instances = [
        sdk_exceptions.ServiceValidationError("v"),
        sdk_exceptions.ServiceNotFoundError("n"),
        sdk_exceptions.ServiceConflictError("c"),
        sdk_exceptions.ServiceStaleVersionError("s"),
        sdk_exceptions.ServiceTerminalStateError("t"),
        sdk_exceptions.ServiceIdempotencyMismatchError("i"),
        sdk_exceptions.ServiceIntegrityError("g"),
        sdk_exceptions.ServiceUnavailableError("u"),
        sdk_exceptions.ServiceInternalError("x"),
    ]
    codes = {error.code for error in instances}
    assert codes == ERROR_CODES
    for error in instances:
        assert isinstance(error, ServiceError)
        assert isinstance(error, sdk_exceptions.AstridSDKError)
        obj = error.to_error_object()
        assert set(obj.as_dict().keys()) == ERROR_OBJECT_KEY_SET
        assert obj.code == error.code


def test_service_error_details_are_bounded_and_redacted() -> None:
    err = ServiceValidationError(
        "bad input",
        details={"project_id": "p1", "api_key": "sk-abcdefghijklmnop123456"},
    )
    assert err.details["project_id"] == "p1"
    assert err.details["api_key"] == "<redacted>"
    # The error object serializes as bounded JSON.
    assert canonical_json(err.to_error_object().as_dict())


# ---------------------------------------------------------------------------
# 3. Immutable command receipt: exact shape, read-only, lossless
# ---------------------------------------------------------------------------


def test_receipt_has_exactly_nine_keys_and_is_read_only() -> None:
    receipt = _receipt()
    assert set(receipt.as_dict().keys()) == {
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
    assert isinstance(receipt.project_seq, tuple)
    assert isinstance(receipt.event_ids, tuple)
    with pytest.raises(AttributeError):
        receipt.receipt_id = "other"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        receipt.event_ids = ("x",)  # type: ignore[misc]


def test_receipt_lossless_json_round_trip() -> None:
    receipt = _receipt(result={"config_version": 3, "registry": {"layers": []}})
    restored = CommandReceipt.from_json(receipt.to_json())
    assert restored == receipt
    assert restored.as_dict() == receipt.as_dict()
    with pytest.raises(ReceiptValidationError, match="exactly the keys"):
        CommandReceipt.from_dict({"receipt_id": "x"})


def test_receipt_validation_rejects_invalid_ranges_and_ids() -> None:
    with pytest.raises(ReceiptValidationError, match="project_seq"):
        _receipt(project_seq=(2, 1))
    with pytest.raises(ReceiptValidationError, match="project_seq"):
        _receipt(project_seq=(0, 1))
    with pytest.raises(ReceiptValidationError, match="event_ids"):
        _receipt(event_ids=("", "e2"))
    with pytest.raises(ReceiptValidationError, match="receipt_id"):
        _receipt(receipt_id="")


# ---------------------------------------------------------------------------
# 4. Idempotency keys and stable derived ids
# ---------------------------------------------------------------------------


def test_caller_supplied_key_is_preserved_and_generated_key_is_fresh() -> None:
    assert resolve_idempotency_key("caller-key") == "caller-key"
    first = resolve_idempotency_key(None)
    second = resolve_idempotency_key(None)
    assert isinstance(first, str) and first
    assert first != second
    assert generate_idempotency_key() != generate_idempotency_key()
    with pytest.raises(ValueError, match="non-empty string"):
        resolve_idempotency_key("")


def test_stable_derived_ids_depend_only_on_kind_scope_key_ordinal() -> None:
    base = dict(command_kind="timeline.save", scope="p1", idempotency_key="k1")
    first = derive_stable_id(**base, ordinal=0)
    assert first == derive_stable_id(**base, ordinal=0)
    # Every component participates in identity.
    assert derive_stable_id(**base, ordinal=1) != first
    assert derive_stable_id(**{**base, "idempotency_key": "k2"}) != first
    assert derive_stable_id(**{**base, "scope": "p2"}) != first
    assert derive_stable_id(**{**base, "command_kind": "timeline.load"}) != first
    with pytest.raises(ValueError, match="non-negative integer"):
        derive_stable_id(**base, ordinal=-1)
    with pytest.raises(ValueError, match="non-empty string"):
        derive_stable_id(**{**base, "idempotency_key": ""})


# ---------------------------------------------------------------------------
# 5. Read-only committed-receipt lookup, replay, mismatch-before-mutation
# ---------------------------------------------------------------------------


def test_lookup_committed_returns_complete_receipt_read_only(writer) -> None:
    _seed_project(writer)
    _record_receipt(writer)
    receipts = ReceiptService()
    with writer.read_only_connection() as conn:
        receipt = receipts.lookup_committed(conn, project_id="p1", idempotency_key="k1")
        assert receipt is not None
        assert receipt.receipt_id == "txn-1"
        assert receipt.command_kind == "core.project.create"
        assert receipt.project_seq == (1, 2)
        assert receipt.event_ids == ("e1", "e2")
        assert receipt.result == {"project_id": "p1"}
        assert receipt.request_hash == "h1"
        # Missing pairs and ids return None.
        assert receipts.lookup_committed(conn, project_id="p1", idempotency_key="nope") is None
        assert receipts.get_committed(conn, receipt_id="nope") is None
        assert receipts.get_committed(conn, receipt_id="txn-1") == receipt
    # The lookup performed zero writes: exactly one receipt row remains.
    count = writer.submit(lambda s: s.query_one("SELECT COUNT(*) FROM command_receipts")[0])
    assert count == 1


def test_identical_retry_replays_stored_result_with_zero_new_rows(writer) -> None:
    _seed_project(writer)
    _record_receipt(writer)
    receipts = ReceiptService()
    uow = UnitOfWork(writer)

    def replay(uow: UnitOfWork) -> object:
        return receipts.check(
            uow,
            project_id="p1",
            idempotency_key="k1",
            request_hash="h1",
            command_kind="core.project.create",
        )

    assert uow.run(replay) == {"project_id": "p1"}
    count = writer.submit(lambda s: s.query_one("SELECT COUNT(*) FROM command_receipts")[0])
    assert count == 1


def test_mismatch_raises_before_any_mutation(writer) -> None:
    _seed_project(writer)
    _record_receipt(writer)
    receipts = ReceiptService()

    def mismatch(uow: UnitOfWork) -> object:
        return receipts.check(
            uow,
            project_id="p1",
            idempotency_key="k1",
            request_hash="CHANGED-HASH",
            command_kind="core.project.create",
        )

    with pytest.raises(ReceiptMismatchError):
        UnitOfWork(writer).run(mismatch)
    # Mismatch performed zero mutation: the receipt row and project head
    # are unchanged.
    state = writer.submit(
        lambda s: s.query_one(
            "SELECT (SELECT COUNT(*) FROM command_receipts) AS receipts, "
            "event_head_seq FROM projects WHERE id = 'p1'"
        )
    )
    assert state["receipts"] == 1
    assert state["event_head_seq"] == 0


def test_mismatch_maps_to_idempotency_mismatch_before_mutation(writer) -> None:
    _seed_project(writer)
    _record_receipt(writer)
    receipts = ReceiptService()

    def mismatch(uow: UnitOfWork) -> object:
        return receipts.check(
            uow,
            project_id="p1",
            idempotency_key="k1",
            request_hash="CHANGED-HASH",
            command_kind="core.project.create",
        )

    with pytest.raises(ReceiptMismatchError) as exc_info:
        UnitOfWork(writer).run(mismatch)
    mapped = map_error(exc_info.value)
    assert mapped.code == "idempotency_mismatch"
    assert mapped.details == {"project_id": "p1", "idempotency_key": "k1"}
    assert set(mapped.as_dict().keys()) == ERROR_OBJECT_KEY_SET


# ---------------------------------------------------------------------------
# 6. Centralized bounded exception mapping with redaction
# ---------------------------------------------------------------------------


def test_map_error_passes_service_errors_through() -> None:
    err = ServiceNotFoundError("missing", details={"project_id": "p1"})
    mapped = map_error(err)
    assert mapped == err.to_error_object()
    assert mapped.code == "not_found"


def test_map_error_maps_known_kernel_errors_to_frozen_codes() -> None:
    from astrid.core.events.service import (
        EventChainError,
        EventHeadConflictError,
        EventStreamNotFoundError,
    )
    from astrid.core.repositories.media import MediaRelationError
    from astrid.core.repositories.projects import (
        ProjectAlreadyExistsError,
        ProjectNotFoundError,
    )
    from astrid.core.repositories.runs import RunTerminalError
    from astrid.core.store.writer import WriterShutdownError

    cases = [
        (ProjectNotFoundError(project_id="p1"), "not_found"),
        (EventStreamNotFoundError(stream_id="s1"), "not_found"),
        (ProjectAlreadyExistsError(project_id="p1"), "conflict"),
        (MediaRelationError(from_media_id="a", to_media_id="b", kind="x", reason="duplicate"), "validation_error"),
        (EventHeadConflictError(stream_id="s1", expected_head_seq=1, actual_head_seq=2), "stale_version"),
        (RunTerminalError(run_id="r1", status="succeeded"), "terminal_state"),
        (WriterShutdownError("writer closed"), "unavailable"),
        (EventChainError(stream_id="s1", position=2, reason="tampered"), "integrity_error"),
    ]
    for exc, code in cases:
        mapped = map_error(exc)
        assert mapped.code == code, f"{type(exc).__name__} mapped to {mapped.code}"
        assert set(mapped.as_dict().keys()) == ERROR_OBJECT_KEY_SET
        assert mapped.message  # stable non-empty message


def test_timeline_stale_version_mapping_is_actionable_and_typed() -> None:
    from astrid.packs.timeline.repository import TimelineVersionConflictError

    mapped = map_error(
        TimelineVersionConflictError(
            project_id="p1",
            timeline_id="timeline-1",
            expected_version=1,
            current_version=2,
        )
    )

    assert mapped.code == "stale_version"
    assert mapped.details == {"expected_version": 1, "current_version": 2}
    assert "no write occurred" in mapped.message
    assert "show the current timeline" in mapped.message
    assert "merge your changes" in mapped.message
    assert "config_version" in mapped.message
    assert "same idempotency key" in mapped.message
    assert "fresh key" in mapped.message
    assert len(mapped.message) < MAX_ERROR_MESSAGE_LENGTH


def test_map_error_maps_receipt_validation_to_validation_error() -> None:
    mapped = map_error(ReceiptValidationError("bad receipt"))
    assert mapped.code == "validation_error"


def test_map_error_redacts_paths_secrets_and_excess_length() -> None:
    long_junk = "x" * (MAX_ERROR_MESSAGE_LENGTH * 2)
    exc = ValueError(
        "failed at /tmp/secret/projects/p1/file.json with "
        "sk-abcdefghijklmnopqrstuvwxyz123456 " + long_junk
    )
    mapped = map_error(exc)
    assert mapped.code == "internal_error"
    assert "/tmp/secret" not in mapped.message
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in mapped.message
    assert len(mapped.message) <= MAX_ERROR_MESSAGE_LENGTH
    assert mapped.details == {"error_type": "ValueError"}
    # The mapped error object stays bounded JSON.
    assert canonical_json(mapped.as_dict())


def test_map_error_unknown_exception_is_bounded() -> None:
    mapped = map_error(RuntimeError("boom"))
    assert mapped.code == "internal_error"
    assert mapped.message == "boom"
    assert mapped.details == {"error_type": "RuntimeError"}


def test_service_error_constructor_redacts_details() -> None:
    err = ServiceInternalError(
        "kaboom", details={"token": "ghp_abcdefghijklmnopqrstuvwxyz123456"}
    )
    assert err.details["token"] == "<redacted>"
    mapped = map_error(err)
    assert mapped.code == "internal_error"
    assert mapped.details["token"] == "<redacted>"
