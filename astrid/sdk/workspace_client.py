"""Explicit transport adapter around the generated workspace client.

HTTP protocol encoding, authentication, and response decoding are delegated
to the generated ``banodoco_workspace_client`` package from the runtime
contract. Endpoint and credential values are supplied by the caller.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from banodoco_workspace_client import WorkspaceClient as GeneratedWorkspaceClient
from banodoco_workspace_client.contract_metadata import PROTOCOL, SCHEMA_DIGEST

from .pagination import page_pair, paged_rows

__all__ = [
    "GeneratedWorkspaceClient",
    "PROTOCOL",
    "SCHEMA_DIGEST",
    "WorkspaceClient",
    "WorkspaceClientError",
    "paged_rows",
    "resolve_runtime_connection",
]

RECONFIGURE_ACTION = "reconfigure the Astrid runtime with `banodoco-local up --profile astrid`"


def _reconfigure(field: str, message: str) -> "WorkspaceClientError":
    return WorkspaceClientError(
        0,
        "reconfigure_required",
        message,
        {"field": field, "next_action": RECONFIGURE_ACTION},
    )


def _safe_local_path(value: str | Path, *, field: str) -> Path:
    """Return a regular local path, rejecting symlinked discovery inputs.

    Launcher result paths are security-sensitive: resolving a symlink before
    checking it would let a changed manifest or credential path silently point
    at an unrelated file.  Check the lexical path and every existing parent
    first, then let the caller check the file type/content.
    """
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = Path(path.absolute())
    current = path
    while True:
        try:
            if current.is_symlink():
                raise _reconfigure(field, f"{field} path must not be a symlink; {RECONFIGURE_ACTION}")
        except OSError as exc:
            raise _reconfigure(field, f"cannot inspect {field} path; {RECONFIGURE_ACTION}") from exc
        if current == current.parent:
            break
        current = current.parent
    return path


def validate_runtime_endpoint(endpoint: str) -> str:
    """Validate an explicit runtime URL without permitting network pivots."""
    value = str(endpoint).strip()
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        # Accessing port validates malformed values such as ``:not-a-port``.
        _ = parsed.port
    except ValueError as exc:
        raise _reconfigure("endpoint", f"runtime endpoint is malformed; {RECONFIGURE_ACTION}") from exc
    host = hostname.rstrip(".").lower() if hostname else ""
    is_loopback = host == "localhost"
    if host and not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not is_loopback
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or value.rstrip("/") in {"http:", "https:"}
    ):
        raise _reconfigure(
            "endpoint",
            "runtime endpoint must be an explicit loopback http(s) URL; " + RECONFIGURE_ACTION,
        )
    return value.rstrip("/")


class WorkspaceClientError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = dict(details or {})


def _read_credential(path: Path) -> str:
    path = _safe_local_path(path, field="credential")
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise _reconfigure("credential", f"runtime credential is unavailable; {RECONFIGURE_ACTION}") from exc
    if not raw:
        raise _reconfigure("credential", f"runtime credential is empty; {RECONFIGURE_ACTION}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    token = value.get("token") if isinstance(value, dict) else None
    if not isinstance(token, str) or not token:
        raise _reconfigure("credential", f"runtime credential is invalid; {RECONFIGURE_ACTION}")
    return token


def resolve_runtime_connection(endpoint: str, credential: str | Path) -> tuple[str, str]:
    """Validate an explicitly supplied endpoint and credential."""
    endpoint = validate_runtime_endpoint(endpoint)
    if not isinstance(credential, (str, Path)):
        raise _reconfigure("credential", f"runtime credential must be explicit and non-empty; {RECONFIGURE_ACTION}")
    if isinstance(credential, Path):
        token = _read_credential(Path(credential))
    else:
        token = str(credential).removeprefix("Bearer ").strip()
    if not token:
        raise _reconfigure("credential", f"runtime credential must be explicit and non-empty; {RECONFIGURE_ACTION}")
    return endpoint, token


class WorkspaceClient:
    """Small typed facade over the runtime's generated workspace client.

    This class deliberately contains no HTTP protocol code or local discovery.
    It translates only generated exceptions into Astrid's stable error type.
    """

    def __init__(self, endpoint: str, token: str):
        self.endpoint, self.token = resolve_runtime_connection(endpoint, token)
        self._generated = GeneratedWorkspaceClient(self.endpoint, self.token)

    def _call_generated(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke one generated operation and normalize its typed value."""
        try:
            # Resolve exactly one method on demand.  The generated contract is
            # versioned independently of Astrid: a partial client used for a
            # narrow operation (for example ``settle_attempt``) must not fail
            # while constructing a map that eagerly looks up unrelated newer
            # operations such as ``health``.
            operations = {
                "health", "handshake", "doctor", "create_backup", "restore_backup",
                "export_realm", "tombstone_realm", "recover_realm", "purge_realm",
                "create_project", "get_project", "update_project", "list_projects",
                "select_project", "current_project", "create_timeline",
                "create_timeline_document", "update_timeline_document", "list_timelines",
                "get_timeline", "list_timeline_history", "diff_timeline", "archive_timeline",
                "recover_timeline", "list_project_shots", "create_project_shot",
                "get_project_shot", "update_project_shot", "archive_project_shot",
                "recover_project_shot", "add_shot_item", "remove_shot_item",
                "reorder_shot_items", "list_project_references", "create_project_reference",
                "list_project_shot_text_bindings", "set_project_shot_text_binding",
                "get_project_shot_text_binding", "set_project_shot_text_binding_by_id",
                "rebind_project_shot_text_binding",
                "get_project_reference", "update_project_reference", "archive_project_reference",
                "recover_project_reference", "associate_reference", "set_primary_reference",
                "link_references", "create_document", "list_documents", "get_document",
                "update_document", "ingest_object", "ingest_project_object",
                "list_project_objects", "create_media_relation", "list_media_relations",
                "get_object", "head_object", "admit_task", "get_task", "list_project_tasks",
                "cancel_task", "retry_task", "cancel_run", "retry_run", "get_run",
                "list_project_runs", "list_events", "list_run_events", "list_generations",
                "get_generation", "list_variants", "create_generation", "create_variant",
                "list_capabilities", "register_capability", "claim_task", "register_executor",
                "settle_attempt",
            }
            if operation not in operations:
                raise ValueError(f"unknown generated workspace operation: {operation!r}")
            generated = getattr(self._generated, operation)
            if not callable(generated):
                raise AttributeError(f"generated workspace operation is not callable: {operation!r}")
            value = generated(*args, **kwargs)
        except Exception as exc:  # generated ApiError has stable fields
            fields = exc.__dict__ if hasattr(exc, "__dict__") else {}
            raise WorkspaceClientError(
                int(fields.get("status", 0)),
                str(fields.get("code", "transport_error")),
                str(fields.get("message", exc)),
                fields.get("details", {}),
            ) from exc
        def plain(item: Any) -> Any:
            if is_dataclass(item):
                return {key: plain(child) for key, child in asdict(item).items()}
            if isinstance(item, tuple):
                # Transport values are part of the JSON product surface;
                # never leave tuples in a DomainResult payload where the
                # canonical encoder would reject them.
                return [plain(child) for child in item]
            if isinstance(item, list):
                return [plain(child) for child in item]
            if isinstance(item, dict):
                return {key: plain(child) for key, child in item.items()}
            return item
        # The generated client carries committed mutation receipts as an
        # out-of-band ``MutationResult.receipt`` attribute on its resource
        # mapping. Preserve that attribute across the plain JSON conversion;
        # RemoteAstridClient._typed consumes the stable {data, receipt}
        # envelope and turns it into DomainResult.receipt.
        if hasattr(value, "receipt") and isinstance(value, dict):
            return {"data": plain(dict(value)), "receipt": plain(value.receipt)}
        return plain(value)

    # The following methods are intentionally explicit.  They form the
    # product adapter's typed vocabulary and keep generated operation names in
    # one explicit mapping.
    def health(self) -> Any:
        return self._call_generated("health")

    def handshake(self, client_name: str, client_version: str, requested_scopes: list[str]) -> Any:
        return self._call_generated("handshake", client_name, client_version, requested_scopes)

    def doctor(self) -> Any:
        return self._call_generated("doctor")

    def create_backup(self, destination: str) -> Any:
        return self._call_generated("create_backup", destination)

    def restore_backup(self, backup: str, destination: str) -> Any:
        return self._call_generated("restore_backup", backup, destination)

    def export_realm(self) -> Any:
        return self._call_generated("export_realm")

    def tombstone_realm(self, *, reason: str | None = None, expected_version: int | None = None) -> Any:
        return self._call_generated("tombstone_realm", reason=reason, expected_version=expected_version)

    def recover_realm(
        self,
        *,
        expected_realm_id: str,
        expected_version: int,
        confirmation: str | None = None,
        noninteractive: bool = False,
    ) -> Any:
        return self._call_generated(
            "recover_realm",
            expected_realm_id=expected_realm_id,
            expected_version=expected_version,
            confirmation=confirmation,
            noninteractive=noninteractive,
        )

    def purge_realm(self, confirmation: str) -> Any:
        return self._call_generated("purge_realm", confirmation)

    def create_project(
        self,
        name: str,
        *,
        idempotency_key: str,
        slug: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        return self._call_generated(
            "create_project", name, idempotency_key=idempotency_key, slug=slug, metadata=metadata
        )

    def update_project(
        self,
        project_id: str,
        *,
        idempotency_key: str,
        expected_version: int | None = None,
        name: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        return self._call_generated(
            "update_project",
            project_id,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
            name=name,
            metadata=metadata,
        )

    def list_projects(self, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_projects", cursor=cursor, limit=limit)

    def select_project(self, project: str, *, scope: str = "workspace", idempotency_key: str | None = None) -> Any:
        return self._call_generated("select_project", project, scope=scope, idempotency_key=idempotency_key)

    def current_project(self) -> Any:
        return self._call_generated("current_project")

    def get_project(self, project_id: str) -> Any:
        return self._call_generated("get_project", project_id)

    def create_timeline(self, project_id: str, timeline_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("create_timeline", project_id, timeline_id, idempotency_key=idempotency_key)

    def create_timeline_document(self, project_id: str, timeline_id: str, *, config: Mapping[str, Any], registry: Mapping[str, Any], slug: str | None = None, name: str | None = None, idempotency_key: str) -> Any:
        return self._call_generated("create_timeline_document", project_id, timeline_id, config=config, registry=registry, slug=slug, name=name, idempotency_key=idempotency_key)

    def update_timeline_document(self, project_id: str, timeline_id: str, *, expected_version: int, config: Mapping[str, Any], registry: Mapping[str, Any], slug: str | None = None, name: str | None = None, idempotency_key: str) -> Any:
        return self._call_generated("update_timeline_document", project_id, timeline_id, expected_version=expected_version, config=config, registry=registry, slug=slug, name=name, idempotency_key=idempotency_key)

    def list_timelines(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_timelines", project_id, cursor=cursor, limit=limit)

    def get_timeline(self, timeline_id: str) -> Any:
        return self._call_generated("get_timeline", timeline_id)

    def list_timeline_history(self, timeline_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_timeline_history", timeline_id, cursor=cursor, limit=limit)

    def diff_timeline(self, timeline_id: str, *, from_version: int, to_version: int) -> Any:
        return self._call_generated(
            "diff_timeline", timeline_id, from_version=from_version, to_version=to_version
        )

    def archive_timeline(self, timeline_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated(
            "archive_timeline", timeline_id, expected_version=expected_version, idempotency_key=idempotency_key
        )

    def recover_timeline(
        self,
        timeline_id: str,
        *,
        expected_version: int,
        version: int,
        idempotency_key: str,
    ) -> Any:
        return self._call_generated(
            "recover_timeline",
            timeline_id,
            expected_version=expected_version,
            version=version,
            idempotency_key=idempotency_key,
        )

    def list_project_shots(
        self,
        project_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        include_archived: bool = False,
    ) -> Any:
        return self._call_generated("list_project_shots", project_id, cursor=cursor, limit=limit, include_archived=include_archived)

    def create_project_shot(self, project_id: str, shot: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("create_project_shot", project_id, shot, idempotency_key=idempotency_key)

    def get_project_shot(self, project_id: str, shot_id: str) -> Any:
        return self._call_generated("get_project_shot", project_id, shot_id)

    def update_project_shot(self, project_id: str, shot_id: str, *, expected_version: int, name=None, metadata=None, idempotency_key: str | None = None) -> Any:
        return self._call_generated("update_project_shot", project_id, shot_id, expected_version=expected_version, name=name, metadata=metadata, idempotency_key=idempotency_key or "")

    def archive_project_shot(self, project_id: str, shot_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("archive_project_shot", project_id, shot_id, expected_version=expected_version, idempotency_key=idempotency_key)

    def recover_project_shot(self, project_id: str, shot_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("recover_project_shot", project_id, shot_id, expected_version=expected_version, idempotency_key=idempotency_key)

    def add_shot_item(self, project_id: str, shot_id: str, item: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("add_shot_item", project_id, shot_id, item, idempotency_key=idempotency_key)

    def remove_shot_item(self, project_id: str, shot_id: str, item_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("remove_shot_item", project_id, shot_id, item_id, expected_version=expected_version, idempotency_key=idempotency_key)

    def reorder_shot_items(self, project_id: str, shot_id: str, item_ids: list[str], *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("reorder_shot_items", project_id, shot_id, item_ids, expected_version=expected_version, idempotency_key=idempotency_key)

    def list_project_shot_text_bindings(self, project_id: str, *, shot_id: str | None = None, kind: str | None = None, slot: str | None = None) -> Any:
        return self._call_generated("list_project_shot_text_bindings", project_id, shot_id=shot_id, kind=kind, slot=slot)

    def set_project_shot_text_binding(self, project_id: str, body: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("set_project_shot_text_binding", project_id, body, idempotency_key=idempotency_key)

    def get_project_shot_text_binding(self, project_id: str, binding_id: str) -> Any:
        return self._call_generated("get_project_shot_text_binding", project_id, binding_id)

    def set_project_shot_text_binding_by_id(self, project_id: str, binding_id: str, body: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("set_project_shot_text_binding_by_id", project_id, binding_id, body, idempotency_key=idempotency_key)

    def rebind_project_shot_text_binding(self, project_id: str, binding_id: str, *, media_id: str, expected_head: int, idempotency_key: str) -> Any:
        return self._call_generated("rebind_project_shot_text_binding", project_id, binding_id, media_id=media_id, expected_head=expected_head, idempotency_key=idempotency_key)

    def list_project_references(
        self,
        project_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        include_archived: bool = False,
    ) -> Any:
        return self._call_generated("list_project_references", project_id, cursor=cursor, limit=limit, include_archived=include_archived)

    def create_project_reference(self, project_id: str, reference: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("create_project_reference", project_id, reference, idempotency_key=idempotency_key)

    def get_project_reference(self, project_id: str, reference_id: str) -> Any:
        return self._call_generated("get_project_reference", project_id, reference_id)

    def update_project_reference(self, project_id: str, reference_id: str, *, expected_version: int, name=None, description=None, metadata=None, idempotency_key: str | None = None) -> Any:
        return self._call_generated("update_project_reference", project_id, reference_id, expected_version=expected_version, name=name, description=description, metadata=metadata, idempotency_key=idempotency_key or "")

    def archive_project_reference(self, project_id: str, reference_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("archive_project_reference", project_id, reference_id, expected_version=expected_version, idempotency_key=idempotency_key)

    def recover_project_reference(self, project_id: str, reference_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("recover_project_reference", project_id, reference_id, expected_version=expected_version, idempotency_key=idempotency_key)

    def associate_reference(self, project_id: str, reference_id: str, association: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("associate_reference", project_id, reference_id, association, idempotency_key=idempotency_key)

    def set_primary_reference(self, project_id: str, reference_id: str, association_id: str, *, expected_version: int, idempotency_key: str) -> Any:
        return self._call_generated("set_primary_reference", project_id, reference_id, association_id, expected_version=expected_version, idempotency_key=idempotency_key)

    def link_references(self, project_id: str, link: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("link_references", project_id, link, idempotency_key=idempotency_key)

    def create_document(self, project_id: str, document_id: str, kind: str, content: Any, *, idempotency_key: str) -> Any:
        return self._call_generated("create_document", project_id, document_id, kind, content, idempotency_key=idempotency_key)

    def list_documents(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_documents", project_id, cursor=cursor, limit=limit)

    def get_document(self, project_id: str, document_id: str) -> Any:
        return self._call_generated("get_document", project_id, document_id)

    def update_document(
        self,
        project_id: str,
        document_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        content: Any = None,
        kind: str | None = None,
    ) -> Any:
        return self._call_generated(
            "update_document",
            project_id,
            document_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            content=content,
            kind=kind,
        )

    def ingest_object(self, data: bytes, *, media_type: str, idempotency_key: str, filename: str | None = None) -> Any:
        return self._call_generated("ingest_object", data, media_type=media_type, idempotency_key=idempotency_key, filename=filename)

    def ingest_project_object(
        self,
        project_id: str,
        data: bytes,
        *,
        media_type: str,
        idempotency_key: str,
        filename: str | None = None,
    ) -> Any:
        return self._call_generated(
            "ingest_project_object",
            project_id,
            data,
            media_type=media_type,
            idempotency_key=idempotency_key,
            filename=filename,
        )

    def list_project_objects(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_project_objects", project_id, cursor=cursor, limit=limit)

    def create_media_relation(
        self,
        project_id: str,
        from_object_id: str,
        to_object_id: str,
        kind: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
    ) -> Any:
        return self._call_generated(
            "create_media_relation",
            project_id,
            from_object_id,
            to_object_id,
            kind,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )

    def list_media_relations(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_media_relations", project_id, cursor=cursor, limit=limit)

    def get_object(self, object_id: str) -> Any:
        return self._call_generated("get_object", object_id)

    def head_object(self, object_id: str) -> Any:
        return self._call_generated("head_object", object_id)

    def admit_task(
        self,
        *,
        capability_id: str,
        capability_digest: str,
        input_object_ids: list[str],
        idempotency_key: str,
        schema_version: str = "1",
        settlement_effect: Mapping[str, Any] | None = None,
        project_id: str | None = None,
        spec: Mapping[str, Any] | None = None,
    ) -> Any:
        return self._call_generated(
            "admit_task",
            capability_id=capability_id,
            capability_digest=capability_digest,
            input_object_ids=input_object_ids,
            idempotency_key=idempotency_key,
            schema_version=schema_version,
            settlement_effect=settlement_effect,
            project_id=project_id,
            spec=spec,
        )

    def get_task(self, task_id: str) -> Any:
        return self._call_generated("get_task", task_id)

    def list_project_tasks(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_project_tasks", project_id, cursor=cursor, limit=limit)

    def cancel_task(self, task_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("cancel_task", task_id, idempotency_key=idempotency_key)

    def retry_task(self, task_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("retry_task", task_id, idempotency_key=idempotency_key)

    def cancel_run(self, run_id: str, *, idempotency_key: str) -> Any:
        return self._call_generated("cancel_run", run_id, idempotency_key=idempotency_key)

    def retry_run(self, run_id: str, *, idempotency_key: str, selected_task_ids: list[str] | None = None) -> Any:
        return self._call_generated("retry_run", run_id, idempotency_key=idempotency_key, selected_task_ids=selected_task_ids)

    def get_run(self, run_id: str) -> Any:
        return self._call_generated("get_run", run_id)

    def list_project_runs(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_project_runs", project_id, cursor=cursor, limit=limit)

    def list_events(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
        aggregate_id: str | None = None,
    ) -> Any:
        return self._call_generated(
            "list_events", cursor=cursor, limit=limit, aggregate_id=aggregate_id
        )

    def list_run_events(self, run_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_run_events", run_id, cursor=cursor, limit=limit)

    def list_generations(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_generations", project_id, cursor=cursor, limit=limit)

    def get_generation(self, generation_id: str) -> Any:
        return self._call_generated("get_generation", generation_id)

    def list_variants(self, generation_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        return self._call_generated("list_variants", generation_id, cursor=cursor, limit=limit)

    def create_generation(self, project_id: str, generation_id: str, *, metadata: Mapping[str, Any] | None = None, type: str = "generation", source_task_id: str | None = None, idempotency_key: str) -> Any:
        return self._call_generated("create_generation", project_id, generation_id, metadata=metadata, type=type, source_task_id=source_task_id, idempotency_key=idempotency_key)

    def create_variant(self, generation_id: str, variant_id: str, *, object_id: str | None = None, variant_type: str = "original", metadata: Mapping[str, Any] | None = None, idempotency_key: str) -> Any:
        return self._call_generated("create_variant", generation_id, variant_id, object_id=object_id, variant_type=variant_type, metadata=metadata, idempotency_key=idempotency_key)

    def list_capabilities(self, *, cursor: str | None = None, limit: int = 50) -> Any:
        """Return one strict ``[items, next_cursor]`` capability page.

        The sibling runtime's generated client is cursor-bearing.  Preserve
        that boundary in the Astrid transport wrapper so callers can either
        request a page explicitly or use the shared ``paged_rows`` helper to
        exhaust the collection.  A bare list is never a valid response.
        """
        value = self._call_generated("list_capabilities", cursor=cursor, limit=limit)
        page = page_pair(value)
        if page is None:
            raise WorkspaceClientError(
                0,
                "protocol_error",
                "runtime capability listing returned an invalid page",
            )
        items, next_cursor = page
        return [[asdict(item) if is_dataclass(item) else item for item in items], next_cursor]

    def register_capability(self, capability_id: str, definition_digest: str, *, required_resource_keys: list[str] | None = None, status: str = "ready", estimated_scratch_bytes: int = 0, estimated_output_bytes: int = 0, unavailable_reason: str | None = None, idempotency_key: str | None = None) -> Any:
        return self._call_generated("register_capability", capability_id, definition_digest, required_resource_keys=required_resource_keys, status=status, estimated_scratch_bytes=estimated_scratch_bytes, estimated_output_bytes=estimated_output_bytes, unavailable_reason=unavailable_reason, idempotency_key=idempotency_key)

    def claim_task(
        self,
        *,
        executor_id: str,
        capability_ids: list[str],
        idempotency_key: str,
        runtime_epoch: int | None = None,
    ) -> Any:
        if runtime_epoch is None:
            health = self.health()
            runtime_epoch = int(health.get("runtime_epoch", 0)) if isinstance(health, Mapping) else 0
        return self._call_generated(
            "claim_task",
            executor_id=executor_id,
            capability_ids=capability_ids,
            idempotency_key=idempotency_key,
            runtime_epoch=runtime_epoch,
        )

    def register_executor(self, executor: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("register_executor", executor, idempotency_key=idempotency_key)

    def settle_attempt(self, attempt_id: str, settlement: Mapping[str, Any], *, idempotency_key: str) -> Any:
        return self._call_generated("settle_attempt", attempt_id, settlement, idempotency_key=idempotency_key)
