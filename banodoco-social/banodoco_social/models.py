"""Request and response models for social publishing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse


class PublishError(Exception):
    """Raised when a social publish request cannot be completed."""


ALLOWED_PRIVACY_STATUSES = frozenset({"private", "unlisted", "public"})
URL_ONLY_VIDEO_ERROR = (
    "Video input must be a reachable http(s) URL. Local files and non-http(s) "
    "inputs are not supported; upload or stage the file to a reachable URL first."
)


def normalize_tags(tags: Iterable[str] | str | None = None) -> tuple[str, ...]:
    """Normalize repeated and comma-separated tag values."""
    if tags is None:
        return ()

    if isinstance(tags, str):
        raw_tags = (tags,)
    else:
        raw_tags = tags

    normalized: list[str] = []
    for raw_tag in raw_tags:
        for part in str(raw_tag).split(","):
            tag = part.strip()
            if tag:
                normalized.append(tag)
    return tuple(normalized)


def validate_privacy_status(privacy_status: str) -> str:
    if not isinstance(privacy_status, str):
        raise PublishError(
            f"Invalid privacy status {privacy_status!r}; expected a string."
        )

    normalized = privacy_status.strip().lower()
    if normalized not in ALLOWED_PRIVACY_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_PRIVACY_STATUSES))
        raise PublishError(
            f"Invalid privacy status {privacy_status!r}; expected one of: {allowed}."
        )
    return normalized


def validate_reachable_video_url(video_url: str) -> str:
    if not isinstance(video_url, str):
        raise PublishError(URL_ONLY_VIDEO_ERROR)

    normalized = video_url.strip()
    parsed = urlparse(normalized)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise PublishError(URL_ONLY_VIDEO_ERROR)
    return normalized


@dataclass(frozen=True)
class YouTubePublishRequest:
    """Validated request metadata for a YouTube publish."""

    video_url: str
    title: str
    description: str
    tags: Iterable[str] | str | None = field(default_factory=tuple)
    privacy_status: str = "private"
    playlist_id: str | None = None
    made_for_kids: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "video_url", validate_reachable_video_url(self.video_url)
        )
        object.__setattr__(
            self, "privacy_status", validate_privacy_status(self.privacy_status)
        )
        object.__setattr__(self, "tags", normalize_tags(self.tags))
