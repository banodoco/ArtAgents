from dataclasses import dataclass

import pytest

from banodoco_social import cli
from banodoco_social.models import PublishError


@dataclass(frozen=True)
class FakeResult:
    def as_dict(self):
        return {
            "provider_ref": "abc123",
            "provider_url": "https://www.youtube.com/watch?v=abc123",
            "delete_supported": False,
            "youtube_response": {"youtube_video_id": "abc123"},
        }


def test_cli_youtube_prints_compact_json(monkeypatch, capsys):
    captured = {}

    def fake_publish_youtube_video(**kwargs):
        captured.update(kwargs)
        return FakeResult()

    monkeypatch.setattr(cli, "publish_youtube_video", fake_publish_youtube_video)

    exit_code = cli.main(
        [
            "youtube",
            "--video-url",
            "https://cdn.example.com/render.mp4",
            "--title",
            "Rendered talk",
            "--description",
            "A rendered talk video.",
            "--tag",
            "talk",
            "--tag",
            "ai",
            "--tags",
            "banodoco,event",
            "--privacy-status",
            "unlisted",
            "--playlist-id",
            "playlist-123",
            "--made-for-kids",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "video_url": "https://cdn.example.com/render.mp4",
        "title": "Rendered talk",
        "description": "A rendered talk video.",
        "tags": ["talk", "ai", "banodoco,event"],
        "privacy_status": "unlisted",
        "playlist_id": "playlist-123",
        "made_for_kids": True,
    }
    assert capsys.readouterr().out == (
        '{"provider_ref":"abc123","provider_url":"https://www.youtube.com/watch?v=abc123",'
        '"delete_supported":false,"youtube_response":{"youtube_video_id":"abc123"}}\n'
    )


def test_cli_youtube_alias_video_flag(monkeypatch):
    captured = {}

    def fake_publish_youtube_video(**kwargs):
        captured.update(kwargs)
        return FakeResult()

    monkeypatch.setattr(cli, "publish_youtube_video", fake_publish_youtube_video)

    assert (
        cli.main(
            [
                "youtube",
                "--video",
                "https://cdn.example.com/render.mp4",
                "--title",
                "Rendered talk",
                "--description",
                "A rendered talk video.",
            ]
        )
        == 0
    )
    assert captured["video_url"] == "https://cdn.example.com/render.mp4"


def test_cli_youtube_publish_error_returns_one(monkeypatch, capsys):
    def fake_publish_youtube_video(**kwargs):
        raise PublishError("Video input must be a reachable http(s) URL.")

    monkeypatch.setattr(cli, "publish_youtube_video", fake_publish_youtube_video)

    exit_code = cli.main(
        [
            "youtube",
            "--video-url",
            "./render.mp4",
            "--title",
            "Rendered talk",
            "--description",
            "A rendered talk video.",
        ]
    )

    assert exit_code == 1
    assert capsys.readouterr().err == (
        "banodoco-social: Video input must be a reachable http(s) URL.\n"
    )


def test_cli_youtube_local_path_rejected_by_shared_validation(capsys):
    exit_code = cli.main(
        [
            "youtube",
            "--video-url",
            "./render.mp4",
            "--title",
            "Rendered talk",
            "--description",
            "A rendered talk video.",
        ]
    )

    assert exit_code == 1
    assert "upload or stage" in capsys.readouterr().err


def test_cli_youtube_requires_video_title_and_description():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["youtube"])

    assert exc_info.value.code == 2
