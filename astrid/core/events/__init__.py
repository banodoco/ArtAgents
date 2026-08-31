"""Pure event vocabulary helpers.

The workspace runtime owns event persistence, ordering, hash chains, and
recovery. Astrid has no local event-file reader or writer. Runtime event reads
are exposed by :mod:`astrid.sdk.events` through the generated client.
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


from astrid.core.events.registry import (  # noqa: E402
    CORE_COMMAND_KINDS,
    CORE_EVENT_KINDS,
    CORE_MANIFEST_VERSION,
    CORE_PACK_ID,
    CORE_STREAM_TYPES,
    STREAM_AGGREGATE_RULES,
    StreamAggregateRule,
    aggregate_rule_for,
    core_only_registry,
    core_schema_pack_manifest,
    register_core_vocabulary,
    validate_command_kind,
    validate_event_append,
    validate_event_kind,
    validate_stream_creation,
    validate_stream_type,
)

__all__ = [
    "CORE_COMMAND_KINDS", "CORE_EVENT_KINDS", "CORE_MANIFEST_VERSION",
    "CORE_PACK_ID", "CORE_STREAM_TYPES", "STREAM_AGGREGATE_RULES",
    "StreamAggregateRule", "aggregate_rule_for", "canonical_event_json",
    "core_only_registry", "core_schema_pack_manifest", "register_core_vocabulary",
    "validate_command_kind", "validate_event_append", "validate_event_kind",
    "validate_stream_creation", "validate_stream_type",
]
