"""Astrid's product-neutral adapter over the generated workspace client."""

from __future__ import annotations

import mimetypes
from pathlib import Path
import uuid
from typing import Any, Mapping

from astrid.core.receipts.contract import CommandReceipt

from .contracts import DomainResult, ErrorObject
from .workspace_client import WorkspaceClient, WorkspaceClientError
from .pagination import paged_rows


class _RemoteFamily:
    def __init__(self, client: WorkspaceClient):
        self._client = client

    def _typed(self, operation: str, *args: Any, key: str | None = None, **kwargs: Any) -> DomainResult[Any]:
        reads = {"get_project", "list_projects", "current_project", "get_timeline", "list_timelines", "list_timeline_history", "diff_timeline", "get_shot", "list_project_shots", "get_reference", "list_project_references", "get_object", "head_object", "list_project_objects", "list_media_relations", "get_task", "list_project_tasks", "get_run", "list_project_runs", "list_events", "list_run_events", "list_generations", "get_generation", "list_variants", "get_document", "list_documents"}
        if key is None and operation not in reads:
            key = uuid.uuid4().hex
        try:
            # Keep the operation vocabulary auditable.  In particular, never
            # let a caller turn an arbitrary string into an attribute lookup
            # on the generated client.
            if operation == "add_shot_item": value = self._client.add_shot_item(*args, **kwargs)
            elif operation == "admit_task": value = self._client.admit_task(*args, **kwargs)
            elif operation == "archive_project_reference": value = self._client.archive_project_reference(*args, **kwargs)
            elif operation == "archive_project_shot": value = self._client.archive_project_shot(*args, **kwargs)
            elif operation == "archive_timeline": value = self._client.archive_timeline(*args, **kwargs)
            elif operation == "associate_reference": value = self._client.associate_reference(*args, **kwargs)
            elif operation == "cancel_run": value = self._client.cancel_run(*args, **kwargs)
            elif operation == "cancel_task": value = self._client.cancel_task(*args, **kwargs)
            elif operation == "claim_task": value = self._client.claim_task(*args, **kwargs)
            elif operation == "create_generation": value = self._client.create_generation(*args, **kwargs)
            elif operation == "create_media_relation": value = self._client.create_media_relation(*args, **kwargs)
            elif operation == "create_project": value = self._client.create_project(*args, **kwargs)
            elif operation == "create_project_reference": value = self._client.create_project_reference(*args, **kwargs)
            elif operation == "create_project_shot": value = self._client.create_project_shot(*args, **kwargs)
            elif operation == "create_timeline_document": value = self._client.create_timeline_document(*args, **kwargs)
            elif operation == "create_variant": value = self._client.create_variant(*args, **kwargs)
            elif operation == "current_project": value = self._client.current_project(*args, **kwargs)
            elif operation == "diff_timeline": value = self._client.diff_timeline(*args, **kwargs)
            elif operation == "get_generation": value = self._client.get_generation(*args, **kwargs)
            elif operation == "get_object": value = self._client.get_object(*args, **kwargs)
            elif operation == "get_project": value = self._client.get_project(*args, **kwargs)
            elif operation == "get_project_reference": value = self._client.get_project_reference(*args, **kwargs)
            elif operation == "get_project_shot": value = self._client.get_project_shot(*args, **kwargs)
            elif operation == "get_run": value = self._client.get_run(*args, **kwargs)
            elif operation == "get_task": value = self._client.get_task(*args, **kwargs)
            elif operation == "get_timeline": value = self._client.get_timeline(*args, **kwargs)
            elif operation == "head_object": value = self._client.head_object(*args, **kwargs)
            elif operation == "ingest_project_object": value = self._client.ingest_project_object(*args, **kwargs)
            elif operation == "link_references": value = self._client.link_references(*args, **kwargs)
            elif operation == "list_events": value = self._client.list_events(*args, **kwargs)
            elif operation == "list_generations": value = self._client.list_generations(*args, **kwargs)
            elif operation == "list_media_relations": value = self._client.list_media_relations(*args, **kwargs)
            elif operation == "list_project_objects": value = self._client.list_project_objects(*args, **kwargs)
            elif operation == "list_project_references": value = self._client.list_project_references(*args, **kwargs)
            elif operation == "list_project_runs": value = self._client.list_project_runs(*args, **kwargs)
            elif operation == "list_project_shots": value = self._client.list_project_shots(*args, **kwargs)
            elif operation == "list_project_tasks": value = self._client.list_project_tasks(*args, **kwargs)
            elif operation == "list_projects": value = self._client.list_projects(*args, **kwargs)
            elif operation == "list_run_events": value = self._client.list_run_events(*args, **kwargs)
            elif operation == "list_timeline_history": value = self._client.list_timeline_history(*args, **kwargs)
            elif operation == "list_timelines": value = self._client.list_timelines(*args, **kwargs)
            elif operation == "list_variants": value = self._client.list_variants(*args, **kwargs)
            elif operation == "recover_project_reference": value = self._client.recover_project_reference(*args, **kwargs)
            elif operation == "recover_project_shot": value = self._client.recover_project_shot(*args, **kwargs)
            elif operation == "recover_timeline": value = self._client.recover_timeline(*args, **kwargs)
            elif operation == "register_capability": value = self._client.register_capability(*args, **kwargs)
            elif operation == "register_executor": value = self._client.register_executor(*args, **kwargs)
            elif operation == "remove_shot_item": value = self._client.remove_shot_item(*args, **kwargs)
            elif operation == "reorder_shot_items": value = self._client.reorder_shot_items(*args, **kwargs)
            elif operation == "retry_run": value = self._client.retry_run(*args, **kwargs)
            elif operation == "retry_task": value = self._client.retry_task(*args, **kwargs)
            elif operation == "select_project": value = self._client.select_project(*args, **kwargs)
            elif operation == "set_primary_reference": value = self._client.set_primary_reference(*args, **kwargs)
            elif operation == "settle_attempt": value = self._client.settle_attempt(*args, **kwargs)
            elif operation == "update_project": value = self._client.update_project(*args, **kwargs)
            elif operation == "update_project_reference": value = self._client.update_project_reference(*args, **kwargs)
            elif operation == "update_project_shot": value = self._client.update_project_shot(*args, **kwargs)
            elif operation == "update_timeline_document": value = self._client.update_timeline_document(*args, **kwargs)
            else: raise ValueError(f"unsupported generated operation: {operation}")
            receipt = None
            if isinstance(value, dict) and set(value) >= {"data", "receipt"}:
                receipt = CommandReceipt.from_dict(value["receipt"]) if value["receipt"] is not None else None
                value = value["data"]
            return DomainResult.success(value, receipt=receipt, idempotency_key=key or "")
        except WorkspaceClientError as exc:
            return DomainResult.failure(ErrorObject(code=exc.code, message=exc.message, details=exc.details), idempotency_key=key or "")


