"""Generated Python client; do not edit by hand.

This source is rendered from the shared component manifest and OpenAPI
operation projection.  Product adapters may use ``call`` for any declared
operation while keeping HTTP ownership in this generated boundary.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping

PROTOCOL = "workspace.v1"
GENERATOR = 'GENERATOR-PYTHON-ASTRID'
COMPONENT_MANIFEST_SHA256 = 'a3cdf22214af24b6a5b9482015bbef90196f969c67e6da3f47547ad1e5cc7ea2'
CONTRACT_SHA256 = 'cacda0808156fd6fbf11617a0c503696dd10c71e0aae12b33b715b56859ad68f'
SCHEMA_MANIFEST_SHA256 = 'b9802ac560fcd33e3c5c3603b2e92c81bd9f05bebef648e837e81508430393f5'
OPERATIONS = ('addShotItem', 'admitTask', 'archiveProjectReference', 'archiveProjectShot', 'archiveReference', 'archiveShot', 'archiveTimeline', 'associateReference', 'cancelRun', 'cancelTask', 'checkpointAttempt', 'claimTask', 'createBackup', 'createDocument', 'createGeneration', 'createMediaRelation', 'createProject', 'createProjectReference', 'createProjectShot', 'createReference', 'createShot', 'createTimeline', 'createVariant', 'diffTimeline', 'doctor', 'exportRealm', 'failAttempt', 'getDocument', 'getGeneration', 'getObject', 'getProject', 'getProjectReference', 'getProjectShot', 'getRealm', 'getReference', 'getRun', 'getShot', 'getTask', 'getTimeline', 'getVariant', 'handshake', 'headObject', 'health', 'heartbeatAttempt', 'ingestObject', 'linkReferences', 'listCapabilities', 'listDocuments', 'listEvents', 'listGenerations', 'listMediaRelations', 'listProjectObjects', 'listProjectReferences', 'listProjectRuns', 'listProjectShots', 'listProjectTasks', 'listProjects', 'listRunEvents', 'listTimelineHistory', 'listTimelines', 'listVariants', 'prepareReboot', 'purgeRealm', 'recoverProjectReference', 'recoverProjectShot', 'recoverRealm', 'recoverReference', 'recoverShot', 'recoverTimeline', 'registerCapability', 'registerExecutor', 'removeShotItem', 'reorderShotItems', 'requestReboot', 'restoreBackup', 'resumeAttempt', 'retryRun', 'retryTask', 'setPrimaryReference', 'settleAttempt', 'tombstoneRealm', 'updateDocument', 'updateProject', 'updateProjectReference', 'updateProjectShot', 'updateReference', 'updateShot', 'updateTimeline')

Transport = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, Mapping[str, str], bytes]]


class ApiError(RuntimeError):
    """A typed HTTP error returned by the neutral runtime."""

    def __init__(self, status: int, code: str, message: str, request_id: str = "", details: Mapping[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.details = dict(details or {})


class WorkspaceClient:
    """Minimal generated transport client for the workspace.v1 operations."""

    def __init__(self, base_url: str, token: str | None = None, *, transport: Transport | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport

    @staticmethod
    def supports(operation_id: str) -> bool:
        return operation_id in OPERATIONS

    def call(self, operation_id: str, method: str, path: str, *, body: bytes | None = None, headers: Mapping[str, str] | None = None, expected: tuple[int, ...] = (200,)) -> tuple[int, Mapping[str, str], bytes]:
        if not self.supports(operation_id):
            raise ValueError(f"unknown workspace operation: {operation_id}")
        request_headers = {"Accept": "application/json", **dict(headers or {})}
        if self.token:
            request_headers.setdefault("Authorization", f"Bearer {self.token}")
        if self.transport is not None:
            status, response_headers, payload = self.transport(method, path, request_headers, body)
        else:
            request = urllib.request.Request(self.base_url + path, data=body, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request) as response:
                    status = response.status
                    response_headers = dict(response.headers.items())
                    payload = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                response_headers = dict(exc.headers.items())
                payload = exc.read()
        if status not in expected:
            try:
                value = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = {}
            raise ApiError(status, str(value.get("code", "http_error")), str(value.get("message", f"HTTP {status}")), str(value.get("request_id", "")), value.get("details", {}))
        return status, response_headers, payload
