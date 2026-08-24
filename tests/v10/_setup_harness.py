"""Shared B8 setup-journal test harness: deterministic bytes, a
Range-capable local HTTP origin, and signed-manifest factories.

The origin server is real ``http.server`` so Range resume is exercised
against actual 206 responses — never simulated.
"""

from __future__ import annotations

import hashlib
import http.server
import threading
from pathlib import Path

from astrid.core.model_setup.journal import manifests_dir
from astrid.core.model_setup.manifest import (
    make_manifest,
    save_manifest,
)

#: Deterministic multi-chunk payload (2 MiB — two CHUNK_SIZE appends).
PAYLOAD = bytes(range(256)) * 8192


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    """Serves one immutable payload with HTTP Range/206 support."""

    payload: bytes = PAYLOAD
    log_requests: list[tuple[str, int | None]] = []

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        payload = type(self).payload
        range_header = self.headers.get("Range")
        offset: int | None = None
        if range_header is not None:
            marker = "bytes="
            assert range_header.startswith(marker), range_header
            offset = int(range_header[len(marker) :].split("-", 1)[0])
            type(self).log_requests.append(("range", offset))
        else:
            type(self).log_requests.append(("full", None))
        if offset is None:
            body = payload
            status = 200
        elif offset >= len(payload):
            # Resume from exactly EOF: 206 with zero remaining bytes.
            body = b""
            status = 206
        else:
            body = payload[offset:]
            status = 206
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        if status == 206:
            self.send_header(
                "Content-Range", f"bytes {offset}-{len(payload) - 1}/{len(payload)}"
            )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


class RangeOrigin:
    """A threaded local origin serving deterministic bytes over Range."""

    def __init__(self, payload: bytes = PAYLOAD) -> None:
        handler = type(
            "_Handler", (_RangeHandler,), {"payload": payload, "log_requests": []}
        )
        self._server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), handler
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.requests = handler.log_requests

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/bundle.bin"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "RangeOrigin":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


def manifest_for(
    content: bytes,
    artifact_id: str = "test_bundle",
    **overrides: object,
):
    """A signed distribution manifest over exact *content* bytes."""
    return make_manifest(
        artifact_id=artifact_id,
        version=overrides.pop("version", "1.0.0"),
        content=content,
        license_identity=overrides.pop("license_identity", "Apache-2.0"),
        license_text=overrides.pop("license_text", b"Copyright 2026 Astrid"),
        **overrides,
    )


def store_manifest(root: Path, manifest) -> Path:
    """Persist a signed manifest into the project's setup store."""
    directory = manifests_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest.artifact_id.replace(':', '_')}.json"
    save_manifest(manifest, path)
    return path


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "PAYLOAD",
    "RangeOrigin",
    "manifest_for",
    "sha256_hex",
    "store_manifest",
]

