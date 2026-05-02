import json

import pytest

from banodoco_social.models import PublishError, YouTubePublishRequest
from banodoco_social.youtube import (
    build_youtube_payload,
    publish_youtube_request,
    publish_youtube_video,
)


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        if isinstance(self.body, bytes):
            return self.body
        return json.dumps(self.body).encode("utf-8")


def test_build_youtube_payload_uses_established_zapier_keys():
    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
        tags=["talk", "ai"],
        privacy_status="public",
        playlist_id="playlist-123",
        made_for_kids=True,
    )

    assert build_youtube_payload(request) == {
        "platform": "youtube",
        "action": "post",
        "title": "Rendered talk",
        "description": "A rendered talk video.",
        "media_url": "https://cdn.example.com/render.mp4",
        "media_urls": ["https://cdn.example.com/render.mp4"],
        "privacy_status": "public",
        "tags": ["talk", "ai"],
        "playlist_id": "playlist-123",
        "made_for_kids": True,
    }


def test_publish_youtube_request_posts_json_and_parses_video_id(monkeypatch):
    monkeypatch.delenv("ZAPIER_YOUTUBE_URL", raising=False)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse({"youtube_video_id": "abc123"})

    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
        tags="talk, ai",
        privacy_status="unlisted",
    )

    result = publish_youtube_request(
        request,
        webhook_url="https://hooks.zapier.com/hooks/catch/example/",
        timeout=12,
        urlopen_func=fake_urlopen,
    )

    assert captured["request"].get_method() == "POST"
    assert captured["request"].get_header("Content-type") == "application/json"
    assert captured["timeout"] == 12
    assert json.loads(captured["request"].data.decode("utf-8"))["media_urls"] == [
        "https://cdn.example.com/render.mp4"
    ]
    assert result.provider_ref == "abc123"
    assert result.provider_url == "https://www.youtube.com/watch?v=abc123"
    assert result.youtube_response == {"youtube_video_id": "abc123"}


@pytest.mark.parametrize(
    ("response_body", "provider_ref", "provider_url"),
    [
        (
            {"video_id": "video-1"},
            "video-1",
            "https://www.youtube.com/watch?v=video-1",
        ),
        (
            {"id": "zapier-id", "youtube_url": "https://youtu.be/video-2"},
            "zapier-id",
            "https://youtu.be/video-2",
        ),
        ({"attempt": "attempt-1", "url": "https://youtu.be/video-3"}, "attempt-1", "https://youtu.be/video-3"),
    ],
)
def test_publish_youtube_request_parses_response_fallbacks(
    monkeypatch, response_body, provider_ref, provider_url
):
    monkeypatch.setenv("ZAPIER_YOUTUBE_URL", "https://hooks.zapier.test/youtube")

    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
    )

    result = publish_youtube_request(
        request,
        urlopen_func=lambda request, timeout: FakeResponse(response_body),
    )

    assert result.provider_ref == provider_ref
    assert result.provider_url == provider_url


def test_publish_youtube_video_rejects_local_path_before_http(monkeypatch):
    monkeypatch.setenv("ZAPIER_YOUTUBE_URL", "https://hooks.zapier.test/youtube")
    called = False

    def fake_urlopen(request, timeout):
        nonlocal called
        called = True
        return FakeResponse({"youtube_video_id": "abc123"})

    with pytest.raises(PublishError, match="upload or stage"):
        publish_youtube_video(
            video_url="./render.mp4",
            title="Rendered talk",
            description="A rendered talk video.",
            urlopen_func=fake_urlopen,
        )

    assert called is False


def test_publish_youtube_request_requires_zapier_url(monkeypatch):
    monkeypatch.delenv("ZAPIER_YOUTUBE_URL", raising=False)
    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
    )

    with pytest.raises(PublishError, match="ZAPIER_YOUTUBE_URL is not configured"):
        publish_youtube_request(
            request,
            urlopen_func=lambda request, timeout: FakeResponse({"id": "unused"}),
        )


def test_publish_youtube_request_rejects_invalid_zapier_url_before_http(monkeypatch):
    monkeypatch.setenv("ZAPIER_YOUTUBE_URL", "./zapier-hook")
    called = False
    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
    )

    def fake_urlopen(request, timeout):
        nonlocal called
        called = True
        return FakeResponse({"youtube_video_id": "abc123"})

    with pytest.raises(PublishError, match="http\\(s\\) Zapier webhook URL"):
        publish_youtube_request(request, urlopen_func=fake_urlopen)

    assert called is False


def test_publish_youtube_request_rejects_non_2xx_response(monkeypatch):
    monkeypatch.setenv("ZAPIER_YOUTUBE_URL", "https://hooks.zapier.test/youtube")
    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
    )

    with pytest.raises(PublishError, match="HTTP 500"):
        publish_youtube_request(
            request,
            urlopen_func=lambda request, timeout: FakeResponse(b"server error", 500),
        )


def test_publish_youtube_request_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("ZAPIER_YOUTUBE_URL", "https://hooks.zapier.test/youtube")
    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
    )

    with pytest.raises(PublishError, match="invalid JSON"):
        publish_youtube_request(
            request,
            urlopen_func=lambda request, timeout: FakeResponse(b"not json"),
        )


def test_publish_youtube_request_rejects_malformed_response(monkeypatch):
    monkeypatch.setenv("ZAPIER_YOUTUBE_URL", "https://hooks.zapier.test/youtube")
    request = YouTubePublishRequest(
        video_url="https://cdn.example.com/render.mp4",
        title="Rendered talk",
        description="A rendered talk video.",
    )

    with pytest.raises(PublishError, match="malformed response data"):
        publish_youtube_request(
            request,
            urlopen_func=lambda request, timeout: FakeResponse({"status": "ok"}),
        )