class RemoteProjects(_RemoteFamily):
    def create(self, *, slug: str, name: str, metadata: Mapping[str, Any] | None = None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("create_project", name, key=key, idempotency_key=key, slug=slug, metadata=metadata)
    def list(self, *, cursor=None, limit=50):
        return self._typed("list_projects", cursor=cursor, limit=limit)
    def show(self, ref): return self._typed("get_project", ref)
    def update(self, ref, *, name=None, metadata=None, expected_version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("update_project", ref, key=key, idempotency_key=key, name=name, metadata=metadata, expected_version=expected_version)
    def select(self, ref, *, scope="workspace", idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("select_project", key=key, project=ref, scope=scope, idempotency_key=key)
    def current(self):
        return self._typed("current_project")


class RemoteTimelines(_RemoteFamily):
    def create(self, *, project, config: Mapping[str, Any], registry: Mapping[str, Any], slug=None, name=None, timeline_id=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("create_timeline_document", project, timeline_id or uuid.uuid4().hex, key=key, config=config, registry=registry, slug=slug, name=name, idempotency_key=key)
    def list(self, project, *, cursor=None, limit=50):
        return self._typed("list_timelines", project, cursor=cursor, limit=limit)
    def show(self, project, ref):
        # The runtime read endpoint is id-addressed while the product CLI is
        # deliberately slug-friendly. Resolve the project-local slug to the
        # canonical id before issuing the resource read. This keeps slug
        # resolution inside the remote client and never creates a filesystem
        # timeline authority.
        rows = paged_rows(self._client.list_timelines, str(project), limit=50)
        if rows is None:
            return DomainResult.failure(ErrorObject("not_found", "timeline not found", {"project": str(project), "ref": str(ref)}))
        match = next(
            (
                item for item in rows
                if isinstance(item, Mapping)
                and str(ref) in {str(item.get("timeline_id", "")), str(item.get("slug", ""))}
            ),
            None,
        )
        if match is None:
            return DomainResult.failure(ErrorObject("not_found", "timeline not found", {"project": str(project), "ref": str(ref)}))
        return self._typed("get_timeline", str(match.get("timeline_id")))
    def save(self, project, ref, *, config: Mapping[str, Any], registry: Mapping[str, Any], expected_version=1, slug=None, name=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if not project:
            return DomainResult.failure(
                ErrorObject("validation_error", "timeline save requires a project", {"field": "project"}),
                idempotency_key=key,
            )
        return self._typed("update_timeline_document", project, ref, expected_version=expected_version, config=config, registry=registry, slug=slug, name=name)
    def history(self, project, ref, *, cursor=None, limit=50):
        return self._typed("list_timeline_history", ref, cursor=cursor, limit=limit)
    def diff(self, project, ref, *, from_version=None, to_version=None):
        if from_version is None or to_version is None: return DomainResult.failure(ErrorObject("validation_error", "timeline diff requires from_version and to_version", {}))
        return self._typed("diff_timeline", ref, from_version=from_version, to_version=to_version)
    def _version(self, ref, expected_version):
        if expected_version is not None: return int(expected_version)
        current = self._client.get_timeline(ref)
        return int(current.get("version", 1))
    def archive(self, project, ref, *, expected_version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("archive_timeline", ref, key=key, expected_version=self._version(ref, expected_version), idempotency_key=key)
    def recover(self, project, ref, *, expected_version=None, version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        current_version = self._version(ref, expected_version)
        return self._typed("recover_timeline", ref, key=key, expected_version=current_version, version=int(version) if version is not None else max(1, current_version - 1), idempotency_key=key)


class RemoteMedia(_RemoteFamily):
    @staticmethod
    def _managed_realm_error(realm: str | None, *, idempotency_key: str | None = None) -> DomainResult[Any] | None:
        if realm == "managed_local":
            return None
        return DomainResult.failure(
            ErrorObject(
                "validation_error",
                "only the managed_local media realm is supported",
                {"field": "realm", "value": realm, "valid_options": ["managed_local"]},
            ),
            idempotency_key=idempotency_key or "",
        )

    def import_file(self, *, project: str, path: Path, realm="managed_local", idempotency_key=None):
        realm_error = self._managed_realm_error(realm, idempotency_key=idempotency_key)
        if realm_error is not None:
            return realm_error
        try: data = path.read_bytes()
        except OSError: return DomainResult.failure(ErrorObject("not_found", "media source is unavailable", {}), idempotency_key=idempotency_key or "")
        if project is None: return DomainResult.failure(ErrorObject("validation_error", "media import requires a project", {"field": "project"}), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("ingest_project_object", project, data, key=key, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", idempotency_key=key, filename=path.name)
    def import_directory(self, *, project: str, directory: Path, realm="managed_local", idempotency_key=None):
        realm_error = self._managed_realm_error(realm, idempotency_key=idempotency_key)
        if realm_error is not None:
            return realm_error
        items = []
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            result = self.import_file(project=project, path=path, realm=realm, idempotency_key=f"{idempotency_key or 'import'}-{path.name}")
            if not result.ok: return result
            items.append(result.data)
        return DomainResult.success(items, idempotency_key=idempotency_key or "")
    def list(self, project, *, cursor=None, limit=50):
        return self._typed("list_project_objects", project, cursor=cursor, limit=limit)
    def show(self, project, ref):
        rows = paged_rows(self._client.list_project_objects, str(project), limit=50)
        if rows is None:
            return DomainResult.failure(ErrorObject("not_found", "media object is not in the selected project", {"project": str(project)}))
        if not any(isinstance(item, dict) and str(ref) in {str(item.get("digest")), str(item.get("object_id"))} for item in rows):
            return DomainResult.failure(ErrorObject("not_found", "media object is not in the selected project", {"project": str(project)}))
        return self._typed("get_object", ref)
    def verify(self, project, ref, *, realm="managed_local", idempotency_key=None):
        realm_error = self._managed_realm_error(realm, idempotency_key=idempotency_key)
        if realm_error is not None:
            return realm_error
        scoped = self.show(project, ref)
        if not scoped.ok: return scoped
        result = self._typed("head_object", ref, key=idempotency_key)
        return DomainResult.success({"verified": True, "object_id": str(ref)}, idempotency_key=result.idempotency_key) if result.ok else result
    def relate(self, project, *, from_object_id: str, to_object_id: str, kind: str, metadata=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed(
            "create_media_relation",
            project,
            from_object_id,
            to_object_id,
            kind,
            key=key,
            metadata=metadata,
            idempotency_key=key,
        )

    def list_relations(self, project, *, cursor=None, limit=50):
        return self._typed("list_media_relations", project, cursor=cursor, limit=limit)



class RemoteTasks(_RemoteFamily):
    def register_executor(self, *, executor_id: str, capabilities: list[str], idempotency_key: str):
        return self._typed("register_executor", {"executor_id": executor_id, "capabilities": capabilities}, key=idempotency_key, idempotency_key=idempotency_key)
    def register_capability(self, capability_id: str, definition_digest: str, *, idempotency_key=None):
        return self._typed("register_capability", capability_id, definition_digest, key=idempotency_key, idempotency_key=idempotency_key)
    def create(self, *, project_id: str, capability: str, spec: Mapping[str, Any], input_manifest=None, idempotency_key=None, settlement_effect=None):
        key = idempotency_key or uuid.uuid4().hex
        capabilities = paged_rows(self._client.list_capabilities, limit=50)
        if capabilities is None:
            return DomainResult.failure(
                ErrorObject(
                    "protocol_error",
                    "runtime capability listing returned an invalid page",
                    {},
                ),
                idempotency_key=key,
            )
        match = next((item for item in capabilities if isinstance(item, Mapping) and item.get("capability_id") == capability), None)
        if match is None: return DomainResult.failure(ErrorObject("not_found", "capability is not registered", {"capability_id": capability}), idempotency_key=key)
        return self._typed("admit_task", key=key, capability_id=capability, capability_digest=str(match["definition_digest"]), input_object_ids=input_manifest or [], idempotency_key=key, project_id=project_id, spec=spec, settlement_effect=settlement_effect)
    def claim(self, *, executor_id: str, capability_ids: list[str], idempotency_key: str):
        return self._typed("claim_task", key=idempotency_key, executor_id=executor_id, capability_ids=capability_ids, idempotency_key=idempotency_key)
    def settle(
        self,
        attempt_id: str,
        *,
        lease_id: str,
        fence: int,
        outputs: list[dict],
        idempotency_key: str,
        effect: dict | None = None,
        runtime_epoch: int | None = None,
    ):
        if runtime_epoch is None:
            health = self._client.health()
            runtime_epoch = int(health.get("runtime_epoch", 0)) if isinstance(health, dict) else 0
        settlement = {"lease_id": lease_id, "fence": fence, "outputs": outputs, "runtime_epoch": runtime_epoch}
        if effect is not None:
            settlement["effect"] = effect
        return self._typed("settle_attempt", attempt_id, settlement, key=idempotency_key, idempotency_key=idempotency_key)
    def list(self, project_id, *, cursor=None, limit=50):
        return self._typed("list_project_tasks", project_id, cursor=cursor, limit=limit)
    def show(self, task_id): return self._typed("get_task", task_id)
    def cancel(self, task_id, *, idempotency_key=None): return self._typed("cancel_task", task_id, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def retry(self, task_id, *, idempotency_key=None): return self._typed("retry_task", task_id, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def events(self, task_id, *, cursor=None, limit=50):
        return self._typed(
            "list_events", cursor=cursor, limit=limit, aggregate_id=task_id
        )


class RemoteRuns(_RemoteFamily):
    def list(self, project_id, *, cursor=None, limit=50):
        return self._typed("list_project_runs", project_id, cursor=cursor, limit=limit)
    def show(self, run_id): return self._typed("get_run", run_id)
    def cancel(self, run_id, *, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("cancel_run", run_id, key=key, idempotency_key=key)
    def retry(self, run_id, *, selected_task_ids=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("retry_run", run_id, key=key, idempotency_key=key, selected_task_ids=selected_task_ids)
    def events(self, run_id, *, cursor=None, limit=50):
        return self._typed(
            "list_events", cursor=cursor, limit=limit, aggregate_id=run_id
        )


class RemoteReferences(_RemoteFamily):
    def create(self, *, project: str, reference_id: str | None = None, kind: str = "other", name: str | None = None, media_id: str, description: str = "", metadata: Mapping[str, Any] | None = None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if not project:
            return DomainResult.failure(ErrorObject("validation_error", "reference creation requires a project", {}), idempotency_key=key)
        reference_id = reference_id or str(uuid.uuid5(uuid.NAMESPACE_URL, f"astrid:reference:{key}"))
        body = {"reference_id": reference_id, "kind": kind, "name": name or reference_id, "media_id": media_id, "description": description, "metadata": metadata or {}}
        return self._typed("create_project_reference", project, body, key=key, idempotency_key=key)
    def list(self, project, *, cursor=None, limit=50, include_archived=False):
        return self._typed("list_project_references", project, cursor=cursor, limit=limit, include_archived=include_archived)
    def show(self, project, ref): return self._typed("get_project_reference", project, ref)
    def _version(self, ref, expected_version, project=None):
        if expected_version is not None: return int(expected_version)
        current = self._client.get_project_reference(project, ref)
        return int(current.get("version", 1))
    def update(self, project, ref, *, expected_version=None, name=None, description=None, metadata=None, idempotency_key=None):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "update_reference"}), idempotency_key=idempotency_key or "")
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("update_project_reference", project, ref, key=key, expected_version=version, name=name, description=description, metadata=metadata, idempotency_key=key)
    def archive(self, project, ref, *, expected_version=None, idempotency_key=None):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "archive_reference"}), idempotency_key=idempotency_key or "")
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("archive_project_reference", project, ref, key=key, expected_version=version, idempotency_key=key)
    def recover(self, project, ref, *, expected_version=None, idempotency_key=None):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "recover_reference"}), idempotency_key=idempotency_key or "")
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("recover_project_reference", project, ref, key=key, expected_version=version, idempotency_key=key)
    def associate(self, project, ref, *, media_id: str, role="depicts", association_id=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "associate_reference"}), idempotency_key=key)
        return self._typed("associate_reference", project, ref, {"media_id": media_id, "role": role, **({"association_id": association_id} if association_id else {})}, key=key, idempotency_key=key)
    def link(self, project, from_reference_id, to_reference_id, kind, *, metadata=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "link_references"}), idempotency_key=key)
        return self._typed("link_references", project, {"from_reference_id": from_reference_id, "to_reference_id": to_reference_id, "kind": kind, "metadata": metadata or {}}, key=key, idempotency_key=key)
    def set_primary(self, project, ref, *, association_id=None, expected_version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "set_primary_reference"}), idempotency_key=key)
        if not association_id:
            return DomainResult.failure(ErrorObject("validation_error", "media reference association is required", {}), idempotency_key=key)
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        return self._typed("set_primary_reference", project, ref, association_id, key=key, expected_version=version, idempotency_key=key)


