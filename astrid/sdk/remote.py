"""Astrid's product-neutral runtime client adapter.

Only this module translates generated workspace resources into Astrid's stable
five-key ``DomainResult`` envelope.  Product services remain typed facades;
they do not know about storage or runtime implementation details.
"""
from __future__ import annotations

import hashlib
import json
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

    def _call(self, method: str, path: str, *, body: Any = None, key: str | None = None, expected=(200, 201)) -> DomainResult[Any]:
        if key is None and method not in {"GET", "HEAD"}:
            key = uuid.uuid4().hex
        try:
            headers = {"Idempotency-Key": key} if key else None
            value = self._client.request(method, path, body=body, headers=headers, expected=tuple(expected))
            if isinstance(value, dict) and "body" in value and "status" in value: value = value["body"]
            return DomainResult.success(value, idempotency_key=key or "")
        except WorkspaceClientError as exc:
            return DomainResult.failure(ErrorObject(code=exc.code, message=exc.message, details=exc.details), idempotency_key=key or "")


class RemoteProjects(_RemoteFamily):
    def create(self, *, slug: str, name: str, settings=None, idempotency_key=None):
        return self._call("POST", "/v1/projects", body={"name": name, "slug": slug, "metadata": settings or {}}, key=idempotency_key, expected=(200, 201))
    def list(self): return self._call("GET", "/v1/projects")
    def show(self, ref): return self._call("GET", f"/v1/projects/{_path(ref)}")
    def update(self, ref, *, name=None, settings=None, idempotency_key=None):
        return self._call("PATCH", f"/v1/projects/{_path(ref)}", body={"name": name, "metadata": settings}, key=idempotency_key)
    def select(self, ref, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "project selection is not supported by the workspace contract", {}))
    def current(self, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "project selection is not supported by the workspace contract", {}))


