"""Shared event-hash computation for timeline and task event logs.

Algorithms are UNCHANGED from the pre-consolidation code — this module is a
structural extraction only. The two functions intentionally return different
formats because the two consumers have different on-disk conventions that
predate this module:

- ``hash_embedded`` — timeline convention: bare hex digest (no prefix).
- ``hash_prepended`` — task event log convention: ``sha256:<hex>`` with prefix.

Do NOT unify the two algorithms or change either return format. On-disk hash
chains for existing timelines and event logs depend on byte-identical output.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrid.core.timeline.events.schema.types import TimelineEvent


def hash_embedded(prev_hash: str | None, event: "TimelineEvent") -> str:
    """Return the bare-hex SHA-256 digest for a timeline event.

    Embeds *prev_hash* in the event payload JSON and hashes with
    ``exclude_hash=True`` (the ``hash`` field is stripped before hashing).
    Returns a bare hexadecimal digest — no ``sha256:`` prefix.

    Used by timeline serialization (``serialize.py:with_event_hash``).
    Algorithms are frozen; do not modify.
    """
    from astrid.core.timeline.events.schema.serialize import sha256_hex

    payload = event.to_json_obj()
    payload["prev_hash"] = prev_hash
    payload["hash"] = None
    return sha256_hex(payload, exclude_hash=True)


def hash_prepended(prev_hash: str, event: dict[str, Any]) -> str:
    """Return the ``sha256:<hex>`` digest for a task event log entry.

    Prepends the raw *prev_hash* string to the canonical JSON representation
    of *event* (with the ``hash`` field excluded), then SHA-256 hashes the
    concatenated UTF-8 bytes.  Returns ``f"sha256:{digest}"`` — WITH the
    ``sha256:`` prefix.

    Used by the task event log (``events.py:_event_hash``).
    Algorithms are frozen; do not modify.
    """
    payload = {key: value for key, value in event.items() if key != "hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = ["hash_embedded", "hash_prepended"]
