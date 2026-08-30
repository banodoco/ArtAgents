"""Astrid's product-neutral runtime client adapter.

Only this module translates generated workspace resources into Astrid's stable
five-key ``DomainResult`` envelope.  Product services remain typed facades;
they do not know about storage or runtime implementation details.
"""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
import uuid
from urllib.parse import quote
from typing import Any

from .contracts import DomainResult, ErrorObject
from .workspace_client import WorkspaceClient, WorkspaceClientError


def _path(value: Any) -> str:
    return quote(str(value), safe="")


class _RemoteFamily:
    def __init__(self, client: WorkspaceClient): self._client = client

    def _typed(self, operation: str, *args: Any, key: str | None = None, **kwargs: Any) -> DomainResult[Any]:
        if key is None and operation not in {"get_project", "list_projects", "get_timeline", "list_timelines", "get_shot", "get_reference", "get_object", "head_object", "get_task", "get_run", "list_events", "list_run_events", "list_generations", "get_generation", "list_variants"}:
            key = uuid.uuid4().hex
        try:
            return DomainResult.success(getattr(self._client, operation)(*args, **kwargs), idempotency_key=key or "")
        except WorkspaceClientError as exc:
            return DomainResult.failure(ErrorObject(code=exc.code, message=exc.message, details=exc.details), idempotency_key=key or "")

    def _call(self, method: str, path: str, *, body: Any = None, key: str | None = None, expected=(200, 201), headers: dict[str, str] | None = None) -> DomainResult[Any]:
        if key is None and method not in {"GET", "HEAD"}:
            key = uuid.uuid4().hex
        try:
            request_headers = {"Idempotency-Key": key} if key else {}
            request_headers.update(headers or {})
            value = self._client.request(method, path, body=body, headers=request_headers or None, expected=tuple(expected))
            if isinstance(value, dict) and "body" in value and "status" in value: value = value["body"]
            return DomainResult.success(value, idempotency_key=key or "")
        except WorkspaceClientError as exc:
            return DomainResult.failure(ErrorObject(code=exc.code, message=exc.message, details=exc.details), idempotency_key=key or "")


class RemoteProjects(_RemoteFamily):
    def create(self, *, slug: str, name: str, settings=None, idempotency_key=None):
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("create_project", name, key=key, idempotency_key=key)
    def list(self): return self._typed("list_projects")
    def show(self, ref): return self._typed("get_project", ref)
    def update(self, ref, *, name=None, settings=None, idempotency_key=None):
        return self._call("PATCH", f"/v1/projects/{_path(ref)}", body={"name": name, "metadata": settings}, key=idempotency_key)
    def select(self, ref, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "project selection is not supported by the workspace contract", {}))
    def current(self, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "project selection is not supported by the workspace contract", {}))


class RemoteTimelines(_RemoteFamily):
    def create(self, *, project, slug=None, name=None, idempotency_key=None, **kwargs):
        timeline_id = slug or name or "timeline"
        key = idempotency_key or uuid.uuid4().hex
        return self._typed("create_timeline", project, timeline_id, key=key, idempotency_key=key)
    def list(self, project, **kwargs): return self._typed("list_timelines", project)
    def show(self, project, ref): return self._typed("get_timeline", ref)
    def save(self, project, ref, *, expected_version=1, shots=None, references=None, idempotency_key=None, **kwargs):
        return self._typed("update_timeline", ref, key=idempotency_key, expected_version=expected_version, shots=shots, references=references)
    def archive(self, *args, idempotency_key=None, **kwargs): return self.save(*args, idempotency_key=idempotency_key, **kwargs)
    unarchive = archive
    history = archive
    diff = archive


