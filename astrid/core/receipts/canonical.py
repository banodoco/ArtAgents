"""Bounded canonical JSON encoding and semantic request hashing.

Canonical form: UTF-8 output, object keys sorted, compact separators
``("," , ":")``, no NaN/Infinity, and explicit size/depth bounds. The
canonical request hash — command kind plus semantic request fields with
generated values excluded — defines the idempotency identity stored on
``command_receipts.request_hash`` (v10 section 2.3, m1 plan step 9).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

MAX_CANONICAL_INPUT_BYTES = 1024 * 1024
"""Upper bound (bytes) for a raw JSON document accepted by :func:`parse_json`."""

MAX_CANONICAL_OUTPUT_BYTES = 4 * 1024 * 1024
"""Upper bound (bytes) for canonical UTF-8 output before hashing."""

MAX_CANONICAL_DEPTH = 100
"""Upper bound for JSON nesting depth; deeper documents are rejected."""

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized.

    Covers non-JSON values, non-finite numbers (NaN/Infinity), non-string
    object keys, and inputs or outputs exceeding the declared bounds.
    """


# ---------------------------------------------------------------------------
# Strict parsing
# ---------------------------------------------------------------------------


def _reject_json_constant(name: str) -> Any:
    raise CanonicalizationError(
        f"non-JSON number {name} is not allowed in canonical JSON"
    )


def parse_json(text: str | bytes, *, max_bytes: int = MAX_CANONICAL_INPUT_BYTES) -> Any:
    """Parse *text* into JSON values, rejecting NaN/Infinity and oversized input.

    The standard :func:`json.loads` accepts ``NaN``/``Infinity`` tokens by
    default; this parser refuses them so an oversized or non-JSON document can
    never silently enter the canonical pipeline.
    """
    if isinstance(text, bytes):
        raw = text
        if len(raw) > max_bytes:
            raise CanonicalizationError(
                f"JSON input exceeds {max_bytes} bytes ({len(raw)} bytes)"
            )
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CanonicalizationError("JSON input is not valid UTF-8") from exc
    else:
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise CanonicalizationError("JSON input is not valid UTF-8") from exc
        if len(raw) > max_bytes:
            raise CanonicalizationError(
                f"JSON input exceeds {max_bytes} bytes ({len(raw)} bytes)"
            )
        decoded = text
    try:
        return json.loads(decoded, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise CanonicalizationError(f"invalid JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate(value: Any, depth: int) -> None:
    if depth > MAX_CANONICAL_DEPTH:
        raise CanonicalizationError(
            f"JSON value exceeds maximum nesting depth {MAX_CANONICAL_DEPTH}"
        )
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError(
                f"non-finite float {value!r} is not a JSON number"
            )
        return
    if isinstance(value, list):
        for item in value:
            _validate(item, depth + 1)
        return
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    "JSON object keys must be strings, got "
                    f"{type(key).__name__}"
                )
        for item in value.values():
            _validate(item, depth + 1)
        return
    raise CanonicalizationError(
        f"value of type {type(value).__name__} is not JSON-serializable"
    )


# ---------------------------------------------------------------------------
# Canonical encoding
# ---------------------------------------------------------------------------


def canonical_json(value: Any, *, max_bytes: int = MAX_CANONICAL_OUTPUT_BYTES) -> str:
    """Return the canonical JSON text for *value*.

    Stable across equivalent objects: key order and whitespace differences
    produce identical output. Non-JSON values, non-finite floats, non-string
    keys, excessive depth, and oversized output raise
    :class:`CanonicalizationError`.
    """
    _validate(value, 0)
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(f"cannot canonicalize value: {exc}") from exc
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise CanonicalizationError("canonical output is not valid UTF-8") from exc
    if size > max_bytes:
        raise CanonicalizationError(
            f"canonical JSON exceeds {max_bytes} bytes ({size} bytes)"
        )
    return text


def canonical_bytes(value: Any, *, max_bytes: int = MAX_CANONICAL_OUTPUT_BYTES) -> bytes:
    """Return the canonical JSON for *value* as UTF-8 bytes."""
    return canonical_json(value, max_bytes=max_bytes).encode("utf-8")


# ---------------------------------------------------------------------------
# Semantic request hashing
# ---------------------------------------------------------------------------

GENERATED_FIELD_NAMES = frozenset(
    {
        # Timestamps assigned by the system at write time.
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "last_heartbeat_at",
        "available_at",
        "lease_expires_at",
        "verified_at",
        "applied_at",
        # Generated transaction/event identifiers.
        "txn_id",
        "txn",
        "transaction_id",
        "event_id",
        "receipt_id",
    }
)
"""Field names that are generated at write time and excluded from request identity."""


def strip_generated_fields(
    value: Any,
    *,
    exclude_fields: frozenset[str] = GENERATED_FIELD_NAMES,
    _depth: int = 0,
) -> Any:
    """Return *value* with generated fields removed recursively.

    Keys whose names appear in *exclude_fields* are dropped at every nesting
    level. Non-mapping values are returned unchanged.
    """
    if _depth > MAX_CANONICAL_DEPTH:
        raise CanonicalizationError(
            f"JSON value exceeds maximum nesting depth {MAX_CANONICAL_DEPTH}"
        )
    if isinstance(value, dict):
        return {
            key: strip_generated_fields(item, exclude_fields=exclude_fields, _depth=_depth + 1)
            for key, item in value.items()
            if key not in exclude_fields
        }
    if isinstance(value, list):
        return [
            strip_generated_fields(item, exclude_fields=exclude_fields, _depth=_depth + 1)
            for item in value
        ]
    return value


def request_hash(
    command_kind: str,
    request: Mapping[str, Any],
    *,
    exclude_fields: frozenset[str] = GENERATED_FIELD_NAMES,
    max_bytes: int = MAX_CANONICAL_OUTPUT_BYTES,
) -> str:
    """Return the SHA-256 hex digest identifying one semantic command request.

    The hash covers the command kind plus the semantic request fields with
    generated values (timestamps, transaction/event IDs) excluded, so an
    identical retry hashes identically and a meaningfully changed request does
    not. The idempotency key itself is matched separately by the receipt
    service and is deliberately not part of this digest.
    """
    if not isinstance(command_kind, str) or not command_kind:
        raise CanonicalizationError("command_kind must be a non-empty string")
    if not isinstance(request, Mapping):
        raise CanonicalizationError("request must be a JSON object")
    semantic = strip_generated_fields(dict(request), exclude_fields=exclude_fields)
    payload = {"command_kind": command_kind, "request": semantic}
    return hashlib.sha256(canonical_bytes(payload, max_bytes=max_bytes)).hexdigest()


__all__ = [
    "CanonicalizationError",
    "GENERATED_FIELD_NAMES",
    "MAX_CANONICAL_DEPTH",
    "MAX_CANONICAL_INPUT_BYTES",
    "MAX_CANONICAL_OUTPUT_BYTES",
    "canonical_bytes",
    "canonical_json",
    "parse_json",
    "request_hash",
    "strip_generated_fields",
]
