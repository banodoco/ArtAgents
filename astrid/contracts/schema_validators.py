"""Shared schema validation helpers used across Astrid contracts.

Each helper accepts the caller's error class as a parameter so that call sites
preserve their domain-specific exception types (e.g. ProjectValidationError vs
TimelineEventSchemaError) without duplicating validation logic.
"""

from __future__ import annotations

from uuid import UUID


def require_uuid_str(value: object, field: str, error_cls: type[Exception]) -> str:
    """Validate that *value* is a valid UUID string; raise *error_cls* otherwise.

    Returns *value* unchanged when valid.
    """
    if not isinstance(value, str):
        raise error_cls(f"{field} must be a UUID string")
    try:
        UUID(value)
    except ValueError as exc:
        raise error_cls(f"{field} must be a UUID string") from exc
    return value


__all__ = ["require_uuid_str"]
