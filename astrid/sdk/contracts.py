"""Immutable domain result envelopes, error objects, and identity helpers.

(m4 plan step 3, task T3.) This module implements the frozen SDK contract
``docs/contracts/astrid-sdk-v10.md`` as executable types:

- :class:`DomainResult` — the immutable generic domain result envelope with
  exactly the five keys ``ok``/``data``/``error``/``receipt``/
  ``idempotency_key``; ``success``/``failure`` factories enforce the frozen
  invariants (``ok`` true implies ``error`` null; ``ok`` false implies
  ``data`` null and a frozen error object).
- :class:`ErrorObject` — the frozen error object with exactly the three keys
  ``code``/``message``/``details`` and bounded, JSON-safe details.
- :class:`astrid.core.receipts.service.CommandReceipt` (re-exported here) —
  the immutable committed receipt with the exact nine-key exposed shape.
- Idempotency and identity helpers: :func:`generate_idempotency_key`,
  :func:`resolve_idempotency_key` (caller key preserved, generated key
  otherwise), and :func:`derive_stable_id` (deterministic object ids derived
  solely from command kind, project/global scope, idempotency key, and child
  ordinal, SDK contract section 4.4).

Every value serializes **losslessly** through :meth:`DomainResult.to_json` /
:meth:`DomainResult.from_json` and the equivalent ``as_dict``/``from_dict``
pairs, using the kernel bounded canonical JSON encoder, so an envelope
written by any SDK service or CLI round-trips byte-for-byte in semantic
content (object key order is canonical and therefore not part of the wire
form).

This module is a pure SDK-side surface: it never imports execution or pack
machinery, and it never writes to the database. Mutation commands live in
the repository/services layers and return these envelopes.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import CommandReceipt

__all__ = [
    "CommandReceipt",
    "DomainResult",
    "ENVELOPE_KEYS",
    "ERROR_OBJECT_KEYS",
    "ErrorObject",
    "derive_stable_id",
    "generate_idempotency_key",
    "request_hash",
    "resolve_idempotency_key",
]

T = TypeVar("T")

ENVELOPE_KEYS: tuple[str, ...] = (
    "ok",
    "data",
    "error",
    "receipt",
    "idempotency_key",
)
"""The exact top-level envelope keys (SDK contract section 1, closed set)."""

ERROR_OBJECT_KEYS: tuple[str, ...] = ("code", "message", "details")
"""The exact error-object keys (SDK contract section 2.1, closed set)."""


# ---------------------------------------------------------------------------
# Frozen error object
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ErrorObject:
    """Immutable frozen error object (SDK contract section 2.1).

    Exactly three keys: ``code`` (one of the nine frozen machine codes),
    ``message`` (a stable human-readable string that never leaks SQL,
    filesystem paths, receipt internals, request bodies, or secrets), and
    ``details`` (a bounded JSON object with typed fields only).
    """

    code: str
    message: str
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise ValueError("error code must be a non-empty string")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("error message must be a non-empty string")
        if not isinstance(self.details, Mapping):
            raise ValueError("error details must be a JSON object")
        try:
            canonical_json(dict(self.details))
        except CanonicalizationError as exc:
            raise ValueError(f"error details must be bounded JSON: {exc}") from exc

    def as_dict(self) -> dict[str, Any]:
        """Return the error object as a plain JSON-ready mapping."""
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ErrorObject:
        """Build an error object from a plain mapping, rejecting shape drift.

        Accepts exactly the three frozen keys; extra or missing keys raise
        ``ValueError`` so a wire change can never silently produce a
        partial error object.
        """
        if not isinstance(value, Mapping):
            raise ValueError("error object must be a JSON object")
        if set(value.keys()) != set(ERROR_OBJECT_KEYS):
            raise ValueError(
                "error object must have exactly the keys "
                + ", ".join(ERROR_OBJECT_KEYS)
            )
        return cls(
            code=value["code"],
            message=value["message"],
            details=value["details"],
        )

    def to_json(self) -> str:
        """Serialize losslessly to canonical JSON."""
        return canonical_json(self.as_dict())

    @classmethod
    def from_json(cls, text: str | bytes) -> ErrorObject:
        """Parse a canonical JSON error object produced by :meth:`to_json`."""
        try:
            return cls.from_dict(parse_json(text))
        except CanonicalizationError as exc:
            raise ValueError(f"invalid error object JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Immutable domain result envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainResult(Generic[T]):
    """Immutable generic domain result (SDK contract section 1).

    Every SDK service method returns exactly one of these; serialization
    yields exactly the five envelope keys. ``receipt`` is the committed
    command receipt on mutations (``None`` on pure reads and on failures
    that performed zero mutation); ``idempotency_key`` is always present —
    the caller-supplied key when one was provided, otherwise the key the
    SDK generated before mutation.
    """

    ok: bool
    data: T | None
    error: ErrorObject | None
    receipt: CommandReceipt | None
    idempotency_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.ok, bool):
            raise ValueError("ok must be a boolean")
        if self.ok:
            if self.error is not None:
                raise ValueError("ok=True requires error=None")
        else:
            if self.data is not None:
                raise ValueError("ok=False requires data=None")
            if self.error is None:
                raise ValueError("ok=False requires a frozen error object")
        if not isinstance(self.idempotency_key, str):
            raise ValueError("idempotency_key must be a string")
        if self.receipt is not None and not isinstance(self.receipt, CommandReceipt):
            raise TypeError("receipt must be a CommandReceipt or None")
        if self.error is not None and not isinstance(self.error, ErrorObject):
            raise TypeError("error must be an ErrorObject or None")

    @classmethod
    def success(
        cls,
        data: T,
        *,
        receipt: CommandReceipt | None = None,
        idempotency_key: str = "",
    ) -> DomainResult[T]:
        """Build a committed read/mutation result envelope."""
        return cls(
            ok=True,
            data=data,
            error=None,
            receipt=receipt,
            idempotency_key=idempotency_key,
        )

    @classmethod
    def failure(
        cls,
        error: ErrorObject,
        *,
        idempotency_key: str = "",
    ) -> DomainResult[None]:
        """Build a failure envelope (``data`` is always ``None``)."""
        return DomainResult[None](
            ok=False,
            data=None,
            error=error,
            receipt=None,
            idempotency_key=idempotency_key,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the envelope as a plain JSON-ready mapping (exact shape)."""
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error.as_dict() if self.error is not None else None,
            "receipt": self.receipt.as_dict() if self.receipt is not None else None,
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_dict(cls, value: Any) -> DomainResult[Any]:
        """Build an envelope from a plain mapping, rejecting shape drift.

        Accepts exactly the five frozen keys; extra or missing keys raise
        ``ValueError`` so an envelope change can never silently produce a
        partial result.
        """
        if not isinstance(value, Mapping):
            raise ValueError("domain result must be a JSON object")
        if set(value.keys()) != set(ENVELOPE_KEYS):
            raise ValueError(
                "domain result must have exactly the keys "
                + ", ".join(ENVELOPE_KEYS)
            )
        return cls(
            ok=value["ok"],
            data=value["data"],
            error=(
                ErrorObject.from_dict(value["error"])
                if value["error"] is not None
                else None
            ),
            receipt=(
                CommandReceipt.from_dict(value["receipt"])
                if value["receipt"] is not None
                else None
            ),
            idempotency_key=value["idempotency_key"],
        )

    def to_json(self) -> str:
        """Serialize losslessly to canonical JSON (exact envelope shape)."""
        return canonical_json(self.as_dict())

    @classmethod
    def from_json(cls, text: str | bytes) -> DomainResult[Any]:
        """Parse a canonical JSON envelope produced by :meth:`to_json`."""
        try:
            return cls.from_dict(parse_json(text))
        except CanonicalizationError as exc:
            raise ValueError(f"invalid domain result JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic identity
# ---------------------------------------------------------------------------


def generate_idempotency_key() -> str:
    """Return a fresh caller-visible idempotency key (UUID hex).

    The SDK generates one of these **before any mutation** when the caller
    does not supply a key, and returns it in the envelope's
    ``idempotency_key`` field (SDK contract sections 1 and 4.2).
    """
    return uuid.uuid4().hex


def resolve_idempotency_key(key: str | None) -> str:
    """Return the caller-supplied *key*, or generate a fresh key when absent.

    A provided key must be a non-empty string (SDK contract section 4.2);
    an empty or non-string key raises ``ValueError`` before any mutation can
    be attempted.
    """
    if key is None:
        return generate_idempotency_key()
    if not isinstance(key, str) or not key:
        raise ValueError(
            "idempotency_key must be a non-empty string when provided"
        )
    return key


_STABLE_ID_SEPARATOR = "\x1f"


def derive_stable_id(
    *,
    command_kind: str,
    scope: str,
    idempotency_key: str,
    ordinal: int = 0,
) -> str:
    """Return the deterministic object id for one derived object.

    Stable object ids are derived **solely** from command kind, project or
    global scope, idempotency key, and child ordinal (SDK contract section
    4.4), so the same ``(kind, scope, key, ordinal)`` always derives the
    same id and a retry creates no duplicate object. The id is a
    version-5 UUID over the four components, which is deterministic across
    processes and machines.
    """
    if not isinstance(command_kind, str) or not command_kind:
        raise ValueError("command_kind must be a non-empty string")
    if not isinstance(scope, str) or not scope:
        raise ValueError("scope must be a non-empty string")
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise ValueError("idempotency_key must be a non-empty string")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise ValueError("ordinal must be a non-negative integer")
    material = _STABLE_ID_SEPARATOR.join(
        (command_kind, scope, idempotency_key, str(ordinal))
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, material))
