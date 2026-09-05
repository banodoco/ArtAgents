"""Generated from contract/openapi/workspace-v1.yaml; do not edit by hand."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

PROTOCOL = "workspace.v1"
SCHEMA_DIGEST = "sha256:4be7e530215b56e2a2936dbea4bfc5b26625e91a2c8c45493e4de59ea7813702"
OPERATIONS = ('health', 'handshake', 'getRealm', 'doctor', 'createBackup', 'restoreBackup', 'exportRealm', 'tombstoneRealm', 'recoverRealm', 'purgeRealm', 'listProjects', 'createProject', 'getProject', 'updateProject', 'currentProject', 'selectProject', 'listDocuments', 'createDocument', 'getDocument', 'updateDocument', 'listProjectObjects', 'ingestProjectObject', 'listProjectTasks', 'listProjectRuns', 'createTimeline', 'listTimelines', 'createTimelineDocument', 'getTimeline', 'updateTimeline', 'listTimelineHistory', 'diffTimeline', 'archiveTimeline', 'recoverTimeline', 'createShot', 'getShot', 'updateShot', 'archiveShot', 'recoverShot', 'createReference', 'createProjectShot', 'listProjectShots', 'getProjectShot', 'updateProjectShot', 'archiveProjectShot', 'recoverProjectShot', 'addShotItem', 'removeShotItem', 'promoteProjectShotCandidate', 'reorderShotItems', 'listProjectShotTextBindings', 'setProjectShotTextBinding', 'getProjectShotTextBinding', 'setProjectShotTextBindingById', 'rebindProjectShotTextBinding', 'createProjectReference', 'listProjectReferences', 'getProjectReference', 'updateProjectReference', 'archiveProjectReference', 'recoverProjectReference', 'associateReference', 'setPrimaryReference', 'linkReferences', 'getReference', 'updateReference', 'archiveReference', 'recoverReference', 'listMediaRelations', 'createMediaRelation', 'ingestObject', 'getObject', 'headObject', 'admitTask', 'claimTask', 'getTask', 'cancelTask', 'retryTask', 'getRun', 'cancelRun', 'retryRun', 'listRunEvents', 'listEvents', 'registerExecutor', 'listCapabilities', 'registerCapability', 'listGenerations', 'createGeneration', 'getGeneration', 'listVariants', 'createVariant', 'getVariant', 'settleAttempt', 'prepareReboot', 'checkpointAttempt', 'failAttempt', 'heartbeatAttempt', 'requestReboot', 'resumeAttempt')


@dataclass(frozen=True)
class Health:
    status: str
    protocol: str
    schema_digest: str
    runtime_epoch: int

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Health":
        return cls(status=value["status"], protocol=value["protocol"], schema_digest=value["schema_digest"], runtime_epoch=int(value.get("runtime_epoch", 0)))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class IntegrityCheck:
    ok: bool
    values: Mapping[str, Any]

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "IntegrityCheck":
        return cls(ok=bool(value.get("ok", False)), values=dict(value))

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


@dataclass(frozen=True)
class IntegrityReport:
    state: str
    ok: bool
    schema_version: int
    recovery_action: str
    checks: Mapping[str, IntegrityCheck]
    issues: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "IntegrityReport":
        checks = {str(key): IntegrityCheck.from_json(item) for key, item in value.get("checks", {}).items() if isinstance(item, Mapping)}
        return cls(state=str(value.get("state", "unhealthy")), ok=bool(value.get("ok", False)), schema_version=int(value.get("schema_version", 0)), recovery_action=str(value.get("recovery_action", "")), checks=checks, issues=tuple(value.get("issues", [])))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class RealmLifecycle:
    realm_id: str
    state: str
    version: int
    tombstoned_at: str | None = None
    reason: str | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "RealmLifecycle":
        return cls(realm_id=str(value["realm_id"]), state=str(value["state"]), version=int(value["version"]), tombstoned_at=value.get("tombstoned_at"), reason=value.get("reason"))


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, request_id: str = "", details: Mapping[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.status, self.code, self.message = status, code, message
        self.request_id, self.details = request_id, dict(details or {})


@dataclass(frozen=True)
class Handshake:
    protocol: str
    schema_digest: str
    session_id: str
    actor_id: str
    realm_id: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class Realm:
    realm_id: str
    display_name: str
    version: int
    created_at: str

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Realm":
        return cls(realm_id=value["realm_id"], display_name=value["display_name"], version=int(value["version"]), created_at=value["created_at"])


@dataclass(frozen=True)
class Project:
    project_id: str
    realm_id: str
    slug: str
    name: str
    metadata: Mapping[str, Any]
    version: int
    created_at: str
    updated_at: str
    archived: bool = False

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Project":
        return cls(project_id=value["project_id"], realm_id=value["realm_id"], slug=value.get("slug", value["project_id"]), name=value["name"], metadata=value.get("metadata", {}), version=int(value["version"]), created_at=value["created_at"], updated_at=value["updated_at"], archived=bool(value.get("archived", False)))


@dataclass(frozen=True)
class ProjectDocument:
    document_id: str
    project_id: str
    kind: str
    content: Any
    version: int
    created_at: str
    updated_at: str

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ProjectDocument":
        return cls(document_id=value["document_id"], project_id=value["project_id"], kind=value["kind"], content=value.get("content"), version=int(value["version"]), created_at=value["created_at"], updated_at=value["updated_at"])


@dataclass(frozen=True)
class Generation:
    generation_id: str
    project_id: str
    type: str
    status: str
    metadata: Mapping[str, Any]
    version: int
    created_at: str
    updated_at: str

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Generation":
        return cls(generation_id=value["generation_id"], project_id=value["project_id"], type=value["type"], status=value["status"], metadata=value.get("metadata", {}), version=int(value["version"]), created_at=value["created_at"], updated_at=value["updated_at"])


@dataclass(frozen=True)
class GenerationVariant:
    variant_id: str
    generation_id: str
    variant_type: str
    metadata: Mapping[str, Any]
    created_at: str
    object_id: str | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "GenerationVariant":
        return cls(variant_id=value["variant_id"], generation_id=value["generation_id"], variant_type=value["variant_type"], metadata=value.get("metadata", {}), created_at=value["created_at"], object_id=value.get("object_id"))


@dataclass(frozen=True)
class ManagedObject:
    object_id: str
    digest: str
    media_type: str
    size: int
    version: int
    created_at: str
    filename: str | None = None
    relation: str | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ManagedObject":
        return cls(object_id=value["object_id"], digest=value["digest"], media_type=value["media_type"], size=int(value["size"]), version=int(value["version"]), created_at=value["created_at"], filename=value.get("filename"), relation=value.get("relation"))


@dataclass(frozen=True)
class ShotTextBinding:
    binding_id: str
    project_id: str
    shot_id: str
    kind: str
    media_id: str
    event_stream_id: str
    head: int
    content_hash: str
    mime_type: str
    byte_size: int
    slot: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ShotTextBinding":
        return cls(binding_id=value["binding_id"], project_id=value["project_id"], shot_id=value["shot_id"], kind=value["kind"], media_id=value["media_id"], event_stream_id=value["event_stream_id"], head=int(value["head"]), content_hash=value["content_hash"], mime_type=value["mime_type"], byte_size=int(value["byte_size"]), slot=value.get("slot"), created_at=value.get("created_at", ""), updated_at=value.get("updated_at", ""))


@dataclass(frozen=True)
class ByteResponse:
    data: bytes
    status: int
    headers: Mapping[str, str]

    @property
    def etag(self) -> str | None:
        return self.headers.get("ETag") or self.headers.get("etag")

    @property
    def content_range(self) -> str | None:
        return self.headers.get("Content-Range") or self.headers.get("content-range")


@dataclass(frozen=True)
class Task:
    task_id: str
    run_id: str
    state: str
    version: int
    capability_id: str
    capability_digest: str
    idempotency_key: str
    created_at: str
    updated_at: str
    runtime_epoch: int
    input_object_ids: list[str]
    spec: Mapping[str, Any]
    project_id: str | None = None
    attempt_id: str | None = None
    result: Mapping[str, Any] | None = None
    storage_estimate: Mapping[str, int] | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Task":
        return cls(task_id=value["task_id"], run_id=value["run_id"], state=value["state"], version=int(value["version"]), capability_id=value["capability_id"], capability_digest=value["capability_digest"], idempotency_key=value["idempotency_key"], created_at=value["created_at"], updated_at=value["updated_at"], input_object_ids=list(value.get("input_object_ids") or []), spec=dict(value.get("spec") or {}), project_id=value.get("project_id"), attempt_id=value.get("attempt_id"), runtime_epoch=int(value["runtime_epoch"]), result=value.get("result"), storage_estimate=dict(value["storage_estimate"]) if value.get("storage_estimate") is not None else None)


@dataclass(frozen=True)
class AttemptFence:
    attempt_id: str
    task_id: str
    lease_id: str
    fence: int
    lease_expires_at: str
    runtime_epoch: int
    input_object_ids: list[str]
    spec: Mapping[str, Any]
    project_id: str | None = None
    storage_estimate: Mapping[str, int] | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "AttemptFence":
        return cls(attempt_id=value["attempt_id"], task_id=value["task_id"], lease_id=value["lease_id"], fence=int(value["fence"]), lease_expires_at=value["lease_expires_at"], runtime_epoch=int(value["runtime_epoch"]), input_object_ids=list(value.get("input_object_ids") or []), spec=dict(value.get("spec") or {}), project_id=value.get("project_id"), storage_estimate=dict(value["storage_estimate"]) if value.get("storage_estimate") is not None else None)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class ClaimWaiting:
    task: Task
    waiting_reason: str

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ClaimWaiting":
        return cls(task=Task.from_json(value["task"]), waiting_reason=str(value["waiting_reason"]))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class RecoveryAuthorization:
    attempt_id: str
    task_id: str
    executor_id: str
    runtime_epoch: int
    nonce: str
    expires_in_seconds: int

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "RecoveryAuthorization":
        return cls(attempt_id=value["attempt_id"], task_id=value["task_id"], executor_id=value["executor_id"], runtime_epoch=int(value["runtime_epoch"]), nonce=value["nonce"], expires_in_seconds=int(value["expires_in_seconds"]))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class RecoveryCheckpointReceipt:
    checkpoint_id: str
    attempt_id: str
    task_id: str
    runtime_epoch: int
    nonce: str
    digest: str
    size: int
    state: str
    path: str | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "RecoveryCheckpointReceipt":
        return cls(checkpoint_id=value["checkpoint_id"], attempt_id=value["attempt_id"], task_id=value["task_id"], runtime_epoch=int(value["runtime_epoch"]), nonce=value["nonce"], digest=value["digest"], size=int(value["size"]), state=value["state"], path=value.get("path"))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class RecoveryReceipt:
    type: str
    checkpoint_id: str
    attempt_id: str
    task_id: str
    runtime_epoch: int
    command: str
    status: str
    version: int | None = None
    checkpoint_digest: str | None = None
    executor_result: Any = None
    checkpoint: Any = None
    error: Mapping[str, Any] | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "RecoveryReceipt":
        return cls(type=value["type"], checkpoint_id=value["checkpoint_id"], attempt_id=value["attempt_id"], task_id=value["task_id"], runtime_epoch=int(value["runtime_epoch"]), command=value["command"], status=value["status"], version=int(value["version"]) if value.get("version") is not None else None, checkpoint_digest=value.get("checkpoint_digest"), executor_result=value.get("executor_result"), checkpoint=value.get("checkpoint"), error=value.get("error"))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class RecoveryResumeReceipt:
    receipt: RecoveryReceipt
    attempt: AttemptFence

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "RecoveryResumeReceipt":
        return cls(receipt=RecoveryReceipt.from_json(value["receipt"]), attempt=AttemptFence.from_json(value["attempt"]))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class Event:
    event_id: str
    sequence: int
    cursor: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: Mapping[str, Any]
    occurred_at: str

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Event":
        return cls(event_id=value["event_id"], sequence=int(value["sequence"]), cursor=value["cursor"], event_type=value["event_type"], aggregate_type=value["aggregate_type"], aggregate_id=value["aggregate_id"], payload=value.get("payload", {}), occurred_at=value["occurred_at"])


@dataclass(frozen=True)
class Capability:
    capability_id: str
    definition_digest: str
    status: str
    required_resource_keys: tuple[str, ...]
    estimated_scratch_bytes: int
    estimated_output_bytes: int
    unavailable_reason: str | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Capability":
        return cls(capability_id=value["capability_id"], definition_digest=value["definition_digest"], status=value["status"], required_resource_keys=tuple(value.get("required_resource_keys", [])), estimated_scratch_bytes=int(value.get("estimated_scratch_bytes", 0)), estimated_output_bytes=int(value.get("estimated_output_bytes", 0)), unavailable_reason=value.get("unavailable_reason"))


@dataclass(frozen=True)
class Executor:
    executor_id: str
    max_concurrency: int
    resource_keys: tuple[str, ...]
    capabilities: tuple[Capability, ...]
    protocol: str
    runtime_epoch: int | None = None
    source_digest: str | None = None
    dependency_digest: str | None = None
    source_epoch: str | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "Executor":
        return cls(executor_id=value["executor_id"], max_concurrency=int(value["max_concurrency"]), resource_keys=tuple(value.get("resource_keys", [])), capabilities=tuple(Capability.from_json(item) for item in value.get("capabilities", [])), protocol=value["protocol"], runtime_epoch=int(value["runtime_epoch"]) if value.get("runtime_epoch") is not None else None, source_digest=value.get("source_digest"), dependency_digest=value.get("dependency_digest"), source_epoch=value.get("source_epoch"))


def _decode_error(status: int, body: bytes) -> ApiError:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = {}
    return ApiError(status, str(value.get("code", "http_error")), str(value.get("message", f"HTTP {status}")), str(value.get("request_id", "")), value.get("details", {}))


class MutationResult(dict):
    """Resource mapping carrying its committed receipt out-of-band."""

    def __init__(self, data: Mapping[str, Any], receipt: Mapping[str, Any] | None):
        super().__init__(data)
        self.receipt = receipt
        if receipt is not None:
            self["receipt"] = receipt

    def __getattr__(self, name: str) -> Any:
        """Preserve generated resource attribute access on mutation results."""
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class WorkspaceClient:
    """Small stdlib HTTP client generated from the neutral OpenAPI contract.

    ``transport`` is injectable for conformance tests. It receives method, path,
    headers, and body and returns ``(status, headers, body)``.
    """

    def __init__(self, base_url: str, token: str | None = None, *, transport: Callable[..., tuple[int, Mapping[str, str], bytes]] | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._transport = transport
        self.handshake_info: Handshake | None = None

    def _request(self, method: str, path: str, *, body: bytes | None = None, headers: Mapping[str, str] | None = None, expected: tuple[int, ...] = (200,)) -> tuple[int, Mapping[str, str], bytes]:
        request_headers = {"Accept": "application/json", **dict(headers or {})}
        if self.token:
            request_headers.setdefault("Authorization", f"Bearer {self.token}")
        if self._transport:
            status, response_headers, response_body = self._transport(method, path, request_headers, body)
        else:
            request = urllib.request.Request(self.base_url + path, data=body, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request) as response:  # noqa: S310 - endpoint is caller-configured
                    status, response_headers, response_body = response.status, dict(response.headers), response.read()
            except urllib.error.HTTPError as error:
                raise _decode_error(error.code, error.read()) from error
            except urllib.error.URLError as error:
                raise ApiError(0, "transport_error", str(error.reason)) from error
        if status not in expected:
            raise _decode_error(status, response_body)
        return status, response_headers, response_body

    @staticmethod
    def _json(body: bytes) -> Mapping[str, Any]:
        value = json.loads(body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ApiError(0, "invalid_response", "expected JSON object")
        return value

    @staticmethod
    def _page(value: Mapping[str, Any]) -> tuple[list[Any], str | None]:
        """Decode a page strictly; pagination fields are part of the contract."""
        try:
            items = value["items"]
            next_cursor = value["next_cursor"]
        except KeyError as exc:
            raise ApiError(0, "invalid_response", "page must contain items and next_cursor") from exc
        if not isinstance(items, list) or (next_cursor is not None and not isinstance(next_cursor, str)):
            raise ApiError(0, "invalid_response", "page must contain list items and string-or-null next_cursor")
        return items, next_cursor

    def _mutation_json(self, body: bytes) -> Mapping[str, Any]:
        value = self._json(body)
        if set(value) != {"data", "receipt"}:
            raise ApiError(0, "invalid_response", "mutation response must contain data and committed receipt")
        data = value.get("data")
        receipt = value.get("receipt")
        if not isinstance(data, Mapping) or not isinstance(receipt, Mapping):
            raise ApiError(0, "invalid_response", "mutation response must contain data and committed receipt")
        return MutationResult(data, receipt)

    def health(self) -> Health:
        _, _, body = self._request("GET", "/v1/health")
        return Health.from_json(self._json(body))

    def handshake(self, client_name: str, client_version: str, requested_scopes: list[str]) -> Handshake:
        payload = {"protocol": PROTOCOL, "client_name": client_name, "client_version": client_version, "requested_scopes": requested_scopes}
        _, _, body = self._request("POST", "/v1/handshake", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})
        value = self._json(body)
        result = Handshake(protocol=value["protocol"], schema_digest=value["schema_digest"], session_id=value["session_id"], actor_id=value["actor_id"], realm_id=value["realm_id"], scopes=tuple(value["scopes"]))
        self.handshake_info = result
        return result

    def get_realm(self) -> Realm:
        return Realm.from_json(self._json(self._request("GET", "/v1/realm")[2]))

    def doctor(self) -> IntegrityReport:
        return IntegrityReport.from_json(self._json(self._request("GET", "/v1/doctor")[2]))

    def create_backup(self, destination: str) -> Mapping[str, Any]:
        payload = {"destination": destination}
        return self._json(self._request("POST", "/v1/backup", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"}, expected=(200, 201))[2])

    def restore_backup(self, backup: str, destination: str) -> Mapping[str, Any]:
        payload = {"backup": backup, "destination": destination}
        return self._json(self._request("POST", "/v1/restore", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"}, expected=(200, 201))[2])

    def export_realm(self) -> Mapping[str, Any]:
        return self._json(self._request("GET", "/v1/export")[2])

    def tombstone_realm(self, *, reason: str | None = None, expected_version: int | None = None) -> RealmLifecycle:
        payload: dict[str, Any] = {}
        if reason is not None: payload["reason"] = reason
        if expected_version is not None: payload["expected_version"] = expected_version
        return RealmLifecycle.from_json(self._json(self._request("POST", "/v1/realm/tombstone", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})[2]))

    def recover_realm(self, *, expected_realm_id: str | None = None, expected_version: int | None = None, confirmation: str | None = None, noninteractive: bool = False) -> RealmLifecycle:
        payload: dict[str, Any] = {}
        if expected_realm_id is not None: payload["expected_realm_id"] = expected_realm_id
        if expected_version is not None: payload["expected_version"] = expected_version
        if confirmation is not None: payload["confirmation"] = confirmation
        if noninteractive: payload["noninteractive"] = True
        return RealmLifecycle.from_json(self._json(self._request("POST", "/v1/realm/recover", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})[2]))

    def purge_realm(self, confirmation: str) -> Mapping[str, Any]:
        payload = {"confirmation": confirmation}
        return self._json(self._request("POST", "/v1/realm/purge", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})[2])

    def create_project(self, name: str, *, idempotency_key: str, slug: str | None = None, metadata: Mapping[str, Any] | None = None) -> MutationResult:
        payload: dict[str, Any] = {"name": name}
        if slug is not None: payload["slug"] = slug
        if metadata is not None: payload["metadata"] = metadata
        _, _, body = self._request("POST", "/v1/projects", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))
        return self._mutation_json(body)

    def get_project(self, project_id: str) -> Project:
        _, _, body = self._request("GET", f"/v1/projects/{_path_part(project_id)}")
        return Project.from_json(self._json(body))

    def update_project(self, project_id: str, *, idempotency_key: str, expected_version: int | None = None, name: str | None = None, metadata: Mapping[str, Any] | None = None) -> Project:
        payload: dict[str, Any] = {}
        if expected_version is not None: payload["expected_version"] = expected_version
        if name is not None: payload["name"] = name
        if metadata is not None: payload["metadata"] = metadata
        _, _, body = self._request("PATCH", f"/v1/projects/{_path_part(project_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return Project.from_json(self._json(body))

    def create_document(self, project_id: str, document_id: str, kind: str, content: Any, *, idempotency_key: str) -> MutationResult:
        payload = {"document_id": document_id, "kind": kind, "content": content}
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/documents", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def list_documents(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[ProjectDocument], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/documents" + query)[2])
        items, next_cursor = self._page(value)
        return [ProjectDocument.from_json(item) for item in items], next_cursor

    def get_document(self, project_id: str, document_id: str) -> ProjectDocument:
        return ProjectDocument.from_json(self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/documents/{_path_part(document_id)}")[2]))

    def update_document(self, project_id: str, document_id: str, *, expected_version: int, idempotency_key: str, content: Any = None, kind: str | None = None) -> MutationResult:
        payload: dict[str, Any] = {"expected_version": expected_version}
        if content is not None: payload["content"] = content
        if kind is not None: payload["kind"] = kind
        return self._mutation_json(self._request("PATCH", f"/v1/projects/{_path_part(project_id)}/documents/{_path_part(document_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def create_timeline(self, project_id: str, timeline_id: str, *, idempotency_key: str) -> MutationResult:
        value = self._json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/timelines", body=json.dumps({"timeline_id": timeline_id}, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])
        if isinstance(value, dict) and "data" in value and "receipt" in value:
            result = MutationResult(value["data"], value["receipt"])
            return result
        return value

    def create_timeline_document(
        self,
        project_id: str,
        timeline_id: str,
        *,
        config: Mapping[str, Any],
        registry: Mapping[str, Any],
        idempotency_key: str,
        slug: str | None = None,
        name: str | None = None,
    ) -> MutationResult:
        """Create the timeline and composition document in one runtime transaction."""
        slug = slug or timeline_id
        name = name or slug
        payload = {"timeline_id": timeline_id, "slug": slug, "name": name, "config": dict(config), "registry": dict(registry)}
        _, _, body = self._request("POST", f"/v1/projects/{_path_part(project_id)}/timeline-documents", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(201,))
        return self._mutation_json(body)

    def update_timeline_document(
        self,
        project_id: str,
        timeline_id: str,
        *,
        expected_version: int,
        config: Mapping[str, Any],
        registry: Mapping[str, Any],
        idempotency_key: str,
        slug: str | None = None,
        name: str | None = None,
    ) -> MutationResult:
        current = self.get_document(project_id, f"timeline:{timeline_id}")
        content = dict(current.content) if isinstance(current.content, Mapping) else {}
        content.update({"config": dict(config), "registry": dict(registry)})
        if slug is not None: content["slug"] = slug
        if name is not None: content["name"] = name
        document = self.update_document(project_id, f"timeline:{timeline_id}", expected_version=expected_version, idempotency_key=idempotency_key, content=content)
        timeline = self.get_timeline(timeline_id)
        result = dict(timeline)
        result.update({"slug": content.get("slug", timeline_id), "name": content.get("name", timeline_id), "config_version": document.version, "config": dict(config), "registry": dict(registry)})
        return MutationResult(result, document.receipt)

    def list_timelines(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Mapping[str, Any]], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/timelines" + query)[2])
        items, next_cursor = self._page(value)
        return list(items), next_cursor

    def get_timeline(self, timeline_id: str) -> Mapping[str, Any]:
        return self._json(self._request("GET", f"/v1/timelines/{_path_part(timeline_id)}")[2])

    def list_timeline_history(self, timeline_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Mapping[str, Any]], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/timelines/{_path_part(timeline_id)}/history" + query)[2])
        items, next_cursor = self._page(value)
        return list(items), next_cursor

    def diff_timeline(self, timeline_id: str, *, from_version: int, to_version: int) -> Mapping[str, Any]:
        path = f"/v1/timelines/{_path_part(timeline_id)}/diff?from_version={int(from_version)}&to_version={int(to_version)}"
        return self._json(self._request("GET", path)[2])

    def archive_timeline(self, timeline_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        payload = {"expected_version": expected_version}
        return self._mutation_json(self._request("POST", f"/v1/timelines/{_path_part(timeline_id)}/archive", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def recover_timeline(self, timeline_id: str, *, expected_version: int, version: int, idempotency_key: str) -> MutationResult:
        payload = {"expected_version": expected_version, "version": version}
        return self._mutation_json(self._request("POST", f"/v1/timelines/{_path_part(timeline_id)}/recover", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def update_timeline(self, timeline_id: str, *, expected_version: int, idempotency_key: str, shots: list[Mapping[str, Any]] | None = None, references: list[Mapping[str, Any]] | None = None) -> MutationResult:
        payload: dict[str, Any] = {"expected_version": expected_version}
        if shots is not None: payload["shots"] = shots
        if references is not None: payload["references"] = references
        return self._mutation_json(self._request("PATCH", f"/v1/timelines/{_path_part(timeline_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def create_shot(self, timeline_id: str, shot: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._json(self._request("POST", f"/v1/timelines/{_path_part(timeline_id)}/shots", body=json.dumps(dict(shot), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def get_shot(self, shot_id: str) -> Mapping[str, Any]:
        return self._json(self._request("GET", f"/v1/shots/{_path_part(shot_id)}")[2])

    def list_project_shots(self, project_id: str, *, cursor: str | None = None, limit: int = 50, include_archived: bool = False) -> tuple[list[Mapping[str, Any]], str | None]:
        query = f"?limit={int(limit)}&include_archived={'true' if include_archived else 'false'}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/shots" + query)[2])
        items, next_cursor = self._page(value)
        return list(items), next_cursor

    def create_project_shot(self, project_id: str, shot: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shots", body=json.dumps(dict(shot), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def get_project_shot(self, project_id: str, shot_id: str) -> Mapping[str, Any]:
        return self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}")[2])

    def update_project_shot(self, project_id: str, shot_id: str, *, expected_version: int, name: str | None = None, metadata: Mapping[str, Any] | None = None, idempotency_key: str) -> MutationResult:
        payload: dict[str, Any] = {"expected_version": expected_version}
        if name is not None: payload["name"] = name
        if metadata is not None: payload["metadata"] = metadata
        return self._mutation_json(self._request("PATCH", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def archive_project_shot(self, project_id: str, shot_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}/archive", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def recover_project_shot(self, project_id: str, shot_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}/recover", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def add_shot_item(self, project_id: str, shot_id: str, item: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}/items", body=json.dumps(dict(item), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def promote_project_shot_candidate(self, project_id: str, shot_id: str, candidate_item_id: str, *, expected_head_seq: int, timeline_assets: list[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]] = (), idempotency_key: str) -> MutationResult:
        payload: dict[str, Any] = {"candidate_item_id": candidate_item_id, "expected_head_seq": expected_head_seq}
        if timeline_assets:
            payload["timeline_assets"] = timeline_assets
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}/promote-candidate", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def remove_shot_item(self, project_id: str, shot_id: str, item_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("DELETE", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}/items/{_path_part(item_id)}", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def reorder_shot_items(self, project_id: str, shot_id: str, item_ids: list[str], *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shots/{_path_part(shot_id)}/reorder", body=json.dumps({"expected_version": expected_version, "item_ids": item_ids}, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def list_project_shot_text_bindings(self, project_id: str, *, shot_id: str | None = None, kind: str | None = None, slot: str | None = None) -> tuple[list[Mapping[str, Any]], str | None]:
        query = []
        if shot_id is not None: query.append("shot_id=" + _path_part(shot_id))
        if kind is not None: query.append("kind=" + _path_part(kind))
        if slot is not None: query.append("slot=" + _path_part(slot))
        suffix = ("?" + "&".join(query)) if query else ""
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/shot-text-bindings" + suffix)[2])
        return self._page(value)

    def get_project_shot_text_binding(self, project_id: str, binding_id: str) -> Mapping[str, Any]:
        return self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/shot-text-bindings/{_path_part(binding_id)}")[2])

    def set_project_shot_text_binding(self, project_id: str, body: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shot-text-bindings", body=json.dumps(dict(body), ensure_ascii=False, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def set_project_shot_text_binding_by_id(self, project_id: str, binding_id: str, body: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shot-text-bindings/{_path_part(binding_id)}", body=json.dumps(dict(body), ensure_ascii=False, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def rebind_project_shot_text_binding(self, project_id: str, binding_id: str, *, media_id: str, expected_head: int, idempotency_key: str) -> MutationResult:
        body = {"media_id": media_id, "expected_head": expected_head}
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/shot-text-bindings/{_path_part(binding_id)}/rebind", body=json.dumps(body, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def update_shot(self, shot_id: str, *, expected_version: int, start_ms: int | None = None, duration_ms: int | None = None, reference_ids: list[str] | None = None, idempotency_key: str | None = None) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"expected_version": expected_version}
        if start_ms is not None: payload["start_ms"] = start_ms
        if duration_ms is not None: payload["duration_ms"] = duration_ms
        if reference_ids is not None: payload["reference_ids"] = reference_ids
        headers = {"Content-Type": "application/json"}
        if idempotency_key: headers["Idempotency-Key"] = idempotency_key
        return self._json(self._request("PATCH", f"/v1/shots/{_path_part(shot_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers=headers)[2])

    def archive_shot(self, shot_id: str, *, expected_version: int, idempotency_key: str) -> Mapping[str, Any]:
        return self._json(self._request("POST", f"/v1/shots/{_path_part(shot_id)}/archive", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def recover_shot(self, shot_id: str, *, expected_version: int, idempotency_key: str) -> Mapping[str, Any]:
        return self._json(self._request("POST", f"/v1/shots/{_path_part(shot_id)}/recover", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def create_reference(self, timeline_id: str, reference: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._json(self._request("POST", f"/v1/timelines/{_path_part(timeline_id)}/references", body=json.dumps(dict(reference), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def get_reference(self, reference_id: str) -> Mapping[str, Any]:
        return self._json(self._request("GET", f"/v1/references/{_path_part(reference_id)}")[2])

    def list_project_references(self, project_id: str, *, cursor: str | None = None, limit: int = 50, include_archived: bool = False) -> tuple[list[Mapping[str, Any]], str | None]:
        query = f"?limit={int(limit)}&include_archived={'true' if include_archived else 'false'}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/references" + query)[2])
        items, next_cursor = self._page(value)
        return list(items), next_cursor

    def create_project_reference(self, project_id: str, reference: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/references", body=json.dumps(dict(reference), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def get_project_reference(self, project_id: str, reference_id: str) -> Mapping[str, Any]:
        return self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/references/{_path_part(reference_id)}")[2])

    def update_project_reference(self, project_id: str, reference_id: str, *, expected_version: int, name: str | None = None, description: str | None = None, metadata: Mapping[str, Any] | None = None, idempotency_key: str) -> MutationResult:
        payload: dict[str, Any] = {"expected_version": expected_version}
        if name is not None: payload["name"] = name
        if description is not None: payload["description"] = description
        if metadata is not None: payload["metadata"] = metadata
        return self._mutation_json(self._request("PATCH", f"/v1/projects/{_path_part(project_id)}/references/{_path_part(reference_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def archive_project_reference(self, project_id: str, reference_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/references/{_path_part(reference_id)}/archive", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def recover_project_reference(self, project_id: str, reference_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/references/{_path_part(reference_id)}/recover", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def associate_reference(self, project_id: str, reference_id: str, association: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/references/{_path_part(reference_id)}/associations", body=json.dumps(dict(association), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def set_primary_reference(self, project_id: str, reference_id: str, association_id: str, *, expected_version: int, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/references/{_path_part(reference_id)}/primary", body=json.dumps({"association_id": association_id, "expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def link_references(self, project_id: str, link: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/reference-links", body=json.dumps(dict(link), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def update_reference(self, reference_id: str, *, expected_version: int, object_id: str | None = None, role: str | None = None, idempotency_key: str | None = None) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"expected_version": expected_version}
        if object_id is not None: payload["object_id"] = object_id
        if role is not None: payload["role"] = role
        headers = {"Content-Type": "application/json"}
        if idempotency_key: headers["Idempotency-Key"] = idempotency_key
        return self._json(self._request("PATCH", f"/v1/references/{_path_part(reference_id)}", body=json.dumps(payload, separators=(",", ":")).encode(), headers=headers)[2])

    def archive_reference(self, reference_id: str, *, expected_version: int, idempotency_key: str) -> Mapping[str, Any]:
        return self._json(self._request("POST", f"/v1/references/{_path_part(reference_id)}/archive", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def recover_reference(self, reference_id: str, *, expected_version: int, idempotency_key: str) -> Mapping[str, Any]:
        return self._json(self._request("POST", f"/v1/references/{_path_part(reference_id)}/recover", body=json.dumps({"expected_version": expected_version}).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})[2])

    def list_projects(self, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Project], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        _, _, body = self._request("GET", "/v1/projects" + query)
        value = self._json(body)
        items, next_cursor = self._page(value)
        return [Project.from_json(item) for item in items], next_cursor

    def select_project(self, project: str, *, scope: str = "workspace", idempotency_key: str) -> MutationResult:
        payload = {"project": project, "scope": scope}
        headers = {"Content-Type": "application/json"}
        headers["Idempotency-Key"] = idempotency_key
        return self._mutation_json(self._request("PUT", "/v1/projects/selection", body=json.dumps(payload, separators=(",", ":")).encode(), headers=headers)[2])

    def current_project(self) -> Mapping[str, Any]:
        return self._json(self._request("GET", "/v1/projects/selection")[2])

    def ingest_object(self, data: bytes, *, media_type: str, idempotency_key: str, filename: str | None = None) -> MutationResult:
        headers = {"Content-Type": media_type, "Idempotency-Key": idempotency_key}
        if filename:
            headers["X-Filename"] = filename
        _, _, body = self._request("POST", "/v1/objects", body=bytes(data), headers=headers, expected=(200, 201))
        return self._mutation_json(body)

    def ingest_project_object(self, project_id: str, data: bytes, *, media_type: str, idempotency_key: str, filename: str | None = None) -> MutationResult:
        headers = {"Content-Type": media_type, "Idempotency-Key": idempotency_key}
        if filename: headers["X-Original-Name"] = filename
        _, _, body = self._request("POST", f"/v1/projects/{_path_part(project_id)}/objects", body=bytes(data), headers=headers, expected=(200, 201))
        return self._mutation_json(body)

    def list_project_objects(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[ManagedObject], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/objects" + query)[2])
        items, next_cursor = self._page(value)
        return [ManagedObject.from_json(item) for item in items], next_cursor


    def create_media_relation(self, project_id: str, from_object_id: str, to_object_id: str, kind: str, *, idempotency_key: str, metadata: Mapping[str, Any] | None = None, ordinal: int = 0) -> MutationResult:
        payload: dict[str, Any] = {"from_object_id": from_object_id, "to_object_id": to_object_id, "kind": kind}
        if metadata is not None: payload["metadata"] = metadata
        if ordinal: payload["ordinal"] = ordinal
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/media-relations", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def list_media_relations(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Mapping[str, Any]], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/media-relations" + query)[2])
        items, next_cursor = self._page(value)
        return list(items), next_cursor

    def get_object(self, object_id: str, *, byte_range: tuple[int, int | None] | None = None) -> ByteResponse:
        headers: dict[str, str] = {}
        if byte_range:
            start, end = byte_range
            if start < 0 or (end is not None and end < start):
                raise ValueError("invalid byte range")
            headers["Range"] = f"bytes={start}-{'' if end is None else end}"
        status, response_headers, body = self._request("GET", f"/v1/objects/{_path_part(object_id)}", headers=headers, expected=(200, 206))
        return ByteResponse(body, status, response_headers)

    def head_object(self, object_id: str, *, byte_range: tuple[int, int | None] | None = None) -> ByteResponse:
        headers: dict[str, str] = {}
        if byte_range:
            start, end = byte_range
            headers["Range"] = f"bytes={start}-{'' if end is None else end}"
        status, response_headers, body = self._request("HEAD", f"/v1/objects/{_path_part(object_id)}", headers=headers, expected=(200, 206))
        return ByteResponse(body, status, response_headers)

    def admit_task(self, *, capability_id: str, capability_digest: str, input_object_ids: list[str], idempotency_key: str, schema_version: str = "1", settlement_effect: Mapping[str, Any] | None = None, project_id: str | None = None, spec: Mapping[str, Any] | None = None, storage_estimate: Mapping[str, int] | None = None) -> MutationResult:
        payload: dict[str, Any] = {"capability_id": capability_id, "capability_digest": capability_digest, "schema_version": schema_version, "input_object_ids": input_object_ids}
        if settlement_effect is not None:
            payload["settlement_effect"] = settlement_effect
        if project_id is not None: payload["project"] = project_id
        if spec is not None: payload["spec"] = spec
        if storage_estimate is not None: payload["storage_estimate"] = dict(storage_estimate)
        _, _, body = self._request("POST", "/v1/tasks", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))
        return self._mutation_json(body)

    def get_task(self, task_id: str) -> Task:
        _, _, body = self._request("GET", f"/v1/tasks/{_path_part(task_id)}")
        return Task.from_json(self._json(body))

    def list_project_tasks(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Task], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/tasks" + query)[2])
        items, next_cursor = self._page(value)
        return [Task.from_json(item) for item in items], next_cursor


    def claim_task(self, *, executor_id: str, capability_ids: list[str], idempotency_key: str, runtime_epoch: int) -> AttemptFence | ClaimWaiting | None:
        payload: dict[str, Any] = {"executor_id": executor_id, "capability_ids": capability_ids, "runtime_epoch": runtime_epoch}
        status, _, body = self._request("POST", "/v1/tasks/claim", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 204))
        if status == 204:
            return None
        value = self._json(body)
        return ClaimWaiting.from_json(value) if isinstance(value, Mapping) and "waiting_reason" in value else AttemptFence.from_json(value)

    def heartbeat_attempt(self, attempt_id: str, *, lease_id: str, fence: int, idempotency_key: str, runtime_epoch: int) -> MutationResult:
        payload: dict[str, Any] = {"lease_id": lease_id, "fence": fence, "runtime_epoch": runtime_epoch}
        _, _, body = self._request("POST", f"/v1/attempts/{_path_part(attempt_id)}/heartbeat", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return self._mutation_json(body)

    def prepare_reboot(self, attempt_id: str, *, lease_id: str, fence: int, runtime_epoch: int) -> RecoveryAuthorization:
        payload: dict[str, Any] = {"lease_id": lease_id, "fence": fence, "runtime_epoch": runtime_epoch}
        return RecoveryAuthorization.from_json(self._json(self._request("POST", f"/v1/attempts/{_path_part(attempt_id)}/prepare-reboot", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})[2]))

    def checkpoint_attempt(self, attempt_id: str, *, lease_id: str, fence: int, nonce: str, authorization: str, state: Mapping[str, Any] | None = None, runtime_epoch: int) -> RecoveryCheckpointReceipt:
        payload: dict[str, Any] = {"lease_id": lease_id, "fence": fence, "nonce": nonce, "authorization": authorization, "state": dict(state or {}), "runtime_epoch": runtime_epoch}
        return RecoveryCheckpointReceipt.from_json(self._json(self._request("POST", f"/v1/attempts/{_path_part(attempt_id)}/checkpoint", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"}, expected=(200, 201))[2]))

    def request_reboot(self, *, checkpoint_id: str, nonce: str, authorization: str, runtime_epoch: int, command: str = "reboot") -> RecoveryReceipt:
        payload = {"checkpoint_id": checkpoint_id, "nonce": nonce, "authorization": authorization, "runtime_epoch": runtime_epoch, "command": command}
        return RecoveryReceipt.from_json(self._json(self._request("POST", "/v1/recovery/reboot", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})[2]))

    def resume_attempt(self, *, checkpoint_id: str, nonce: str, authorization: str, runtime_epoch: int) -> RecoveryResumeReceipt:
        payload = {"checkpoint_id": checkpoint_id, "nonce": nonce, "authorization": authorization, "runtime_epoch": runtime_epoch}
        return RecoveryResumeReceipt.from_json(self._json(self._request("POST", "/v1/recovery/resume", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json"})[2]))

    def cancel_task(self, task_id: str, *, idempotency_key: str, expected_version: int | None = None) -> MutationResult:
        return self._task_transition("cancel", task_id, idempotency_key=idempotency_key, expected_version=expected_version)

    def retry_task(self, task_id: str, *, idempotency_key: str, expected_version: int | None = None) -> MutationResult:
        return self._task_transition("retry", task_id, idempotency_key=idempotency_key, expected_version=expected_version)

    def _task_transition(self, action: str, task_id: str, *, idempotency_key: str, expected_version: int | None) -> MutationResult:
        payload = {} if expected_version is None else {"expected_version": expected_version}
        _, _, body = self._request("POST", f"/v1/tasks/{_path_part(task_id)}/{action}", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return self._mutation_json(body)

    def get_run(self, run_id: str) -> Mapping[str, Any]:
        _, _, body = self._request("GET", f"/v1/runs/{_path_part(run_id)}")
        return self._json(body)

    def cancel_run(self, run_id: str, *, idempotency_key: str) -> Mapping[str, Any]:
        _, _, body = self._request("POST", f"/v1/runs/{_path_part(run_id)}/cancel", body=b"{}", headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return self._json(body)

    def retry_run(self, run_id: str, *, idempotency_key: str, selected_task_ids: list[str] | None = None) -> Mapping[str, Any]:
        payload = {} if selected_task_ids is None else {"selected_task_ids": selected_task_ids}
        _, _, body = self._request("POST", f"/v1/runs/{_path_part(run_id)}/retry", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return self._json(body)

    def list_project_runs(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Mapping[str, Any]], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/runs" + query)[2])
        items, next_cursor = self._page(value)
        return list(items), next_cursor


    def list_events(self, *, cursor: str | None = None, limit: int = 50, aggregate_id: str | None = None) -> tuple[list[Event], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "") + (f"&aggregate_id={_path_part(aggregate_id)}" if aggregate_id else "")
        _, _, body = self._request("GET", "/v1/events" + query)
        value = self._json(body)
        items, next_cursor = self._page(value)
        return [Event.from_json(item) for item in items], next_cursor

    def list_run_events(self, run_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Event], str | None]:
        query = (f"?limit={int(limit)}" if cursor or int(limit) != 50 else "") + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/runs/{_path_part(run_id)}/events" + query)[2])
        items, next_cursor = self._page(value)
        return [Event.from_json(item) for item in items], next_cursor

    def list_generations(self, project_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Generation], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/projects/{_path_part(project_id)}/generations" + query)[2])
        items, next_cursor = self._page(value)
        return [Generation.from_json(item) for item in items], next_cursor

    def create_generation(self, project_id: str, generation_id: str, *, idempotency_key: str, metadata: Mapping[str, Any] | None = None, type: str = "generation", source_task_id: str | None = None, status: str = "created") -> MutationResult:
        payload: dict[str, Any] = {"generation_id": generation_id, "type": type, "status": status, "metadata": metadata or {}}
        if source_task_id is not None: payload["source_task_id"] = source_task_id
        return self._mutation_json(self._request("POST", f"/v1/projects/{_path_part(project_id)}/generations", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def get_generation(self, generation_id: str) -> Generation:
        return Generation.from_json(self._json(self._request("GET", f"/v1/generations/{_path_part(generation_id)}")[2]))

    def list_variants(self, generation_id: str, *, cursor: str | None = None, limit: int = 50) -> tuple[list[GenerationVariant], str | None]:
        query = f"?limit={int(limit)}" + (f"&cursor={_path_part(cursor)}" if cursor else "")
        value = self._json(self._request("GET", f"/v1/generations/{_path_part(generation_id)}/variants" + query)[2])
        items, next_cursor = self._page(value)
        return [GenerationVariant.from_json(item) for item in items], next_cursor

    def get_variant(self, variant_id: str) -> GenerationVariant:
        return GenerationVariant.from_json(self._json(self._request("GET", f"/v1/variants/{_path_part(variant_id)}")[2]))

    def create_variant(self, generation_id: str, variant_id: str, *, idempotency_key: str, object_id: str | None = None, variant_type: str = "original", metadata: Mapping[str, Any] | None = None) -> MutationResult:
        payload: dict[str, Any] = {"variant_id": variant_id, "variant_type": variant_type, "metadata": metadata or {}}
        if object_id is not None: payload["object_id"] = object_id
        return self._mutation_json(self._request("POST", f"/v1/generations/{_path_part(generation_id)}/variants", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))[2])

    def register_executor(self, executor: Mapping[str, Any], *, idempotency_key: str) -> Executor:
        _, _, body = self._request("POST", "/v1/executors", body=json.dumps(dict(executor), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key}, expected=(200, 201))
        return Executor.from_json(self._json(body))

    def list_capabilities(self, *, cursor: str | None = None, limit: int = 50) -> tuple[list[Capability], str | None]:
        query = (f"?limit={int(limit)}" if cursor or int(limit) != 50 else "") + (f"&cursor={_path_part(cursor)}" if cursor else "")
        _, _, body = self._request("GET", "/v1/capabilities" + query)
        items, next_cursor = self._page(self._json(body))
        return [Capability.from_json(item) for item in items], next_cursor

    def register_capability(self, capability_id: str, definition_digest: str, *, required_resource_keys: list[str] | None = None, status: str = "ready", estimated_scratch_bytes: int = 0, estimated_output_bytes: int = 0, unavailable_reason: str | None = None, idempotency_key: str | None = None) -> Capability:
        payload = {"capability_id": capability_id, "definition_digest": definition_digest, "status": status, "required_resource_keys": required_resource_keys or [], "estimated_scratch_bytes": estimated_scratch_bytes, "estimated_output_bytes": estimated_output_bytes, "unavailable_reason": unavailable_reason}
        headers = {"Content-Type": "application/json"}
        if idempotency_key: headers["Idempotency-Key"] = idempotency_key
        return Capability.from_json(self._json(self._request("POST", "/v1/capabilities", body=json.dumps(payload, separators=(",", ":")).encode(), headers=headers, expected=(200, 201))[2]))

    def settle_attempt(self, attempt_id: str, settlement: Mapping[str, Any], *, idempotency_key: str) -> MutationResult:
        _, _, body = self._request("POST", f"/v1/attempts/{_path_part(attempt_id)}/settle", body=json.dumps(dict(settlement), separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return self._mutation_json(body)

    def fail_attempt(self, attempt_id: str, *, lease_id: str, fence: int, error: Any, runtime_epoch: int, idempotency_key: str) -> MutationResult:
        payload = {"lease_id": lease_id, "fence": fence, "runtime_epoch": runtime_epoch, "error": error}
        _, _, body = self._request("POST", f"/v1/attempts/{_path_part(attempt_id)}/fail", body=json.dumps(payload, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key})
        return self._mutation_json(body)


def _path_part(value: str) -> str:
    from urllib.parse import quote
    return quote(str(value), safe="")
