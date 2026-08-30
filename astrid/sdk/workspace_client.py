"""Discovery and compatibility wrapper around the generated workspace client.

This module owns only runtime endpoint/credential discovery. HTTP protocol
encoding, authentication, and response decoding are delegated to the
generated ``banodoco_workspace_client`` package from the runtime contract.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
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

    def _call_generated(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke one generated operation and normalize its typed value."""
        try:
            value = getattr(self._generated, name)(*args, **kwargs)
        except Exception as exc:  # generated ApiError has stable fields
            raise WorkspaceClientError(
                int(getattr(exc, "status", 0)),
                str(getattr(exc, "code", "transport_error")),
                str(getattr(exc, "message", exc)),
                getattr(exc, "details", {}),
            ) from exc
        return asdict(value) if is_dataclass(value) else value

    def create_project(self, name: str, *, idempotency_key: str) -> Any:
        return self._call_generated("create_project", name, idempotency_key=idempotency_key)

    def list_projects(self) -> Any:
        items, cursor = self._call_generated("list_projects")
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": cursor}

    def get_project(self, project_id: str) -> Any:
        return self._call_generated("get_project", project_id)

    def create_timeline(self, project_id: str, timeline_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("create_timeline", project_id, timeline_id, idempotency_key=idempotency_key)

    def list_timelines(self, project_id: str) -> Any:
        items, cursor = self._call_generated("list_timelines", project_id)
        return {"items": list(items), "next_cursor": cursor}

    def get_timeline(self, timeline_id: str) -> Any:
        return self._call_generated("get_timeline", timeline_id)

    def update_timeline(self, timeline_id: str, *, expected_version: int, shots=None, references=None) -> Any:
        return self._call_generated("update_timeline", timeline_id, expected_version=expected_version, shots=shots, references=references)

    def create_shot(self, timeline_id: str, shot: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("create_shot", timeline_id, shot, idempotency_key=idempotency_key)

    def get_shot(self, shot_id: str) -> Any:
        return self._call_generated("get_shot", shot_id)

    def create_reference(self, timeline_id: str, reference: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("create_reference", timeline_id, reference, idempotency_key=idempotency_key)

    def get_reference(self, reference_id: str) -> Any:
        return self._call_generated("get_reference", reference_id)

    def ingest_object(self, data: bytes, *, media_type: str, idempotency_key: str, filename: str | None = None) -> Any:
        return self._call_generated("ingest_object", data, media_type=media_type, idempotency_key=idempotency_key, filename=filename)

    def get_object(self, object_id: str) -> Any:
        return self._call_generated("get_object", object_id)

    def head_object(self, object_id: str) -> Any:
        return self._call_generated("head_object", object_id)

    def admit_task(self, **kwargs: Any) -> Any:
        return self._call_generated("admit_task", **kwargs)

    def get_task(self, task_id: str) -> Any:
        return self._call_generated("get_task", task_id)

    def cancel_task(self, task_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("cancel_task", task_id, idempotency_key=idempotency_key)

    def retry_task(self, task_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("retry_task", task_id, idempotency_key=idempotency_key)

    def get_run(self, run_id: str) -> Any:
        return self._call_generated("get_run", run_id)

    def list_events(self, *, aggregate_id: str | None = None) -> Any:
        items, cursor = self._call_generated("list_events", aggregate_id=aggregate_id)
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": cursor}

    def list_run_events(self, run_id: str) -> Any:
        return [asdict(item) if is_dataclass(item) else item for item in self._call_generated("list_run_events", run_id)]

    def list_generations(self, project_id: str) -> Any:
        items, cursor = self._call_generated("list_generations", project_id)
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": cursor}

    def get_generation(self, generation_id: str) -> Any:
        return self._call_generated("get_generation", generation_id)

    def list_variants(self, generation_id: str) -> Any:
        items, cursor = self._call_generated("list_variants", generation_id)
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": cursor}

    def create_generation(self, project_id: str, generation_id: str, **kwargs: Any) -> Any:
        return self._call_generated("create_generation", project_id, generation_id, **kwargs)

    def list_capabilities(self) -> Any:
        return [asdict(item) if is_dataclass(item) else item for item in self._call_generated("list_capabilities")]

    def register_capability(self, *args: Any, **kwargs: Any) -> Any:
        return self._call_generated("register_capability", *args, **kwargs)
