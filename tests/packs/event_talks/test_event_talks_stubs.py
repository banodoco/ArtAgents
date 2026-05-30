"""Smoke tests: event_talks stubs and data loading."""

import argparse
import pytest

from astrid.packs.video_editing.orchestrators.event_talks.run import (
    ADOS_SUNDAY_SPEAKERS,
    _exec_render_manifest,
)


def test_ados_sunday_speakers_loads():
    assert isinstance(ADOS_SUNDAY_SPEAKERS, list)
    assert len(ADOS_SUNDAY_SPEAKERS) > 0
    first = ADOS_SUNDAY_SPEAKERS[0]
    assert "speaker" in first
    assert "title" in first


def test_render_manifest_raises():
    args = argparse.Namespace()
    with pytest.raises(NotImplementedError, match="event_talks.render_manifest"):
        _exec_render_manifest(args)
