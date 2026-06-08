"""Shared schema-validator primitives for Astrid capability manifests.

The executor and orchestrator schema modules historically carried byte-for-byte
copies of the same low-level parsing/validation helpers, differing only in which
exception type they raised on failure. This module extracts those primitives
once and parameterizes the raised error class via :class:`SchemaValidator`, so
each domain keeps raising its own type (``ExecutorValidationError`` /
``OrchestratorValidationError``) while sharing a single implementation.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, TypeVar, cast

_LiteralT = TypeVar("_LiteralT")

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

SHORT_DESCRIPTION_MAX_LEN = 120
DESCRIPTION_MAX_LEN = 500
KEYWORD_MAX_LEN = 32
KEYWORDS_MAX_COUNT = 12


class _Named(Protocol):
    name: str


class SchemaValidator:
    """Schema-validator primitives bound to a single ``ValueError`` subclass.

    All methods raise ``error_cls`` on failure, so callers in each domain get
    domain-specific exceptions from a shared implementation.
    """

    def __init__(self, error_cls: type[Exception]) -> None:
        self.error_cls = error_cls

    # -- low-level mapping/field accessors ---------------------------------

    def require_mapping(self, raw: Any, path: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise self.error_cls(f"{path} must be an object")
        return raw

    def require_string(self, data: dict[str, Any], key: str, path: str) -> str:
        if key not in data:
            raise self.error_cls(f"missing required field {path}")
        value = data[key]
        self.validate_non_empty_string(value, path)
        return value

    def optional_string(self, data: dict[str, Any], key: str, path: str, *, default: str = "") -> str:
        if key not in data:
            return default
        value = data[key]
        if value == "":
            return default
        self.validate_non_empty_string(value, path)
        return value

    def optional_nullable_string(self, data: dict[str, Any], key: str, path: str) -> str | None:
        if key not in data or data[key] is None:
            return None
        value = data[key]
        self.validate_non_empty_string(value, path)
        return value

    def optional_bool(self, data: dict[str, Any], key: str, path: str, *, default: bool) -> bool:
        if key not in data:
            return default
        value = data[key]
        if not isinstance(value, bool):
            raise self.error_cls(f"{path} must be a boolean")
        return value

    def optional_list(self, data: dict[str, Any], key: str, path: str) -> list[Any]:
        if key not in data:
            return []
        value = data[key]
        if not isinstance(value, list):
            raise self.error_cls(f"{path} must be a list")
        return value

    def string_list(self, raw: Any, path: str) -> list[str]:
        if not isinstance(raw, (list, tuple)):
            raise self.error_cls(f"{path} must be a list")
        result: list[str] = []
        for index, value in enumerate(raw):
            if not isinstance(value, str) or not value.strip():
                raise self.error_cls(f"{path}[{index}] must be a non-empty string")
            result.append(value)
        return result

    def optional_string_list(self, data: dict[str, Any], key: str, path: str) -> list[str]:
        if key not in data:
            return []
        return self.string_list(data[key], path)

    # -- value-level validators -------------------------------------------

    def require_literal(
        self, value: Any, allowed: frozenset[str], path: str, literal_type: type[_LiteralT]
    ) -> _LiteralT:
        """Validate ``value`` is a string in ``allowed`` and return it typed as the Literal alias."""
        if not isinstance(value, str):
            raise self.error_cls(f"{path} must be a string")
        if value not in allowed:
            raise self.error_cls(f"{path} must be one of {sorted(allowed)} (got {value!r})")
        return cast(literal_type, value)

    def validate_in_allowed(self, value: str, allowed: frozenset[str], path: str) -> None:
        if value not in allowed:
            raise self.error_cls(f"{path} must be one of {sorted(allowed)}")

    def validate_non_empty_string(self, value: Any, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise self.error_cls(f"{path} must be a non-empty string")

    def validate_non_empty_identifier(self, value: Any, path: str) -> None:
        self.validate_non_empty_string(value, path)
        if not _IDENTIFIER_RE.match(value):
            raise self.error_cls(
                f"{path} must start with a letter and contain only letters, numbers, '.', '_' or '-'"
            )

    def validate_qualified_identifier(self, value: Any, path: str) -> None:
        self.validate_non_empty_identifier(value, path)
        if "." not in value or any(not part for part in value.split(".")):
            raise self.error_cls(f"{path} must be qualified as <pack>.<name>")

    def validate_env_name(self, value: str, path: str) -> None:
        if not _ENV_NAME_RE.fullmatch(value):
            raise self.error_cls(f"{path} must be a valid environment variable name")

    def validate_placeholders(self, value: str, allowed: set[str], path: str) -> None:
        for placeholder in _PLACEHOLDER_RE.findall(value):
            if placeholder not in allowed:
                raise self.error_cls(f"{path} uses unknown placeholder {{{placeholder}}}")

    def validate_unique_named(self, values: tuple[_Named, ...], label: str) -> set[str]:
        names: set[str] = set()
        for value in values:
            if value.name in names:
                raise self.error_cls(f"duplicate {label} name {value.name!r}")
            names.add(value.name)
        return names


def validate_capability_text(
    description: str,
    short_description: str,
    keywords: tuple[str, ...],
    *,
    manifest_id: str,
    error_cls: type[Exception],
) -> None:
    """Validate capability description/keyword limits, raising ``error_cls`` on failure."""
    if len(description) > DESCRIPTION_MAX_LEN:
        raise error_cls(
            f"{manifest_id}: description is {len(description)} chars; max is {DESCRIPTION_MAX_LEN}"
        )
    if len(short_description) > SHORT_DESCRIPTION_MAX_LEN:
        raise error_cls(
            f"{manifest_id}: short_description is {len(short_description)} chars; max is {SHORT_DESCRIPTION_MAX_LEN}"
        )
    if len(keywords) > KEYWORDS_MAX_COUNT:
        raise error_cls(
            f"{manifest_id}: keywords has {len(keywords)} entries; max is {KEYWORDS_MAX_COUNT}"
        )
    seen: set[str] = set()
    for index, keyword_value in enumerate(keywords):
        if len(keyword_value) > KEYWORD_MAX_LEN:
            raise error_cls(
                f"{manifest_id}: keywords[{index}] is {len(keyword_value)} chars; max is {KEYWORD_MAX_LEN}"
            )
        if any(ch.isspace() for ch in keyword_value):
            raise error_cls(
                f"{manifest_id}: keywords[{index}] {keyword_value!r} must not contain whitespace"
            )
        if keyword_value.lower() != keyword_value:
            raise error_cls(
                f"{manifest_id}: keywords[{index}] {keyword_value!r} must be lowercase"
            )
        if keyword_value in seen:
            raise error_cls(
                f"{manifest_id}: keywords[{index}] {keyword_value!r} is a duplicate"
            )
        seen.add(keyword_value)


def drop_none(value: Any) -> Any:
    """Recursively drop ``None`` values from dicts and normalize tuples to lists."""
    if isinstance(value, dict):
        return {key: drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, tuple):
        return [drop_none(item) for item in value]
    if isinstance(value, list):
        return [drop_none(item) for item in value]
    return value


__all__ = [
    "DESCRIPTION_MAX_LEN",
    "KEYWORDS_MAX_COUNT",
    "KEYWORD_MAX_LEN",
    "SHORT_DESCRIPTION_MAX_LEN",
    "SchemaValidator",
    "drop_none",
    "validate_capability_text",
]
