"""Discovery and compatibility wrapper around the generated workspace client.

This module owns only runtime endpoint/credential discovery. HTTP protocol
encoding, authentication, and response decoding are delegated to the
generated ``banodoco_workspace_client`` package from the runtime contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


class WorkspaceClientError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = dict(details or {})


def _read_credential(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise WorkspaceClientError(0, "unavailable", "runtime credential is unavailable") from exc
    if not raw:
        raise WorkspaceClientError(0, "unavailable", "runtime credential is unavailable")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    token = value.get("token") if isinstance(value, dict) else None
    if not isinstance(token, str) or not token:
        raise WorkspaceClientError(0, "unavailable", "runtime credential is unavailable")
    return token


def resolve_runtime_connection() -> tuple[str, str]:
    endpoint = os.environ.get("BANODOCO_RUNTIME_ENDPOINT", "").strip()
    discovery_path = os.environ.get("BANODOCO_RUNTIME_DISCOVERY", "").strip()
    if not discovery_path:
        home = Path(os.environ.get("HOME", "~")).expanduser()
        discovery_path = str(home / "Library" / "Application Support" / "Banodoco" / "runtime" / "discovery.json")
    if not endpoint:
        try:
            value = json.loads(Path(discovery_path).read_text(encoding="utf-8"))
            endpoint = str(value.get("endpoint", ""))
        except (OSError, json.JSONDecodeError):
            endpoint = ""
    credential_path = os.environ.get("BANODOCO_RUNTIME_CREDENTIAL", "").strip()
    if not credential_path:
        home = Path(os.environ.get("HOME", "~")).expanduser()
        credential_path = str(home / "Library" / "Application Support" / "Banodoco" / "credentials" / "astrid.json")
    if not endpoint:
        raise WorkspaceClientError(0, "unavailable", "runtime is unavailable; run `banodoco-local up --profile astrid`")
    return endpoint.rstrip("/"), _read_credential(Path(credential_path))


class WorkspaceClient:
    """Generated-client transport with the adapter's historical request seam."""

    def __init__(self, endpoint: str, token: str):
        try:
            from banodoco_workspace_client import WorkspaceClient as GeneratedWorkspaceClient
        except ImportError as exc:
            raise WorkspaceClientError(
                0,
                "unavailable",
                "generated workspace client is unavailable; run `banodoco-local up --profile astrid`",
            ) from exc
        self.endpoint, self.token = endpoint.rstrip("/"), token
        self._generated = GeneratedWorkspaceClient(self.endpoint, token)

    def request(self, method: str, path: str, *, body: Any = None, headers: Mapping[str, str] | None = None, expected: tuple[int, ...] = (200,)) -> Any:
        raw = body if isinstance(body, bytes) else (json.dumps(body, separators=(",", ":")).encode() if body is not None else None)
        request_headers = dict(headers or {})
        if body is not None and not isinstance(body, bytes):
            request_headers.setdefault("Content-Type", "application/json")
        try:
            status, response_headers, response_body = self._generated._request(
                method, path, body=raw, headers=request_headers, expected=expected
            )
        except Exception as exc:
            code = str(getattr(exc, "code", "transport_error"))
            message = str(getattr(exc, "message", exc))
            details = getattr(exc, "details", {})
            raise WorkspaceClientError(int(getattr(exc, "status", 0)), code, message, details) from exc
        if method == "HEAD" or not response_body:
            return {"status": status, "headers": dict(response_headers), "body": response_body}
        if str(response_headers.get("Content-Type", "")).startswith("application/json"):
            return json.loads(response_body.decode())
        return {"status": status, "headers": dict(response_headers), "body": response_body}
