"""Facade-boundary tests for ``rendering.render`` after the T4.2 rework.

The facade keeps its public ``render(...)`` signature and the
``rendering.render`` capability id, but delegates all dispatch to
:class:`RenderService`: legacy engine translation, renderer/planner selection,
support, invocation, validation, and publication.  These tests pin the
facade's delegation surface without spawning any media tool.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.packs.rendering.executors.render import run as render_run


class _FakeService:
    def __init__(self, sentinel: Path | None = None) -> None:
        self.sentinel = sentinel
        self.calls: list[tuple[tuple, dict]] = []

    def render(self, *args, **kwargs) -> Path:
        self.calls.append((args, kwargs))
        if self.sentinel is not None:
            return self.sentinel
        raise AssertionError("unexpected service render call")


@pytest.fixture
def fake_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _FakeService:
    fake = _FakeService(tmp_path / "sentinel.mp4")
    monkeypatch.setattr(render_run, "_default_service", lambda: fake)
    return fake


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    timeline = tmp_path / "hype.timeline.json"
    assets = tmp_path / "hype.assets.json"
    out = tmp_path / "out" / "hype.mp4"
    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
    assets.write_text('{"assets": {}}', encoding="utf-8")
    return timeline, assets, out


def test_render_delegates_to_service_with_default_selector(fake_service: _FakeService, tmp_path: Path) -> None:
    timeline, assets, out = _inputs(tmp_path)
    sentinel = tmp_path / "sentinel.mp4"
    fake_service.sentinel = sentinel

    result = render_run.render(timeline, assets, out)

    assert result == sentinel
    assert len(fake_service.calls) == 1
    (call_args, call_kwargs) = fake_service.calls[0]
    assert call_args == (timeline, assets, out)
    assert call_kwargs["selector"] == "remotion"
    assert call_kwargs["previous_outputs"] == ()
    # Legacy kwargs map onto namespaced backend config.
    assert call_kwargs["backend_config"]["rendering.remotion"] == {
        "composition_id": "TimelineComposition"
    }


@pytest.mark.parametrize(
    "engine",
    ["remotion", "ffmpeg", "hybrid", "rendering.remotion", "rendering.ffmpeg"],
)
def test_render_forwards_legacy_and_qualified_selectors(
    fake_service: _FakeService, tmp_path: Path, engine: str
) -> None:
    timeline, assets, out = _inputs(tmp_path)

    render_run.render(timeline, assets, out, engine=engine)

    assert len(fake_service.calls) == 1
    assert fake_service.calls[0][1]["selector"] == engine


def test_render_maps_legacy_kwargs_into_namespaced_backend_config(
    fake_service: _FakeService, tmp_path: Path
) -> None:
    timeline, assets, out = _inputs(tmp_path)

    render_run.render(
        timeline,
        assets,
        out,
        engine="hybrid",
        project_dir=tmp_path / "remotion",
        composition_id="CustomComposition",
        theme_path=tmp_path / "theme.json",
        min_free_gb=2.0,
    )

    assert len(fake_service.calls) == 1
    config = fake_service.calls[0][1]["backend_config"]
    assert config["rendering.remotion"] == {
        "project_dir": str(tmp_path / "remotion"),
        "composition_id": "CustomComposition",
        "theme_path": str(tmp_path / "theme.json"),
        "min_free_gb": 2.0,
    }
    assert config["rendering.legacy_hybrid"] == {
        "theme_path": str(tmp_path / "theme.json")
    }


def test_render_merges_explicit_backend_config_after_legacy_kwargs(
    fake_service: _FakeService, tmp_path: Path
) -> None:
    timeline, assets, out = _inputs(tmp_path)

    render_run.render(
        timeline,
        assets,
        out,
        engine="rendering.remotion",
        theme_path=tmp_path / "theme.json",
        backend_config={
            "rendering.remotion": {
                "theme_path": str(tmp_path / "override.json"),
                "min_free_gb": 9.5,
            }
        },
    )

    assert len(fake_service.calls) == 1
    config = fake_service.calls[0][1]["backend_config"]
    assert config["rendering.remotion"]["theme_path"] == str(tmp_path / "override.json")
    assert config["rendering.remotion"]["min_free_gb"] == 9.5


def test_render_passes_previous_outputs_when_preserving(fake_service: _FakeService, tmp_path: Path) -> None:
    timeline, assets, out = _inputs(tmp_path)

    render_run.render(timeline, assets, out, keep_previous_renders=True)

    assert len(fake_service.calls) == 1
    assert fake_service.calls[0][1]["previous_outputs"] == ()


def test_render_validates_output_name_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    timeline, assets, _out = _inputs(tmp_path)
    bad_out = tmp_path / "out" / "video.mov"

    with pytest.raises(ValueError, match=r"\.mp4"):
        render_run.render(timeline, assets, bad_out)


def test_main_accepts_output_name_and_forward_parses_any_order(
    fake_service: _FakeService, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    timeline, assets, out = _inputs(tmp_path)
    out = tmp_path / "out" / "iteration.mp4"
    fake_service.sentinel = out

    result = render_run.main(
        [
            "--out",
            str(out),
            "--output-name",
            "iteration.mp4",
            "--timeline",
            str(timeline),
            "--assets",
            str(assets),
            "--engine",
            "rendering.ffmpeg",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.strip() == str(out)
    assert len(fake_service.calls) == 1
    assert fake_service.calls[0][1]["selector"] == "rendering.ffmpeg"


def test_main_rejects_traversal_output_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    timeline, assets, _out = _inputs(tmp_path)

    result = render_run.main(
        [
            "--timeline",
            str(timeline),
            "--assets",
            str(assets),
            "--out",
            str(tmp_path / "out" / "hype.mp4"),
            "--output-name",
            "../evil.mp4",
        ]
    )

    assert result == 1
    assert "traverse" in capsys.readouterr().err


def test_main_rejects_conflicting_engine_and_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    timeline, assets, _out = _inputs(tmp_path)

    result = render_run.main(
        [
            "--timeline",
            str(timeline),
            "--assets",
            str(assets),
            "--out",
            str(tmp_path / "out" / "hype.mp4"),
            "--engine",
            "remotion",
            "--backend",
            "ffmpeg",
        ]
    )

    assert result == 1
    assert "conflict" in capsys.readouterr().err


def test_main_engine_defaults_to_remotion_when_absent(
    tmp_path: Path, fake_service: _FakeService
) -> None:
    timeline, assets, out = _inputs(tmp_path)
    fake_service.sentinel = out

    result = render_run.main(
        [
            "--timeline",
            str(timeline),
            "--assets",
            str(assets),
            "--out",
            str(out),
        ]
    )

    assert result == 0
    assert len(fake_service.calls) == 1
    assert fake_service.calls[0][1]["selector"] == "remotion"
