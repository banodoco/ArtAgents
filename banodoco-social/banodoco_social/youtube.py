"""YouTube publishing entry points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import PublishError, YouTubePublishRequest

ZAPIER_YOUTUBE_ENV_VAR = "ZAPIER_YOUTUBE_URL"
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v="


@dataclass(frozen=True)
class YouTubePublishResult:
    provider_ref: str
    provider_url: str | None
    youtube_response: dict[str, Any]
    delete_supported: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_ref": self.provider_ref,
            "provider_url": self.provider_url,
            "delete_supported": self.delete_supported,
            "youtube_response": self.youtube_response,
        }


def publish_youtube_video(
    *,
    video_url: str,
    title: str,
    description: str,
    tags: list[str] | tuple[str, ...] | str | None = None,
    privacy_status: str = "private",
    playlist_id: str | None = None,
    made_for_kids: bool = False,
    webhook_url: str | None = None,
    timeout: float = 60,
    urlopen_func: Callable[..., Any] = urlopen,
) -> YouTubePublishResult:
    request = YouTubePublishRequest(
        video_url=video_url,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        playlist_id=playlist_id,
        made_for_kids=made_for_kids,
    )
    return publish_youtube_request(
        request,
        webhook_url=webhook_url,
        timeout=timeout,
        urlopen_func=urlopen_func,
    )


def publish_youtube_request(
    request: YouTubePublishRequest,
    *,
    webhook_url: str | None = None,
    timeout: float = 60,
    urlopen_func: Callable[..., Any] = urlopen,
) -> YouTubePublishResult:
    resolved_webhook_url = _resolve_webhook_url(webhook_url)
    payload = build_youtube_payload(request)
    response_json = _post_json(
        resolved_webhook_url,
        payload,
        timeout=timeout,
        urlopen_func=urlopen_func,
    )

    provider_ref = _provider_ref(response_json)
    if not provider_ref:
        raise PublishError("Zapier webhook returned malformed response data.")

    return YouTubePublishResult(
        provider_ref=provider_ref,
        provider_url=_provider_url(response_json),
        youtube_response=response_json,
    )


def build_youtube_payload(request: YouTubePublishRequest) -> dict[str, Any]:
    return {
        "platform": "youtube",
        "action": "post",
        "title": request.title,
        "description": request.description,
        "media_url": request.video_url,
        "media_urls": [request.video_url],
        "privacy_status": request.privacy_status,
        "tags": list(request.tags),
        "playlist_id": request.playlist_id,
        "made_for_kids": bool(request.made_for_kids),
    }


def _resolve_webhook_url(webhook_url: str | None) -> str:
    resolved = (webhook_url or os.getenv(ZAPIER_YOUTUBE_ENV_VAR) or "").strip()
    if not resolved:
        raise PublishError(
            f"{ZAPIER_YOUTUBE_ENV_VAR} is not configured; set it or pass webhook_url."
        )
    parsed = urlparse(resolved)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise PublishError(
            f"{ZAPIER_YOUTUBE_ENV_VAR} must be a reachable http(s) Zapier webhook URL."
        )
    return resolved


def _post_json(
    webhook_url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    urlopen_func: Callable[..., Any],
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen_func(request, timeout=timeout) as response:
            status = _response_status(response)
            response_body = response.read()
    except HTTPError as exc:
        response_body = exc.read()
        message = _decode_response_body(response_body)
        raise PublishError(
            f"Zapier webhook failed with HTTP {exc.code}: {message}"
        ) from exc
    except URLError as exc:
        raise PublishError(f"Zapier webhook request failed: {exc.reason}") from exc
    except OSError as exc:
        raise PublishError(f"Zapier webhook request failed: {exc}") from exc

    if status < 200 or status >= 300:
        message = _decode_response_body(response_body)
        raise PublishError(f"Zapier webhook failed with HTTP {status}: {message}")

    try:
        parsed = json.loads(_decode_response_body(response_body))
    except json.JSONDecodeError as exc:
        raise PublishError("Zapier webhook returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise PublishError("Zapier webhook returned malformed response data.")
    return parsed


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is not None:
        return int(status)
    return int(response.getcode())


def _decode_response_body(response_body: bytes) -> str:
    return response_body.decode("utf-8", errors="replace")


def _provider_ref(response_json: dict[str, Any]) -> str | None:
    for key in ("youtube_video_id", "video_id", "id", "attempt"):
        value = response_json.get(key)
        if value:
            return str(value)
    return None


def _provider_url(response_json: dict[str, Any]) -> str | None:
    for key in ("youtube_url", "video_url", "url"):
        value = response_json.get(key)
        if value:
            return str(value)

    video_id = response_json.get("youtube_video_id") or response_json.get("video_id")
    if video_id:
        return f"{YOUTUBE_WATCH_URL}{video_id}"
    return None


__all__ = [
    "PublishError",
    "YouTubePublishResult",
    "build_youtube_payload",
    "publish_youtube_request",
    "publish_youtube_video",
]
