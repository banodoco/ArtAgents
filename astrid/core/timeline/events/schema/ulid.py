"""Crockford-base32 ULID generation and validation for timeline events."""

import os
import re
import threading
import time

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$")
_ULID_RANDOM_BITS = 80
_ULID_RANDOM_MASK = (1 << _ULID_RANDOM_BITS) - 1
_ULID_LOCK = threading.Lock()
_ULID_LAST_MS = -1
_ULID_LAST_RANDOM = 0


def generate_event_ulid() -> str:
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
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def is_event_ulid(value: object) -> bool:
    return isinstance(value, str) and _ULID_RE.fullmatch(value) is not None
