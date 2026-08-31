"""Astrid's product-neutral adapter over the generated workspace client."""

from __future__ import annotations

import mimetypes
from pathlib import Path
import uuid
from typing import Any, Mapping

from .contracts import DomainResult, ErrorObject
from .workspace_client import WorkspaceClient, WorkspaceClientError
from astrid.core.receipts.service import CommandReceipt


class _RemoteFamily:
    def __init__(self, client: WorkspaceClient):
        self._client = client

    def _typed(self, operation: str, *args: Any, key: str | None = None, **kwargs: Any) -> DomainResult[Any]:
        reads = {"get_project", "list_projects", "current_project", "get_timeline", "list_timelines", "list_timeline_history", "diff_timeline", "get_shot", "list_project_shots", "get_reference", "list_project_references", "get_object", "head_object", "list_project_objects", "list_media_relations", "get_task", "list_project_tasks", "get_run", "list_project_runs", "list_events", "list_run_events", "list_generations", "get_generation", "list_variants", "get_document", "list_documents"}
        if key is None and operation not in reads:
            key = uuid.uuid4().hex
        try:
            value = getattr(self._client, operation)(*args, **kwargs)
            receipt = None
            if isinstance(value, dict) and set(value) >= {"data", "receipt"}:
                receipt = CommandReceipt.from_dict(value["receipt"]) if value["receipt"] is not None else None
                value = value["data"]
            elif getattr(value, "receipt", None) is not None:
                receipt = CommandReceipt.from_dict(value.receipt)
            return DomainResult.success(value, receipt=receipt, idempotency_key=key or "")
        except WorkspaceClientError as exc:
            return DomainResult.failure(ErrorObject(code=exc.code, message=exc.message, details=exc.details), idempotency_key=key or "")