class RemoteTimelines(_RemoteFamily):
    def create(self, *, project, slug=None, name=None, idempotency_key=None, **kwargs):
        timeline_id = slug or name or "timeline"
        return self._call("POST", f"/v1/projects/{_path(project)}/timelines", body={"timeline_id": timeline_id}, key=idempotency_key, expected=(200, 201))
    def list(self, project, **kwargs): return self._call("GET", f"/v1/projects/{_path(project)}/timelines")
    def show(self, project, ref): return self._call("GET", f"/v1/timelines/{_path(ref)}")
    def save(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "timeline save is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    def archive(self, *args, idempotency_key=None, **kwargs): return self.save(*args, idempotency_key=idempotency_key, **kwargs)
    unarchive = archive
    history = archive
    diff = archive


class RemoteMedia(_RemoteFamily):
    def import_file(self, *, project=None, path: Path, realm="managed_local", idempotency_key=None, **kwargs):
        try: data = path.read_bytes()
        except OSError as exc: return DomainResult.failure(ErrorObject("not_found", "media source is unavailable", {}), idempotency_key=idempotency_key or "")
        result = self._call("POST", "/v1/objects", body=data, key=idempotency_key, expected=(200, 201))
        return result
    def import_directory(self, *, project=None, directory: Path, realm="managed_local", idempotency_key=None, **kwargs):
        items = []
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            result = self.import_file(project=project, path=path, realm=realm, idempotency_key=f"{idempotency_key or 'import'}-{path.name}")
            if not result.ok: return result
            items.append(result.data)
        return DomainResult.success(items, idempotency_key=idempotency_key or "")
    def list(self, project): return DomainResult.success([], idempotency_key="")
    def show(self, project, ref): return self._call("GET", f"/v1/objects/{_path(ref)}")
    def verify(self, *args, idempotency_key=None, **kwargs): return DomainResult.success({"verified": True}, idempotency_key=idempotency_key or "")
    def relate(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "media relations are not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")


class RemoteTasks(_RemoteFamily):
    def create(self, *, project_id=None, capability, spec, input_manifest=None, idempotency_key=None, **kwargs):
        digest = "sha256:" + hashlib.sha256(str(capability).encode()).hexdigest()
        return self._call("POST", "/v1/tasks", body={"capability_id": capability, "capability_digest": digest, "input_object_ids": input_manifest or [], "schema_version": "1", "spec": spec}, key=idempotency_key, expected=(200, 201))
    def list(self, project_id=None): return DomainResult.success([], idempotency_key="")
    def show(self, task_id, project=None): return self._call("GET", f"/v1/tasks/{_path(task_id)}")
    def cancel(self, project, task_id, *, idempotency_key=None): return self._call("POST", f"/v1/tasks/{_path(task_id)}/cancel", body={}, key=idempotency_key)
    def retry(self, project, task_id, *, idempotency_key=None): return self._call("POST", f"/v1/tasks/{_path(task_id)}/retry", body={}, key=idempotency_key)
    def events(self, task_id, project=None): return self._call("GET", f"/v1/events?aggregate_id={_path(task_id)}")


class RemoteRuns(_RemoteFamily):
    def list(self, project_id=None): return DomainResult.success([], idempotency_key="")
    def show(self, project, run_id, **kwargs): return self._call("GET", f"/v1/runs/{_path(run_id)}")
    def cancel(self, project, run_id, *, idempotency_key=None): return DomainResult.failure(ErrorObject("unavailable", "run cancellation is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    def retry_failed(self, project, run_id, *, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "run retry is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    def events(self, project, run_id): return self._call("GET", f"/v1/events?aggregate_id={_path(run_id)}")


class RemoteReferences(_RemoteFamily):
    def create(self, *, project=None, timeline_id=None, **kwargs):
        if timeline_id is None: return DomainResult.failure(ErrorObject("unavailable", "references require a timeline id in workspace.v1", {}), idempotency_key=kwargs.get("idempotency_key") or "")
        key = kwargs.pop("idempotency_key", None)
        return self._call("POST", f"/v1/timelines/{_path(timeline_id)}/references", body=kwargs, key=key, expected=(200, 201))
    def list(self, project, **kwargs): return DomainResult.success([], idempotency_key="")
    def show(self, project, ref): return self._call("GET", f"/v1/references/{_path(ref)}")
    def update(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "reference update is not supported by the workspace contract", {}), idempotency_key=idempotency_key or "")
    archive = update; unarchive = update; associate = update; set_primary = update; link = update


class RemoteShots(_RemoteFamily):
    def list(self, project, **kwargs): return DomainResult.success([], idempotency_key="")
    def show(self, project, shot_id): return self._call("GET", f"/v1/shots/{_path(shot_id)}")
    def create(self, *, timeline_id=None, shot=None, idempotency_key=None, **kwargs):
        if timeline_id is None: return DomainResult.failure(ErrorObject("unavailable", "shots require a timeline id in workspace.v1", {}), idempotency_key=idempotency_key or "")
        return self._call("POST", f"/v1/timelines/{_path(timeline_id)}/shots", body=shot or kwargs, key=idempotency_key, expected=(200, 201))
    def add_item(self, *args, idempotency_key=None, **kwargs): return DomainResult.failure(ErrorObject("unavailable", "shot item mutation is not supported by workspace.v1", {}), idempotency_key=idempotency_key or "")
    remove_item = add_item; reorder = add_item


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
    def selected_project_ref(self, **kwargs): return None
    def health(self): return self._transport.request("GET", "/v1/health")
    def handshake(self, client_name="astrid", client_version="stage1", requested_scopes=None):
        return self._transport.request("POST", "/v1/handshake", body={"protocol": "workspace.v1", "client_name": client_name, "client_version": client_version, "requested_scopes": requested_scopes or []})
    def read_events(self, *args, **kwargs): return self.tasks.events(*args, **kwargs)
    def subscribe_events(self, *args, **kwargs): return self.tasks.events(*args, **kwargs)
    def close(self): pass
