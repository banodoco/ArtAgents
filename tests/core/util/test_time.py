from __future__ import annotations

import re
from datetime import datetime

from astrid.core.util.time import utc_now_iso, utc_now_milliseconds, utc_now_seconds


def test_utc_now_iso_uses_zulu_utc_suffix() -> None:
    stamp = utc_now_iso()

    assert stamp.endswith("Z")
    assert "+00:00" not in stamp
    datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def test_utc_now_seconds_preserves_whole_second_format() -> None:
    stamp = utc_now_seconds()

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp)


def test_utc_now_milliseconds_preserves_millisecond_format() -> None:
    stamp = utc_now_milliseconds()

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", stamp)