class RemoteProjects(_RemoteFamily):
    def create(self, *, slug: str, name: str, settings=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("create_project", name, key=key, idempotency_key=key, slug=slug, settings=settings)
    def list(self): return self._typed("list_projects")
    def show(self, ref): return self._typed("get_project", ref)
    def update(self, ref, *, name=None, settings=None, expected_version=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("update_project", ref, key=key, idempotency_key=key, name=name, metadata=settings, expected_version=expected_version)
    def select(self, ref, *, scope="workspace", cwd=None, idempotency_key=None, **kwargs):
        del cwd, kwargs
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("select_project", key=key, project=ref, scope=scope, idempotency_key=key)
    def current(self, *, cwd=None, **kwargs):
        del cwd, kwargs
        return self._typed("current_project")


class RemoteTimelines(_RemoteFamily):
    def create(self, *, project, slug=None, name=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        config = kwargs.pop("config", {"tracks": [], "clips": []})
        registry = kwargs.pop("registry", {"assets": {}})
        timeline_id = kwargs.pop("timeline_id", uuid.uuid4().hex)
        if callable(getattr(self._client, "create_timeline_document", None)):
            return self._typed(
                "create_timeline_document",
                project,
                timeline_id,
                key=key,
                config=config,
                registry=registry,
                slug=slug,
                name=name,
                idempotency_key=key,
            )
        return self._typed("create_timeline", project, timeline_id, key=key, idempotency_key=key)
    def list(self, project, **kwargs):
        result = self._typed("list_timelines", project)
        if result.ok and isinstance(result.data, dict):
            return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def show(self, project, ref):
        result = self._typed("get_timeline", ref)
        if result.ok:
            return result
        listed = self.list(project)
        if listed.ok:
            match = next((row for row in listed.data or [] if isinstance(row, dict) and row.get("slug") == ref), None)
            if match and match.get("timeline_id"):
                return self._typed("get_timeline", str(match["timeline_id"]))
        return result
    def save(self, project, ref, *, expected_version=1, shots=None, references=None, idempotency_key=None, **kwargs):
        config = kwargs.pop("config", None)
        registry = kwargs.pop("registry", None)
        del shots, references
        key = idempotency_key or uuid.uuid4().hex
        if not project:
            return DomainResult.failure(
                ErrorObject("validation_error", "timeline save requires a project", {"field": "project"}),
                idempotency_key=key,
            )
        if config is None and registry is None:
            return DomainResult.failure(
                ErrorObject(
                    "unsupported_operation",
                    "timeline save requires project-scoped config and registry",
                    {"operation": "timelines.save", "legacy_route": "update_timeline"},
                ),
                idempotency_key=key,
            )
        current = self._client.get_document(project, f"timeline:{ref}")
        content = dict(current.content) if hasattr(current, "content") and isinstance(current.content, dict) else {}
        return self._typed("update_timeline_document", project, ref, expected_version=expected_version, config=config or content.get("config", {}), registry=registry or content.get("registry", {}), slug=kwargs.pop("slug", None), name=kwargs.pop("name", None))
    def history(self, project, ref, *, cursor=None, limit=50, **kwargs):
        result = self._typed("list_timeline_history", ref, cursor=cursor, limit=limit)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def diff(self, project, ref, *, from_version=None, to_version=None, **kwargs):
        if from_version is None or to_version is None: return DomainResult.failure(ErrorObject("validation_error", "timeline diff requires from_version and to_version", {}))
        return self._typed("diff_timeline", ref, from_version=from_version, to_version=to_version)
    def _version(self, ref, expected_version):
        if expected_version is not None: return int(expected_version)
        current = self._client.get_timeline(ref)
        return int(current.get("version", 1) if isinstance(current, dict) else getattr(current, "version", 1))
    def archive(self, project, ref, *, expected_version=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("archive_timeline", ref, key=key, expected_version=self._version(ref, expected_version), idempotency_key=key)
    def unarchive(self, project, ref, *, expected_version=None, version=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        current_version = self._version(ref, expected_version)
        return self._typed("recover_timeline", ref, key=key, expected_version=current_version, version=int(version) if version is not None else max(1, current_version - 1), idempotency_key=key)
    recover = unarchive


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

    def import_file(self, *, project=None, path: Path, realm="managed_local", idempotency_key=None, **kwargs):
        if kwargs.get("reference_in_place") or kwargs.get("locator") is not None:
            return DomainResult.failure(
                ErrorObject("validation_error", "reference-in-place media is not supported", {"field": "reference_in_place"}),
                idempotency_key=idempotency_key or "",
            )
        realm_error = self._managed_realm_error(realm, idempotency_key=idempotency_key)
        if realm_error is not None:
            return realm_error
        try: data = path.read_bytes()
        except OSError: return DomainResult.failure(ErrorObject("not_found", "media source is unavailable", {}), idempotency_key=idempotency_key or "")
        if project is None: return DomainResult.failure(ErrorObject("validation_error", "media import requires a project", {"field": "project"}), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("ingest_project_object", project, data, key=key, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", idempotency_key=key, filename=path.name)
    def import_directory(self, *, project=None, directory: Path, realm="managed_local", idempotency_key=None, **kwargs):
        if kwargs.get("reference_in_place") or kwargs.get("locator") is not None:
            return DomainResult.failure(
                ErrorObject("validation_error", "reference-in-place media is not supported", {"field": "reference_in_place"}),
                idempotency_key=idempotency_key or "",
            )
        realm_error = self._managed_realm_error(realm, idempotency_key=idempotency_key)
        if realm_error is not None:
            return realm_error
        items = []
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            result = self.import_file(project=project, path=path, realm=realm, idempotency_key=f"{idempotency_key or 'import'}-{path.name}")
            if not result.ok: return result
            items.append(result.data)
        return DomainResult.success(items, idempotency_key=idempotency_key or "")
    def list(self, project):
        result = self._typed("list_project_objects", project)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def show(self, project, ref):
        listed = self.list(project)
        if not listed.ok: return listed
        if not any(isinstance(item, dict) and str(ref) in {str(item.get("digest")), str(item.get("object_id"))} for item in (listed.data or [])):
            return DomainResult.failure(ErrorObject("not_found", "media object is not in the selected project", {"project": str(project)}))
        return self._typed("get_object", ref)
    def verify(self, project, ref, *, realm="managed_local", idempotency_key=None, **kwargs):
        realm_error = self._managed_realm_error(realm, idempotency_key=idempotency_key)
        if realm_error is not None:
            return realm_error
        if kwargs.get("reference_in_place") or kwargs.get("locator") is not None:
            return DomainResult.failure(
                ErrorObject("validation_error", "reference-in-place media is not supported", {"field": "reference_in_place"}),
                idempotency_key=idempotency_key or "",
            )
        scoped = self.show(project, ref)
        if not scoped.ok: return scoped
        result = self._typed("head_object", ref, key=idempotency_key)
        return DomainResult.success({"verified": True, "object_id": str(ref)}, idempotency_key=result.idempotency_key) if result.ok else result
    def relate(self, project, *, from_object_id=None, to_object_id=None, kind=None, metadata=None, relations=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if relations is not None:
            created = []
            for relation in relations:
                source = relation.get("from_object_id", relation.get("from_media_id"))
                target = relation.get("to_object_id", relation.get("to_media_id"))
                result = self._typed("create_media_relation", project, source, target, relation["kind"], key=key, metadata=relation.get("metadata"), idempotency_key=key)
                if not result.ok: return result
                created.append(result.data)
            return DomainResult.success(created, idempotency_key=key)
        if kind is None:
            return DomainResult.failure(ErrorObject("validation_error", "media relation kind is required", {}), idempotency_key=key)
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

    def list_relations(self, project, *, cursor=None, limit=50, **kwargs):
        result = self._typed("list_media_relations", project, cursor=cursor, limit=limit)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result

    relations = list_relations


class RemoteTasks(_RemoteFamily):
    def register_executor(self, *, executor_id: str, capabilities: list[str], idempotency_key: str, **kwargs):
        return self._typed("register_executor", {"executor_id": executor_id, "capabilities": capabilities, **kwargs}, key=idempotency_key, idempotency_key=idempotency_key)
    def register_capability(self, capability_id: str, definition_digest: str, *, idempotency_key=None, **kwargs):
        return self._typed("register_capability", capability_id, definition_digest, key=idempotency_key, idempotency_key=idempotency_key, **kwargs)
    def create(self, *, project_id=None, capability, spec, input_manifest=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if project_id is None:
            project_id = kwargs.pop("project", None)
        try:
            match = next((item for item in self._client.list_capabilities() if item.get("capability_id") == capability), None)
            if project_id is not None and callable(getattr(self._client, "get_project", None)):
                project = self._client.get_project(project_id)
                if isinstance(project, Mapping):
                    project_id = project.get("project_id") or project.get("id") or project_id
                else:
                    project_id = getattr(project, "project_id", None) or getattr(project, "id", None) or project_id
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        if match is None: return DomainResult.failure(ErrorObject("not_found", "capability is not registered", {"capability_id": capability}), idempotency_key=key)
        return self._typed("admit_task", key=key, capability_id=capability, capability_digest=str(match["definition_digest"]), input_object_ids=input_manifest or [], idempotency_key=key, project_id=project_id, spec=spec)
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
    def list(self, project_id, *, cursor=None, limit=50, **kwargs):
        result = self._typed("list_project_tasks", project_id, cursor=cursor, limit=limit)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def show(self, task_id, project=None): return self._typed("get_task", task_id)
    def cancel(self, project, task_id, *, idempotency_key=None): return self._typed("cancel_task", task_id, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def retry(self, project, task_id, *, idempotency_key=None): return self._typed("retry_task", task_id, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def events(self, task_id, project=None): return self._typed("list_events", aggregate_id=task_id)


class RemoteRuns(_RemoteFamily):
    def list(self, project_id, *, cursor=None, limit=50, **kwargs):
        result = self._typed("list_project_runs", project_id, cursor=cursor, limit=limit)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def show(self, project, run_id, **kwargs): return self._typed("get_run", run_id)
    def cancel(self, project, run_id, *, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("cancel_run", run_id, key=key, idempotency_key=key)
    def retry_failed(self, project, run_id, *, selected_task_ids=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("retry_run", run_id, key=key, idempotency_key=key, selected_task_ids=selected_task_ids)
    def events(self, project, run_id): return self._typed("list_run_events", run_id)


class RemoteReferences(_RemoteFamily):
    def create(self, *, project=None, timeline_id=None, **kwargs):
        key = kwargs.pop("idempotency_key", None) or uuid.uuid4().hex
        if timeline_id is not None:
            return DomainResult.failure(
                ErrorObject("unsupported_operation", "timeline-scoped references are retired", {"operation": "create_reference"}),
                idempotency_key=key,
            )
        if not project:
            return DomainResult.failure(ErrorObject("validation_error", "reference creation requires a project", {}), idempotency_key=key)
        reference_id = str(kwargs.pop("reference_id", None) or uuid.uuid5(uuid.NAMESPACE_URL, f"astrid:reference:{key}"))
        object_id = kwargs.pop("object_id", None) or kwargs.pop("media_id", None)
        if not object_id:
            return DomainResult.failure(ErrorObject("validation_error", "reference creation requires media_id or object_id", {}), idempotency_key=key)
        body = {"reference_id": reference_id, "kind": kwargs.pop("kind", "other"), "name": kwargs.pop("name", reference_id), "media_id": object_id, "description": kwargs.pop("description", ""), "metadata": kwargs.pop("metadata", {})}
        return self._typed("create_project_reference", project, body, key=key, idempotency_key=key)
    def list(self, project, *, cursor=None, limit=50, include_archived=False, **kwargs):
        result = self._typed("list_project_references", project, cursor=cursor, limit=limit, include_archived=include_archived)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def show(self, project, ref): return self._typed("get_project_reference", project, ref)
    def _version(self, ref, expected_version, project=None):
        if expected_version is not None: return int(expected_version)
        current = self._client.get_project_reference(project, ref)
        return int(current.get("version", 1))
    def update(self, project, ref, *, expected_version=None, object_id=None, role=None, idempotency_key=None, **kwargs):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "update_reference"}), idempotency_key=idempotency_key or "")
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("update_project_reference", project, ref, key=key, expected_version=version, name=kwargs.get("name"), description=kwargs.get("description"), metadata=kwargs.get("metadata"), idempotency_key=key)
    def archive(self, project, ref, *, expected_version=None, idempotency_key=None, **kwargs):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "archive_reference"}), idempotency_key=idempotency_key or "")
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("archive_project_reference", project, ref, key=key, expected_version=version, idempotency_key=key)
    def unarchive(self, project, ref, *, expected_version=None, idempotency_key=None, **kwargs):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "recover_reference"}), idempotency_key=idempotency_key or "")
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("recover_project_reference", project, ref, key=key, expected_version=version, idempotency_key=key)
    def associate(self, project, ref, *, media_id=None, role="depicts", idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "associate_reference"}), idempotency_key=key)
        return self._typed("associate_reference", project, ref, {"media_id": media_id, "role": role, **({"association_id": kwargs["association_id"]} if kwargs.get("association_id") else {})}, key=key, idempotency_key=key)
    def link(self, project, from_reference_id, to_reference_id, kind, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "link_references"}), idempotency_key=key)
        return self._typed("link_references", project, {"from_reference_id": from_reference_id, "to_reference_id": to_reference_id, "kind": kind, "metadata": kwargs.get("metadata", {})}, key=key, idempotency_key=key)
    def set_primary(self, project, ref, *, association_id=None, media_reference_id=None, expected_version=None, idempotency_key=None, **kwargs):
        association_id = association_id or media_reference_id
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped references are required", {"operation": "set_primary_reference"}), idempotency_key=key)
        if not association_id:
            return DomainResult.failure(ErrorObject("validation_error", "media reference association is required", {}), idempotency_key=key)
        try: version = self._version(ref, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        return self._typed("set_primary_reference", project, ref, association_id, key=key, expected_version=version, idempotency_key=key)


class RemoteShots(_RemoteFamily):
    def list(self, project, *, cursor=None, limit=50, include_archived=False, **kwargs):
        result = self._typed("list_project_shots", project, cursor=cursor, limit=limit, include_archived=include_archived)
        if result.ok and isinstance(result.data, dict): return DomainResult.success(result.data.get("items", []), idempotency_key=result.idempotency_key)
        return result
    def show(self, project, shot_id): return self._typed("get_project_shot", project, shot_id)
    def create(self, *, timeline_id=None, shot=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if timeline_id is not None:
            return DomainResult.failure(
                ErrorObject("unsupported_operation", "timeline-scoped shots are retired", {"operation": "create_shot"}),
                idempotency_key=key,
            )
        project = kwargs.pop("project", None)
        if not project:
            return DomainResult.failure(ErrorObject("validation_error", "shot creation requires a project", {}), idempotency_key=key)
        body = dict(shot or {})
        body.update(kwargs)
        body.setdefault("name", body.pop("name", "Shot"))
        body.pop("start_ms", None); body.pop("duration_ms", None); body.pop("reference_ids", None)
        body.setdefault("shot_id", str(uuid.uuid5(uuid.NAMESPACE_URL, f"astrid:shot:{key}")))
        return self._typed("create_project_shot", project, body, key=key, idempotency_key=key)
    def _version(self, shot_id, expected_version, project=None):
        if expected_version is not None: return int(expected_version)
        current = self._client.get_project_shot(project, shot_id)
        return int(current.get("version", 1))
    def update(self, project, shot_id, *, expected_version=None, start_ms=None, duration_ms=None, reference_ids=None, idempotency_key=None, **kwargs):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "update_shot"}), idempotency_key=idempotency_key or "")
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("update_project_shot", project, shot_id, key=key, expected_version=version, name=kwargs.get("name"), metadata=kwargs.get("metadata"), idempotency_key=key)
    def archive(self, project, shot_id, *, expected_version=None, idempotency_key=None, **kwargs):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "archive_shot"}), idempotency_key=idempotency_key or "")
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("archive_project_shot", project, shot_id, key=key, expected_version=version, idempotency_key=key)
    def recover(self, project, shot_id, *, expected_version=None, idempotency_key=None, **kwargs):
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "recover_shot"}), idempotency_key=idempotency_key or "")
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=idempotency_key or "")
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("recover_project_shot", project, shot_id, key=key, expected_version=version, idempotency_key=key)

    unarchive = recover
    def add_item(self, project, shot_id, *, media_id, position=None, source_frame=None, metadata=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "add_shot_item"}), idempotency_key=key)
        return self._typed("add_shot_item", project, shot_id, {"media_id": media_id, "position": position, "source_frame": source_frame, "metadata": metadata or {}}, key=key, idempotency_key=key)
    def remove_item(self, project, shot_id, item_id, *, expected_version=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "remove_shot_item"}), idempotency_key=key)
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        return self._typed("remove_shot_item", project, shot_id, item_id, key=key, expected_version=version, idempotency_key=key)
    def reorder(self, project, shot_id, item_ids=None, *, expected_version=None, idempotency_key=None, **kwargs):
        key = idempotency_key or uuid.uuid4().hex
        if project is None:
            return DomainResult.failure(ErrorObject("unsupported_operation", "project-scoped shots are required", {"operation": "reorder_shot_items"}), idempotency_key=key)
        try: version = self._version(shot_id, expected_version, project)
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
        return self._typed("reorder_shot_items", project, shot_id, list(item_ids or []), key=key, expected_version=version, idempotency_key=key)


