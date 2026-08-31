"""Supported SDK wire-contract tests.

These assertions cover the store-free public DTO/error surface.  Receipt
lookup/replay tests that depended on the retired local SQLite authority were
removed; generated-runtime round trips are covered by the SDK/rendering gates.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.receipts.canonical import canonical_json
from astrid.core.receipts.contract import CommandReceipt, ReceiptValidationError
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
ERROR_CODES = frozenset({
    "validation_error", "not_found", "conflict", "stale_version",
    "terminal_state", "idempotency_mismatch", "integrity_error",
    "unavailable", "internal_error",
})


def _receipt(**overrides: object) -> CommandReceipt:
    values: dict[str, object] = {
        "receipt_id": "txn-1", "command_kind": "timeline.save",
        "idempotency_key": "k1", "request_hash": "h1", "project_id": "p1",
        "project_seq": (1, 2), "event_ids": ("e1", "e2"),
        "result": {"config_version": 3}, "created_at": TS,
    }
    values.update(overrides)
    return CommandReceipt(**values)  # type: ignore[arg-type]


def test_envelope_serializes_to_exactly_five_keys() -> None:
    result = DomainResult.success({"project_id": "p1"}, receipt=_receipt(), idempotency_key="k1")
    assert set(result.as_dict()) == ENVELOPE_KEY_SET
    assert set(json.loads(result.to_json())) == ENVELOPE_KEY_SET


def test_envelope_success_and_failure_invariants() -> None:
    ok = DomainResult.success({"a": 1}, idempotency_key="k")
    assert (ok.ok, ok.data, ok.error, ok.receipt, ok.idempotency_key) == (True, {"a": 1}, None, None, "k")
    err = ErrorObject(code="not_found", message="missing", details={})
    failed = DomainResult.failure(err, idempotency_key="k")
    assert (failed.ok, failed.data, failed.error) == (False, None, err)
    with pytest.raises(ValueError, match="ok=True requires error=None"):
        DomainResult(ok=True, data=1, error=err, receipt=None, idempotency_key="k")
    with pytest.raises(ValueError, match="ok=False requires data=None"):
        DomainResult(ok=False, data=1, error=err, receipt=None, idempotency_key="k")
    with pytest.raises(ValueError, match="frozen error object"):
        DomainResult(ok=False, data=None, error=None, receipt=None, idempotency_key="k")


def test_envelope_rejects_shape_drift_and_is_immutable() -> None:
    base = {"ok": True, "data": {"a": 1}, "error": None, "receipt": None, "idempotency_key": "k"}
    with pytest.raises(ValueError, match="exactly the keys"):
        DomainResult.from_dict({**base, "extra": 1})
    with pytest.raises(ValueError, match="exactly the keys"):
        DomainResult.from_dict({key: value for key, value in base.items() if key != "ok"})
    result = DomainResult.success({"a": 1}, idempotency_key="k")
    with pytest.raises(AttributeError):
        result.ok = False  # type: ignore[misc]


def test_envelope_lossless_json_round_trip_with_receipt_and_error() -> None:
    ok = DomainResult.success(
        {"project_id": "p1", "nested": {"list": [1, 2, 3]}},
        receipt=_receipt(result={"config_version": 3, "registry": {"a": 1}}),
        idempotency_key="k1",
    )
    assert DomainResult.from_json(ok.to_json()) == ok
    failed = DomainResult.failure(
        ErrorObject("stale_version", "stale head", {"expected_version": 2, "current_version": 5}),
        idempotency_key="k2",
    )
    assert DomainResult.from_json(failed.to_json()) == failed


def test_error_object_has_exactly_three_keys_and_round_trips() -> None:
    err = ErrorObject("conflict", "duplicate", {"project_id": "p1"})
    assert set(err.as_dict()) == ERROR_OBJECT_KEY_SET
    assert ErrorObject.from_json(err.to_json()) == err
    with pytest.raises(ValueError, match="exactly the keys"):
        ErrorObject.from_dict({"code": "conflict", "message": "x"})


def test_service_error_taxonomy_is_exactly_the_nine_frozen_codes() -> None:
    instances = [
        sdk_exceptions.ServiceValidationError("v"), sdk_exceptions.ServiceNotFoundError("n"),
        sdk_exceptions.ServiceConflictError("c"), sdk_exceptions.ServiceStaleVersionError("s"),
        sdk_exceptions.ServiceTerminalStateError("t"), sdk_exceptions.ServiceIdempotencyMismatchError("i"),
        sdk_exceptions.ServiceIntegrityError("g"), sdk_exceptions.ServiceUnavailableError("u"),
        sdk_exceptions.ServiceInternalError("x"),
    ]
    assert {error.code for error in instances} == ERROR_CODES
    assert all(isinstance(error, ServiceError) for error in instances)
    assert all(set(error.to_error_object().as_dict()) == ERROR_OBJECT_KEY_SET for error in instances)


def test_service_error_details_are_bounded_and_redacted() -> None:
    err = ServiceValidationError("bad input", details={"project_id": "p1", "api_key": "sk-abcdefghijklmnop123456"})
    assert err.details["project_id"] == "p1"
    assert err.details["api_key"] == "<redacted>"
    assert canonical_json(err.to_error_object().as_dict())


def test_receipt_has_exact_shape_is_read_only_and_round_trips() -> None:
    receipt = _receipt(result={"config_version": 3, "registry": {"layers": []}})
    assert set(receipt.as_dict()) == {
        "receipt_id", "command_kind", "idempotency_key", "request_hash",
        "project_id", "project_seq", "event_ids", "result", "created_at",
    }
    assert isinstance(receipt.project_seq, tuple) and isinstance(receipt.event_ids, tuple)
    with pytest.raises(AttributeError):
        receipt.receipt_id = "other"  # type: ignore[misc]
    assert CommandReceipt.from_json(receipt.to_json()) == receipt
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


def test_caller_supplied_key_is_preserved_and_generated_key_is_fresh() -> None:
    assert resolve_idempotency_key("caller-key") == "caller-key"
    assert resolve_idempotency_key(None) != resolve_idempotency_key(None)
    assert generate_idempotency_key() != generate_idempotency_key()
    with pytest.raises(ValueError, match="non-empty string"):
        resolve_idempotency_key("")


def test_stable_derived_ids_depend_only_on_kind_scope_key_ordinal() -> None:
    base = dict(command_kind="timeline.save", scope="p1", idempotency_key="k1")
    first = derive_stable_id(**base, ordinal=0)
    assert first == derive_stable_id(**base, ordinal=0)
    assert derive_stable_id(**base, ordinal=1) != first
    assert derive_stable_id(**{**base, "idempotency_key": "k2"}, ordinal=0) != first
    assert derive_stable_id(**{**base, "scope": "p2"}, ordinal=0) != first
    assert derive_stable_id(**{**base, "command_kind": "timeline.load"}, ordinal=0) != first
    with pytest.raises(ValueError, match="non-negative integer"):
        derive_stable_id(**base, ordinal=-1)
    with pytest.raises(ValueError, match="non-empty string"):
        derive_stable_id(**{**base, "idempotency_key": ""}, ordinal=0)


def test_map_error_passes_service_errors_through() -> None:
    err = ServiceNotFoundError("missing", details={"project_id": "p1"})
    assert map_error(err) == err.to_error_object()


def test_map_error_redacts_paths_secrets_and_excess_length() -> None:
    long_junk = "x" * (MAX_ERROR_MESSAGE_LENGTH * 2)
    mapped = map_error(ValueError("failed at /tmp/secret/projects/p1/file.json with sk-abcdefghijklmnopqrstuvwxyz123456 " + long_junk))
    assert mapped.code == "internal_error"
    assert "/tmp/secret" not in mapped.message
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in mapped.message
    assert len(mapped.message) <= MAX_ERROR_MESSAGE_LENGTH
    assert mapped.details == {"error_type": "ValueError"}
    assert canonical_json(mapped.as_dict())


def test_map_error_unknown_exception_is_bounded() -> None:
    mapped = map_error(RuntimeError("boom"))
    assert mapped.code == "internal_error"
    assert mapped.message == "boom"
    assert mapped.details == {"error_type": "RuntimeError"}


def test_service_error_constructor_redacts_details() -> None:
    err = ServiceInternalError("kaboom", details={"token": "ghp_abcdefghijklmnopqrstuvwxyz123456"})
    assert err.details["token"] == "<redacted>"
    assert map_error(err).details["token"] == "<redacted>"


class TimelineVersionConflictError(Exception):
    expected_version = 1
    current_version = 2


def test_stale_version_mapping_is_actionable_without_local_authority() -> None:
    mapped = map_error(TimelineVersionConflictError("stale"))
    assert mapped.code == "stale_version"
    assert mapped.details == {"expected_version": 1, "current_version": 2}
    assert "show the current timeline" in mapped.message
    assert "fresh key" in mapped.message

