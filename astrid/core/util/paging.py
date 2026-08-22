"""Opaque keyset pagination cursors shared by kernel bridges and packs.

A cursor encodes the previous page's last-row ordering keys as URL-safe
text. Decoding never leaks internals: an unreadable cursor is simply a
``ValueError`` the caller maps onto its own typed 400 surface.
"""

from __future__ import annotations

import base64
import json


def encode_keyset_cursor(*keys: str) -> str:
    """Encode one cursor from the last row's ordering keys."""
    raw = json.dumps(list(keys)).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_keyset_cursor(cursor: str, *, width: int | None = None) -> list[str]:
    """Decode one cursor back to its ordering keys.

    Raises ``ValueError`` when *cursor* is not text produced by
    :func:`encode_keyset_cursor` (optionally requiring exactly *width*
    non-empty string keys).
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("cursor is not a valid page cursor") from exc
    if (
        not isinstance(payload, list)
        or not payload
        or not all(isinstance(key, str) and key for key in payload)
    ):
        raise ValueError("cursor is not a valid page cursor")
    if width is not None and len(payload) != width:
        raise ValueError("cursor is not a valid page cursor")
    return payload


__all__ = [
    "decode_keyset_cursor",
    "encode_keyset_cursor",
]
