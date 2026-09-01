"""Pure event-shaped value helpers.

The workspace runtime owns event persistence, vocabulary, ordering, hash
chains, and recovery. Astrid has no local event store, schema registry, or
migration stream. Runtime event reads are exposed by :mod:`astrid.sdk.events`
through the generated client.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_event_json(event: dict[str, Any]) -> str:
    """Return canonical JSON for hashing an event-shaped value."""
    return json.dumps(
        {key: value for key, value in event.items() if key != "hash"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

__all__ = ["canonical_event_json"]
