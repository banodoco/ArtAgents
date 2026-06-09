"""Tests for astrid.core.util.http — mockable HttpClient with secret scrubbing."""

from __future__ import annotations

import json
import time
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.util.http import (
    FAL_QUEUE_URL,
    HttpClient,
    Transport,
    default_client,
    fal_submit_and_poll,
    fal_upload,
)


# ---------------------------------------------------------------------------
# Mock transport helpers
# ---------------------------------------------------------------------------


def _canned_transport(
    status: int = 200,
    body: bytes | dict | str = b"{}",
    headers: dict[str, str] | None = None,
) -> Transport:
    """Return a transport that always returns *status* and *body*."""

    if isinstance(body, dict):
        body = json.dumps(body).encode("utf-8")
    elif isinstance(body, str):
        body = body.encode("utf-8")

    def _transport(_request: Request) -> tuple[int, bytes]:
        return status, body

    return _transport


def _error_transport(
    code: int,
    body: str = "",
    url: str = "https://example.com/api",
) -> Transport:
    """Return a transport that raises HTTPError."""

    def _transport(_request: Request) -> tuple[int, bytes]:
        # Build a minimal response-like object for HTTPError
        from io import BytesIO

        fp = BytesIO(body.encode("utf-8")) if body else BytesIO()
        exc = HTTPError(
            url,
            code,
            "Error",
            {},  # headers
            fp,
        )
        raise exc

    return _transport


def _sequence_transport(*responses: tuple[int, bytes | dict]) -> Transport:
    """Return a transport that cycles through *responses* in order."""

    seq = list(responses)
    it = iter(seq)

    def _transport(_request: Request) -> tuple[int, bytes]:
        try:
            status, body = next(it)
        except StopIteration:
            # Re-raise the last response
            status, body = seq[-1]
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
        return status, body

    return _transport


# ---------------------------------------------------------------------------
# Constructor + injectable transport
# ---------------------------------------------------------------------------


class TestHttpClientConstruction:
    def test_default_transport_is_real(self):
        """Default client uses a real transport (not injected)."""
        client = HttpClient()
        assert client._transport is not None
        # The default transport is _real_transport (not a mock)
        assert callable(client._transport)

    def test_injected_transport_used(self):
        """When a transport is injected, it replaces the default."""
        called = []

        def fake(_req: Request) -> tuple[int, bytes]:
            called.append(True)
            return 200, b"{}"

        client = HttpClient(transport=fake)
        client.get_json("https://example.com/api")
        assert len(called) == 1

    def test_default_client_singleton(self):
        """default_client() returns a singleton."""
        c1 = default_client()
        c2 = default_client()
        assert c1 is c2


# ---------------------------------------------------------------------------
# Secret scrubbing
# ---------------------------------------------------------------------------


class TestSecretScrubbing:
    def test_register_and_scrub(self):
        client = HttpClient(transport=_canned_transport())
        client.register_secret("sk-secret-key-12345")
        result = client.scrub_secret("Auth: sk-secret-key-12345 was used")
        assert "sk-secret-key-12345" not in result
        assert "***" in result

    def test_scrub_multiple_secrets(self):
        client = HttpClient(transport=_canned_transport())
        client.register_secret("sekret1")
        client.register_secret("sekret2")
        result = client.scrub_secret("sekret1 and sekret2 leaked")
        assert "sekret1" not in result
        assert "sekret2" not in result
        assert "***" in result

    def test_empty_secret_noop(self):
        client = HttpClient(transport=_canned_transport())
        client.register_secret("")
        assert client.scrub_secret("text") == "text"

    def test_duplicate_registration_ignored(self):
        client = HttpClient(transport=_canned_transport())
        client.register_secret("dup")
        client.register_secret("dup")
        assert len(client._secrets) == 1

    def test_4xx_error_scrubs_secret(self):
        """SC15: 4xx error body containing API key must be scrubbed."""
        api_key = "sk-secret-key-12345"
        client = HttpClient(transport=_error_transport(401, f'{{"error":"bad key {api_key}"}}'))
        client.register_secret(api_key)

        with pytest.raises(AstridError) as exc_info:
            client.post_json("https://example.com/api", {"prompt": "test"})

        message = str(exc_info.value)
        assert api_key not in message, f"API key leaked in error: {message}"
        assert "***" in message, f"No scrubbing applied: {message}"