class RemoteShots(_RemoteFamily):
    def list(self, project, *, cursor=None, limit=50, include_archived=False):
        return self._typed("list_project_shots", project, cursor=cursor, limit=limit, include_archived=include_archived)
    def show(self, project, shot_id): return self._typed("get_project_shot", project, shot_id)
    def create(self, *, project: str, shot: Mapping[str, Any] | None = None, name: str = "Shot", metadata: Mapping[str, Any] | None = None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if not project:
            return DomainResult.failure(ErrorObject("validation_error", "shot creation requires a project", {}), idempotency_key=key)
        body = dict(shot or {})
        body.setdefault("shot_id", str(uuid.uuid5(uuid.NAMESPACE_URL, f"astrid:shot:{key}")))
        body.setdefault("name", name)
        if metadata is not None:
            body.setdefault("metadata", dict(metadata))
        return self._typed("create_project_shot", project, body, key=key, idempotency_key=key)
    def _version(self, shot_id, expected_version, project=None):
        if expected_version is not None: return int(expected_version)
        current = self._client.get_project_shot(project, shot_id)
        return int(current.get("version", 1))
    def update(self, project, shot_id, *, expected_version=None, name=None, metadata=None, idempotency_key=None):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "update_shot"}), idempotency_key=idempotency_key or "")
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("update_project_shot", project, shot_id, key=key, expected_version=version, name=name, metadata=metadata, idempotency_key=key)
    def archive(self, project, shot_id, *, expected_version=None, idempotency_key=None):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "archive_shot"}), idempotency_key=idempotency_key or "")
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("archive_project_shot", project, shot_id, key=key, expected_version=version, idempotency_key=key)
    def recover(self, project, shot_id, *, expected_version=None, idempotency_key=None):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "recover_shot"}), idempotency_key=idempotency_key or "")
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("recover_project_shot", project, shot_id, key=key, expected_version=version, idempotency_key=key)

    def add_item(self, project, shot_id, *, media_id, position=None, source_frame=None, metadata=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "add_shot_item"}), idempotency_key=key)
        return self._typed("add_shot_item", project, shot_id, {"media_id": media_id, "position": position, "source_frame": source_frame, "metadata": metadata or {}}, key=key, idempotency_key=key)
    def remove_item(self, project, shot_id, item_id, *, expected_version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "remove_shot_item"}), idempotency_key=key)
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        return self._typed("remove_shot_item", project, shot_id, item_id, key=key, expected_version=version, idempotency_key=key)
    def reorder(self, project, shot_id, item_ids=None, *, expected_version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "reorder_shot_items"}), idempotency_key=key)
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        return self._typed("reorder_shot_items", project, shot_id, list(item_ids or []), key=key, expected_version=version, idempotency_key=key)


