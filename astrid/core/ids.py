"""Kernel identifiers: lowercase Crockford-base32 ULIDs (m1 plan step 11).

The kernel's canonical identifier for project aggregates is a 26-character
lowercase Crockford-base32 ULID: 48 bits of millisecond timestamp followed
by 80 bits of randomness, monotonic within a millisecond (the same shape
the timeline event schema uses, but the lowercase spelling is the kernel
canonical form recorded by the v10 decision artifact SD1).

Crockford base32 omits the visually ambiguous letters ``I``, ``L``, ``O``,
and ``U``, so the alphabet is ``0123456789abcdefghjkmnpqrstvwxyz``. ULIDs are
self-describing and time-ordered, which makes them stable, sortable project
identifiers that need no central allocator.

This module has no dependencies on the schema packs, the store, or the
capability-pack loader; it is safe to import anywhere in the kernel.
"""

from __future__ import annotations

import os
import re
import threading
import time

_CROCKFORD_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
"""Lowercase Crockford base32 alphabet (no I, L, O, U)."""

ULID_LENGTH = 26
"""Character length of a canonical kernel ULID (130 bits, 26 base32 digits)."""

_ULID_RE = re.compile(r"^[0123456789abcdefghjkmnpqrstvwxyz]{26}$")
# Timeline files predating the kernel used the uppercase spelling.  Readers
# may still encounter those historical directory names, but all new kernel
# identifiers are emitted in the lowercase spelling above.
_LEGACY_ULID_RE = re.compile(r"^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$")
_ULID_RANDOM_BITS = 80
_ULID_RANDOM_MASK = (1 << _ULID_RANDOM_BITS) - 1
_ULID_LOCK = threading.Lock()
_ULID_LAST_MS = -1
_ULID_LAST_RANDOM = 0


def generate_lowercase_ulid() -> str:
    """Return a new lowercase Crockford ULID, monotonic within a millisecond.

    The 48-bit millisecond timestamp prefixes an 80-bit random component.
    When two calls land in the same millisecond the random component is
    incremented (never reused), and when it would wrap the generator waits
    for the next millisecond, so consecutive ULIDs are strictly increasing.
    """
    global _ULID_LAST_MS, _ULID_LAST_RANDOM

    now_ms = int(time.time() * 1000)
    with _ULID_LOCK:
        if now_ms > _ULID_LAST_MS:
            _ULID_LAST_MS = now_ms
            _ULID_LAST_RANDOM = int.from_bytes(os.urandom(10), "big")
        else:
            _ULID_LAST_RANDOM = (_ULID_LAST_RANDOM + 1) & _ULID_RANDOM_MASK
            if _ULID_LAST_RANDOM == 0:
                while now_ms <= _ULID_LAST_MS:
                    time.sleep(0.001)
                    now_ms = int(time.time() * 1000)
                _ULID_LAST_MS = now_ms
                _ULID_LAST_RANDOM = int.from_bytes(os.urandom(10), "big")
        value = (_ULID_LAST_MS << _ULID_RANDOM_BITS) | _ULID_LAST_RANDOM
    chars = ["0"] * ULID_LENGTH
    for index in range(ULID_LENGTH - 1, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def is_lowercase_ulid(value: object) -> bool:
    """Whether *value* is a canonical 26-character lowercase Crockford ULID."""
    return isinstance(value, str) and _ULID_RE.fullmatch(value) is not None


def generate_run_id() -> str:
    """Generate an opaque run identifier for runtime contracts."""
    return generate_lowercase_ulid()


def generate_group_id() -> str:
    """Generate an opaque group identifier for runtime contracts."""
    return generate_lowercase_ulid()


def generate_ulid() -> str:
    """Generate the uppercase ULID spelling used by legacy timeline storage."""
    return generate_lowercase_ulid().upper()


def is_ulid(value: object) -> bool:
    """Accept current lowercase and historical uppercase ULID directory ids."""
    return isinstance(value, str) and (
        _ULID_RE.fullmatch(value) is not None
        or _LEGACY_ULID_RE.fullmatch(value) is not None
    )


def require_ulid(value: object, field: str = "id") -> str:
    if not is_ulid(value):
        raise ValueError(f"{field} must be a 26-character Crockford ULID")
    return str(value)


__all__ = [
    "ULID_LENGTH",
    "generate_lowercase_ulid",
    "is_lowercase_ulid",
    "generate_ulid",
    "generate_run_id",
    "generate_group_id",
    "is_ulid",
    "require_ulid",
]
