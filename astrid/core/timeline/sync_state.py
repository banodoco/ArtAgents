"""Sync ledger state helpers shared by local and hub-backed transfers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.timeline.eventlog.protocol import EventLogBackend
from astrid.core.timeline.eventlog.types import EventLogHead
from astrid.core.util.time import utc_now_seconds

SYNC_BOOKMARK_FILENAME = "sync_bookmark.json"

SyncSpoke = Literal["local", "app"]
SyncState = Literal[
    "up_to_date",
    "source_only",
    "destination_only",
    "both_advanced",
    "bookmark_missing",
    "bookmark_incompatible",
]
_BookmarkRelation = Literal["matches", "advanced", "behind", "conflict"]


class SyncStateError(ValueError):
    """Raised when a sync bookmark or head snapshot is missing required fields."""


@dataclass(frozen=True)
class HeadSnapshot:
    """Versioned stream head used for bookmark comparison."""

    version: int
    last_hash: str | None
    last_event_id: str | None

    def __post_init__(self) -> None:
        if self.version < 0:
            raise SyncStateError("head.version must be >= 0")
        if self.version == 0:
            if self.last_hash is not None or self.last_event_id is not None:
                raise SyncStateError(
                    "empty heads must not carry last_hash or last_event_id"
                )
            return
        if not self.last_hash or not self.last_event_id:
            raise SyncStateError(
                "non-empty heads must include last_hash and last_event_id"
            )

    @property
    def is_empty(self) -> bool:
        return self.version == 0

    def to_json_obj(self) -> dict[str, object]:
        return {
            "version": self.version,
            "last_hash": self.last_hash,
            "last_event_id": self.last_event_id,
        }

    @classmethod
    def from_dict(cls, raw: object) -> "HeadSnapshot":
        if not isinstance(raw, dict):
            raise SyncStateError("head snapshot must be a JSON object")
        version = raw.get("version")
        if not isinstance(version, int):
            raise SyncStateError("head.version must be an integer")
        last_hash = raw.get("last_hash")
        if last_hash is not None and not isinstance(last_hash, str):
            raise SyncStateError("head.last_hash must be a string or null")
        last_event_id = raw.get("last_event_id")
        if last_event_id is not None and not isinstance(last_event_id, str):
            raise SyncStateError("head.last_event_id must be a string or null")
        return cls(
            version=version,
            last_hash=last_hash,
            last_event_id=last_event_id,
        )

    @classmethod
    def from_eventlog_head(cls, head: EventLogHead) -> "HeadSnapshot":
        return cls(
            version=head.version,
            last_hash=head.last_hash,
            last_event_id=head.last_event_id,
        )


@dataclass(frozen=True)
class SyncBookmark:
    """Durable per-link bookmark matching the DB bookmark row shape."""

    timeline_id: str
    spoke: SyncSpoke
    spoke_version: int
    spoke_hash: str | None
    spoke_event_id: str | None
    hub_version: int
    hub_hash: str | None
    hub_event_id: str | None
    synced_at: str

    def __post_init__(self) -> None:
        _validate_bookmark_side(
            version=self.spoke_version,
            last_hash=self.spoke_hash,
            last_event_id=self.spoke_event_id,
            label="spoke",
        )
        _validate_bookmark_side(
            version=self.hub_version,
            last_hash=self.hub_hash,
            last_event_id=self.hub_event_id,
            label="hub",
        )
        if not self.timeline_id:
            raise SyncStateError("bookmark.timeline_id must be non-empty")
        if self.spoke not in {"local", "app"}:
            raise SyncStateError("bookmark.spoke must be 'local' or 'app'")
        if not self.synced_at:
            raise SyncStateError("bookmark.synced_at must be non-empty")

    def spoke_head(self) -> HeadSnapshot:
        return HeadSnapshot(
            version=self.spoke_version,
            last_hash=self.spoke_hash,
            last_event_id=self.spoke_event_id,
        )

    def hub_head(self) -> HeadSnapshot:
        return HeadSnapshot(
            version=self.hub_version,
            last_hash=self.hub_hash,
            last_event_id=self.hub_event_id,
        )

    def to_json_obj(self) -> dict[str, object]:
        return {
            "timeline_id": self.timeline_id,
            "spoke": self.spoke,
            "spoke_version": self.spoke_version,
            "spoke_hash": self.spoke_hash,
            "spoke_event_id": self.spoke_event_id,
            "hub_version": self.hub_version,
            "hub_hash": self.hub_hash,
            "hub_event_id": self.hub_event_id,
            "synced_at": self.synced_at,
        }

    @classmethod
    def from_dict(cls, raw: object) -> "SyncBookmark":
        if not isinstance(raw, dict):
            raise SyncStateError("sync bookmark must be a JSON object")
        timeline_id = raw.get("timeline_id")
        synced_at = raw.get("synced_at")
        spoke = raw.get("spoke")
        if not isinstance(timeline_id, str):
            raise SyncStateError("bookmark.timeline_id must be a string")
        if not isinstance(spoke, str):
            raise SyncStateError("bookmark.spoke must be a string")
        if not isinstance(synced_at, str):
            raise SyncStateError("bookmark.synced_at must be a string")
        return cls(
            timeline_id=timeline_id,
            spoke=spoke,  # type: ignore[arg-type]
            spoke_version=_require_int(raw.get("spoke_version"), "spoke_version"),
            spoke_hash=_optional_str(raw.get("spoke_hash"), "spoke_hash"),
            spoke_event_id=_optional_str(raw.get("spoke_event_id"), "spoke_event_id"),
            hub_version=_require_int(raw.get("hub_version"), "hub_version"),
            hub_hash=_optional_str(raw.get("hub_hash"), "hub_hash"),
            hub_event_id=_optional_str(raw.get("hub_event_id"), "hub_event_id"),
            synced_at=synced_at,
        )

    @classmethod
    def from_heads(
        cls,
        *,
        timeline_id: str,
        spoke: SyncSpoke,
        spoke_head: HeadSnapshot,
        hub_head: HeadSnapshot,
        synced_at: str | None = None,
    ) -> "SyncBookmark":
        return cls(
            timeline_id=timeline_id,
            spoke=spoke,
            spoke_version=spoke_head.version,
            spoke_hash=spoke_head.last_hash,
            spoke_event_id=spoke_head.last_event_id,
            hub_version=hub_head.version,
            hub_hash=hub_head.last_hash,
            hub_event_id=hub_head.last_event_id,
            synced_at=synced_at or utc_now_seconds(),
        )


def sync_bookmark_path(timeline_home: str | Path) -> Path:
    return Path(timeline_home) / SYNC_BOOKMARK_FILENAME


def read_local_sync_bookmark(timeline_home: str | Path) -> SyncBookmark | None:
    path = sync_bookmark_path(timeline_home)
    try:
        raw = read_json(path)
    except FileNotFoundError:
        return None
    except Exception as exc:
        raise SyncStateError(f"failed to read {path}: {exc}") from exc
    return SyncBookmark.from_dict(raw)


def write_local_sync_bookmark(
    timeline_home: str | Path,
    bookmark: SyncBookmark,
) -> Path:
    path = sync_bookmark_path(timeline_home)
    write_json_atomic(path, bookmark.to_json_obj())
    return path


def head_snapshot_from_backend(backend: EventLogBackend) -> HeadSnapshot:
    return HeadSnapshot.from_eventlog_head(backend.head())


def validate_bookmark_matches_timeline(
    bookmark: SyncBookmark,
    *,
    timeline_id: str,
) -> None:
    if bookmark.timeline_id != timeline_id:
        raise SyncStateError(
            f"bookmark.timeline_id {bookmark.timeline_id!r} does not match {timeline_id!r}"
        )


def is_missing_bookmark_bootstrap_safe(
    *,
    source_head: HeadSnapshot,
    destination_head: HeadSnapshot,
    source_known_safe: bool = False,
    destination_known_safe: bool = False,
) -> bool:
    return (
        source_head.is_empty
        or destination_head.is_empty
        or source_known_safe
        or destination_known_safe
    )


def compare_head_to_bookmark(
    current: HeadSnapshot,
    bookmarked: HeadSnapshot,
) -> _BookmarkRelation:
    if current.version < bookmarked.version:
        return "behind"
    if current.version == bookmarked.version:
        if (
            current.last_hash == bookmarked.last_hash
            and current.last_event_id == bookmarked.last_event_id
        ):
            return "matches"
        return "conflict"
    return "advanced"


def classify_sync_state(
    *,
    source_head: HeadSnapshot,
    destination_head: HeadSnapshot,
    bookmark: SyncBookmark | None,
    expected_timeline_id: str | None = None,
    source_known_safe: bool = False,
    destination_known_safe: bool = False,
) -> SyncState:
    if bookmark is None:
        if is_missing_bookmark_bootstrap_safe(
            source_head=source_head,
            destination_head=destination_head,
            source_known_safe=source_known_safe,
            destination_known_safe=destination_known_safe,
        ):
            return "bookmark_missing"
        return "bookmark_incompatible"

    if expected_timeline_id is not None:
        validate_bookmark_matches_timeline(bookmark, timeline_id=expected_timeline_id)

    source_relation = compare_head_to_bookmark(source_head, bookmark.spoke_head())
    destination_relation = compare_head_to_bookmark(
        destination_head, bookmark.hub_head()
    )

    if source_relation in {"behind", "conflict"}:
        return "bookmark_incompatible"
    if destination_relation in {"behind", "conflict"}:
        return "bookmark_incompatible"
    if source_relation == "matches" and destination_relation == "matches":
        return "up_to_date"
    if source_relation == "advanced" and destination_relation == "matches":
        return "source_only"
    if source_relation == "matches" and destination_relation == "advanced":
        return "destination_only"
    if source_relation == "advanced" and destination_relation == "advanced":
        return "both_advanced"
    return "bookmark_incompatible"


def _require_int(value: object, label: str) -> int:
    if not isinstance(value, int):
        raise SyncStateError(f"bookmark.{label} must be an integer")
    return value


def _optional_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SyncStateError(f"bookmark.{label} must be a string or null")
    return value


def _validate_bookmark_side(
    *,
    version: int,
    last_hash: str | None,
    last_event_id: str | None,
    label: str,
) -> None:
    if version < 0:
        raise SyncStateError(f"bookmark.{label}_version must be >= 0")
    if version == 0:
        if last_hash is not None or last_event_id is not None:
            raise SyncStateError(
                f"bookmark.{label}_hash and {label}_event_id must be null when {label}_version is 0"
            )
        return
    if not last_hash or not last_event_id:
        raise SyncStateError(
            f"bookmark.{label}_hash and {label}_event_id are required when {label}_version is non-zero"
        )
