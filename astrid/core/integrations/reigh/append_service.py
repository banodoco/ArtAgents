"""Hosted Astrid-backed Reigh timeline append HTTP service."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4

from astrid.core.integrations.reigh import env as reigh_env
from astrid.core.integrations.reigh.event_construction import config_to_events
from astrid.core.integrations.reigh.supabase_client import (
    SupabaseHTTPError,
    get_json,
    rpc,
)
from astrid.core.integrations.reigh.worker_jwt import (
    JwtVerificationError,
    verify_user_jwt,
)
from astrid.core.timeline.eventlog.supabase import LiveSupabaseAppendTransport
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError, EventLogTransportError
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.events.schema.payloads._base import TimelineImportSource


DEFAULT_INTERNAL_TOKEN_ENV = "REIGH_APPEND_SERVICE_INTERNAL_TOKEN"


class AppendServiceError(RuntimeError):
    """HTTP-shaped service error."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AuthorizedCaller:
    """Authenticated caller identity for append service requests."""

    scheme: str
    user_id: str | None


@dataclass(frozen=True)
class AppendServiceConfig:
    supabase_url: str
    service_role_key: str
    internal_token: str | None = None
    jwks_url: str | None = None
    timeout: float = 60.0

    @classmethod
    def from_env(cls, *, timeout: float = 60.0) -> "AppendServiceConfig":
        internal_token = os.environ.get(DEFAULT_INTERNAL_TOKEN_ENV, "").strip() or None
        return cls(
            supabase_url=reigh_env.resolve_supabase_url(),
            service_role_key=reigh_env.resolve_service_role_key(),
            internal_token=internal_token,
            jwks_url=_optional(lambda: reigh_env.resolve_jwks_url()),
            timeout=timeout,
        )


