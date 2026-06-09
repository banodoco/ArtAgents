"""Shared UTC timestamp helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

TimeSpec = Literal["auto", "hours", "minutes", "seconds", "milliseconds", "microseconds"]


def utc_now_iso(*, timespec: TimeSpec = "auto") -> str:
    """Return the current UTC time as ISO 8601 with a trailing ``Z``."""

    if timespec == "auto":
        stamp = datetime.now(UTC).isoformat()
    else:
        stamp = datetime.now(UTC).isoformat(timespec=timespec)
    return stamp.replace("+00:00", "Z")


def utc_now_seconds() -> str:
    """Return the current UTC time rounded to whole seconds."""

    return utc_now_iso(timespec="seconds")


def _utc_now() -> str:
    """Return the current UTC time rounded to whole seconds (convenience alias)."""

    return utc_now_seconds()


def utc_now_milliseconds() -> str:
    """Return the current UTC time rounded to milliseconds."""

    return utc_now_iso(timespec="milliseconds")