class RemoteGenerations(_RemoteFamily):
    def create(self, *, project: str, generation_id: str, metadata=None, type="image", source_task_id=None, idempotency_key=None):
        return self._typed("create_generation", project, generation_id, key=idempotency_key, metadata=metadata or {}, type=type, source_task_id=source_task_id)
    def list(self, project): return self._typed("list_generations", project)
    def show(self, project, generation_id): return self._typed("get_generation", generation_id)
    def variants(self, project, generation_id): return self._typed("list_variants", generation_id)
    def create_variant(self, generation_id: str, *, variant_id: str, object_id: str | None = None, variant_type="original", metadata=None, idempotency_key=None):
        return self._typed("create_variant", generation_id, variant_id, key=idempotency_key, object_id=object_id, variant_type=variant_type, metadata=metadata or {})


class RemoteAstridClient:
    def __init__(self, transport: WorkspaceClient):
        self._transport = transport
        self.projects, self.timelines, self.media = RemoteProjects(transport), RemoteTimelines(transport), RemoteMedia(transport)
        self.tasks, self.runs, self.references = RemoteTasks(transport), RemoteRuns(transport), RemoteReferences(transport)
        self.shots, self.generations = RemoteShots(transport), RemoteGenerations(transport)
    def selected_project_ref(self, **kwargs):
        """Resolve the actor-scoped selection stored by the neutral runtime."""
        del kwargs
        try:
            result = self.projects.current()
            if not result.ok or not isinstance(result.data, dict):
                return None
            row = result.data.get("project")
            if not isinstance(row, dict):
                row = vars(row) if hasattr(row, "__dict__") else {}
            return str(row.get("project_id") or row.get("id") or row.get("slug") or "") or None
        except Exception:
            return None
    def health(self): return self._transport.health()
    def handshake(self, client_name="astrid", client_version="stage1", requested_scopes=None): return self._transport.handshake(client_name, client_version, requested_scopes or [])
    def doctor(self): return self._transport.doctor()
    def create_backup(self, destination): return self._transport.create_backup(destination)
    def restore_backup(self, backup, destination): return self._transport.restore_backup(backup, destination)
    def export_realm(self): return self._transport.export_realm()
    def tombstone_realm(self, *, reason=None, expected_version=None): return self._transport.tombstone_realm(reason=reason, expected_version=expected_version)
    def recover_realm(self, *, expected_realm_id=None, expected_version=None, confirmation=None, noninteractive=True):
        return self._transport.recover_realm(
            expected_realm_id=expected_realm_id,
            expected_version=expected_version,
            confirmation=confirmation,
            noninteractive=noninteractive,
        )
    def purge_realm(self, confirmation): return self._transport.purge_realm(confirmation)
    def read_events(self, *args, **kwargs): return self.tasks.events(*args, **kwargs)
    def subscribe_events(self, *args, **kwargs): return self.tasks.events(*args, **kwargs)
    def invoke(self, *args, **kwargs):
        capability_id = str(args[0] if args else kwargs.get("capability_id", "")); key = kwargs.get("idempotency_key") or uuid.uuid4().hex
        try:
            capability = next((item for item in self._transport.list_capabilities() if item.get("capability_id") == capability_id), None)
            if capability is None: return DomainResult.failure(ErrorObject("not_found", "capability is not registered", {"capability_id": capability_id}), idempotency_key=key)
            # Keep the generated client's complete mutation result intact.
            # In particular, ``admit_task`` carries the server's committed
            # receipt out-of-band alongside the task resource.
            return self.tasks._typed(
                "admit_task",
                key=key,
                capability_id=capability_id,
                capability_digest=capability["definition_digest"],
                input_object_ids=list(kwargs.get("input_object_ids", [])),
                idempotency_key=key,
                project_id=kwargs.get("project_id"),
                spec=kwargs.get("spec"),
            )
        except WorkspaceClientError as exc: return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
    def render(self, *args, **kwargs): return self.invoke(*args, **kwargs)
    def close(self): pass