# ---------------------------------------------------------------------------
# HTTP methods
# ---------------------------------------------------------------------------


class TestPostJson:
    def test_2xx_response(self):
        client = HttpClient(transport=_canned_transport(200, {"result": "ok"}))
        result = client.post_json("https://example.com/api", {"key": "val"})
        assert result == {"result": "ok"}

    def test_4xx_raises_system_exit(self):
        client = HttpClient(transport=_error_transport(400, '{"error":"bad request"}'))
        with pytest.raises(AstridError):
            client.post_json("https://example.com/api", {})

    def test_5xx_raises_system_exit(self):
        client = HttpClient(transport=_error_transport(500, "Internal Server Error"))
        with pytest.raises(AstridError):
            client.post_json("https://example.com/api", {})

    def test_custom_headers_sent(self):
        """Headers passed to post_json are included in the request."""
        captured = []

        def capture(req: Request) -> tuple[int, bytes]:
            captured.append(dict(req.headers))
            return 200, b"{}"

        client = HttpClient(transport=capture)
        client.post_json(
            "https://example.com/api",
            {"x": 1},
            headers={"authorization": "Key abc123"},
        )
        assert len(captured) == 1
        assert captured[0].get("Authorization") == "Key abc123" or captured[0].get(
            "authorization"
        ) == "Key abc123"


class TestGetJson:
    def test_2xx_response(self):
        client = HttpClient(transport=_canned_transport(200, {"data": [1, 2, 3]}))
        result = client.get_json("https://example.com/api")
        assert result == {"data": [1, 2, 3]}


class TestGetBytes:
    def test_2xx_bytes(self):
        client = HttpClient(transport=_canned_transport(200, b"\x89PNG..."))
        result = client.get_bytes("https://example.com/image.png")
        assert result == b"\x89PNG..."

    def test_4xx_raises(self):
        client = HttpClient(transport=_error_transport(404))
        with pytest.raises(AstridError):
            client.get_bytes("https://example.com/missing.png")


# ---------------------------------------------------------------------------
# poll_until
# ---------------------------------------------------------------------------


class TestPollUntil:
    def test_completes_on_ok(self):
        """poll_until returns result when status is COMPLETED."""
        responses = [
            (200, {"status": "PENDING"}),
            (200, {"status": "COMPLETED"}),
            (200, {"result": "final"}),
        ]
        client = HttpClient(transport=_sequence_transport(*responses))

        # Patch time.monotonic to avoid real delays
        with patch("time.monotonic", side_effect=[0, 1, 2, 3, 4, 5]):
            with patch("time.sleep", return_value=None):
                result = client.poll_until(
                    "https://queue.fal.run/status",
                    "https://queue.fal.run/result",
                )
        assert result == {"result": "final"}

    def test_fails_on_error_status(self):
        """poll_until raises on FAILED status."""
        responses = [
            (200, {"status": "PENDING"}),
            (200, {"status": "FAILED", "error": "GPU OOM"}),
        ]
        client = HttpClient(transport=_sequence_transport(*responses))

        with patch("time.monotonic", side_effect=[0, 1, 2]):
            with patch("time.sleep", return_value=None):
                with pytest.raises(AstridError) as exc_info:
                    client.poll_until(
                        "https://queue.fal.run/status",
                        "https://queue.fal.run/result",
                    )
        assert "FAILED" in str(exc_info.value)

    def test_timeout(self):
        """poll_until raises on timeout."""
        responses = [(200, {"status": "PENDING"})] * 20
        client = HttpClient(transport=_sequence_transport(*responses))

        with patch("time.monotonic", side_effect=[0, 100, 200, 300, 400]):
            with patch("time.sleep", return_value=None):
                with pytest.raises(AstridError) as exc_info:
                    client.poll_until(
                        "https://queue.fal.run/status",
                        "https://queue.fal.run/result",
                        max_wait_sec=10,
                    )
        assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# fal helpers
# ---------------------------------------------------------------------------