class RemoteMedia(_RemoteFamily):
    def import_file(self, *, project=None, path: Path, realm="managed_local", idempotency_key=None, **kwargs):
        try: data = path.read_bytes()
        except OSError as exc: return DomainResult.failure(ErrorObject("not_found", "media source is unavailable", {}), idempotency_key=idempotency_key or "")
        if project is None:
            return DomainResult.failure(ErrorObject("validation_error", "media import requires a project", {"field": "project"}), idempotency_key=idempotency_key or "")
        # b184's generated client exposes realm-object ingest but not the
        # project-scoped object operation.  Keep this one adapter call on the
        # generated transport until that operation is generated; this route
        # is required for project membership/list/verify semantics.
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        result = self._call(
            "POST",
            f"/v1/projects/{_path(project)}/objects",
            body=data,
            key=idempotency_key,
            expected=(200, 201),
            headers={"Content-Type": media_type, "X-Original-Name": path.name},
        )
        if result.ok and isinstance(result.data, dict):
            result.data.setdefault("object_id", "sha256:" + str(result.data.get("digest", "")))
            if isinstance(result.data.get("digest"), str) and not result.data["digest"].startswith("sha256:"):
                result.data["digest"] = "sha256:" + result.data["digest"]
        return result
    def import_directory(self, *, project=None, directory: Path, realm="managed_local", idempotency_key=None, **kwargs):
        items = []
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            result = self.import_file(project=project, path=path, realm=realm, idempotency_key=f"{idempotency_key or 'import'}-{path.name}")
            if not result.ok: return result
            items.append(result.data)
        return DomainResult.success(items, idempotency_key=idempotency_key or "")
    def list(self, project):
        # The generated object API is realm-scoped; enforce project scope by
        # using the runtime's project object listing when available.
        result = self._call("GET", f"/v1/projects/{_path(project)}/objects")
        if result.ok and isinstance(result.data, list):
            for item in result.data:
                if isinstance(item, dict) and isinstance(item.get("digest"), str) and not item["digest"].startswith("sha256:"):
                    item["digest"] = "sha256:" + item["digest"]
        return result
    def show(self, project, ref):
        listed = self.list(project)
        if not listed.ok:
            return listed
        wanted = str(ref)
        matches = [
            item for item in (listed.data or [])
            if isinstance(item, dict) and wanted in {str(item.get("digest")), str(item.get("object_id"))}
        ]
        if not matches:
            return DomainResult.failure(ErrorObject("not_found", "media object is not in the selected project", {"project": str(project)}))
        return self._typed("get_object", ref)
    def verify(self, project, ref, *, idempotency_key=None, **kwargs):
        del kwargs
        scoped = self.show(project, ref)
        if not scoped.ok:
            return scoped
        result = self._typed("head_object", ref, key=idempotency_key)
        if result.ok:
            result = DomainResult.success({"verified": True, "object_id": str(ref)}, idempotency_key=result.idempotency_key)
        return result
    def relate(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "media relations are not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")


