"""Small, observable network policy hook for generic pack children.

This is intentionally an application-level hook, not a sandbox.  It is useful
for the Python provider fixtures and for recording what the child attempted;
an operating-system firewall remains the enforcement point for arbitrary
native binaries.  The hook rejects undeclared DNS/TCP/UDP destinations and
records only non-sensitive endpoint metadata.
"""

from __future__ import annotations

import atexit
import hashlib
import hmac
import ipaddress
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


_LOCK = threading.Lock()
_INSTALLED = False
_ORIGINALS: dict[tuple[Any, str], Any] = {}
_DNS_NAMES: dict[str, set[str]] = {}
_EVENTS: list[dict[str, Any]] = []
_POLICY: dict[str, Any] = {}
_EVIDENCE: Path | None = None
_EVIDENCE_KEY = ""
_ADMISSION: dict[str, Any] = {}


class NetworkPolicyError(RuntimeError):
    """A child attempted a network operation outside its admitted policy."""


def _policy_bool(policy: Mapping[str, Any], name: str, default: bool = False) -> bool:
    value = policy.get(name)
    if isinstance(value, Mapping):
        value = value.get("allow", value.get("enabled", default))
    return bool(default if value is None else value)


def _destinations(policy: Mapping[str, Any]) -> tuple[str, ...]:
    values = policy.get("allowed_destinations", policy.get("destinations", ()))
    if isinstance(values, str):
        values = (values,)
    return tuple(str(value).strip().lower() for value in (values or ()) if str(value).strip())


def _protocol_allowed(protocol: str) -> bool:
    protocols = _POLICY.get("allowed_protocols", _POLICY.get("protocols"))
    if protocols is None:
        return _policy_bool(_POLICY, protocol, _policy_bool(_POLICY, "network", False))
    if isinstance(protocols, str):
        protocols = (protocols,)
    return protocol.lower() in {str(item).lower() for item in protocols}


def _endpoint_parts(address: Any) -> tuple[str, int | None]:
    if isinstance(address, tuple) and address:
        host = str(address[0])
        port = int(address[1]) if len(address) > 1 and str(address[1]).isdigit() else None
        return host.lower(), port
    raw = str(address)
    if "://" in raw:
        parsed = urlsplit(raw)
        return (parsed.hostname or "").lower(), parsed.port
    if raw.startswith("[") and "]" in raw:
        host, _, port = raw[1:].partition("]")
        return host.lower(), int(port[1:]) if port.startswith(":") and port[1:].isdigit() else None
    host, separator, port = raw.rpartition(":")
    return (host if separator and port.isdigit() else raw).lower(), int(port) if separator and port.isdigit() else None


def _allowed_destination(host: str, port: int | None) -> bool:
    host = host.strip("[]").lower().rstrip(".")
    allowed = _destinations(_POLICY)
    if not allowed:
        return False
    aliases = {host}
    aliases.update(_DNS_NAMES.get(host, set()))
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    for candidate in allowed:
        candidate_host, candidate_port = _endpoint_parts(candidate)
        if candidate_host in {"*", host} or candidate_host in aliases:
            if candidate_port is None or port is None or candidate_port == port:
                return True
        try:
            if ip is not None and ipaddress.ip_address(candidate_host) == ip:
                if candidate_port is None or port is None or candidate_port == port:
                    return True
        except ValueError:
            continue
    return False


def _record(kind: str, *, host: str = "", port: int | None = None, allowed: bool, detail: str = "") -> None:
    event = {"kind": kind, "host": host, "port": port, "allowed": bool(allowed), "pid": os.getpid(), "time_ns": time.time_ns()}
    if detail:
        event["detail"] = detail
    with _LOCK:
        _EVENTS.append(event)


def _check(kind: str, address: Any) -> tuple[str, int | None]:
    host, port = _endpoint_parts(address)
    allowed = _protocol_allowed(kind) and _allowed_destination(host, port)
    _record(kind, host=host, port=port, allowed=allowed)
    if not allowed:
        raise NetworkPolicyError(f"network policy denied {kind} destination {host}:{port or ''}")
    return host, port