class AppendService:
    """Authorized facade over Python-owned event construction and Supabase RPCs."""

    def __init__(self, config: AppendServiceConfig) -> None:
        self.config = config

    def append_config_replaced(
        self,
        *,
        timeline_id: str,
        body: dict[str, Any],
        headers: Any,
    ) -> dict[str, Any]:
        caller = self._authenticate(headers)
        owner = self._authorize_existing_timeline(timeline_id, caller)
        config = _require_object(body.get("config"), "config")
        asset_registry = _optional_object(body.get("asset_registry"), "asset_registry")
        actor = self._actor_from_body(body, caller=caller, owner_user_id=owner["user_id"])
        source = _coerce_source(body.get("source"))
        expected_version = _optional_int(body.get("expected_version"), "expected_version")
        txn_id = _optional_str(body.get("txn_id"), "txn_id")

        transport = LiveSupabaseAppendTransport(
            supabase_url=self.config.supabase_url,
            auth_token=self.config.service_role_key,
            timeout=self.config.timeout,
        )
        try:
            result = transport.append_config_replaced(
                timeline_id=timeline_id,
                config=config,
                asset_registry=asset_registry,
                actor=actor,
                source=source,
                expected_version=expected_version,
                txn_id=txn_id,
            )
        except EventLogStaleVersionError as exc:
            raise AppendServiceError(
                409,
                "version_conflict",
                f"timeline config_version mismatch: expected {exc.conflict.expected_version}, "
                f"found {exc.conflict.current_version}",
            ) from exc
        except EventLogTransportError as exc:
            raise AppendServiceError(502, "append_failed", str(exc)) from exc

        return {
            "timeline_id": timeline_id,
            "config_version": result.config_version,
            "inserted_event_ids": list(result.inserted_event_ids),
            "events": result.batch.to_append_json(),
        }

    def create_with_config(self, *, body: dict[str, Any], headers: Any) -> dict[str, Any]:
        caller = self._authenticate(headers)
        project_id = _require_str(body.get("project_id"), "project_id")
        config = _require_object(body.get("config"), "config")
        asset_registry = _optional_object(body.get("asset_registry"), "asset_registry")
        timeline_id = _optional_str(body.get("timeline_id"), "timeline_id")
        name = _optional_str(body.get("name"), "name") or "Untitled timeline"
        source = _coerce_source(body.get("source"))
        txn_id = _optional_str(body.get("txn_id"), "txn_id")
        owner_user_id = self._authorize_new_timeline(project_id, body, caller)
        actor = self._actor_from_body(body, caller=caller, owner_user_id=owner_user_id)
        if actor.type == "human" and actor.id != owner_user_id:
            raise AppendServiceError(403, "forbidden", "human actor must match timeline owner")

        initial_timeline_id = timeline_id or _optional_str(
            body.get("id") or body.get("timeline_uuid"),
            "timeline_id",
        ) or str(uuid4())
        batch = config_to_events(
            config,
            None,
            initial_timeline_id,
            None,
            1,
            actor,
            source,
            expected_version=0,
            txn_id=txn_id,
        )
        initial_event = batch.events[0].to_append_json_obj()
        timeline_payload = {
            "id": initial_timeline_id,
            "project_id": project_id,
            "user_id": owner_user_id,
            "name": name,
        }
        try:
            response = rpc(
                "create_timeline_with_initial_event",
                {
                    "p_timeline": timeline_payload,
                    "p_event": initial_event,
                    "p_projected_config": batch.projected_config,
                    "p_projected_asset_registry": None,
                },
                supabase_url=self.config.supabase_url,
                auth=("service_role", self.config.service_role_key),
                timeout=self.config.timeout,
            )
        except SupabaseHTTPError as exc:
            raise AppendServiceError(502, "create_failed", str(exc)) from exc

        created = _coerce_rpc_row(response, "create_timeline_with_initial_event")
        inserted_ids = list(created["inserted_event_ids"])
        config_version = created["config_version"]
        if asset_registry is not None:
            transport = LiveSupabaseAppendTransport(
                supabase_url=self.config.supabase_url,
                auth_token=self.config.service_role_key,
                timeout=self.config.timeout,
            )
            try:
                registry_result = transport.append_asset_registry_replaced(
                    timeline_id=created["timeline_id"],
                    asset_registry=asset_registry,
                    actor=actor,
                    source=source,
                    expected_version=config_version,
                    txn_id=txn_id,
                )
            except EventLogTransportError as exc:
                raise AppendServiceError(502, "registry_append_failed", str(exc)) from exc
            inserted_ids.extend(registry_result.inserted_event_ids)
            config_version = registry_result.config_version

        return {
            "timeline_id": created["timeline_id"],
            "config_version": config_version,
            "inserted_event_ids": inserted_ids,
            "events": batch.to_append_json(),
        }

    def _authenticate(self, headers: Any) -> AuthorizedCaller:
        auth_header = headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AppendServiceError(401, "unauthorized", "missing Authorization bearer token")
        token = auth_header[7:].strip()
        if not token:
            raise AppendServiceError(401, "unauthorized", "empty bearer token")
        if self.config.internal_token and token == self.config.internal_token:
            return AuthorizedCaller(scheme="internal", user_id=None)
        try:
            verified = verify_user_jwt(
                token,
                jwks_url=self.config.jwks_url,
                timeout=min(self.config.timeout, 10.0),
            )
        except JwtVerificationError as exc:
            raise AppendServiceError(401, "unauthorized", f"invalid user JWT: {exc}") from exc
        return AuthorizedCaller(scheme="user_jwt", user_id=verified.user_id)

    def _authorize_existing_timeline(
        self,
        timeline_id: str,
        caller: AuthorizedCaller,
    ) -> dict[str, str]:
        rows = self._service_read(
            "timelines",
            f"select=id,project_id,user_id&id=eq.{quote(timeline_id, safe='')}&limit=1",
        )
        if not rows:
            raise AppendServiceError(404, "timeline_not_found", f"timeline {timeline_id} was not found")
        row = rows[0]
        user_id = _require_str(row.get("user_id"), "timeline.user_id")
        project_id = _require_str(row.get("project_id"), "timeline.project_id")
        if caller.scheme == "user_jwt" and caller.user_id != user_id:
            raise AppendServiceError(403, "forbidden", "caller does not own timeline")
        return {"user_id": user_id, "project_id": project_id}

    def _authorize_new_timeline(
        self,
        project_id: str,
        body: dict[str, Any],
        caller: AuthorizedCaller,
    ) -> str:
        explicit_user_id = _optional_str(body.get("user_id"), "user_id")
        if caller.scheme == "user_jwt":
            rows = self._service_read(
                "projects",
                f"select=id,user_id&id=eq.{quote(project_id, safe='')}&limit=1",
            )
            if not rows:
                raise AppendServiceError(404, "project_not_found", f"project {project_id} was not found")
            owner_user_id = _require_str(rows[0].get("user_id"), "project.user_id")
            if caller.user_id != owner_user_id:
                raise AppendServiceError(403, "forbidden", "caller does not own project")
            if explicit_user_id is not None and explicit_user_id != owner_user_id:
                raise AppendServiceError(403, "forbidden", "user_id must match project owner")
            return owner_user_id
        if explicit_user_id is None:
            raise AppendServiceError(400, "invalid_user_id", "internal create callers must provide user_id")
        return explicit_user_id

    def _service_read(self, table: str, query: str) -> list[dict[str, Any]]:
        url = f"{self.config.supabase_url.rstrip('/')}/rest/v1/{table}?{query}"
        try:
            payload = get_json(
                url,
                auth=("service_role", self.config.service_role_key),
                timeout=self.config.timeout,
            )
        except SupabaseHTTPError as exc:
            raise AppendServiceError(502, "authorization_read_failed", str(exc)) from exc
        if not isinstance(payload, list):
            raise AppendServiceError(502, "authorization_read_failed", "Supabase read returned non-list")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _actor_from_body(
        self,
        body: dict[str, Any],
        *,
        caller: AuthorizedCaller,
        owner_user_id: str,
    ) -> TimelineActor:
        raw_actor = body.get("actor")
        if isinstance(raw_actor, dict):
            actor_type = _optional_str(raw_actor.get("type"), "actor.type") or "human"
            actor_id = _optional_str(raw_actor.get("id"), "actor.id")
            display = _optional_str(raw_actor.get("display"), "actor.display")
        else:
            actor_type = "human" if caller.scheme == "user_jwt" else "agent"
            actor_id = None
            display = None
        if caller.scheme == "user_jwt":
            actor_type = "human"
            actor_id = caller.user_id
        if actor_id is None:
            actor_id = owner_user_id if actor_type == "human" else "reigh-append-service"
        return TimelineActor(type=actor_type, id=actor_id, display=display)


