"""Tiny observable loopback broker used by provider boundary tests.

This is deliberately a test-sized protocol rather than a general-purpose
proxy.  A child first performs an admission-bound ``ASTRID-BROKER/1``
handshake, then sends ordinary absolute-form HTTP requests through the
loopback listener.  The broker records both events so a successful route is
evidence of a live owner, not a manifest boolean.
"""

from __future__ import annotations

import json
import socketserver
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any


@dataclass
class BrokerEvent:
    kind: str
    detail: str = ""


class _BrokerHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        broker: "ObservableNetworkBroker" = self.server.broker  # type: ignore[attr-defined]
        first = self.rfile.readline(8192)
        if first.startswith(b"ASTRID-BROKER/1 HELLO "):
            admission = first.decode("utf-8", "replace").strip()[22:]
            broker.events.append(BrokerEvent("handshake", admission))
            self.wfile.write(b"ASTRID-BROKER/1 OK\n")
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
        broker.events.append(BrokerEvent("route", target))
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
    """Live loopback broker with admission handshake and event evidence."""

    response_body: bytes | None = b"broker-response"
    events: list[BrokerEvent] = field(default_factory=list)
    _server: _BrokerServer | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

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
