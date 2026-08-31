"""Discovery and compatibility wrapper around the generated workspace client.

This module owns only runtime endpoint/credential discovery. HTTP protocol
encoding, authentication, and response decoding are delegated to the
generated ``banodoco_workspace_client`` package from the runtime contract.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


class WorkspaceClientError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = dict(details or {})


def _support_home() -> Path:
    return Path(os.environ.get("BANODOCO_LOCAL_HOME") or os.environ.get("HOME", "~")).expanduser()


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
        home = _support_home()
        discovery_path = str(home / "Library" / "Application Support" / "Banodoco" / "runtime" / "discovery.json")
    if not endpoint:
        try:
            value = json.loads(Path(discovery_path).read_text(encoding="utf-8"))
            endpoint = str(value.get("endpoint", ""))
        except (OSError, json.JSONDecodeError):
            endpoint = ""
    credential_path = os.environ.get("BANODOCO_RUNTIME_CREDENTIAL", "").strip()
    if not credential_path:
        home = _support_home()
        credential_path = str(home / "Library" / "Application Support" / "Banodoco" / "credentials" / "astrid.json")
    if not endpoint:
        raise WorkspaceClientError(0, "unavailable", "runtime is unavailable; run `banodoco-local up --profile astrid`")
    return endpoint.rstrip("/"), _read_credential(Path(credential_path))


def _runtime_checkout() -> Path | None:
    """Resolve the generated-client checkout without importing runtime code."""
    for name in ("BANODOCO_RUNTIME_CHECKOUT", "BANODOCO_LOCAL_RUNTIME_CHECKOUT"):
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value).expanduser().resolve()

    home = _support_home()
    catalog_path = home / "Library" / "Application Support" / "Banodoco" / "runtime" / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    source = (catalog.get("source_profiles") or {}).get("astrid") if isinstance(catalog, Mapping) else None
    checkout = source.get("runtime_checkout") if isinstance(source, Mapping) else None
    return Path(str(checkout)).expanduser().resolve() if checkout else None


def _ensure_generated_client_path() -> None:
    """Make an editable runtime's generated Python client importable."""
    checkout = _runtime_checkout()
    if checkout is None:
        return
    client_root = checkout / "packages" / "python"
    if client_root.is_dir():
        client_root_str = str(client_root)
        if client_root_str in sys.path:
            sys.path.remove(client_root_str)
        sys.path.insert(0, client_root_str)


