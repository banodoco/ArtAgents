"""Explicit transport adapter around the generated workspace client.

HTTP protocol encoding, authentication, and response decoding are delegated
to the generated ``banodoco_workspace_client`` package from the runtime
contract. Endpoint and credential values are supplied by the caller.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from banodoco_workspace_client import WorkspaceClient as GeneratedWorkspaceClient
except ImportError:  # The SDK remains importable when the runtime package is absent.
    GeneratedWorkspaceClient = None  # type: ignore[assignment,misc]


class WorkspaceClientError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = dict(details or {})


def page_pair(value: Any) -> tuple[list[Any], str | None] | None:
    """Decode the generated client's canonical list-page value.

    The generated client returns ``(items, next_cursor)`` and
    :meth:`WorkspaceClient._call_generated` converts that tuple to the
    JSON-safe ``[items, next_cursor]`` pair.  A bare list (or a mapping-shaped
    adapter response) is not a page and must never be treated as a terminal
    page: doing so loses the pagination boundary and can silently truncate a
    runtime read.
    """

    if not isinstance(value, list) or len(value) != 2:
        return None
    items, next_cursor = value
    if not isinstance(items, list):
        return None
    if next_cursor is not None and (
        not isinstance(next_cursor, str)
        or not next_cursor
        or any(
            character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
            for character in next_cursor
        )
    ):
        return None
    return items, next_cursor


def paged_rows(
    reader: Any,
    *args: Any,
    cursor: str | None = None,
    limit: int = 50,
    max_pages: int = 10_000,
    **kwargs: Any,
) -> list[Any] | None:
    """Read every page from a canonical cursor-bearing runtime operation.

    This is the one pagination boundary shared by product adapters and
    runtime-backed packs.  A page is *only* the JSON-safe ``[items,
    next_cursor]`` pair; bare lists, mappings, malformed cursors, failures,
    and cursor cycles fail closed as ``None``.  ``max_pages`` is an explicit
    safety bound so an unhealthy runtime cannot turn a read into an unbounded
    loop.

    ``reader`` is called with the canonical ``cursor`` and ``limit`` keyword
    arguments on every request, including the first page.  The runtime
    sibling's generated signatures are required to accept these arguments.
    DomainResult-like values are unwrapped only through their explicit
    ``ok``/``data`` contract; no alternate page shape is accepted.
    """

    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        return None
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0:
        return None
    rows: list[Any] = []
    seen_cursors: set[str] = set()
    current = cursor
    for _ in range(max_pages):
        call_kwargs = dict(kwargs)
        call_kwargs.update(cursor=current, limit=limit)
        try:
            value = reader(*args, **call_kwargs)
        except TypeError:
            # Keep narrow test doubles and older generated clients usable for
            # a terminal first page. A continuation still necessarily uses
            # the canonical cursor-bearing call and therefore fails closed if
            # the reader cannot accept it.
            if current is not None or kwargs:
                return None
            try:
                value = reader(*args)
            except Exception:
                return None
        except Exception:
            return None
        if hasattr(value, "ok") and hasattr(value, "data"):
            if not bool(value.ok):
                return None
            value = value.data
        page = page_pair(value)
        if page is None:
            return None
        page_rows, next_cursor = page
        if len(page_rows) > limit:
            return None
        rows.extend(page_rows)
        if next_cursor is None:
            return rows
        if next_cursor == current or next_cursor in seen_cursors:
            return None
        seen_cursors.add(next_cursor)
        current = next_cursor
    return None


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


def resolve_runtime_connection(endpoint: str, credential: str | Path) -> tuple[str, str]:
    """Validate an explicitly supplied endpoint and credential."""
    endpoint = str(endpoint).strip()
    if not endpoint.startswith(("http://", "https://")) or endpoint.rstrip("/") in {"http:", "https:"}:
        raise WorkspaceClientError(0, "validation_error", "runtime endpoint must be an explicit http(s) URL")
    if isinstance(credential, Path):
        token = _read_credential(Path(credential))
    else:
        token = str(credential).removeprefix("Bearer ").strip()
    if not token:
        raise WorkspaceClientError(0, "validation_error", "runtime credential must be explicit and non-empty")
    return endpoint.rstrip("/"), token


class WorkspaceClient:
    """Small typed facade over the runtime's generated workspace client.

    This class deliberately contains no HTTP protocol code or local discovery.
    It translates only generated exceptions into Astrid's stable error type.
    """

    def __init__(self, endpoint: str, token: str):
        if GeneratedWorkspaceClient is None:
            raise WorkspaceClientError(
                0,
                "unavailable",
                "generated workspace client is unavailable; run `banodoco-local up --profile astrid`",
            )
        self.endpoint, self.token = resolve_runtime_connection(endpoint, token)
        self._generated = GeneratedWorkspaceClient(self.endpoint, token)

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

    def update_timeline_document(self, project_id: str, timeline_id: str, *, expected_version: int, config: Mapping[str, Any], registry: Mapping[str, Any], slug: str | None = None, name: str | None = None) -> Any:
        return self._call_generated("update_timeline_document", project_id, timeline_id, expected_version=expected_version, config=config, registry=registry, slug=slug, name=name)

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

    def create_document(self, project_id: str, document_id: str, kind: str, content: Any) -> Any:
        return self._call_generated("create_document", project_id, document_id, kind, content)

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

    def create_generation(self, project_id: str, generation_id: str, *, metadata: Mapping[str, Any] | None = None, type: str = "generation", source_task_id: str | None = None) -> Any:
        return self._call_generated("create_generation", project_id, generation_id, metadata=metadata, type=type, source_task_id=source_task_id)

    def create_variant(self, generation_id: str, variant_id: str, *, object_id: str | None = None, variant_type: str = "original", metadata: Mapping[str, Any] | None = None) -> Any:
        return self._call_generated("create_variant", generation_id, variant_id, object_id=object_id, variant_type=variant_type, metadata=metadata)

    def list_capabilities(self) -> Any:
        return [asdict(item) if is_dataclass(item) else item for item in self._call_generated("list_capabilities")]

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
