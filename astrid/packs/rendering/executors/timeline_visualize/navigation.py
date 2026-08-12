"""Stable semantic and lineage-local display identities for one inspection model.

R3's :mod:`ids` machinery defines the display-id grammar (``TL01``,
``TL01.CL03``) and the semantic identity shape ``(timeline_uuid, kind,
authored_id)``.  This module wires those identities onto R7's frozen
:class:`~astrid.packs.rendering.executors.timeline_visualize.model.TimelineInspectionModel`
so every object reachable in a view can be addressed by a stable display id.

Ordinal allocation (deterministic, one root snapshot per map):

* ``TL01`` is always the timeline itself; its semantic authored id is the
  timeline UUID.
* ``CL`` ordinals follow ``model.clips`` exactly — that order is already the
  compositor order ``(track config order, clip at, source index)`` produced by
  :func:`build_model`, so display ordinals can never drift from model order.
* ``AS`` ordinals follow ``sorted(model.registry_keys)`` (registry-key sort).
* ``SH`` ordinals follow ``model.shots``, i.e. ``pinnedShotGroups`` order;
  a fixture without pinned shots simply allocates none.
* ``RG`` ordinals are minted later by :func:`assign_range_ids` (R9) in range
  start-time order; re-passing an already allocated range never renumbers it.
* ``TS``/``SP`` stay empty in M1 (R20 fills them).

Display ids are stored in *qualified* form (``TL01.CL03``), because
:func:`ids.parse_qualified_ref` deliberately rejects bare object ids such as
``CL03``; the lineage-local stable id is the suffix (``QualifiedRef.stable_id``).

Duplicate policy follows R3's ``validate.py``: production rejects duplicates.
:func:`build_identity_map` raises ``ValueError`` listing *every* duplicate
authored id it finds, rather than failing on the first one.

Composition with ``ids.py``: entries are allocated through :class:`RootIdMap`,
which re-validates kind codes, display-id grammar, timeline-ID consistency and
uniqueness.  ``navigation.py`` adds the read-only two-way map, snapshot
metadata, and per-kind conveniences that ``RootIdMap`` deliberately lacks.

Divergence from ``ids.py`` (noted, not patched): the R3 scheme defines no
``TR`` code for tracks, so track authored ids get **no display ordinals in
M1** — ``stable_id_for(model, \"track\", ...)`` raises ``KeyError``.  Ranges
need :func:`assign_range_ids`; TS/SP await R20.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Final, Iterable, Mapping

from astrid.packs.rendering.executors.timeline_visualize.ids import (
    RootIdMap,
    format_qualified_ref,
    parse_qualified_ref,
)
from astrid.packs.rendering.executors.timeline_visualize.model import (
    TimelineInspectionModel,
)
from astrid.packs.rendering.executors.timeline_visualize.transcripts import (
    SpeechOccurrence,
    TranscriptSegment,
    speech_occurrence_authored_id,
    transcript_segment_authored_id,
)

_TIMELINE_DISPLAY_ID: Final[str] = "TL01"
_TIMELINE_ORDINAL: Final[int] = 1

_KIND_NOUNS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "timeline": "timeline id",
        "shot": "shot id",
        "clip": "clip id",
        "asset": "asset key",
        "range": "range id",
        "transcript_source_segment": "transcript segment id",
        "speech_occurrence": "speech occurrence id",
    }
)


@dataclass(frozen=True, slots=True)
class IdentityMap:
    """Two-way semantic <-> display identity for one root visualization.

    The root map's mappings are live dicts (the allocator's artifact); hand a
    :meth:`child_copy` to any consumer instead — it is a sealed, byte-identical
    snapshot that never renumbers, and later root additions cannot reach it.
    """

    semantic_to_display: Mapping[tuple[str, str, str], str]
    display_to_semantic: Mapping[str, tuple[str, str, str]]
    root_sns: str
    timeline_uuid: str
    timeline_ulid: str

    def lookup_semantic(self, kind: str, authored_id: str) -> str | None:
        """Return the qualified display id (``TL01.CL03``) or ``None``."""

        return self.semantic_to_display.get((self.timeline_uuid, kind, authored_id))

    def lookup_display(self, display_id: str) -> tuple[str, str, str] | None:
        """Return the semantic identity ``(timeline_uuid, kind, authored_id)``."""

        return self.display_to_semantic.get(display_id)

    def child_copy(self) -> "IdentityMap":
        """Return a sealed, byte-identical copy for a child view."""

        return IdentityMap(
            semantic_to_display=MappingProxyType(dict(self.semantic_to_display)),
            display_to_semantic=MappingProxyType(dict(self.display_to_semantic)),
            root_sns=self.root_sns,
            timeline_uuid=self.timeline_uuid,
            timeline_ulid=self.timeline_ulid,
        )


def _reject_duplicate_authored_ids(entries: Iterable[tuple[str, str]]) -> None:
    """Raise ValueError listing every duplicate authored id, per kind."""

    counts: dict[tuple[str, str], int] = {}
    for kind, authored_id in entries:
        key = (kind, authored_id)
        counts[key] = counts.get(key, 0) + 1
    duplicates = [
        f"duplicate {_KIND_NOUNS.get(kind, kind)} {authored_id!r}"
        for (kind, authored_id), count in counts.items()
        if count > 1
    ]
    if duplicates:
        raise ValueError("; ".join(duplicates))


def _materialize(
    candidates: Iterable[tuple[tuple[str, str, str], str]],
    *,
    root_sns: str,
    timeline_uuid: str,
    timeline_ulid: str,
) -> IdentityMap:
    """Allocate through RootIdMap (validates grammar, kind, uniqueness), then freeze."""

    root = RootIdMap()
    for identity, display_id in candidates:
        root.add(identity, display_id)
    semantic_to_display = dict(root.entries)
    display_to_semantic = {
        display_id: identity for identity, display_id in semantic_to_display.items()
    }
    return IdentityMap(
        semantic_to_display=semantic_to_display,
        display_to_semantic=display_to_semantic,
        root_sns=root_sns,
        timeline_uuid=timeline_uuid,
        timeline_ulid=timeline_ulid,
    )


def _object_ordinal(display_id: str) -> int:
    ordinal = parse_qualified_ref(display_id).object_ordinal
    if ordinal is None:
        raise ValueError(f"{display_id!r} is not an object display id")
    return ordinal


def build_identity_map(
    model: TimelineInspectionModel,
    *,
    root_sns: str,
    timeline_uuid: str,
    timeline_ulid: str,
) -> IdentityMap:
    """Allocate display ordinals for one frozen inspection model.

    Ordering is deterministic: TL01, then SH by ``pinnedShotGroups`` order,
    CL by model clip order, AS by sorted registry key.  Duplicate authored ids
    raise ``ValueError`` listing every duplicate.  ``timeline_uuid`` must match
    ``model.timeline_uuid`` so semantic lookups cannot silently miss.
    """

    if not isinstance(model, TimelineInspectionModel):
        raise TypeError("model must be a TimelineInspectionModel")
    for label, value in (
        ("root_sns", root_sns),
        ("timeline_uuid", timeline_uuid),
        ("timeline_ulid", timeline_ulid),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label} must be a non-empty string")
    if timeline_uuid != model.timeline_uuid:
        raise ValueError(
            f"timeline_uuid {timeline_uuid!r} does not match "
            f"model.timeline_uuid {model.timeline_uuid!r}"
        )

    candidates: list[tuple[tuple[str, str, str], str]] = [
        (
            (timeline_uuid, "timeline", timeline_uuid),
            _TIMELINE_DISPLAY_ID,
        )
    ]
    for ordinal, shot in enumerate(model.shots, start=1):
        candidates.append(
            (
                (timeline_uuid, "shot", shot.shot_id),
                format_qualified_ref(_TIMELINE_ORDINAL, "SH", ordinal),
            )
        )
    for ordinal, clip in enumerate(model.clips, start=1):
        candidates.append(
            (
                (timeline_uuid, "clip", clip.clip_id),
                format_qualified_ref(_TIMELINE_ORDINAL, "CL", ordinal),
            )
        )
    for ordinal, asset_key in enumerate(sorted(model.registry_keys), start=1):
        candidates.append(
            (
                (timeline_uuid, "asset", asset_key),
                format_qualified_ref(_TIMELINE_ORDINAL, "AS", ordinal),
            )
        )

    _reject_duplicate_authored_ids(
        (identity[1], identity[2]) for identity, _display_id in candidates
    )
    return _materialize(
        candidates,
        root_sns=root_sns,
        timeline_uuid=timeline_uuid,
        timeline_ulid=timeline_ulid,
    )


def _normalize_range(item: object, index: int) -> tuple[str, float, float]:
    if not isinstance(item, (tuple, list)) or len(item) != 3:
        raise ValueError(f"ranges[{index}] must be a (authored_id, start, end) triple")
    authored_id, raw_start, raw_end = item
    if not isinstance(authored_id, str) or not authored_id:
        raise ValueError(f"ranges[{index}] authored id must be a non-empty string")
    for label, raw in (("start", raw_start), ("end", raw_end)):
        if isinstance(raw, bool) or not isinstance(raw, Real):
            raise ValueError(f"ranges[{index}] {label} must be a number")
        if not math.isfinite(float(raw)):
            raise ValueError(f"ranges[{index}] {label} must be finite")
    start = float(raw_start)
    end = float(raw_end)
    if start < 0:
        raise ValueError(f"ranges[{index}] start must be non-negative")
    if end <= start:
        raise ValueError(f"ranges[{index}] end must be greater than start")
    return (authored_id, start, end)


def assign_range_ids(
    identity_map: IdentityMap,
    ranges: list[tuple[str, float, float]],
) -> IdentityMap:
    """Mint ``RG`` ordinals for range scopes (R9) in start-time order.

    Ranges sort by ``(start, end, authored_id)`` so ties stay deterministic.
    An authored id that already owns a display id keeps it (never renumber);
    a fresh id continues the ordinal run.  Duplicate new authored ids raise
    ``ValueError`` listing every duplicate.  Returns a new map; the input is
    never mutated.
    """

    if not isinstance(identity_map, IdentityMap):
        raise TypeError("identity_map must be an IdentityMap")
    normalized = [_normalize_range(item, index) for index, item in enumerate(ranges)]

    existing: dict[str, str] = {}
    for display_id, identity in identity_map.display_to_semantic.items():
        if identity[1] == "range":
            existing[identity[2]] = display_id

    new_ranges = [item for item in normalized if item[0] not in existing]
    _reject_duplicate_authored_ids(
        ("range", authored_id) for authored_id, _start, _end in new_ranges
    )

    next_ordinal = 1
    if existing:
        next_ordinal = max(_object_ordinal(display_id) for display_id in existing.values()) + 1

    ordered = sorted(new_ranges, key=lambda item: (item[1], item[2], item[0]))
    candidates: list[tuple[tuple[str, str, str], str]] = list(
        identity_map.semantic_to_display.items()
    )
    for authored_id, _start, _end in ordered:
        candidates.append(
            (
                (identity_map.timeline_uuid, "range", authored_id),
                format_qualified_ref(_TIMELINE_ORDINAL, "RG", next_ordinal),
            )
        )
        next_ordinal += 1

    return _materialize(
        candidates,
        root_sns=identity_map.root_sns,
        timeline_uuid=identity_map.timeline_uuid,
        timeline_ulid=identity_map.timeline_ulid,
    )


def assign_transcript_ids(
    identity_map: IdentityMap,
    segments: list[TranscriptSegment],
    occurrences: list[SpeechOccurrence],
    *,
    transcript_sha256: str,
) -> IdentityMap:
    """Add hash-scoped TS and occurrence-specific SP ids to a root map.

    TS order is normalized transcript order. SP order is the deterministic
    order returned by ``map_occurrences`` (model clip order, then source order).
    Existing allocations are retained verbatim, which is what frozen children
    require.
    """

    if not isinstance(identity_map, IdentityMap):
        raise TypeError("identity_map must be an IdentityMap")
    candidates: list[tuple[tuple[str, str, str], str]] = list(
        identity_map.semantic_to_display.items()
    )
    seen_segments: set[str] = set()
    for ordinal, segment in enumerate(segments, start=1):
        authored_id = transcript_segment_authored_id(
            transcript_sha256, segment.segment_id
        )
        if authored_id in seen_segments:
            raise ValueError(f"duplicate transcript segment identity {authored_id!r}")
        seen_segments.add(authored_id)
        existing = identity_map.lookup_semantic("transcript_source_segment", authored_id)
        if existing is None:
            candidates.append(
                (
                    (identity_map.timeline_uuid, "transcript_source_segment", authored_id),
                    format_qualified_ref(_TIMELINE_ORDINAL, "TS", ordinal),
                )
            )
    seen_occurrences: set[str] = set()
    for ordinal, occurrence in enumerate(occurrences, start=1):
        authored_id = speech_occurrence_authored_id(
            transcript_sha256, occurrence.segment_id, occurrence.clip_id
        )
        if authored_id in seen_occurrences:
            raise ValueError(f"duplicate speech occurrence identity {authored_id!r}")
        seen_occurrences.add(authored_id)
        existing = identity_map.lookup_semantic("speech_occurrence", authored_id)
        if existing is None:
            candidates.append(
                (
                    (identity_map.timeline_uuid, "speech_occurrence", authored_id),
                    format_qualified_ref(_TIMELINE_ORDINAL, "SP", ordinal),
                )
            )
    return _materialize(
        candidates,
        root_sns=identity_map.root_sns,
        timeline_uuid=identity_map.timeline_uuid,
        timeline_ulid=identity_map.timeline_ulid,
    )


def stable_id_for(
    model: TimelineInspectionModel,
    kind: str,
    authored_id: str,
) -> str:
    """Convenience lookup: build the model's root map and resolve one id.

    Raises ``KeyError`` with a clear message when the authored id has no
    allocated display id (including kinds M1 does not yet allocate, such as
    tracks, ranges before R9, and TS/SP before R20).
    """

    if not isinstance(model, TimelineInspectionModel):
        raise TypeError("model must be a TimelineInspectionModel")
    if not isinstance(kind, str) or not kind:
        raise ValueError("kind must be a non-empty string")
    if not isinstance(authored_id, str) or not authored_id:
        raise ValueError("authored_id must be a non-empty string")

    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    display_id = identity_map.lookup_semantic(kind, authored_id)
    if display_id is None:
        raise KeyError(
            f"no display id allocated for {kind!r} authored id {authored_id!r} "
            f"(snapshot {model.snapshot_sns!r}); M1 allocates timeline/shot/clip/"
            f"asset ordinals only — tracks have no R3 code; range and "
            f"transcript ids require their explicit assignment helpers"
        )
    return display_id


__all__ = [
    "IdentityMap",
    "assign_range_ids",
    "assign_transcript_ids",
    "build_identity_map",
    "stable_id_for",
]