class RemoteTasks(_RemoteFamily):
    def create(self, *, project_id=None, capability, spec, input_manifest=None, idempotency_key=None, **kwargs):
        capabilities = self._client.list_capabilities()
        match = next((item for item in capabilities if item.get("capability_id") == capability), None)
        if match is None:
            return DomainResult.failure(ErrorObject("not_found", "capability is not registered", {"capability_id": capability}), idempotency_key=idempotency_key or "")
        digest = str(match["definition_digest"])
        return self._typed("admit_task", key=idempotency_key, capability_id=capability, capability_digest=digest, input_object_ids=input_manifest or [], idempotency_key=idempotency_key or uuid.uuid4().hex)
    def list(self, project_id=None): return DomainResult.failure(ErrorObject("unavailable", "task listing is not exposed by workspace.v1", {}), idempotency_key="")
    def show(self, task_id, project=None): return self._typed("get_task", task_id)
    def cancel(self, project, task_id, *, idempotency_key=None): return self._typed("cancel_task", task_id, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def retry(self, project, task_id, *, idempotency_key=None): return self._typed("retry_task", task_id, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def events(self, task_id, project=None): return self._typed("list_events", aggregate_id=task_id)


class RemoteRuns(_RemoteFamily):
    def list(self, project_id=None): return DomainResult.failure(ErrorObject("unavailable", "run listing is not exposed by workspace.v1", {}), idempotency_key="")
    def show(self, project, run_id, **kwargs): return self._typed("get_run", run_id)
    def cancel(self, project, run_id, *, idempotency_key=None): return DomainResult.failure(ErrorObject("unavailable", "run cancellation is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    def retry_failed(self, project, run_id, *, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "run retry is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    def events(self, project, run_id): return self._typed("list_run_events", run_id)


class RemoteReferences(_RemoteFamily):
    def create(self, *, project=None, timeline_id=None, **kwargs):
        if timeline_id is None: return DomainResult.failure(ErrorObject("unavailable", "references require a timeline id in workspace.v1", {}), idempotency_key=kwargs.get("idempotency_key") or "")
        key = kwargs.pop("idempotency_key", None)
        return self._typed("create_reference", timeline_id, kwargs, key=key, idempotency_key=key or uuid.uuid4().hex)
    def list(self, project, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "reference listing is not supported by the workspace contract", {}), idempotency_key="")
    def show(self, project, ref): return self._call("GET", f"/v1/references/{_path(ref)}")
    def update(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "reference update is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    archive = update; unarchive = update; associate = update; set_primary = update; link = update


class RemoteShots(_RemoteFamily):
    def list(self, project, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "shot listing is not supported by the workspace contract", {}), idempotency_key="")
    def show(self, project, shot_id): return self._call("GET", f"/v1/shots/{_path(shot_id)}")
    def create(self, *, timeline_id=None, shot=None, idempotency_key=None, **kwargs):
        if timeline_id is None: return DomainResult.failure(ErrorObject("unavailable", "shots require a timeline id in workspace.v1", {}), idempotency_key=idempotency_key or "")
        return self._typed("create_shot", timeline_id, shot or kwargs, key=idempotency_key, idempotency_key=idempotency_key or uuid.uuid4().hex)
    def add_item(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "shot item mutation is not supported by workspace.v1", {}), idempotency_key=idempotency_key or "")
    remove_item = add_item; reorder = add_item


class RemoteGenerations(_RemoteFamily):
    def list(self, project): return self._typed("list_generations", project)
    def show(self, project, generation_id): return self._typed("get_generation", generation_id)
    def variants(self, project, generation_id): return self._typed("list_variants", generation_id)


class RemoteAstridClient:
    def __init__(self, transport: WorkspaceClient):
        self._transport = transport
        self.projects = RemoteProjects(transport)
        self.timelines = RemoteTimelines(transport)
        self.media = RemoteMedia(transport)
        self.tasks = RemoteTasks(transport)
        self.runs = RemoteRuns(transport)
        self.references = RemoteReferences(transport)
        self.shots = RemoteShots(transport)
        self.generations = RemoteGenerations(transport)
    def selected_project_ref(self, **kwargs): return None
    def health(self): return self._transport.request("GET", "/v1/health")
    def handshake(self, client_name="astrid", client_version="stage1", requested_scopes=None):
        return self._transport.request("POST", "/v1/handshake", body={"protocol": "workspace.v1", "client_name": client_name, "client_version": client_version, "requested_scopes": requested_scopes or []})
    def read_events(self, *args, **kwargs): return self.tasks.events(*args, **kwargs)
    def subscribe_events(self, *args, **kwargs): return self.tasks.events(*args, **kwargs)
    def invoke(self, *args, **kwargs):
        capability_id = str(args[0] if args else kwargs.get("capability_id", ""))
        key = kwargs.get("idempotency_key") or uuid.uuid4().hex
        try:
            capabilities = self._transport.list_capabilities()
            capability = next((item for item in capabilities if item.get("capability_id") == capability_id), None)
            if capability is None:
                return DomainResult.failure(ErrorObject("not_found", "capability is not registered", {"capability_id": capability_id}), idempotency_key=key)
            task = self._transport.admit_task(capability_id=capability_id, capability_digest=capability["definition_digest"], input_object_ids=list(kwargs.get("input_object_ids", [])), idempotency_key=key)
            return DomainResult.success(task, idempotency_key=key)
        except WorkspaceClientError as exc:
            return DomainResult.failure(ErrorObject(exc.code, exc.message, exc.details), idempotency_key=key)
    def render(self, *args, **kwargs):
        return self.invoke(*args, **kwargs)
    def close(self): pass
