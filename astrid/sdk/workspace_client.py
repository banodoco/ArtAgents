"""Small generated-client transport used by the Astrid product adapter.

The module intentionally contains only HTTP/discovery concerns: no SQLite,
CAS, repository, or runtime imports.  The neutral runtime publishes direct
JSON resources matching the generated workspace client contract.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request
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
    def __init__(self, endpoint: str, token: str):
        self.endpoint, self.token = endpoint.rstrip("/"), token

    def request(self, method: str, path: str, *, body: Any = None, headers: Mapping[str, str] | None = None, expected: tuple[int, ...] = (200,)) -> Any:
        request_headers = {"Accept": "application/json", "Authorization": f"Bearer {self.token}", **dict(headers or {})}
        raw = body if isinstance(body, bytes) else (json.dumps(body, separators=(",", ":")).encode() if body is not None else None)
        if body is not None and not isinstance(body, bytes): request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(self.endpoint + path, data=raw, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, response_body = response.status, response.read()
                response_headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            try: value = json.loads(response_body.decode())
            except (UnicodeDecodeError, json.JSONDecodeError): value = {}
            raise WorkspaceClientError(exc.code, str(value.get("code", "http_error")), str(value.get("message", f"HTTP {exc.code}")), value.get("details", {})) from exc
        except urllib.error.URLError as exc:
            raise WorkspaceClientError(0, "unavailable", "runtime is unavailable; run `banodoco-local up --profile astrid`") from exc
        if status not in expected:
            raise WorkspaceClientError(status, "http_error", f"HTTP {status}")
        if method == "HEAD" or not response_body: return {"status": status, "headers": response_headers, "body": response_body}
        if response_headers.get("Content-Type", "").startswith("application/json"):
            return json.loads(response_body.decode())
        return {"status": status, "headers": response_headers, "body": response_body}
