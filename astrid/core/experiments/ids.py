"""Deterministic identifier helpers for experiment artifacts.

These helpers derive stable, schema-conformant identifiers from source evidence
(e.g. a legacy run-directory name) so that importer runs are idempotent and
byte-stable.  They never weaken the canonical ID vocabularies defined in
:mod:`astrid.core.experiments.schema`.
"""

from __future__ import annotations

import hashlib

# Crockford Base32 alphabet (excludes I, L, O, U).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def derive_ulid(seed: str) -> str:
    """Derive a deterministic 26-character Crockford ULID from *seed*.

    The result matches the experiment-contract ``run_id`` vocabulary
    (``^[0-7][0-9A-HJKMNP-TV-Z]{25}$``) and is stable for a given seed, which
    lets the legacy importer hand every unmanaged run directory the same
    synthetic run id across reruns without copying or rewriting anything.

    The derived value is a *synthetic* identifier.  It carries no timestamp
    ordering guarantees and must never be presented as a real Astrid project
    run id — callers record its synthetic provenance alongside it.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    # 128 bits = 3 (first char, 0-7) + 25*5.  Use the first 16 bytes.
    bits = int.from_bytes(digest[:16], "big")
    chars = [""] * 26
    # First character: 3 bits → index 0..7 → Crockford '0'..'7'.
    chars[0] = _CROCKFORD[bits & 0b111]
    bits >>= 3
    for i in range(1, 26):
        chars[i] = _CROCKFORD[bits & 0b11111]
        bits >>= 5
    return "".join(chars)


__all__ = ["derive_ulid"]
