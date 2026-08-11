from __future__ import annotations

from astrid.packs.editorial.executors.validate.run import clip_timeline_duration_sec


def test_clip_duration_accepts_raw_json_from_alias() -> None:
    clip = {"clipType": "media", "from": 10.0, "to": 16.0, "speed": 2.0}

    assert clip_timeline_duration_sec(clip) == 3.0


def test_clip_duration_accepts_loaded_timeline_from_field() -> None:
    clip = {"clipType": "media", "from_": 10.0, "to": 16.0, "speed": 2.0}

    assert clip_timeline_duration_sec(clip) == 3.0
