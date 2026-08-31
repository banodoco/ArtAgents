"""Regression coverage for the P4 still-window and P5 root repairs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.timeline.banodoco_schema import canonical_timeline_config
from astrid.core.timeline.expand_shots import ShotExpansionError, expand_shot_clips
from scripts import build_storyboard as bs


FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINIMAL = FIXTURES / "storyboard-minimal.json"


class _Import:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, str | Path | None]] = []

    def __call__(
        self,
        path: Path,
        *,
        project: str = bs.DEFAULT_PROJECT,
        projects_root: str | Path | None = None,
    ) -> bs.AssetImport:
        self.calls.append((Path(path), project, projects_root))
        return bs.AssetImport(
            file=str(path),
            content_sha256="0" * 64,
            media_id=f"media-{len(self.calls)}",
        )


def _story() -> dict:
    return json.loads(MINIMAL.read_text(encoding="utf-8"))


def test_image_media_is_emitted_as_a_bounded_window() -> None:
    pytest.importorskip("banodoco_timeline_schema")
    importer = _Import()
    story = _story()
    config, registry, _ = bs.compile_storyboard(
        story,
        base_dir=FIXTURES,
        import_asset=importer,
        probe_duration=lambda _path: 2.5,
    )

    broll = [clip for clip in config["clips"] if clip["clipType"] == "media" and clip["track"] == "broll"]
    assert len(broll) == 2
    for clip, duration in zip(broll, (2.85, 2.85)):
        assert clip["from"] == 0.0
        assert clip["to"] == duration
        assert "hold" not in clip
        assert registry["assets"][clip["asset"]]["duration"] == duration
    assert canonical_timeline_config(config) is not None

    no_vo = _story()
    del no_vo["sections"][0]["vo"]
    no_vo_config, _, _ = bs.compile_storyboard(
        no_vo,
        base_dir=FIXTURES,
        import_asset=importer,
        probe_duration=lambda _path: 2.5,
    )
    no_vo_broll = [
        clip
        for clip in no_vo_config["clips"]
        if clip["clipType"] == "media" and clip["track"] == "broll"
    ]
    assert no_vo_broll[0]["from"] == 0.0
    assert no_vo_broll[0]["to"] == 3.0  # meta.timing.default_hold
    assert "hold" not in no_vo_broll[0]


def test_expansion_rejects_unbounded_image_media_before_renderer() -> None:
    config = {
        "clips": [
            {
                "id": "shot",
                "at": 0.0,
                "hold": 2.0,
                "clipType": "shot",
                "params": {"shot_id": "s", "timeline_document_id": "child"},
            }
        ]
    }

    def load_child(_ref: str):
        return (
            {
                "clips": [
                    {
                        "id": "image",
                        "at": 0.0,
                        "hold": 2.0,
                        "clipType": "media",
                        "asset": "still",
                    }
                ]
            },
            {"assets": {"still": {"file": "still.png", "type": "image"}}},
        )

    with pytest.raises(ShotExpansionError, match="hold without explicit from/to"):
        expand_shot_clips(config, {"assets": {}}, load_timeline=load_child)


def test_compile_threads_isolated_projects_root_to_default_importer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("banodoco_timeline_schema")
    importer = _Import()
    root = Path("/isolated/projects-root")
    monkeypatch.setattr(bs, "sdk_import_asset", importer)
    bs.compile_storyboard(
        _story(),
        base_dir=FIXTURES,
        import_asset=None,
        projects_root=root,
        project="isolated",
        probe_duration=lambda _path: 1.0,
    )
    assert importer.calls
    assert {call[2] for call in importer.calls} == {root}
