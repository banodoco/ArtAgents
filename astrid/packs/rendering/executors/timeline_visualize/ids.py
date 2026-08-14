"""Stable display IDs and timeline-qualified references.

Display ordinals are allocated once for a root visualization snapshot.  A
child view receives a sealed copy of that root mapping; it never allocates or
renumbers IDs.  Semantic identity remains independent of those display
ordinals and is always the tuple ``(timeline_uuid, kind, authored_id)``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Mapping, TypeAlias
from uuid import UUID


SemanticIdentity: TypeAlias = tuple[str, str, str]

ORDINAL_PATTERN: Final[str] = r"(?:0[1-9]|[1-9][0-9]+)"
OBJECT_KIND_CODES: Final[tuple[str, ...]] = ("SH", "RG", "CL", "AS", "TS", "SP")
STABLE_KIND_CODES: Final[tuple[str, ...]] = ("TL", *OBJECT_KIND_CODES)

STABLE_ID_PATTERN: Final[str] = (
    rf"^(?:{'|'.join(STABLE_KIND_CODES)}){ORDINAL_PATTERN}$"
)
QUALIFIED_REF_PATTERN: Final[str] = (
    rf"^TL{ORDINAL_PATTERN}(?:\.(?:{'|'.join(OBJECT_KIND_CODES)})"
    rf"{ORDINAL_PATTERN})?$"
)
TIMESTAMP_LOCATOR_PATTERN: Final[str] = (
    rf"^TL{ORDINAL_PATTERN}@(?:[0-9]{{2,}}:)?[0-5][0-9]:[0-5][0-9]"
    rf"(?:\.[0-9]{{3}})?$"
)

_STABLE_ID_RE = re.compile(STABLE_ID_PATTERN, flags=re.ASCII)
_QUALIFIED_REF_RE = re.compile(
    rf"^(?P<timeline>TL{ORDINAL_PATTERN})"
    rf"(?:\.(?P<object>(?:{'|'.join(OBJECT_KIND_CODES)}){ORDINAL_PATTERN}))?$",
    flags=re.ASCII,
)
_TIMESTAMP_LOCATOR_RE = re.compile(
    rf"^(?P<timeline>TL{ORDINAL_PATTERN})@(?P<timestamp>"
    rf"(?:[0-9]{{2,}}:)?[0-5][0-9]:[0-5][0-9](?:\.[0-9]{{3}})?)$",
    flags=re.ASCII,
)

SEMANTIC_KIND_TO_CODE: Final[Mapping[str, str]] = MappingProxyType(
    {
        "timeline": "TL",
        "shot": "SH",
        "range": "RG",
        "clip": "CL",
        "asset": "AS",
        "transcript_source_segment": "TS",
        "speech_occurrence": "SP",
    }
)


def _ordinal_from_id(display_id: str) -> int:
    return int(display_id[2:])


def _format_ordinal(value: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("display ordinal must be a positive integer")
    return f"{value:02d}"


@dataclass(frozen=True, slots=True)
class QualifiedRef:
    """One parsed timeline, object, or timestamp reference."""

    timeline_id: str
    object_id: str | None = None
    timestamp: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.timeline_id, str) or not re.fullmatch(
            rf"TL{ORDINAL_PATTERN}", self.timeline_id, flags=re.ASCII
        ):
            raise ValueError(f"malformed timeline display id: {self.timeline_id!r}")
        if self.object_id is not None and self.timestamp is not None:
            raise ValueError("a qualified reference cannot be both an object and a timestamp")
        if self.object_id is not None and not re.fullmatch(
            rf"(?:{'|'.join(OBJECT_KIND_CODES)}){ORDINAL_PATTERN}",
            self.object_id,
            flags=re.ASCII,
        ):
            raise ValueError(f"malformed object display id: {self.object_id!r}")
        if self.timestamp is not None and not re.fullmatch(
            r"(?:[0-9]{2,}:)?[0-5][0-9]:[0-5][0-9](?:\.[0-9]{3})?",
            self.timestamp,
            flags=re.ASCII,
        ):
            raise ValueError(f"malformed timestamp locator: {self.timestamp!r}")

    @property
    def kind(self) -> str:
        """Return ``TL``, an object kind code, or ``timestamp``."""

        if self.timestamp is not None:
            return "timestamp"
        if self.object_id is not None:
            return self.object_id[:2]
        return "TL"

    @property
    def timeline_ordinal(self) -> int:
        return _ordinal_from_id(self.timeline_id)

    @property
    def object_ordinal(self) -> int | None:
        return None if self.object_id is None else _ordinal_from_id(self.object_id)

    @property
    def stable_id(self) -> str:
        """Return the lineage-local ID without its timeline qualifier."""

        return self.object_id or self.timeline_id

    @property
    def is_timestamp(self) -> bool:
        return self.timestamp is not None

    def __str__(self) -> str:
        if self.timestamp is not None:
            return f"{self.timeline_id}@{self.timestamp}"
        if self.object_id is not None:
            return f"{self.timeline_id}.{self.object_id}"
        return self.timeline_id


def parse_qualified_ref(ref: str) -> QualifiedRef:
    """Parse a canonical qualified reference or timestamp locator.

    Bare object display IDs such as ``CL03`` are deliberately rejected.  A
    bare timeline ID is already globally qualified within one root ID map and
    is therefore valid.
    """

    if not isinstance(ref, str):
        raise ValueError("qualified reference must be a string")

    match = _QUALIFIED_REF_RE.fullmatch(ref)
    if match is not None:
        return QualifiedRef(match.group("timeline"), match.group("object"))

    match = _TIMESTAMP_LOCATOR_RE.fullmatch(ref)
    if match is not None:
        return QualifiedRef(match.group("timeline"), timestamp=match.group("timestamp"))

    raise ValueError(f"malformed qualified reference: {ref!r}")


def format_qualified_ref(
    timeline: int | str,
    object_kind_or_id: str | None = None,
    object_ordinal: int | None = None,
    *,
    timestamp: str | None = None,
) -> str:
    """Build a canonical reference and validate it through the parser.

    ``timeline`` accepts either a positive ordinal or a canonical ``TL`` ID.
    Objects may be supplied as a full local ID (``"CL03"``), as a kind code
    plus ordinal (``"CL", 3``), or as a semantic kind plus ordinal
    (``"clip", 3``).  Passing only the timeline builds ``TLxx``; passing
    ``timestamp=`` builds a timestamp locator.
    """

    if isinstance(timeline, int) and not isinstance(timeline, bool):
        timeline_id = f"TL{_format_ordinal(timeline)}"
    elif isinstance(timeline, str) and re.fullmatch(
        rf"TL{ORDINAL_PATTERN}", timeline, flags=re.ASCII
    ):
        timeline_id = timeline
    else:
        raise ValueError("timeline must be a positive ordinal or canonical TL display id")

    if timestamp is not None:
        if object_kind_or_id is not None or object_ordinal is not None:
            raise ValueError("timestamp locators cannot also identify an object")
        return str(parse_qualified_ref(f"{timeline_id}@{timestamp}"))

    if object_kind_or_id is None:
        if object_ordinal is not None:
            raise ValueError("object ordinal requires an object kind")
        return str(parse_qualified_ref(timeline_id))

    if object_ordinal is None:
        if not _STABLE_ID_RE.fullmatch(object_kind_or_id) or object_kind_or_id.startswith(
            "TL"
        ):
            raise ValueError("object id must be a canonical non-TL stable id")
        object_id = object_kind_or_id
    else:
        kind_code = SEMANTIC_KIND_TO_CODE.get(object_kind_or_id, object_kind_or_id)
        if kind_code not in OBJECT_KIND_CODES:
            raise ValueError(f"unsupported object kind: {object_kind_or_id!r}")
        object_id = f"{kind_code}{_format_ordinal(object_ordinal)}"

    return str(parse_qualified_ref(f"{timeline_id}.{object_id}"))


def _normalize_semantic_identity(identity: SemanticIdentity) -> SemanticIdentity:
    if not isinstance(identity, tuple) or len(identity) != 3:
        raise TypeError("semantic identity must be (timeline_uuid, kind, authored_id)")
    timeline_uuid, kind, authored_id = identity
    if not all(isinstance(value, str) and value for value in identity):
        raise ValueError("semantic identity components must be non-empty strings")
    try:
        canonical_uuid = str(UUID(timeline_uuid))
    except ValueError as exc:
        raise ValueError(f"invalid timeline UUID: {timeline_uuid!r}") from exc
    if canonical_uuid != timeline_uuid:
        raise ValueError("timeline UUID must use canonical hyphenated form")
    if kind not in SEMANTIC_KIND_TO_CODE:
        raise ValueError(f"unsupported semantic identity kind: {kind!r}")
    return (canonical_uuid, kind, authored_id)


@dataclass(slots=True)
class RootIdMap:
    """Root semantic-identity to display-ID mapping.

    ``copy()`` returns a sealed child map.  A child can look up every root ID
    but cannot allocate new ones; later root additions also cannot affect the
    child's copied bytes.
    """

    _entries: dict[SemanticIdentity, str] = field(default_factory=dict, repr=False)
    _sealed: bool = field(default=False, repr=False)
    _display_to_identity: dict[str, SemanticIdentity] = field(
        default_factory=dict, init=False, repr=False
    )
    _timeline_ids: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        initial = list(self._entries.items())
        self._entries = {}
        sealed = self._sealed
        self._sealed = False
        for identity, display_id in initial:
            self.add(identity, display_id)
        self._sealed = sealed

    def add(self, identity: SemanticIdentity, display_id: str) -> None:
        """Add one root allocation without ever overwriting an allocation."""

        if self._sealed:
            raise TypeError("child RootIdMap is immutable")
        normalized = _normalize_semantic_identity(identity)
        if normalized in self._entries:
            raise ValueError(f"duplicate semantic identity: {normalized!r}")

        parsed = parse_qualified_ref(display_id)
        if parsed.is_timestamp:
            raise ValueError("timestamp locators cannot be stored in a RootIdMap")
        expected_code = SEMANTIC_KIND_TO_CODE[normalized[1]]
        if parsed.kind != expected_code:
            raise ValueError(
                f"semantic kind {normalized[1]!r} requires a {expected_code} display id"
            )
        if display_id in self._display_to_identity:
            raise ValueError(f"duplicate display id: {display_id!r}")

        timeline_uuid = normalized[0]
        allocated_timeline = self._timeline_ids.get(timeline_uuid)
        if allocated_timeline is not None and allocated_timeline != parsed.timeline_id:
            raise ValueError(
                f"timeline UUID {timeline_uuid!r} is already allocated as {allocated_timeline}"
            )
        for known_uuid, known_timeline_id in self._timeline_ids.items():
            if known_uuid != timeline_uuid and known_timeline_id == parsed.timeline_id:
                raise ValueError(
                    f"timeline display id {parsed.timeline_id!r} is already allocated"
                )

        self._entries[normalized] = display_id
        self._display_to_identity[display_id] = normalized
        self._timeline_ids[timeline_uuid] = parsed.timeline_id

    def lookup(self, identity: SemanticIdentity) -> str:
        """Return the allocated display ID, raising ``KeyError`` when absent."""

        return self._entries[_normalize_semantic_identity(identity)]

    def copy(self) -> "RootIdMap":
        """Return an entry-for-entry sealed copy for a child view."""

        return RootIdMap(dict(self._entries), _sealed=True)

    @property
    def entries(self) -> Mapping[SemanticIdentity, str]:
        """Expose a read-only, insertion-ordered view of the mapping."""

        return MappingProxyType(self._entries)

    @property
    def sealed(self) -> bool:
        return self._sealed


__all__ = [
    "OBJECT_KIND_CODES",
    "ORDINAL_PATTERN",
    "QUALIFIED_REF_PATTERN",
    "QualifiedRef",
    "RootIdMap",
    "SEMANTIC_KIND_TO_CODE",
    "STABLE_ID_PATTERN",
    "STABLE_KIND_CODES",
    "SemanticIdentity",
    "TIMESTAMP_LOCATOR_PATTERN",
    "format_qualified_ref",
    "parse_qualified_ref",
]
