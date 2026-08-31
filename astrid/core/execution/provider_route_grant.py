"""Host-owned, single-use provider route grants.

The grant is an opaque handle.  Its claims stay in the host authority and the
handle is authenticated with a host-only key; it is never placed in the child
environment or in settlement evidence.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Iterable


class ProviderRouteGrantError(RuntimeError):
    """A provider route grant is missing, invalid, expired, or already used."""


@dataclass
class _Grant:
    task_id: str
    capability_id: str
    capability_digest: str
    routes: tuple[str, ...]
    broker_binding: str
    expires_at: float
    consumed: bool = False


def _routes(routes: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(route).strip() for route in routes if str(route).strip()}))


class ProviderRouteGrantAuthority:
    """Issue and consume grants for one host process."""

    version = "provider-route-grant-v1"

    def __init__(self, *, secret: bytes | None = None, clock=time.time) -> None:
        self._secret = bytes(secret or secrets.token_bytes(32))
        self._clock = clock
        self._grants: dict[str, _Grant] = {}
        self._lock = threading.Lock()

    @staticmethod
    def binding(*, capability_id: str, capability_digest: str, broker: object) -> str:
        descriptor = {
            "capability_id": str(capability_id),
            "capability_digest": str(capability_digest),
            "broker": str(broker),
            "protocol": "tcp-http-broker-v1",
        }
        raw = repr(sorted(descriptor.items())).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def issue(
        self,
        *,
        task_id: str,
        capability_id: str,
        capability_digest: str,
        routes: Iterable[str],
        broker_binding: str,
        ttl_seconds: int = 60,
    ) -> str:
        ttl = int(ttl_seconds)
        if ttl <= 0 or ttl > 300:
            raise ProviderRouteGrantError("provider route grant TTL must be between 1 and 300 seconds")
        token_id = secrets.token_urlsafe(32)
        claims = _Grant(
            task_id=str(task_id),
            capability_id=str(capability_id),
            capability_digest=str(capability_digest),
            routes=_routes(routes),
            broker_binding=str(broker_binding),
            expires_at=float(self._clock()) + ttl,
        )
        with self._lock:
            self._grants[token_id] = claims
        mac = hmac.new(self._secret, f"{self.version}\0{token_id}".encode(), hashlib.sha256).hexdigest()
        return f"{self.version}.{token_id}.{mac}"

    def consume(
        self,
        token: str | None,
        *,
        task_id: str,
        capability_id: str,
        capability_digest: str,
        routes: Iterable[str],
        broker_binding: str,
    ) -> _Grant:
        if not isinstance(token, str) or not token:
            raise ProviderRouteGrantError("provider route grant is required before provider egress")
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != self.version:
            raise ProviderRouteGrantError("provider route grant is malformed")
        token_id, signature = parts[1], parts[2]
        expected = hmac.new(self._secret, f"{self.version}\0{token_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ProviderRouteGrantError("provider route grant authentication failed")
        # The replay check and transition are one critical section.  This is
        # intentionally held through expiry/binding validation: no concurrent
        # host thread may observe an unconsumed grant after this point.
        with self._lock:
            grant = self._grants.get(token_id)
            if grant is None:
                raise ProviderRouteGrantError("provider route grant is unknown")
            if grant.consumed:
                raise ProviderRouteGrantError("provider route grant has already been consumed")
            if float(self._clock()) >= grant.expires_at:
                raise ProviderRouteGrantError("provider route grant has expired")
            if (
                grant.task_id != str(task_id)
                or grant.capability_id != str(capability_id)
                or grant.capability_digest != str(capability_digest)
                or grant.routes != _routes(routes)
                or grant.broker_binding != str(broker_binding)
            ):
                raise ProviderRouteGrantError("provider route grant binding does not match the admitted task")
            grant.consumed = True
            return grant


__all__ = ["ProviderRouteGrantAuthority", "ProviderRouteGrantError"]
