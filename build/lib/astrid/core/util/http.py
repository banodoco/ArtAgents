"""Mockable HTTP client with secret scrubbing and fal.ai helpers.

Uses stdlib ``urllib.request`` by default.  Swap the transport callable in
tests to avoid real HTTP calls.
"""

from __future__ import annotations

import json
import time
from base64 import b64encode
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAL_QUEUE_URL = "https://queue.fal.run"

# ---------------------------------------------------------------------------
# Transport type
# ---------------------------------------------------------------------------

# A transport receives a ``urllib.request.Request`` and returns
# ``(status: int, body: bytes)``.
Transport = Callable[[Request], tuple[int, bytes]]


# ---------------------------------------------------------------------------
# Default (real-http) transport
# ---------------------------------------------------------------------------

def _real_transport(request: Request) -> tuple[int, bytes]:
    """Execute *request* against the real network.

    Returns ``(status, body)``.  Raises ``URLError`` on connection failure.
    """
    with urlopen(request, timeout=_extract_timeout(request)) as response:
        return response.status, response.read()


def _extract_timeout(request: Request) -> int:
    """Pull a timeout value from *request* extras, defaulting to 60."""
    return getattr(request, "timeout", 60) or 60


# ---------------------------------------------------------------------------
# HttpClient
# ---------------------------------------------------------------------------

class HttpClient:
    """Mockable HTTP client with built-in secret scrubbing.

    Parameters:
        transport: A callable ``(Request) -> (status, bytes)``.  Inject a
            mock in tests; leave ``None`` for real HTTP.
        default_timeout: Seconds for requests that don't specify one.
    """

    def __init__(
        self,
        transport: Transport | None = None,
        default_timeout: int = 60,
    ) -> None:
        self._transport = transport or _real_transport
        self._default_timeout = default_timeout
        self._secrets: list[str] = []

    # -- secret management --------------------------------------------------

    def register_secret(self, value: str) -> None:
        """Register *value* for scrubbing from all future error messages."""
        if value and value not in self._secrets:
            self._secrets.append(value)

    def scrub_secret(self, text: str) -> str:
        """Replace every registered secret in *text* with ``"***"``."""
        for secret in self._secrets:
            if secret:
                text = text.replace(secret, "***")
        return text

    # -- HTTP methods -------------------------------------------------------

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """POST *payload* as JSON, return parsed JSON response."""
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, method="POST")
        request.add_header("content-type", "application/json")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        return self._send(request, timeout=timeout)

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """GET *url*, return parsed JSON response."""
        request = Request(url, method="GET")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        return self._send(request, timeout=timeout)

    def get_bytes(
        self,
        url: str,
        *,
        timeout: int | None = None,
    ) -> bytes:
        """GET *url*, return raw bytes."""
        request = Request(url, method="GET")
        try:
            _status, body = self._transport(request)
        except HTTPError as exc:
            detail = self.scrub_secret(
                exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            )
            raise SystemExit(
                self.scrub_secret(f"HTTP {exc.code} GET {url}: {detail}")
            ) from exc
        except URLError as exc:
            raise SystemExit(
                self.scrub_secret(f"Network error GET {url}: {exc}")
            ) from exc
        return body

    # -- polling ------------------------------------------------------------

    def poll_until(
        self,
        status_url: str,
        response_url: str,
        *,
        headers: dict[str, str] | None = None,
        max_wait_sec: int = 300,
        delay_initial: float = 2.0,
        delay_factor: float = 1.4,
        delay_max: float = 8.0,
    ) -> dict[str, Any]:
        """Poll *status_url* until COMPLETED/OK, then GET *response_url*.

        Raises ``SystemExit`` on FAILED / ERROR / CANCELLED status or timeout.
        """
        deadline = time.monotonic() + max_wait_sec
        delay = delay_initial
        while time.monotonic() < deadline:
            status = self.get_json(status_url, headers=headers)
            state = str(status.get("status") or "").upper()
            if state in {"COMPLETED", "OK"}:
                return self.get_json(response_url, headers=headers)
            if state in {"FAILED", "ERROR", "CANCELLED"}:
                raise SystemExit(
                    self.scrub_secret(f"fal job {state}: {json.dumps(status)}")
                )
            time.sleep(delay)
            delay = min(delay * delay_factor, delay_max)
        raise SystemExit(
            self.scrub_secret(
                f"fal job timed out after {max_wait_sec}s; "
                f"last status_url={status_url}"
            )
        )

    # -- internal -----------------------------------------------------------

    def _send(
        self,
        request: Request,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Execute *request*, return parsed JSON body."""
        effective = timeout or self._default_timeout
        if effective:
            request.timeout = effective
        try:
            _status, body = self._transport(request)
        except HTTPError as exc:
            detail = (
                exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            )
            raise SystemExit(
                self.scrub_secret(
                    f"HTTP {exc.code} {request.method} {request.full_url}: {detail}"
                )
            ) from exc
        except URLError as exc:
            raise SystemExit(
                self.scrub_secret(
                    f"Network error {request.method} {request.full_url}: {exc}"
                )
            ) from exc
        return json.loads(body.decode("utf-8")) if body else {}


# ---------------------------------------------------------------------------
# Module-level default client factory
# ---------------------------------------------------------------------------

_default_client: HttpClient | None = None


def default_client() -> HttpClient:
    """Return (or create) the module-level singleton ``HttpClient``."""
    global _default_client
    if _default_client is None:
        _default_client = HttpClient()
    return _default_client


# ---------------------------------------------------------------------------
# fal.ai helpers
# ---------------------------------------------------------------------------

def fal_upload(
    client: HttpClient,
    file_path: Path,
    api_key: str,
) -> str:
    """Return a base64 data URI for *file_path* suitable for fal ``image_url`` fields.

    fal's image-input endpoints accept data URIs inline, so no upload roundtrip
    is needed. ``client`` and ``api_key`` are accepted for signature stability
    but unused.
    """
    data = file_path.read_bytes()
    suffix = file_path.suffix.lower().lstrip(".")
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }
    mime = mime_map.get(suffix, "image/png")
    return f"data:{mime};base64,{b64encode(data).decode('ascii')}"


def fal_submit_and_poll(
    client: HttpClient,
    model_id: str,
    payload: dict[str, Any],
    api_key: str,
    *,
    max_wait_sec: int = 300,
) -> dict[str, Any]:
    """Submit a job to ``fal-ai/<model_id>``, poll until completion.

    Returns the completed job result dictionary.
    """
    submit_url = f"{FAL_QUEUE_URL}/{model_id}"
    headers = {"authorization": f"Key {api_key}"}
    submission = client.post_json(submit_url, payload, headers=headers)

    status_url = submission.get("status_url")
    response_url = submission.get("response_url")
    if not status_url or not response_url:
        raise SystemExit(
            client.scrub_secret(
                f"fal submission missing status_url/response_url: "
                f"{json.dumps(submission)}"
            )
        )
    result = client.poll_until(
        status_url,
        response_url,
        headers=headers,
        max_wait_sec=max_wait_sec,
    )
    # Merge the request_id so callers can record it.
    if "request_id" not in result and "request_id" in submission:
        result["request_id"] = submission["request_id"]
    return result