def _write_evidence() -> None:
    if _EVIDENCE is None:
        return
    protocols = _POLICY.get("allowed_protocols", _POLICY.get("protocols", ()))
    if isinstance(protocols, str):
        protocols = (protocols,)
    payload = {"schema_version": 1, "pid": os.getpid(), "events": list(_EVENTS), "limitations": [
        "application_hook_only; native children outside Python are not OS-firewall isolated",
    ], "admission": dict(_ADMISSION), "policy": {
        "allowed_destinations": list(_destinations(_POLICY)),
        "allowed_protocols": list(protocols or ()),
        "redirects": _policy_bool(_POLICY, "redirects", _policy_bool(_POLICY, "allow_redirects", False)),
        "proxy": bool(_POLICY.get("proxy")),
    }}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if not _EVIDENCE_KEY:
        # A hook without its host-issued key cannot make settlement evidence
        # trustworthy.  Leave no unsigned artifact for the host to accept.
        return
    payload["signature_algorithm"] = "hmac-sha256"
    payload["signature"] = hmac.new(_EVIDENCE_KEY.encode(), canonical, hashlib.sha256).hexdigest()
    _EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    _EVIDENCE.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _patch_socket() -> None:
    def getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any):
        value = _ORIGINALS[(socket, "getaddrinfo")](host, port, *args, **kwargs)
        name = str(host).lower().rstrip(".")
        ips = {str(item[4][0]).lower() for item in value if item and len(item) > 4 and item[4]}
        _DNS_NAMES.setdefault(name, set()).update(ips)
        for ip in ips:
            _DNS_NAMES.setdefault(ip, set()).add(name)
        allowed = _protocol_allowed("dns") and _allowed_destination(name, None)
        _record("dns", host=name, port=int(port) if str(port).isdigit() else None, allowed=allowed)
        if not allowed:
            raise NetworkPolicyError(f"network policy denied dns destination {name}")
        return value

    def connect(self: socket.socket, address: Any):
        _check("tcp" if self.type & socket.SOCK_STREAM else "udp", address)
        return _ORIGINALS[(socket.socket, "connect")](self, address)

    def connect_ex(self: socket.socket, address: Any):
        _check("tcp" if self.type & socket.SOCK_STREAM else "udp", address)
        return _ORIGINALS[(socket.socket, "connect_ex")](self, address)

    def sendto(self: socket.socket, data: Any, address: Any, *args: Any):
        _check("udp", address)
        return _ORIGINALS[(socket.socket, "sendto")](self, data, address, *args)

    _ORIGINALS[(socket, "getaddrinfo")] = socket.getaddrinfo
    _ORIGINALS[(socket.socket, "connect")] = socket.socket.connect
    _ORIGINALS[(socket.socket, "connect_ex")] = socket.socket.connect_ex
    _ORIGINALS[(socket.socket, "sendto")] = socket.socket.sendto
    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = sendto  # type: ignore[method-assign]


def _patch_redirects() -> None:
    try:
        from urllib.request import HTTPRedirectHandler
    except ImportError:
        return
    original = HTTPRedirectHandler.redirect_request
    _ORIGINALS[(HTTPRedirectHandler, "redirect_request")] = original

    def redirect_request(self: Any, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str, *args: Any, **kwargs: Any):
        host, port = _endpoint_parts(newurl)
        allowed = _policy_bool(_POLICY, "redirects", _policy_bool(_POLICY, "allow_redirects", False)) and _allowed_destination(host, port or 80)
        _record("redirect", host=host, port=port, allowed=allowed)
        if not allowed:
            raise NetworkPolicyError(f"network policy denied redirect destination {host}")
        return original(self, req, fp, code, msg, headers, newurl, *args, **kwargs)

    HTTPRedirectHandler.redirect_request = redirect_request  # type: ignore[method-assign]


def install(policy: Mapping[str, Any], evidence_path: str | Path, *, admission: Mapping[str, Any] | None = None, evidence_key: str = "") -> None:
    """Install hooks in a child process and arrange structured evidence output."""
    global _INSTALLED, _POLICY, _EVIDENCE, _EVIDENCE_KEY, _ADMISSION
    if _INSTALLED:
        return
    _POLICY = dict(policy)
    _EVIDENCE = Path(evidence_path)
    _EVIDENCE_KEY = str(evidence_key)
    _ADMISSION = dict(admission or {})
    _INSTALLED = True
    _patch_socket()
    _patch_redirects()
    atexit.register(_write_evidence)


def install_from_environment() -> None:
    raw = os.environ.get("ASTRID_NETWORK_POLICY")
    evidence = os.environ.get("ASTRID_NETWORK_EVIDENCE")
    if not raw or not evidence:
        return
    try:
        policy = json.loads(raw)
    except ValueError:
        return
    admission_raw = os.environ.get("ASTRID_NETWORK_ADMISSION", "{}")
    try:
        admission = json.loads(admission_raw)
    except ValueError:
        admission = {}
    key = os.environ.get("ASTRID_NETWORK_EVIDENCE_KEY", "")
    if isinstance(policy, Mapping) and isinstance(admission, Mapping):
        install(policy, evidence, admission=admission, evidence_key=key)


__all__ = ["NetworkPolicyError", "install", "install_from_environment"]
