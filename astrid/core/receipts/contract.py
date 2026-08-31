"""Store-free command receipt DTO used by the SDK and generated client."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
)

RECEIPT_SHAPE_KEYS: frozenset[str] = frozenset(
    {
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
)


class ReceiptValidationError(ValueError):
    """Raised when a wire receipt does not satisfy the contract."""


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ReceiptValidationError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    """Immutable committed receipt with the exact nine-key wire shape."""

    receipt_id: str
    command_kind: str
    idempotency_key: str
    request_hash: str
    project_id: str
    project_seq: tuple[int, int]
    event_ids: tuple[str, ...]
    result: Any
    created_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("command_kind", self.command_kind),
            ("idempotency_key", self.idempotency_key),
            ("request_hash", self.request_hash),
            ("project_id", self.project_id),
            ("created_at", self.created_at),
        ):
            _require_non_empty_string(name, value)
        if not isinstance(self.project_seq, tuple) or len(self.project_seq) != 2:
            raise ReceiptValidationError(
                "project_seq must be a (first_project_seq, last_project_seq) pair"
            )
        first, last = self.project_seq
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in (first, last)
        ):
            raise ReceiptValidationError("project_seq entries must be positive integers")
        if last < first:
            raise ReceiptValidationError(
                f"project_seq[1] must be >= project_seq[0] ({first} vs {last})"
            )
        if not isinstance(self.event_ids, tuple):
            raise ReceiptValidationError("event_ids must be a tuple")
        for event_id in self.event_ids:
            _require_non_empty_string("event_ids entry", event_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "command_kind": self.command_kind,
            "idempotency_key": self.idempotency_key,
            "request_hash": self.request_hash,
            "project_id": self.project_id,
            "project_seq": [self.project_seq[0], self.project_seq[1]],
            "event_ids": list(self.event_ids),
            "result": self.result,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CommandReceipt":
        if not isinstance(value, Mapping):
            raise ReceiptValidationError("receipt must be a JSON object")
        if set(value.keys()) != RECEIPT_SHAPE_KEYS:
            raise ReceiptValidationError(
                "receipt must have exactly the keys expected by the contract"
            )
        project_seq = value["project_seq"]
        event_ids = value["event_ids"]
        if not isinstance(project_seq, (list, tuple)) or len(project_seq) != 2:
            raise ReceiptValidationError("project_seq must be a two-element [first, last] array")
        if not isinstance(event_ids, (list, tuple)):
            raise ReceiptValidationError("event_ids must be an array")
        return cls(
            receipt_id=value["receipt_id"],
            command_kind=value["command_kind"],
            idempotency_key=value["idempotency_key"],
            request_hash=value["request_hash"],
            project_id=value["project_id"],
            project_seq=(project_seq[0], project_seq[1]),
            event_ids=tuple(event_ids),
            result=value["result"],
            created_at=value["created_at"],
        )

    def to_json(self) -> str:
        return canonical_json(self.as_dict())

    @classmethod
    def from_json(cls, text: str | bytes) -> "CommandReceipt":
        try:
            return cls.from_dict(parse_json(text))
        except CanonicalizationError as exc:
            raise ReceiptValidationError(f"invalid receipt JSON: {exc}") from exc


__all__ = ["CommandReceipt", "RECEIPT_SHAPE_KEYS", "ReceiptValidationError"]
