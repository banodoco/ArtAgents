"""T9: the local-trust boundary (build spec doc 27 §4.7).

Fixtures cover the hostile-web-page posture: DNS-rebinding / Host spoofing,
no-cors cross-origin mutations without the per-boot token, forged tokens,
and proof that the frozen GET routes and CORS preflight stay unaffected.
"""

from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)

TRUST_HEADER = "X-Astrid-Request-Token"


@contextmanager
def trusted_server(
    projects_root: Path,
    *,
    request_token: str | None = None,
) -> Generator[tuple[str, str], None, None]:
    """A running server whose per-boot token is returned explicitly."""
    server = create_local_bridge_server(
        projects_root=projects_root,
        request_token=request_token,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"127.0.0.1:{port}", server.request_token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _raw(
    authority: str,
    method: str,
    path: str,
    *,
    host_header: str | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, Any], bytes]:
    """One raw request with full header control (no urllib auto-Host)."""
    host, port = authority.split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        send_headers = dict(headers or {})
        if host_header is not None:
            send_headers["Host"] = host_header
        conn.request(method, path, body=body, headers=send_headers)
        response = conn.getresponse()
        payload = response.read()
        return response.status, dict(response.getheaders()), payload
    finally:
        conn.close()


def _save_path() -> str:
    return "/projects/p/timelines/t/save"


def _json_body() -> bytes:
    return json.dumps({"config": {}, "registry": {}, "expected_version": 1})


def test_minted_token_delivered_out_of_band_with_private_modes(
    tmp_bridge_root: Path,
) -> None:
    with trusted_server(tmp_bridge_root) as (_authority, token):
        token_file = tmp_bridge_root / ".astrid" / "request-token"
        assert token_file.is_file()
        assert token_file.read_text(encoding="utf-8") == token
        # Secret-bearing file 0600, managed dir 0700 (doc 27 §4.7.4).
        assert token_file.stat().st_mode & 0o777 == 0o600
        assert (tmp_bridge_root / ".astrid").stat().st_mode & 0o777 == 0o700


def test_mutation_without_token_rejected(tmp_bridge_root: Path) -> None:
    with trusted_server(tmp_bridge_root) as (authority, _token):
        status, _headers, payload = _raw(
            authority,
            "POST",
            _save_path(),
            body=_json_body(),
            headers={"Content-Type": "application/json"},
        )
    assert status == 403
    assert json.loads(payload)["error"] == "forbidden"


def test_mutation_with_wrong_token_rejected(tmp_bridge_root: Path) -> None:
    with trusted_server(tmp_bridge_root) as (authority, _token):
        status, _headers, payload = _raw(
            authority,
            "POST",
            _save_path(),
            body=_json_body(),
            headers={
                "Content-Type": "application/json",
                TRUST_HEADER: "forged-token-value",
            },
        )
    assert status == 403
    assert json.loads(payload)["error"] == "forbidden"


def test_mutation_with_boot_token_passes_trust_gate(
    tmp_bridge_root: Path,
) -> None:
    """The right token passes the gate; routing proceeds (fail-closed 500)."""
    with trusted_server(tmp_bridge_root) as (authority, token):
        status, _headers, payload = _raw(
            authority,
            "POST",
            _save_path(),
            body=b"not-json",
            headers={
                "Content-Type": "text/plain",
                TRUST_HEADER: token,
            },
        )
    # The gate passed; the route's own typed handling answers.
    assert status in (400, 500)
    error = json.loads(payload)["error"]
    assert error in ("invalid_body", "invalid_config", "internal")


def test_host_spoof_rejected_on_reads_and_mutations(
    tmp_bridge_root: Path,
) -> None:
    with trusted_server(tmp_bridge_root) as (authority, token):
        rebound = f"attacker.example:{authority.split(':')[1]}"
        for method, path, hdrs in (
            ("GET", "/health", {}),
            (
                "POST",
                _save_path(),
                {"Content-Type": "application/json", TRUST_HEADER: token},
            ),
        ):
            status, _headers, payload = _raw(
                authority,
                method,
                path,
                host_header=rebound,
                headers=hdrs,
                body=_json_body() if method == "POST" else None,
            )
            assert status == 403, (method, status)
            assert json.loads(payload)["error"] == "forbidden"


def test_missing_host_header_rejected(tmp_bridge_root: Path) -> None:
    with trusted_server(tmp_bridge_root) as (authority, _token):
        host, port = authority.split(":")
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        try:
            # HTTP/1.0-style request: no Host header at all.
            conn.putrequest("GET", "/health", skip_host=True)
            conn.endheaders()
            response = conn.getresponse()
            payload = response.read()
            status = response.status
        finally:
            conn.close()
    assert status == 403
    assert json.loads(payload)["error"] == "forbidden"


def test_frozen_get_routes_unaffected_by_gate(tmp_bridge_root: Path) -> None:
    """Reads stay keyless/tokenless; only exact Host is enforced."""
    from astrid.packs import compose_standard_bridge

    composition = compose_standard_bridge(tmp_bridge_root)
    server = create_local_bridge_server(
        projects_root=tmp_bridge_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    authority = f"127.0.0.1:{port}"
    try:
        status, _headers, payload = _raw(
            authority, "GET", "/projects", host_header=authority
        )
        assert status == 200
        assert json.loads(payload) == {"projects": []}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        composition.writer.close()


def test_options_preflight_exempt_from_gate(tmp_bridge_root: Path) -> None:
    with trusted_server(tmp_bridge_root) as (authority, _token):
        status, headers, _payload = _raw(
            authority,
            "OPTIONS",
            "/anything/at/all",
            headers={"Origin": "http://localhost:5173"},
        )
    assert status == 204
    assert headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    allow_headers = headers.get("Access-Control-Allow-Headers", "")
    assert TRUST_HEADER in allow_headers
    assert "Idempotency-Key" in allow_headers


def test_no_cors_browser_post_is_blocked(tmp_bridge_root: Path) -> None:
    """A hostile page's no-cors POST carries no token header -> blocked."""
    with trusted_server(tmp_bridge_root) as (authority, _token):
        # Simulated no-cors fetch: simple headers only, no preflight possible.
        status, _headers, payload = _raw(
            authority,
            "POST",
            "/queue/claim",
            body=json.dumps({"executor_id": "x", "capabilities": []}).encode(),
            headers={"Content-Type": "text/plain"},
        )
    assert status == 403