class RemoteGenerations(_RemoteFamily):
    def create(self, *, project: str, generation_id: str, metadata=None, type="image", source_task_id=None, idempotency_key=None):
        return self._typed("create_generation", project, generation_id, key=idempotency_key, metadata=metadata or {}, type=type, source_task_id=source_task_id)
    def list(self, project, *, cursor=None, limit=50):
        return self._typed("list_generations", project, cursor=cursor, limit=limit)
    def show(self, project, generation_id): return self._typed("get_generation", generation_id)
    def variants(self, project, generation_id, *, cursor=None, limit=50):
        return self._typed("list_variants", generation_id, cursor=cursor, limit=limit)
    def create_variant(self, generation_id: str, *, variant_id: str, object_id: str | None = None, variant_type="original", metadata=None, idempotency_key=None):
        return self._typed("create_variant", generation_id, variant_id, key=idempotency_key, object_id=object_id, variant_type=variant_type, metadata=metadata or {})


class RemoteAstridClient:
    def __init__(self, transport: WorkspaceClient):
        self._transport = transport
        self.projects, self.timelines, self.media = RemoteProjects(transport), RemoteTimelines(transport), RemoteMedia(transport)
        self.tasks, self.runs, self.references = RemoteTasks(transport), RemoteRuns(transport), RemoteReferences(transport)
        self.shots, self.generations = RemoteShots(transport), RemoteGenerations(transport)
    def health(self): return self._transport.health()
    def handshake(self, client_name: str, client_version: str, requested_scopes: list[str]): return self._transport.handshake(client_name, client_version, requested_scopes)
    def doctor(self): return self._transport.doctor()
    def create_backup(self, destination): return self._transport.create_backup(destination)
    def restore_backup(self, backup, destination): return self._transport.restore_backup(backup, destination)
    def export_realm(self): return self._transport.export_realm()
    def tombstone_realm(self, *, reason=None, expected_version=None): return self._transport.tombstone_realm(reason=reason, expected_version=expected_version)
    def recover_realm(self, *, expected_realm_id, expected_version, confirmation=None, noninteractive=True):
        return self._transport.recover_realm(
            expected_realm_id=expected_realm_id,
            expected_version=expected_version,
            confirmation=confirmation,
            noninteractive=noninteractive,
        )
    def purge_realm(self, confirmation): return self._transport.purge_realm(confirmation)
    def invoke(self, capability_id: str, *, project_id: str, spec: Mapping[str, Any], input_object_ids: list[str] | None = None, idempotency_key: str | None = None, settlement_effect: Mapping[str, Any] | None = None):
        capability_id = str(capability_id); key = idempotency_key or uuid.uuid4().hex
        capabilities = paged_rows(self._transport.list_capabilities, limit=50)
        if capabilities is None:
            return DomainResult.failure(
                ErrorObject(
                    "protocol_error",
                    "runtime capability listing returned an invalid page",
                    {},
                ),
                idempotency_key=key,
            )
        capability = next((item for item in capabilities if isinstance(item, Mapping) and item.get("capability_id") == capability_id), None)
        if capability is None: return DomainResult.failure(ErrorObject("not_found", "capability is not registered", {"capability_id": capability_id}), idempotency_key=key)
        # Keep the generated client's complete mutation result intact.
        # In particular, ``admit_task`` carries the server's committed
        # receipt out-of-band alongside the task resource.
        return self.tasks._typed(
            "admit_task",
            key=key,
            capability_id=capability_id,
            capability_digest=capability["definition_digest"],
            input_object_ids=list(input_object_ids or []),
            idempotency_key=key,
            project_id=project_id,
            spec=spec,
            settlement_effect=settlement_effect,
        )