class TestFalUpload:
    def test_upload_returns_data_uri(self):
        """fal_upload returns a base64 data URI; no network call is made."""
        import tempfile
        from base64 import b64encode
        from pathlib import Path

        client = HttpClient(transport=_canned_transport(500, {"detail": "should not be called"}))
        body = b"\x89PNG fake"
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(body)
            tmp_path = Path(f.name)

        try:
            url = fal_upload(client, tmp_path, api_key="test-key")
            expected = f"data:image/png;base64,{b64encode(body).decode('ascii')}"
            assert url == expected
        finally:
            tmp_path.unlink()

    def test_upload_uses_mime_from_suffix(self):
        """jpg/webp suffixes pick the right mime; unknown defaults to png."""
        import tempfile
        from pathlib import Path

        client = HttpClient(transport=_canned_transport(500, {"detail": "unused"}))
        for suffix, expected_mime in [(".jpg", "image/jpeg"), (".webp", "image/webp"), (".xyz", "image/png")]:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(b"bytes")
                tmp_path = Path(f.name)
            try:
                url = fal_upload(client, tmp_path, api_key="test-key")
                assert url.startswith(f"data:{expected_mime};base64,")
            finally:
                tmp_path.unlink()


class TestFalSubmitAndPoll:
    def test_submit_and_poll_success(self):
        """fal_submit_and_poll submits, polls, and returns result."""
        responses = [
            # Submit response
            (
                200,
                {
                    "status_url": "https://queue.fal.run/fal-ai/flux/dev/requests/req123/status",
                    "response_url": "https://queue.fal.run/fal-ai/flux/dev/requests/req123",
                    "request_id": "req123",
                },
            ),
            # Status poll
            (200, {"status": "PENDING"}),
            # Status poll
            (200, {"status": "COMPLETED"}),
            # Result
            (
                200,
                {
                    "images": [{"url": "https://fal.media/tmp/out.png"}],
                    "seed": 42,
                    "prompt": "test",
                },
            ),
        ]
        client = HttpClient(transport=_sequence_transport(*responses))

        with patch("time.monotonic", side_effect=[0, 1, 2, 3, 4, 5, 6]):
            with patch("time.sleep", return_value=None):
                result = fal_submit_and_poll(
                    client,
                    "fal-ai/flux/dev",
                    {"prompt": "test"},
                    api_key="test-key",
                )

        assert result["images"][0]["url"] == "https://fal.media/tmp/out.png"
        assert result["seed"] == 42
        assert result["request_id"] == "req123"

    def test_submit_missing_urls_raises(self):
        """fal_submit_and_poll raises if status_url/response_url missing."""
        client = HttpClient(
            transport=_canned_transport(200, {"request_id": "req123"})
        )
        with pytest.raises(AstridError):
            fal_submit_and_poll(
                client,
                "fal-ai/flux/dev",
                {"prompt": "test"},
                api_key="test-key",
            )


# ---------------------------------------------------------------------------
# Mockability verification — no real HTTP
# ---------------------------------------------------------------------------


class TestMockability:
    def test_no_real_http_with_injected_transport(self):
        """When transport is injected, no real HTTP calls fire."""
        call_count = 0

        def fake(_req: Request) -> tuple[int, bytes]:
            nonlocal call_count
            call_count += 1
            return 200, b"{}"

        client = HttpClient(transport=fake)
        client.post_json("https://example.com/api", {})
        client.get_json("https://example.com/api")
        client.get_bytes("https://example.com/api")
        assert call_count == 3

        # Verify no real HTTP — the fake transport doesn't use urllib
        # This is implicit: if urllib were called, the fake wouldn't be hit

    def test_secrets_scrubbed_in_urlerror(self):
        """URLError messages are scrubbed."""
        api_key = "sk-leaked-key"

        def raise_urlerror(_req: Request) -> tuple[int, bytes]:
            raise URLError(f"Connection refused for {api_key}")

        client = HttpClient(transport=raise_urlerror)
        client.register_secret(api_key)

        with pytest.raises(AstridError) as exc_info:
            client.post_json("https://example.com/api", {})

        message = str(exc_info.value)
        assert api_key not in message, f"Secret leaked in URLError: {message}"
        assert "***" in message