def create_append_service_server(
    *,
    config: AppendServiceConfig | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    service = AppendService(config or AppendServiceConfig.from_env())
    handler = make_append_service_handler(service=service)
    return ThreadingHTTPServer((host, port), handler)


def make_append_service_handler(*, service: AppendService):
    class Handler(BaseHTTPRequestHandler):
        _ALLOWED_METHODS = "POST, OPTIONS"
        _ALLOWED_HEADERS = "Authorization, Content-Type"

        def log_message(self, _fmt: str, *_args: Any) -> None:
            return

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._set_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_request_body()
                path = urlparse(self.path).path
                parts = [part for part in unquote(path).split("/") if part]
                if (
                    len(parts) == 4
                    and parts[0] == "v1"
                    and parts[1] == "timelines"
                    and parts[3] == "config-replaced"
                ):
                    result = service.append_config_replaced(
                        timeline_id=parts[2],
                        body=payload,
                        headers=self.headers,
                    )
                    self._send_json(200, result)
                    return
                if parts == ["v1", "timelines", "create-with-config"]:
                    result = service.create_with_config(body=payload, headers=self.headers)
                    self._send_json(200, result)
                    return
                raise AppendServiceError(404, "not_found", f"unknown POST route: {path}")
            except AppendServiceError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})

        def _read_request_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(content_length) if content_length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise AppendServiceError(400, "invalid_body", "request body must be valid JSON") from exc
            if not isinstance(payload, dict):
                raise AppendServiceError(400, "invalid_body", "request body must be a JSON object")
            return payload

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self._set_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _set_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Methods", self._ALLOWED_METHODS)
            self.send_header("Access-Control-Allow-Headers", self._ALLOWED_HEADERS)
            self.send_header("Access-Control-Max-Age", "86400")

    return Handler


def _coerce_rpc_row(response: object, rpc_name: str) -> dict[str, Any]:
    row = response[0] if isinstance(response, list) and response else response
    if not isinstance(row, dict):
        raise AppendServiceError(502, "rpc_failed", f"{rpc_name} returned a non-object response")
    timeline_id = _require_str(row.get("timeline_id"), f"{rpc_name}.timeline_id")
    config_version = _optional_int(row.get("config_version"), f"{rpc_name}.config_version")
    inserted_event_ids = row.get("inserted_event_ids")
    if config_version is None:
        raise AppendServiceError(502, "rpc_failed", f"{rpc_name} did not return config_version")
    if not isinstance(inserted_event_ids, list) or not all(
        isinstance(item, str) for item in inserted_event_ids
    ):
        raise AppendServiceError(502, "rpc_failed", f"{rpc_name} did not return inserted_event_ids")
    return {
        "timeline_id": timeline_id,
        "config_version": config_version,
        "inserted_event_ids": inserted_event_ids,
    }


def _coerce_source(raw: object) -> TimelineImportSource:
    if raw is None:
        return "editor_save"
    if raw in {"legacy_local", "supabase_config", "editor_save", "other"}:
        return raw
    raise AppendServiceError(
        400,
        "invalid_source",
        "source must be legacy_local, supabase_config, editor_save, or other",
    )


def _optional(callback: Any) -> Any:
    try:
        return callback()
    except Exception:
        return None


def _require_object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AppendServiceError(400, f"invalid_{field}", f"{field} must be a JSON object")
    return dict(value)


def _optional_object(value: object, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AppendServiceError(400, f"invalid_{field}", f"{field} must be a JSON object")
    return dict(value)


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppendServiceError(400, f"invalid_{field}", f"{field} must be a non-empty string")
    return value


def _optional_str(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AppendServiceError(400, f"invalid_{field}", f"{field} must be a non-empty string")
    return value


def _optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise AppendServiceError(400, f"invalid_{field}", f"{field} must be an integer")
    return value


__all__ = [
    "AppendService",
    "AppendServiceConfig",
    "AppendServiceError",
    "AuthorizedCaller",
    "create_append_service_server",
    "make_append_service_handler",
]
