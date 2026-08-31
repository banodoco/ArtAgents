"""Pure command-receipt contract helpers.

Receipt persistence and replay are runtime operations; this package contains
only the wire contract and canonicalization primitives.
"""

from __future__ import annotations

from astrid.core.receipts.canonical import (
    CanonicalizationError,
    GENERATED_FIELD_NAMES,
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_INPUT_BYTES,
    MAX_CANONICAL_OUTPUT_BYTES,
    canonical_bytes,
    canonical_json,
    parse_json,
    request_hash,
    strip_generated_fields,
)

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