class WorkspaceClient:
    """Small typed facade over the runtime's generated workspace client.

    This class deliberately contains no HTTP protocol code.  It only discovers
    the generated package, maps Astrid's compatibility names (``settings``
    and ``project``) onto the generated operation signatures, and translates
    generated exceptions into Astrid's stable error type.
    """

    def __init__(self, endpoint: str, token: str):
        _ensure_generated_client_path()
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

    def _call_generated(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke one generated operation and normalize its typed value."""
        try:
            try:
                value = getattr(self._generated, operation)(*args, **kwargs)
            except TypeError as exc:
                # Older pinned generated clients predate optional update
                # idempotency headers; preserve their timeline compatibility.
                if "idempotency_key" not in kwargs or "unexpected keyword" not in str(exc):
                    raise
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("idempotency_key", None)
                value = getattr(self._generated, operation)(*args, **retry_kwargs)
        except Exception as exc:  # generated ApiError has stable fields
            raise WorkspaceClientError(
                int(getattr(exc, "status", 0)),
                str(getattr(exc, "code", "transport_error")),
                str(getattr(exc, "message", exc)),
                getattr(exc, "details", {}),
            ) from exc
        return asdict(value) if is_dataclass(value) else value

    # The following methods are intentionally explicit.  They form the
    # product adapter's typed vocabulary and keep generated operation names and
    # compatibility aliases in one place.
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
        expected_realm_id: str | None = None,
        expected_version: int | None = None,
        confirmation: str | None = None,
        noninteractive: bool = True,
    ) -> Any:
        # The runtime recovery contract fences both realm identity and
        # lifecycle version.  Older Astrid callers supplied only the version;
        # resolve the identity through the read-only export so those callers
        # remain safe and compatible with the current generated client.
        if expected_realm_id is None:
            exported = self.export_realm()
            realm = exported.get("realm") if isinstance(exported, Mapping) else None
            if isinstance(realm, Mapping):
                expected_realm_id = str(realm.get("id") or realm.get("realm_id") or "") or None
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
        settings: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        if metadata is None:
            metadata = settings
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
        settings: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        if metadata is None:
            metadata = settings
        return self._call_generated(
            "update_project",
            project_id,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
            name=name,
            metadata=metadata,
        )

    def list_projects(self) -> Any:
        items, cursor = self._call_generated("list_projects")
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": cursor}

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

    def update_timeline_document(self, project_id: str, timeline_id: str, *, expected_version: int, config: Mapping[str, Any], registry: Mapping[str, Any], slug: str | None = None, name: str | None = None) -> Any:
        return self._call_generated("update_timeline_document", project_id, timeline_id, expected_version=expected_version, config=config, registry=registry, slug=slug, name=name)

    def list_timelines(self, project_id: str) -> Any:
        items, cursor = self._call_generated("list_timelines", project_id)
        return {"items": list(items), "next_cursor": cursor}

    def get_timeline(self, timeline_id: str) -> Any:
        return self._call_generated("get_timeline", timeline_id)

    def list_timeline_history(self, timeline_id: str, *, cursor: str | None = None, limit: int = 50) -> Any:
        items, next_cursor = self._call_generated(
            "list_timeline_history", timeline_id, cursor=cursor, limit=limit
        )
        return {"items": list(items), "next_cursor": next_cursor}

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
        items, next_cursor = self._call_generated(
            "list_project_shots",
            project_id,
            cursor=cursor,
            limit=limit,
            include_archived=include_archived,
        )
        return {"items": list(items), "next_cursor": next_cursor}

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

    def list_project_references(
        self,
        project_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        include_archived: bool = False,
    ) -> Any:
        items, next_cursor = self._call_generated(
            "list_project_references",
            project_id,
            cursor=cursor,
            limit=limit,
            include_archived=include_archived,
        )
        return {"items": list(items), "next_cursor": next_cursor}

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

    def create_document(self, project_id: str, document_id: str, kind: str, content: Any) -> Any:
        return self._call_generated("create_document", project_id, document_id, kind, content)

    def list_documents(self, project_id: str) -> Any:
        items, cursor = self._call_generated("list_documents", project_id)
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": cursor}

    def get_document(self, project_id: str, document_id: str) -> Any:
        return self._call_generated("get_document", project_id, document_id)

    def update_document(
        self,
        project_id: str,
        document_id: str,
        *,
        expected_version: int,
        content: Any = None,
        kind: str | None = None,
    ) -> Any:
        return self._call_generated(
            "update_document",
            project_id,
            document_id,
            expected_version=expected_version,
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
        items, next_cursor = self._call_generated(
            "list_project_objects", project_id, cursor=cursor, limit=limit
        )
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": next_cursor}

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
        items, next_cursor = self._call_generated(
            "list_media_relations", project_id, cursor=cursor, limit=limit
        )
        return {"items": list(items), "next_cursor": next_cursor}

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
        items, next_cursor = self._call_generated(
            "list_project_tasks", project_id, cursor=cursor, limit=limit
        )
        return {"items": [asdict(item) if is_dataclass(item) else item for item in items], "next_cursor": next_cursor}

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
        items, next_cursor = self._call_generated(
            "list_project_runs", project_id, cursor=cursor, limit=limit
        )
        return {"items": list(items), "next_cursor": next_cursor}

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

    def create_variant(self, generation_id: str, variant_id: str, **kwargs: Any) -> Any:
        return self._call_generated("create_variant", generation_id, variant_id, **kwargs)

    def list_capabilities(self) -> Any:
        return [asdict(item) if is_dataclass(item) else item for item in self._call_generated("list_capabilities")]

    def register_capability(self, *args: Any, **kwargs: Any) -> Any:
        return self._call_generated("register_capability", *args, **kwargs)

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
