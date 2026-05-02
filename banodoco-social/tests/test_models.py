import pytest

from banodoco_social.models import (
    PublishError,
    URL_ONLY_VIDEO_ERROR,
    YouTubePublishRequest,
    normalize_tags,
    validate_privacy_status,
)


def test_youtube_publish_request_accepts_reachable_http_url():
    request = YouTubePublishRequest(
        video_url=" https://cdn.example.com/render.mp4 ",
        title="Rendered talk",
        description="A rendered talk video.",
        tags=["talk, ai", "banodoco"],
        privacy_status="UNLISTED",
        playlist_id="playlist-123",
        made_for_kids=True,
    )

    assert request.video_url == "https://cdn.example.com/render.mp4"
    assert request.tags == ("talk", "ai", "banodoco")
    assert request.privacy_status == "unlisted"
    assert request.playlist_id == "playlist-123"
    assert request.made_for_kids is True


def test_normalize_tags_handles_repeated_and_comma_separated_values():
    assert normalize_tags([" alpha, beta ", "gamma", "", "delta,"]) == (
        "alpha",
        "beta",
        "gamma",
        "delta",
    )


@pytest.mark.parametrize("privacy_status", ["private", "unlisted", "public"])
def test_validate_privacy_status_accepts_allowed_values(privacy_status):
    assert validate_privacy_status(privacy_status.upper()) == privacy_status


def test_validate_privacy_status_rejects_unknown_values():
    with pytest.raises(PublishError, match="Invalid privacy status"):
        validate_privacy_status("friends-only")


@pytest.mark.parametrize(
    "video_input",
    [
        "render.mp4",
        "./render.mp4",
        "/tmp/render.mp4",
        "~/render.mp4",
        "file:///tmp/render.mp4",
        "ftp://example.com/render.mp4",
        "https:///missing-host.mp4",
    ],
)
def test_youtube_publish_request_rejects_local_or_non_http_video_inputs(video_input):
    with pytest.raises(PublishError) as exc_info:
        YouTubePublishRequest(
            video_url=video_input,
            title="Rendered talk",
            description="A rendered talk video.",
        )

    assert str(exc_info.value) == URL_ONLY_VIDEO_ERROR
    assert "upload or stage" in str(exc_info.value)
    assert "reachable URL" in str(exc_info.value)
