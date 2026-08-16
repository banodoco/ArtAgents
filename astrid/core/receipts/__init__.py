"""Command receipt kernel: canonical request hashing and idempotency.

``canonical`` provides bounded canonical JSON encoding and semantic request
hashing; ``service`` persists and replays ``command_receipts`` rows inside
the kernel unit of work (m1 plan step 9).
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
from astrid.core.receipts.service import (
    ReceiptError,
    ReceiptMismatchError,
    ReceiptService,
    ReceiptValidationError,
)

__all__ = [
    "CanonicalizationError",
    "GENERATED_FIELD_NAMES",
    "MAX_CANONICAL_DEPTH",
    "MAX_CANONICAL_INPUT_BYTES",
    "MAX_CANONICAL_OUTPUT_BYTES",
    "ReceiptError",
    "ReceiptMismatchError",
    "ReceiptService",
    "ReceiptValidationError",
    "canonical_bytes",
    "canonical_json",
    "parse_json",
    "request_hash",
    "strip_generated_fields",
]
