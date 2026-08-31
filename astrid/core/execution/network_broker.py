"""Tiny observable loopback broker used by provider boundary tests.

This is deliberately a test-sized protocol rather than a general-purpose
proxy.  A child first performs an admission-bound ``ASTRID-BROKER/1``
handshake, then sends ordinary absolute-form HTTP requests through the
loopback listener.  The broker records both events so a successful route is
evidence of a live owner, not a manifest boolean.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import socketserver
import threading
from pathlib import Path
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Mapping
from urllib.parse import urlsplit


@dataclass
class BrokerEvent:
    kind: str
    detail: str = ""


class _BrokerHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        broker: "ObservableNetworkBroker" = self.server.broker  # type: ignore[attr-defined]
        first = self.rfile.readline(8192)
        if first.startswith(b"ASTRID-BROKER/1 HELLO "):
            parts = first.decode("utf-8", "replace").strip().split()
            digest = parts[2] if len(parts) > 2 else ""
            nonce = parts[3] if len(parts) > 3 else ""
            allowed = broker._admission_allowed(digest, nonce)
            broker._record("handshake", f"{digest}:{nonce}", allowed=allowed)
            self.wfile.write(("ASTRID-BROKER/1 OK\n" if allowed else "ASTRID-BROKER/1 REJECT\n").encode("ascii"))
            self.wfile.flush()
            return
        if not first:
            return
        # urllib's proxy request is absolute-form: ``GET http://host/path``.
        line = first.decode("iso-8859-1", "replace").strip()
        headers: dict[str, str] = {}
        while True:
            raw = self.rfile.readline(8192)
            if not raw or raw in {b"\r\n", b"\n"}:
                break
            name, separator, value = raw.decode("iso-8859-1", "replace").partition(":")
            if separator:
                headers[name.lower()] = value.strip()
        if not line.startswith(("GET ", "POST ", "HEAD ")):
            broker.events.append(BrokerEvent("rejected", line[:120]))
            self._response(HTTPStatus.BAD_REQUEST, b"broker requires absolute-form HTTP")
            return
        target = line.split(" ", 2)[1]
        allowed = broker._route_allowed(target)
        broker._record("route", target, allowed=allowed)
        if not allowed:
            self._response(HTTPStatus.FORBIDDEN, b"broker route was not admitted")
            return
        if broker.response_body is None:
            self._response(HTTPStatus.BAD_GATEWAY, b"no broker route configured")
            return
        self._response(HTTPStatus.OK, broker.response_body)

    def _response(self, status: HTTPStatus, body: bytes) -> None:
        self.wfile.write(
            f"HTTP/1.1 {status.value} {status.phrase}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n".encode("ascii") + body
        )
        self.wfile.flush()


class _BrokerServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], broker: "ObservableNetworkBroker") -> None:
        self.broker = broker
        super().__init__(address, _BrokerHandler)


@dataclass
class ObservableNetworkBroker:
    """Live loopback broker with admission-fenced route evidence.

    A broker created without an admission remains permissive for compatibility
    with the small legacy fixture. Production/provider journeys must call
    :meth:`register_admission` before starting traffic; then both the handshake
    and every absolute-form route are checked against the exact admission.
    """

    response_body: bytes | None = b"broker-response"
    events: list[BrokerEvent] = field(default_factory=list)
    expected_admission_digest: str = ""
    expected_nonce: str = ""
    allowed_routes: tuple[str, ...] = ()
    evidence_path: Path | None = None
    evidence_key: str = ""
    _strict: bool = field(default=False, init=False, repr=False)
    _admission: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _server: _BrokerServer | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    def register_admission(
        self,
        admission: Mapping[str, Any],
        *,
        allowed_routes: list[str] | tuple[str, ...] = (),
        evidence_path: str | Path | None = None,
        evidence_key: str = "",
    ) -> "ObservableNetworkBroker":
        """Pre-register the host's immutable admission and route allowlist."""
        self._admission = dict(admission)
        self.expected_admission_digest = hashlib.sha256(
            json.dumps(self._admission, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        self.expected_nonce = str(self._admission.get("network_nonce") or self._admission.get("nonce") or "")
        self.allowed_routes = tuple(str(item) for item in allowed_routes)
        self.evidence_path = Path(evidence_path) if evidence_path is not None else None
        self.evidence_key = str(evidence_key)
        self._strict = True
        return self

    def _record(self, kind: str, detail: str, *, allowed: bool = True) -> None:
        self.events.append(BrokerEvent(kind, f"{detail}|allowed={str(allowed).lower()}"))
        self._write_evidence()

    def _admission_allowed(self, digest: str, nonce: str) -> bool:
        if not self._strict:
            return bool(digest)
        return bool(
            self.expected_admission_digest
            and hmac.compare_digest(digest, self.expected_admission_digest)
            and self.expected_nonce
            and hmac.compare_digest(nonce, self.expected_nonce)
        )

    def _route_allowed(self, target: str) -> bool:
        if not self._strict:
            return True
        parsed = urlsplit(target)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        normalized = f"{parsed.scheme}://{parsed.hostname.lower()}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path or '/'}"
        for route in self.allowed_routes:
            candidate = str(route).strip()
            if candidate == target or candidate == normalized:
                return True
            # A declared host:port destination is allowed for any path, but
            # never a different host or port.
            try:
                declared = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
                declared_port = declared.port or (443 if declared.scheme == "https" else 80)
            except ValueError:
                continue
            if declared.hostname and declared.hostname.lower() == parsed.hostname.lower() and declared_port == (parsed.port or (443 if parsed.scheme == "https" else 80)):
                return True
        return False

    def _write_evidence(self) -> None:
        if not self.evidence_path or not self.evidence_key:
            return
        unsigned = {
            "schema_version": 1,
            "admission": dict(self._admission),
            "events": [{"kind": event.kind, "detail": event.detail} for event in self.events],
        }
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        payload = {
            **unsigned,
            "signature_algorithm": "hmac-sha256",
            "signature": hmac.new(self.evidence_key.encode(), canonical, hashlib.sha256).hexdigest(),
        }
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def start(self) -> "ObservableNetworkBroker":
        if self._server is not None:
            return self
        self._server = _BrokerServer(("127.0.0.1", 0), self)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("broker is not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def evidence(self) -> list[dict[str, Any]]:
        return [{"kind": event.kind, "detail": event.detail} for event in self.events]


__all__ = ["BrokerEvent", "ObservableNetworkBroker"]
