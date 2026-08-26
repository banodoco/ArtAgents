"""Reigh build-task bridge composed by the production Astrid serve root.

Every mutation uses the constructor-injected kernel writer; no repository
opens a second write authority.
"""

from __future__ import annotations

import dataclasses
import json
import re
import threading
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlparse

from astrid.core.integrations.reigh.bridge_service import (
    BridgeBodyError,
    BridgeError,
    BridgeInternalError,
    BridgeInvalidProjectError,
    BridgeIssue,
    BridgeProjectNotFoundError,
    BridgeSchemaIncompatibleError,
)


class BridgeGenerationNotFoundError(BridgeError):
    status_code = 404
    code = "generation_not_found"


class BridgeNotFoundError(BridgeError):
    status_code = 404
    code = "not_found"


class BridgeTaskMismatchError(BridgeError):
    status_code = 409
    code = "idempotency_mismatch"


class BridgeConflictError(BridgeError):
    status_code = 409
    code = "conflict"

    def __init__(
        self,
        detail: str,
        *,
        attempt: Mapping[str, Any] | None = None,
        config_version: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.attempt = dict(attempt) if attempt else None
        self.config_version = config_version

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        if self.attempt is not None:
            payload["attempt"] = self.attempt
        if self.config_version is not None:
            payload["config_version"] = self.config_version
        return payload


class BridgeCapabilityUnavailableError(BridgeError):
    status_code = 422
    code = "capability_unavailable"


class BridgeChildAdmissionForbiddenError(BridgeError):
    status_code = 403
    code = "child_admission_forbidden"


class AttemptErrorDiagnostics(TypedDict, total=False):
    """Allowlisted error fields persisted by task executors."""

    code: str
    reason: str
    type: str
    message: str
    retryable: bool


class AttemptDiagnostics(TypedDict):
    """Safe, bounded diagnostics exposed on task-detail attempts.

    The database columns are JSON blobs because executors may report
    capability-specific runtime state.  They are deliberately not exposed
    as-is: this public shape is the small, stable projection consumed by the
    editor and keeps leases, staging identifiers, and arbitrary executor
    metadata out of the detail response.
    """

    progress: dict[str, Any]
    error: AttemptErrorDiagnostics


_DIAGNOSTIC_MAX_DEPTH = 5
_DIAGNOSTIC_MAX_ITEMS = 100
_DIAGNOSTIC_MAX_VALUE_CHARS = 1000
_DIAGNOSTIC_MAX_PROGRESS_BYTES = 16 * 1024
_DIAGNOSTIC_MAX_ERROR_MESSAGE_CHARS = 4000
_DIAGNOSTIC_SECRET_KEY_PARTS = frozenset(
    {
        "accesskey",
        "accesstoken",
        "apikey",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "jwt",
        "password",
        "privatekey",
        "refreshtoken",
        "secret",
        "stagingtxn",
        "token",
    }
)
_DIAGNOSTIC_SECRET_TEXT_RE = re.compile(
    r"(?ix)"
    r"(?:"
    r"(?:\b(?:authorization|bearer)\s*[:=]\s*(?:bearer\s+)?|"
    r"\bbearer\s+|"
    r"\b(?:access[_ -]?token|api[_ -]?(?:key|token)|password|refresh[_ -]?token|secret|token)\s*[:=]\s*)"
    r"[^\s,;]+"
    r"|\b(?:api[_ -]?token|secret|token)\s+(?:is\s+)?[^\s,;]+"
    r"|\b(?:sk|rk|pk|gh[pousr]|glpat|xox[baprs])[-_][A-Za-z0-9._-]+"
    r"|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{10,})?"
    r")"
)


def _diagnostic_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(part in normalized for part in _DIAGNOSTIC_SECRET_KEY_PARTS)


def _redact_diagnostic_text(value: str, *, limit: int) -> str:
    bounded = value[:limit]
    return _DIAGNOSTIC_SECRET_TEXT_RE.sub("[redacted]", bounded)


def _safe_diagnostic_value(value: Any, *, depth: int = 0) -> Any:
    """Return JSON-safe diagnostics without secret-bearing fields."""

    if depth > _DIAGNOSTIC_MAX_DEPTH:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_diagnostic_text(value, limit=_DIAGNOSTIC_MAX_VALUE_CHARS)
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:_DIAGNOSTIC_MAX_ITEMS]:
            key = str(raw_key)
            if _diagnostic_secret_key(key):
                continue
            safe[key] = _safe_diagnostic_value(raw_value, depth=depth + 1)
        if len(value) > _DIAGNOSTIC_MAX_ITEMS:
            safe["_truncated"] = True
        return safe
    if isinstance(value, (list, tuple)):
        safe_items = [
            _safe_diagnostic_value(item, depth=depth + 1)
            for item in value[:_DIAGNOSTIC_MAX_ITEMS]
        ]
        if len(value) > _DIAGNOSTIC_MAX_ITEMS:
            safe_items.append("[truncated]")
        return safe_items
    return _redact_diagnostic_text(str(value), limit=_DIAGNOSTIC_MAX_VALUE_CHARS)


def _diagnostic_json_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _attempt_diagnostics_wire_shape(row: Mapping[str, Any]) -> AttemptDiagnostics:
    """Project persisted progress/error JSON into a safe detail-only shape."""

    progress = _safe_diagnostic_value(
        _diagnostic_json_object(row.get("progress_json")),
    )
    if not isinstance(progress, dict):  # pragma: no cover - mapping input
        progress = {}
    try:
        progress_size = len(
            json.dumps(progress, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
    except (TypeError, ValueError):  # pragma: no cover - sanitizer is JSON-safe
        progress_size = _DIAGNOSTIC_MAX_PROGRESS_BYTES + 1
    if progress_size > _DIAGNOSTIC_MAX_PROGRESS_BYTES:
        progress = {"_truncated": True}

    raw_error = _diagnostic_json_object(row.get("error_json"))
    error: AttemptErrorDiagnostics = {}
    # These are the two persisted error vocabularies: the task executor's
    # reason/type/message form and the bridge's code/message/retryable form.
    for key in ("code", "reason", "type"):
        value = raw_error.get(key)
        if isinstance(value, str) and not _diagnostic_secret_key(key):
            error[key] = _redact_diagnostic_text(
                value, limit=_DIAGNOSTIC_MAX_VALUE_CHARS
            )
    message = raw_error.get("message")
    if isinstance(message, str):
        error["message"] = _redact_diagnostic_text(
            message, limit=_DIAGNOSTIC_MAX_ERROR_MESSAGE_CHARS
        )
    retryable = raw_error.get("retryable")
    if isinstance(retryable, bool):
        error["retryable"] = retryable
    return {"progress": progress, "error": error}


def _attempt_detail_wire_shape(row: Mapping[str, Any]) -> dict[str, Any]:
    """The detail-only attempt projection, including safe diagnostics."""

    attempt = _attempt_wire_shape(row)
    attempt["diagnostics"] = _attempt_diagnostics_wire_shape(row)
    return attempt


def _attempt_wire_shape(row: Mapping[str, Any]) -> dict[str, Any]:
    """The bounded current-attempt extra allowed on a fence ``409``."""
    return {
        "attempt_id": str(row["id"]),
        "attempt_no": int(row["attempt_no"]),
        "status": str(row["status"]),
        "status_version": int(row["status_version"]),
        "lease_id": str(row["lease_id"]),
        "lease_expires_at": str(row["lease_expires_at"]),
        "heartbeat_counter": int(row["heartbeat_counter"]),
        "last_heartbeat_at": row["last_heartbeat_at"],
    }


def _task_output_wire_shape(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project SQLite's integer flags to the JSON task-output contract."""
    output = dict(row)
    output["is_primary"] = bool(output["is_primary"])
    return output


class ReighTaskBridge:
    """The task/executor bridge over the one kernel writer (doc 27 §§3-5).

    Composed once at the serve root alongside the timeline bridge. Every
    mutation enters the kernel repositories through the single writer's
    ``BEGIN IMMEDIATE`` units of work; this adapter adds no SQL of its own
    beyond read-only queue scans and the bounded progress merge, and it
    never opens a second write authority.
    """

    _SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    _MAX_PROGRESS_BYTES = 16 * 1024
    _MAX_ERROR_MESSAGE_CHARS = 4000

    def __init__(
        self,
        *,
        writer: Any,
        registry: Any,
        projects_root: Path,
        generation_repo_factory: Callable[[], Any] | None = None,
        timeline_repo_factory: Callable[[], Any] | None = None,
    ):
        self._writer = writer
        self._registry = registry
        self._projects_root = Path(projects_root)
        self._lock = threading.Lock()
        self._tasks: Any | None = None
        self._media: Any | None = None
        self._receipts: Any | None = None
        # Pack repositories join the ONE completion unit of work through
        # factories composed at the serve root (kernel-to-pack boundary:
        # only ``astrid/core/gateway/dispatch.py`` may import packs).
        self._generation_repo_factory = generation_repo_factory
        self._timeline_repo_factory = timeline_repo_factory

    # -- lazy kernel wiring (no repository import at module import time) ---

    def _services(self) -> tuple[Any, Any, Any]:
        with self._lock:
            if self._tasks is None:
                from astrid.core.events.service import EventAppendService
                from astrid.core.receipts.service import ReceiptService
                from astrid.core.repositories.media import MediaRepository
                from astrid.core.repositories.tasks import TaskRepository

                events = EventAppendService(self._registry)
                receipts = ReceiptService()
                self._receipts = receipts
                self._tasks = TaskRepository(events=events, receipts=receipts)
                self._media = MediaRepository(
                    events=events,
                    receipts=receipts,
                    projects_root=self._projects_root,
                )
            return self._tasks, self._media, self._receipts

    @property
    def writer(self) -> Any:
        return self._writer

    # -- shared reads ------------------------------------------------------

    def resolve_project_id(self, slug: str) -> str:
        from astrid.core.repositories.projects import ProjectNotFoundError, ProjectRepository

        if not isinstance(slug, str) or self._SLUG_RE.fullmatch(slug) is None:
            raise BridgeInvalidProjectError(
                f"project slug {slug!r} is not a valid slug"
            )
        projects = ProjectRepository(events=None, receipts=None)
        try:
            return projects.resolve(self._writer, slug)
        except ProjectNotFoundError:
            raise BridgeProjectNotFoundError(
                f"project {slug!r} was not found"
            ) from None

    def _task_row(self, task_id: str) -> dict[str, Any]:
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise BridgeNotFoundError(f"task {task_id!r} was not found")
        return dict(row)

    def _attempt_row(self, attempt_id: str) -> dict[str, Any] | None:
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            row = conn.execute(
                "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def _current_attempt_extra(self, attempt_id: str | None) -> dict | None:
        if not attempt_id:
            return None
        row = self._attempt_row(attempt_id)
        return _attempt_wire_shape(row) if row is not None else None

    def _resolve_render_registry(
        self,
        project_id: str,
        registry: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Freeze render assets as verified, project-owned managed media.

        Timeline registries are intentionally broader than the render task
        contract and historically allowed paths/URLs.  A render admission
        cannot carry those locators across a queue boundary: only a media id,
        its byte digest, and the canonical managed location are admitted.
        The adapter re-verifies the digest and stages a private copy before
        invoking a renderer.
        """
        from astrid.core.io.media_import import managed_media_path, sha256_file_bytes

        assets = registry.get("assets")
        if not isinstance(assets, Mapping):
            raise BridgeBodyError("render_export timeline registry assets must be an object")
        rewritten: dict[str, Any] = {}
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            for asset_key, raw_asset in assets.items():
                if not isinstance(asset_key, str) or not asset_key:
                    raise BridgeBodyError("render_export asset keys must be non-empty strings")
                if not isinstance(raw_asset, Mapping):
                    raise BridgeBodyError(f"render_export asset {asset_key!r} must be an object")
                display_file = raw_asset.get("file")
                if display_file is not None:
                    if not isinstance(display_file, str) or not display_file:
                        raise BridgeBodyError(
                            f"render_export asset {asset_key!r} file must be a string"
                        )
                    parsed = urlparse(display_file)
                    parts = Path(display_file).parts
                    if (
                        Path(display_file).is_absolute()
                        or parsed.scheme
                        or parsed.netloc
                        or display_file.startswith("//")
                        or "\x00" in display_file
                        or ".." in parts
                    ):
                        raise BridgeBodyError(
                            f"render_export asset {asset_key!r} file must be a safe relative display name"
                        )
                if any(key in raw_asset for key in ("path", "url", "uri")):
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} contains an unmanaged locator"
                    )
                media_id = raw_asset.get("media_id")
                if not isinstance(media_id, str) or not media_id:
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} requires a project media_id"
                    )
                rows = conn.execute(
                    "SELECT m.id, m.content_hash, m.byte_size, m.mime_type, "
                    "l.realm, l.locator FROM media m "
                    "LEFT JOIN media_locations l ON l.media_id = m.id "
                    "WHERE m.id = ? AND m.project_id = ? "
                    "ORDER BY l.realm ASC, l.locator ASC",
                    (media_id, project_id),
                ).fetchall()
                if not rows:
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} references unknown or foreign media"
                    )
                media = rows[0]
                digest = str(media["content_hash"])
                declared = raw_asset.get("content_sha256")
                if declared is not None:
                    if not isinstance(declared, str):
                        raise BridgeBodyError(
                            f"render_export asset {asset_key!r} content_sha256 must be a string"
                        )
                    declared_digest = declared.removeprefix("sha256:")
                    if declared_digest != digest:
                        raise BridgeBodyError(
                            f"render_export asset {asset_key!r} digest does not match managed media"
                        )
                canonical = managed_media_path(self._projects_root, digest).resolve()
                managed_locations = [
                    row for row in rows
                    if str(row["realm"] or "") == "managed_local"
                ]
                if not managed_locations or any(
                    str(row["locator"]) != str(canonical) for row in managed_locations
                ):
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} has no canonical managed location"
                    )
                if canonical.is_symlink() or not canonical.is_file():
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} managed bytes are missing"
                    )
                try:
                    actual = sha256_file_bytes(canonical)
                except OSError as exc:
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} managed bytes are unreadable"
                    ) from exc
                if actual != digest:
                    raise BridgeBodyError(
                        f"render_export asset {asset_key!r} managed bytes have a digest mismatch"
                    )
                rewritten[asset_key] = {
                    key: value
                    for key, value in raw_asset.items()
                    if key not in {"file", "path", "url", "uri"}
                }
                rewritten[asset_key].update(
                    {
                        "media_id": media_id,
                        "content_sha256": f"sha256:{digest}",
                        "type": raw_asset.get("type") or str(media["mime_type"]),
                    }
                )
        result = dict(registry)
        result["assets"] = rewritten
        return result

    # -- R1: public family admission (doc 27 §3.5, §4.1) --------------------

    def admit(
        self,
        *,
        slug: str,
        body: Mapping[str, Any],
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]]:
        """R1 public admission: derive the capability, admit one task.

        Returns ``(201, {"task": ...})`` on first commit and
        ``(200, {"task": ...})`` on an idempotent replay; a key reused
        with different canonical bytes raises
        :class:`BridgeTaskMismatchError` (doc 27 §4.1).
        """
        from astrid.core.integrations.reigh.capabilities import (
            CapabilityInputError,
            CapabilityUnavailable,
            ChildAdmissionForbidden,
            check_available,
            load_workflow_snapshot,
            resolve_family_capability,
        )
        from astrid.core.store.uow import UnitOfWork

        family = body.get("family")
        task_input = body.get("input")
        materialized = body.get("materialized_inputs", [])
        priority = body.get("priority", 0)
        if not isinstance(family, str) or not family:
            raise BridgeBodyError("body.family must be a non-empty string")
        if not isinstance(task_input, dict):
            raise BridgeBodyError("body.input must be a JSON object")
        if not isinstance(materialized, list):
            raise BridgeBodyError(
                "body.materialized_inputs must be an array when present"
            )
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise BridgeBodyError("body.priority must be an integer")
        try:
            entry = resolve_family_capability(
                family,
                task_input,
                projects_root=self._projects_root,
            )
            if entry.child_only:
                raise ChildAdmissionForbidden(
                    f"family {family!r} is executor-only; child families "
                    "are admitted only by the live fenced parent executor"
                )
            check_available(entry)
            workflow_snapshot = (
                load_workflow_snapshot(entry) if entry.template is not None else None
            )
        except CapabilityInputError as exc:
            raise BridgeBodyError(str(exc)) from None
        except CapabilityUnavailable as exc:
            raise BridgeCapabilityUnavailableError(
                f"{exc.identifier}: {exc.hint}"
            ) from None
        except ChildAdmissionForbidden as exc:
            raise BridgeChildAdmissionForbiddenError(str(exc)) from None

        project_id = self.resolve_project_id(slug)
        # Build the caller envelope before resolving any derived media.  A
        # reused render key must report an idempotency mismatch for a changed
        # materialized input (even when that new media id is itself invalid),
        # rather than leaking a validation result from a different request.
        request_envelope = json.loads(
            json.dumps(dict(body), sort_keys=True, separators=(",", ":"))
        )
        existing_render_receipt = None
        if family == "render_export":
            with self._writer.read_only_connection() as conn:
                conn.row_factory = _sqlite_row_factory
                existing_render_receipt = conn.execute(
                    "SELECT primary_stream_id FROM command_receipts "
                    "WHERE project_id = ? AND idempotency_key = ? "
                    "AND command_kind = 'core.task.create' LIMIT 1",
                    (project_id, idempotency_key),
                ).fetchone()
            if existing_render_receipt is not None:
                prior_task_id = str(existing_render_receipt["primary_stream_id"]).removesuffix(":core.task")
                with self._writer.read_only_connection() as conn:
                    conn.row_factory = _sqlite_row_factory
                    prior_row = conn.execute(
                        "SELECT spec_json FROM tasks WHERE id = ?", (prior_task_id,)
                    ).fetchone()
                if prior_row is not None:
                    prior_spec = json.loads(str(prior_row["spec_json"]))
                    if (
                        not isinstance(prior_spec, dict)
                        or prior_spec.get("request_envelope") != request_envelope
                    ):
                        raise BridgeTaskMismatchError(
                            "this render_export idempotency key was already committed "
                            "with a different caller request"
                        )
        manifest = self._resolve_materialized_inputs(project_id, materialized)
        timeline_snapshot = None
        if family == "render_export":
            # A replay must reuse the original request bytes even if the
            # timeline advanced after the first response. Avoid reading a new
            # snapshot when this idempotency key already has a receipt.
            if existing_render_receipt is None:
                if self._timeline_repo_factory is None:
                    raise BridgeInternalError(
                        "render_export admission requires a composed timeline "
                        "repository factory"
                    )
                try:
                    current = self._timeline_repo_factory().show(
                        self._writer,
                        project_id,
                        str(task_input["timeline_ref"]),
                    )
                except Exception as exc:  # noqa: BLE001 - normalize below
                    if type(exc).__name__ == "TimelineNotFoundError":
                        raise BridgeNotFoundError(str(exc)) from None
                    if type(exc).__name__ == "TimelineValidationError":
                        raise BridgeBodyError(str(exc)) from None
                    raise BridgeInternalError(str(exc)) from None
                if int(task_input["expected_version"]) != int(current.config_version):
                    raise BridgeConflictError(
                        "render_export timeline version is stale",
                        config_version=int(current.config_version),
                    )
                timeline_snapshot = {
                    "timeline_id": current.timeline_id,
                    "timeline_ulid": current.timeline_ulid,
                    "slug": current.slug,
                    "config": dict(current.config),
                    "registry": self._resolve_render_registry(
                        project_id, dict(current.registry)
                    ),
                    "config_version": current.config_version,
                }
                # A text/effect timeline is Remotion-only.  Check the
                # server-owned runtime while the request is still admission,
                # before a task can be claimed by a worker.  Media-only
                # timelines retain the existing FFmpeg fallback contract.
                from astrid.core.integrations.reigh.remotion_runtime import (
                    remotion_runtime_status,
                    timeline_requires_remotion,
                )

                if timeline_requires_remotion(current.config):
                    runtime = remotion_runtime_status(require_explicit_project=True)
                    if not runtime.available:
                        raise BridgeCapabilityUnavailableError(
                            "rendering.render: server-owned Remotion runtime "
                            "is unavailable: "
                            + (runtime.reason or "unknown reason")
                        )
        # Keep the exact public caller envelope beside the generated snapshot.
        # On replay this is compared before the old snapshot is reused, so a
        # changed filename/correlation/fence/destination/materialized input
        # cannot be smuggled through by the snapshot replay path.
        spec = {
            "schema_version": 1,
            "family": entry.family,
            "source_task_type": entry.capability_id,
            "definition_version": entry.definition_version,
            "params": dict(task_input),
            "output_policy": dict(entry.output_policy),
        }
        if timeline_snapshot is not None:
            spec["project_slug"] = slug
            spec["timeline_snapshot"] = timeline_snapshot
            spec["request_envelope"] = request_envelope
        if workflow_snapshot is not None:
            spec["workflow"] = workflow_snapshot
        tasks, _media, _receipts = self._services()

        def command(uow):
            # Replay requires the same stable id: the kernel receipt gate
            # hashes it into the request, so a fresh ULID would mismatch.
            # primary_stream_id is the event stream ("<task>:core.task");
            # the tasks table maps it back to the bare task id.
            existing = uow.query_one(
                "SELECT t.id AS task_id FROM tasks t "
                "JOIN command_receipts r "
                "ON r.primary_stream_id = t.event_stream_id "
                "WHERE r.project_id = ? AND r.idempotency_key = ?",
                (project_id, idempotency_key),
            )
            stable_id = existing["task_id"] if existing is not None else None
            if existing is not None and entry.family == "render_export":
                prior = uow.query_one(
                    "SELECT spec_json, input_manifest_json FROM tasks WHERE id = ?",
                    (stable_id,),
                )
                if prior is None:
                    raise BridgeInternalError("task receipt points to a missing task")
                try:
                    prior_spec = json.loads(str(prior["spec_json"]))
                    prior_envelope = (
                        prior_spec.get("request_envelope")
                        if isinstance(prior_spec, dict)
                        else None
                    )
                    if prior_envelope != request_envelope:
                        raise BridgeTaskMismatchError(
                            "this render_export idempotency key was already committed "
                            "with a different caller request"
                        )
                    spec.clear()
                    spec.update(prior_spec)
                    manifest.clear()
                    manifest.extend(json.loads(str(prior["input_manifest_json"])))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise BridgeInternalError("stored render task request is malformed") from exc
            if existing is None and entry.family == "render_export":
                self._assert_render_export_current(
                    uow,
                    project_id=project_id,
                    task_input=task_input,
                )
            task = tasks.create(
                uow,
                project_id=project_id,
                capability=entry.capability_id,
                spec=spec,
                input_manifest=manifest,
                idempotency_key=idempotency_key,
                actor_kind="local",
                task_id=stable_id,
                priority=priority,
                max_attempts=3,
            )
            return existing is not None, task

        try:
            replayed, task = UnitOfWork(self._writer).run(command)
        except Exception as exc:
            # Core cannot import pack exception classes. Narrow the injected
            # timeline repository's stable error family at this one boundary.
            if type(exc).__name__ == "TimelineVersionConflictError":
                raise BridgeConflictError(
                    str(exc),
                    config_version=getattr(exc, "current_version", None),
                ) from None
            if type(exc).__name__ in (
                "TimelineNotFoundError",
                "TimelineArchivedError",
            ):
                raise BridgeNotFoundError(str(exc)) from None
            if type(exc).__name__ == "TimelineValidationError":
                raise BridgeBodyError(str(exc)) from None
            raise
        return (200 if replayed else 201), {"task": task.to_dict()}

    def _assert_render_export_current(
        self,
        uow: Any,
        *,
        project_id: str,
        task_input: Mapping[str, Any],
    ) -> None:
        if self._timeline_repo_factory is None:
            raise BridgeInternalError(
                "render_export admission requires a composed timeline "
                "repository factory"
            )
        self._timeline_repo_factory().assert_current_version(
            uow,
            project_id=project_id,
            ref=str(task_input["timeline_ref"]),
            expected_version=int(task_input["expected_version"]),
        )

    def admit_child(
        self,
        *,
        slug: str | None,
        body: Mapping[str, Any],
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]]:
        """T8 hard gate: fenced executor-only child admission (§3.5)."""
        from astrid.core.integrations.reigh.capabilities import (
            resolve_child_capability,
        )
        from astrid.core.store.uow import UnitOfWork

        envelope = body.get("child_admission")
        if not isinstance(envelope, dict):
            raise BridgeChildAdmissionForbiddenError(
                "child admission requires the child_admission envelope"
            )
        parent_task_id = envelope.get("parent_task_id")
        parent_attempt_id = envelope.get("parent_attempt_id")
        executor_id = envelope.get("executor_id")
        lease_id = envelope.get("lease_id")
        status_version = envelope.get("status_version")
        role = envelope.get("role")
        index = envelope.get("index")
        for name, value in (
            ("parent_task_id", parent_task_id),
            ("parent_attempt_id", parent_attempt_id),
            ("executor_id", executor_id),
            ("lease_id", lease_id),
            ("role", role),
        ):
            if not isinstance(value, str) or not value:
                raise BridgeChildAdmissionForbiddenError(
                    f"child_admission.{name} must be a non-empty string"
                )
        if (
            isinstance(status_version, bool)
            or not isinstance(status_version, int)
            or status_version <= 0
        ):
            raise BridgeChildAdmissionForbiddenError(
                "child_admission.status_version must be a positive integer"
            )
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise BridgeChildAdmissionForbiddenError(
                "child_admission.index must be a non-negative integer"
            )
        expected_key = f"reigh.orch:v1:{parent_task_id}:{role}:{index}"
        if idempotency_key != expected_key:
            raise BridgeChildAdmissionForbiddenError(
                f"child admission requires the deterministic key "
                f"{expected_key!r}"
            )

        family = body.get("family")
        try:
            entry = resolve_child_capability(family if isinstance(family, str) else "")
        except Exception as exc:  # noqa: BLE001 - narrowed below
            from astrid.core.integrations.reigh.capabilities import (
                ChildAdmissionForbidden,
            )

            if isinstance(exc, ChildAdmissionForbidden):
                raise BridgeChildAdmissionForbiddenError(str(exc)) from None
            raise

        # Receipt identity is checked before the live fence.  A coordinator
        # can lose the response after the child commit and then resume after
        # the parent lease has been reclaimed; the deterministic key must
        # still return the original row, without re-paying the old fence.
        parent = self._task_row(parent_task_id)
        project_id = str(parent["project_id"])
        task_input = body.get("input")
        if not isinstance(task_input, dict):
            task_input = {}
        dependant_on = task_input.get("dependant_on", [])
        dependencies: list[dict[str, Any]] = []
        if isinstance(dependant_on, list):
            for ordinal, dep in enumerate(dependant_on):
                if isinstance(dep, str) and dep:
                    dependencies.append(
                        {"task_id": dep, "kind": "hard", "ordinal": ordinal}
                    )
        expected_spec = {
            "schema_version": 1,
            "family": entry.family,
            "source_task_type": entry.capability_id,
            "definition_version": entry.definition_version,
            "params": dict(task_input),
            "output_policy": dict(entry.output_policy),
        }
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            receipt = conn.execute(
                "SELECT result_json FROM command_receipts "
                "WHERE project_id = ? AND idempotency_key = ? "
                "AND command_kind = 'core.task.create'",
                (project_id, idempotency_key),
            ).fetchone()
        if receipt is not None:
            import json as _json

            try:
                result = _json.loads(str(receipt["result_json"]))
            except (TypeError, ValueError, KeyError):
                raise BridgeInternalError(
                    "child admission receipt contains invalid task data"
                ) from None
            if not isinstance(result, dict):
                raise BridgeInternalError(
                    "child admission receipt contains invalid task data"
                )
            if (
                result.get("capability") != entry.capability_id
                or result.get("spec") != expected_spec
                or result.get("input_manifest") != []
                or result.get("max_attempts") != 3
            ):
                raise BridgeTaskMismatchError(
                    "this child idempotency key was already committed with "
                    "different canonical request bytes"
                )
            return 200, {"task": result}

        # Live parent fence: the caller's attempt is the parent's live,
        # unexpired leased attempt owned by this executor (doc 27 §3.5.1).
        if slug is not None:
            resolved_slug_project = self.resolve_project_id(slug)
            if resolved_slug_project != project_id:
                raise BridgeNotFoundError(
                    f"parent task {parent_task_id!r} is not in project {slug!r}"
                )
        if str(parent["status"]) != "running":
            raise BridgeConflictError(
                "parent task is not running",
                attempt=self._current_attempt_extra(parent_attempt_id),
            )
        attempt = self._attempt_row(parent_attempt_id)
        if (
            attempt is None
            or str(attempt["task_id"]) != parent_task_id
            or str(attempt["status"]) not in ("claimed", "running")
            or str(attempt["executor_id"] or "") != executor_id
            or str(attempt["lease_id"] or "") != lease_id
            or int(attempt["status_version"]) != status_version
        ):
            raise BridgeChildAdmissionForbiddenError(
                "the parent fence does not match the caller's live attempt"
            )
        from datetime import datetime, timezone

        expires = str(attempt["lease_expires_at"])
        now_dt = datetime.now(timezone.utc)
        try:
            expiry_dt = datetime.fromisoformat(expires)
        except ValueError:
            expiry_dt = None
        if expiry_dt is None or expiry_dt.tzinfo is None:
            expiry_dt = (
                expiry_dt.replace(tzinfo=timezone.utc)
                if expiry_dt is not None
                else now_dt
            )
        if expiry_dt <= now_dt:
            raise BridgeConflictError(
                "parent lease has expired",
                attempt=_attempt_wire_shape(attempt),
            )

        spec = expected_spec
        tasks, _media, _receipts = self._services()
        def command(uow):
            # Supply the committed task id on the tiny race where another
            # writer won the receipt between the read above and this UoW.
            existing = uow.query_one(
                "SELECT t.id AS task_id FROM tasks t "
                "JOIN command_receipts r ON r.primary_stream_id = t.event_stream_id "
                "WHERE r.project_id = ? AND r.idempotency_key = ? "
                "AND r.command_kind = 'core.task.create'",
                (project_id, idempotency_key),
            )
            stable_id = existing["task_id"] if existing is not None else None
            task = tasks.create(
                uow,
                project_id=project_id,
                capability=entry.capability_id,
                spec=spec,
                input_manifest=[],
                idempotency_key=idempotency_key,
                task_id=stable_id,
                max_attempts=3,
                actor_kind="executor",
                dependencies=dependencies,
            )
            return existing is not None, task

        replayed, task = UnitOfWork(self._writer).run(command)
        return (200 if replayed else 201), {"task": task.to_dict()}

    def _resolve_materialized_inputs(
        self,
        project_id: str,
        materialized: list[Any],
    ) -> list[dict[str, Any]]:
        """Resolve ``materialized_inputs`` into kernel manifest entries."""
        manifest: list[dict[str, Any]] = []
        with self._writer.read_only_connection() as conn:
            for index, item in enumerate(materialized):
                if not isinstance(item, dict):
                    raise BridgeBodyError(
                        f"materialized_inputs[{index}] must be an object"
                    )
                role = item.get("target") or item.get("role")
                media_id = item.get("media_id")
                kind = item.get("kind", "file")
                if not isinstance(role, str) or not role:
                    raise BridgeBodyError(
                        f"materialized_inputs[{index}].target is required"
                    )
                if not isinstance(media_id, str) or not media_id:
                    raise BridgeBodyError(
                        f"materialized_inputs[{index}].media_id is required"
                    )
                row = conn.execute(
                    "SELECT id FROM media WHERE id = ? AND project_id = ?",
                    (media_id, project_id),
                ).fetchone()
                if row is None:
                    raise BridgeSchemaIncompatibleError(
                        f"materialized_inputs[{index}] references unknown "
                        f"media {media_id!r}",
                        issues=[
                            BridgeIssue(
                                pointer=f"/materialized_inputs/{index}",
                                code="unknown_media_reference",
                                message=(
                                    f"media {media_id!r} does not exist in "
                                    "this project"
                                ),
                            )
                        ],
                    )
                manifest.append(
                    {
                        "role": role,
                        "media_id": media_id,
                        "kind": kind if isinstance(kind, str) else "file",
                    }
                )
        return manifest

    # -- R3: global deterministic claim (doc 27 §4.2) ------------------------

    def claim(
        self,
        *,
        executor_id: str,
        capabilities: list[str],
        lease_seconds: int = 300,
    ) -> dict[str, Any] | None:
        from astrid.core.ids import generate_lowercase_ulid
        from astrid.core.store.uow import UnitOfWork
        from astrid.core.util.time import utc_now_iso

        if not isinstance(executor_id, str) or not executor_id.strip():
            raise BridgeBodyError("executor_id must be a non-empty string")
        if (
            not isinstance(capabilities, list)
            or not capabilities
            or not all(isinstance(c, str) and c for c in capabilities)
        ):
            raise BridgeBodyError(
                "capabilities must be a non-empty array of capability ids"
            )
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, int
        ) or lease_seconds <= 0:
            raise BridgeBodyError("lease_seconds must be a positive integer")
        requested = frozenset(capabilities)
        tasks, _media, _receipts = self._services()

        def command(uow):
            now = utc_now_iso()
            rows = uow.query(
                "SELECT id, project_id, capability, priority, available_at "
                "FROM tasks WHERE status IN ('queued', 'blocked') "
                "ORDER BY priority DESC, available_at ASC, id ASC"
            )
            heads: dict[str, dict[str, Any]] = {}
            for row in rows:
                project_id = str(row["project_id"])
                if project_id in heads:
                    continue
                if str(row["available_at"]) > now:
                    continue
                if not self._hard_dependencies_satisfied(uow, str(row["id"])):
                    continue
                heads[project_id] = dict(row)
            ordered = sorted(
                heads.values(),
                key=lambda r: (-int(r["priority"]), str(r["available_at"]), str(r["id"])),
            )
            for head in ordered:
                if str(head["capability"]) not in requested:
                    continue
                result = tasks.claim(
                    uow,
                    project_id=str(head["project_id"]),
                    idempotency_key=f"reigh.claim:{generate_lowercase_ulid()}",
                    actor_kind="executor",
                    executor_id=executor_id,
                    lease_seconds=lease_seconds,
                )
                if result is not None:
                    return result
            return None

        won = UnitOfWork(self._writer).run(command)
        if won is None:
            return None
        return {
            "task": won.task.to_dict(),
            "attempt": won.attempt.to_dict(),
            "media": self._claim_media(won.task.input_manifest),
        }

    @staticmethod
    def _hard_dependencies_satisfied(uow, task_id: str) -> bool:
        hard_ids = [
            str(row["depends_on_task_id"])
            for row in uow.query(
                "SELECT depends_on_task_id FROM task_dependencies "
                "WHERE task_id = ? AND kind = 'hard'",
                (task_id,),
            )
        ]
        if not hard_ids:
            return True
        placeholders = ",".join("?" * len(hard_ids))
        satisfied = uow.query_one(
            "SELECT COUNT(*) AS n FROM tasks WHERE id IN ("
            + placeholders
            + ") AND status = 'succeeded'",
            hard_ids,
        )
        return int(satisfied["n"]) == len(hard_ids)

    def _claim_media(self, input_manifest: list[Any]) -> dict[str, Any]:
        """Resolve claimed input media to managed content references."""
        media_map: dict[str, Any] = {}
        if not isinstance(input_manifest, list):
            return media_map
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            for entry in input_manifest:
                if not isinstance(entry, dict):
                    continue
                media_id = entry.get("media_id")
                role = entry.get("role")
                if not media_id or not role:
                    continue
                row = conn.execute(
                    "SELECT id, content_hash, byte_size, mime_type FROM media "
                    "WHERE id = ?",
                    (str(media_id),),
                ).fetchone()
                if row is None:
                    continue
                media_map[str(role)] = {
                    "media_id": str(row["id"]),
                    "content_hash": str(row["content_hash"]),
                    "byte_size": int(row["byte_size"]),
                    "mime_type": str(row["mime_type"]),
                }
        return media_map

    # -- R5: heartbeat (non-event, no receipt; doc 27 §4.3) ------------------

    def heartbeat(
        self,
        *,
        task_id: str,
        attempt_no: int,
        attempt_id: str,
        lease_id: str,
        expected_status_version: int,
        lease_seconds: int = 300,
        progress: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json as _json

        from astrid.core.repositories.tasks import TaskAttemptNotFoundError
        from astrid.core.store.uow import UnitOfWork
        from astrid.core.util.time import utc_now_iso

        tasks, _media, _receipts = self._services()
        task_row = self._task_row(task_id)
        project_id = str(task_row["project_id"])
        attempt = self._attempt_row(attempt_id)
        if attempt is None:
            raise BridgeNotFoundError(
                f"attempt {attempt_id!r} was not found"
            )
        if int(attempt["attempt_no"]) != attempt_no:
            raise BridgeConflictError(
                f"attempt_no {attempt_no} does not match the referenced "
                "attempt",
                attempt=_attempt_wire_shape(attempt),
            )
        UnitOfWork(self._writer).run(
            lambda u: tasks.heartbeat(
                u,
                project_id=project_id,
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                expected_status_version=expected_status_version,
                lease_seconds=lease_seconds,
            )
        )
        if progress is not None:
            if not isinstance(progress, dict):
                raise BridgeBodyError("progress must be a JSON object")
            encoded = _json.dumps(progress, sort_keys=True)
            if len(encoded.encode("utf-8")) > self._MAX_PROGRESS_BYTES:
                raise BridgeBodyError(
                    f"progress exceeds {self._MAX_PROGRESS_BYTES} bytes"
                )
            merged = dict(attempt.get("progress_json") and _json.loads(str(attempt["progress_json"])) or {})
            merged.update(progress)
            merged_encoded = _json.dumps(merged, sort_keys=True)

            def merge(uow):
                uow.execute(
                    "UPDATE execution_attempts SET progress_json = ?, "
                    "updated_at = ? WHERE id = ? AND lease_id = ? "
                    "AND status IN ('claimed', 'running')",
                    (
                        merged_encoded,
                        utc_now_iso(),
                        attempt_id,
                        lease_id,
                    ),
                )

            UnitOfWork(self._writer).run(merge)
        fresh = self._attempt_row(attempt_id)
        if fresh is None:  # pragma: no cover - just heartbeated
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        return {"attempt": _attempt_wire_shape(fresh)}

    # -- R2: cancellation (common kernel service; doc 27 §4.5) ---------------

    def cancel(
        self,
        *,
        slug: str,
        task_id: str,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        from astrid.core.ids import generate_lowercase_ulid
        from astrid.core.repositories.tasks import TaskTransitionError
        from astrid.core.store.uow import UnitOfWork

        project_id = self.resolve_project_id(slug)
        task_row = self._task_row(task_id)
        if str(task_row["project_id"]) != project_id:
            raise BridgeNotFoundError(f"task {task_id!r} was not found")
        attempt_id = body.get("attempt_id")
        lease_id = body.get("lease_id")
        status_version = body.get("status_version")
        for name, value in (("attempt_id", attempt_id), ("lease_id", lease_id)):
            if value is not None and (not isinstance(value, str) or not value):
                raise BridgeBodyError(f"{name} must be a non-empty string")
        if status_version is not None and (
            isinstance(status_version, bool)
            or not isinstance(status_version, int)
            or status_version <= 0
        ):
            raise BridgeBodyError("status_version must be a positive integer")
        running_fenced = any(
            value is not None
            for value in (attempt_id, lease_id, status_version)
        )
        if str(task_row["status"]) == "running":
            if not running_fenced:
                raise BridgeConflictError(
                    "cancelling a running task requires the live attempt "
                    "fence",
                    attempt=self._current_attempt_extra(
                        str(task_row["winning_attempt_id"] or "") or None
                    ),
                )
        tasks, _media, _receipts = self._services()
        try:
            result = UnitOfWork(self._writer).run(
                lambda u: tasks.cancel(
                    u,
                    project_id=project_id,
                    task_id=task_id,
                    idempotency_key=f"reigh.cancel:{generate_lowercase_ulid()}",
                    actor_kind="local",
                    attempt_id=attempt_id,
                    lease_id=lease_id,
                    expected_status_version=status_version,
                )
            )
        except TaskTransitionError as exc:
            if exc.reason == "task_terminal":
                fresh = self._task_row(task_id)
                return {"task": self._task_summary(fresh)}
            raise self._conflict_from_transition(exc) from None
        return {
            "task": result.task.to_dict(),
            "attempt": (
                result.attempt.to_dict() if result.attempt else None
            ),
        }

    # -- R7: multipart atomic completion (doc 27 §4.4, §5) -------------------

    def complete(
        self,
        *,
        task_id: str,
        attempt_no: int,
        idempotency_key: str,
        fence: Mapping[str, Any],
        output_specs: list[Mapping[str, Any]],
        staged_files: list[Any],
    ) -> dict[str, Any]:
        from astrid.core.io.media_import import prepare_media_file
        from astrid.core.store.uow import UnitOfWork

        lease_id = fence.get("lease_id")
        status_version = fence.get("status_version")
        if not isinstance(lease_id, str) or not lease_id:
            raise BridgeBodyError("manifest.lease_id is required")
        if (
            isinstance(status_version, bool)
            or not isinstance(status_version, int)
            or status_version <= 0
        ):
            raise BridgeBodyError("manifest.status_version is required")
        if not output_specs:
            raise BridgeBodyError("manifest.outputs must be a non-empty array")

        by_field = {staged.field_name: staged for staged in staged_files}
        entries: list[dict[str, Any]] = []
        primaries = 0
        for index, spec_out in enumerate(output_specs):
            if not isinstance(spec_out, dict):
                raise BridgeBodyError(
                    f"manifest.outputs[{index}] must be an object"
                )
            key = spec_out.get("key")
            staged = by_field.get(key) if isinstance(key, str) else None
            if staged is None:
                raise BridgeBodyError(
                    f"manifest.outputs[{index}] references unknown part "
                    f"{key!r}"
                )
            declared_sha = spec_out.get("sha256")
            if declared_sha is not None and str(declared_sha) != staged.sha256:
                # Poisoned/mismatched bytes: zero authoritative rows.
                raise BridgeBodyError(
                    f"output {key!r} bytes do not match the declared sha256"
                )
            declared_size = spec_out.get("size")
            if declared_size is not None and int(declared_size) != staged.byte_size:
                raise BridgeBodyError(
                    f"output {key!r} size does not match the declared size"
                )
            prepared = prepare_media_file(staged.path)
            if prepared.digest != staged.sha256:  # pragma: no cover - defense
                raise BridgeBodyError(
                    f"output {key!r} failed server-side verification"
                )
            # The multipart route stages each retry at a fresh server-chosen
            # path, and prepare_media_file then derives a random temp
            # rel_path. Request identity includes rel_path, so pin it to
            # the byte digest: identical bytes replay, different bytes
            # cannot collide.
            prepared = dataclasses.replace(
                prepared, rel_path=f"uploads/{prepared.digest}"
            )
            is_primary = bool(spec_out.get("is_primary", index == 0))
            primaries += int(is_primary)
            entries.append(
                {
                    "ordinal": index,
                    "is_primary": is_primary,
                    "role": "result" if is_primary else str(spec_out.get("role", "artifact")),
                    "label": staged.filename,
                    "prepared": prepared,
                }
            )
        if primaries != 1:
            raise BridgeBodyError(
                "exactly one manifest.outputs entry must be primary"
            )

        # Durable media publication is deliberately outside the writer UoW.
        # A crash after this point may leave an unreferenced CAS object, but
        # can never leave a committed row pointing at a partial object.
        from astrid.core.io.media_import import publish_prepared_for_commit

        publications = publish_prepared_for_commit(
            self._projects_root,
            uuid.uuid4().hex,
            [entry["prepared"] for entry in entries],
        )
        for entry, publication in zip(entries, publications):
            entry["published"] = publication

        import json as _json

        task_row = self._task_row(task_id)
        project_id = str(task_row["project_id"])

        # Output policy (doc 27 §5 steps 6-7): parsed from the admitted
        # spec outside the writer lock; the repositories join the ONE
        # completion unit of work below.
        generation_request: dict[str, Any] | None = None
        registry_merge: dict[str, Any] | None = None
        try:
            spec = _json.loads(str(task_row["spec_json"]))
        except (ValueError, TypeError):
            spec = None
        policy = (
            spec.get("output_policy")
            if isinstance(spec, dict)
            else None
        )
        if isinstance(policy, dict):
            if policy.get("create_generation"):
                primary_prepared = next(
                    e["prepared"] for e in entries if e["is_primary"]
                )
                kind = primary_prepared.media_kind
                gen_params = {
                    key: policy[key]
                    for key in ("shot_id", "based_on_generation_id")
                    if policy.get(key) is not None
                }
                generation_request = {
                    "type": kind if kind in ("image", "video", "audio") else "other",
                    "params": gen_params or None,
                }
            visibility = policy.get("timeline_visibility")
            if isinstance(visibility, dict) and visibility.get("timeline_id"):
                primary_entry = next(e for e in entries if e["is_primary"])
                asset_key = visibility.get("asset_key") or (
                    f"task:{task_id}"
                )
                registry_merge = {
                    "timeline_id": str(visibility["timeline_id"]),
                    "entries": {
                        str(asset_key): {
                            # Resolved to the committed kernel media id by
                            # TaskRepository.complete after materialization,
                            # before the registry entry is persisted.
                            "task_output_ordinal": primary_entry["ordinal"],
                            "content_sha256": primary_entry["prepared"].digest,
                            "type": primary_entry["prepared"].mime_type,
                        }
                    },
                }


        manifest_attempt = None
        attempt_id = fence.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise BridgeBodyError("manifest.attempt_id is required")
        manifest_attempt = self._attempt_row(attempt_id)
        if manifest_attempt is None:
            raise BridgeNotFoundError(
                f"attempt {attempt_id!r} was not found"
            )
        if int(manifest_attempt["attempt_no"]) != attempt_no:
            raise BridgeConflictError(
                "attempt_no does not match the referenced attempt",
                attempt=_attempt_wire_shape(manifest_attempt),
            )
        tasks, media, _receipts = self._services()
        generation_repo = None
        timeline_repo = None
        if generation_request is not None:
            if self._generation_repo_factory is None:
                raise BridgeInternalError(
                    "output_policy.create_generation requires a composed "
                    "generation repository factory; compose the task bridge "
                    "at the serve root with generation_repo_factory"
                )
            generation_repo = self._generation_repo_factory()
        if registry_merge is not None:
            if self._timeline_repo_factory is None:
                raise BridgeInternalError(
                    "output_policy.timeline_visibility requires a composed "
                    "timeline repository factory; compose the task bridge "
                    "at the serve root with timeline_repo_factory"
                )
            timeline_repo = self._timeline_repo_factory()
        try:
            result = UnitOfWork(self._writer).run(
                lambda u: tasks.complete(
                    u,
                    project_id=project_id,
                    task_id=task_id,
                    attempt_id=attempt_id,
                    lease_id=lease_id,
                    expected_status_version=status_version,
                    idempotency_key=idempotency_key,
                    outputs=entries,
                    media_repo=media,
                    actor_kind="executor",
                    generation_repo=generation_repo,
                    generation_request=generation_request,
                    timeline_repo=timeline_repo,
                    registry_merge=registry_merge,
                )
            )
        except Exception:
            _cleanup_staged(staged_files)
            raise
        _cleanup_staged(staged_files)
        payload = result.to_dict()
        payload.pop("event_ids", None)  # receipt secrecy by construction
        # Completion provenance names the immutable build receipt that was
        # verified at serve composition. It remains outside the frozen
        # nine-key CommandReceipt shape and is omitted when serve has not
        # stamped a manifest (for example, direct library usage in tests).
        from astrid.core.integrations.reigh.boot_manifest import (
            load_boot_manifest_hash,
        )

        boot_hash = load_boot_manifest_hash(self._projects_root)
        if boot_hash is not None:
            payload["provenance"] = {
                "kind": "reigh.boot_manifest",
                "sha256": boot_hash,
            }
        return payload

    # -- R8: fenced failure (server applies max_attempts; doc 27 §4.5) -------

    def fail(
        self,
        *,
        task_id: str,
        attempt_no: int,
        idempotency_key: str,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        from astrid.core.store.uow import UnitOfWork

        attempt_id = body.get("attempt_id")
        lease_id = body.get("lease_id")
        status_version = body.get("status_version")
        error_payload = body.get("error")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise BridgeBodyError("attempt_id is required")
        if not isinstance(lease_id, str) or not lease_id:
            raise BridgeBodyError("lease_id is required")
        if (
            isinstance(status_version, bool)
            or not isinstance(status_version, int)
            or status_version <= 0
        ):
            raise BridgeBodyError("status_version is required")
        if not isinstance(error_payload, dict):
            raise BridgeBodyError("error must be an object")
        code = error_payload.get("code")
        message = error_payload.get("message")
        retryable = error_payload.get("retryable")
        if not isinstance(code, str) or not code:
            raise BridgeBodyError("error.code must be a non-empty string")
        if not isinstance(message, str):
            raise BridgeBodyError("error.message must be a string")
        if len(message) > self._MAX_ERROR_MESSAGE_CHARS:
            raise BridgeBodyError(
                f"error.message exceeds {self._MAX_ERROR_MESSAGE_CHARS} chars"
            )
        if not isinstance(retryable, bool):
            raise BridgeBodyError("error.retryable must be a boolean")
        bounded_error = {
            "code": code,
            "message": message,
            "retryable": retryable,
        }
        task_row = self._task_row(task_id)
        project_id = str(task_row["project_id"])
        attempt = self._attempt_row(attempt_id)
        if attempt is None:
            raise BridgeNotFoundError(f"attempt {attempt_id!r} was not found")
        if int(attempt["attempt_no"]) != attempt_no:
            raise BridgeConflictError(
                "attempt_no does not match the referenced attempt",
                attempt=_attempt_wire_shape(attempt),
            )
        tasks, _media, _receipts = self._services()
        result = UnitOfWork(self._writer).run(
            lambda u: tasks.fail(
                u,
                project_id=project_id,
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                expected_status_version=status_version,
                idempotency_key=idempotency_key,
                error=bounded_error,
                actor_kind="executor",
            )
        )
        return result.to_dict()

    # -- task reads (polling surface; doc 27 §4.1) ---------------------------

    def list_tasks(
        self,
        *,
        slug: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        project_id = self.resolve_project_id(slug)
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            rows = conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? "
                "ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?",
                (project_id, limit + 1, offset),
            ).fetchall()
        summaries = [self._task_summary(dict(row)) for row in rows[:limit]]
        next_offset = (
            offset + limit if len(rows) > limit else None
        )
        return {"tasks": summaries, "next_offset": next_offset}

    def task_detail(self, *, slug: str, task_id: str) -> dict[str, Any]:
        project_id = self.resolve_project_id(slug)
        task_row = self._task_row(task_id)
        if str(task_row["project_id"]) != project_id:
            raise BridgeNotFoundError(f"task {task_id!r} was not found")
        detail = self._task_summary(task_row)
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            attempts = [
                _attempt_detail_wire_shape(dict(row))
                for row in conn.execute(
                    "SELECT * FROM execution_attempts WHERE task_id = ? "
                    "ORDER BY attempt_no ASC",
                    (task_id,),
                ).fetchall()
            ]
            outputs = [
                _task_output_wire_shape(row)
                for row in conn.execute(
                    "SELECT ordinal, role, media_id, is_primary, "
                    "params_json FROM task_outputs "
                    "WHERE task_id = ? ORDER BY ordinal ASC",
                    (task_id,),
                ).fetchall()
            ]
        detail["attempts"] = attempts
        detail["outputs"] = outputs
        return {"task": detail}

    # -- Gallery reads (doc 27 §4.1) -----------------------------------------

    def _generation_repository(self) -> Any:
        """The pack generation repository composed at the serve root."""
        if self._generation_repo_factory is None:
            raise BridgeInternalError(
                "the generation repository factory is not composed on this "
                "bridge"
            )
        return self._generation_repo_factory()

    def list_generations(
        self,
        *,
        slug: str,
        limit: int = 50,
        cursor: str | None = None,
        starred: bool | None = None,
    ) -> dict[str, Any]:
        """One bounded gallery page with primary-variant summaries.

        Ordered ``created_at DESC, id ASC``; deleted generations are
        hidden; ``next_cursor`` is ``None`` at the end of the project.
        """
        from astrid.core.util.paging import decode_keyset_cursor

        limit = max(1, min(int(limit), 200))
        if cursor is not None:
            if not isinstance(cursor, str) or not cursor:
                raise BridgeBodyError("cursor must be a non-empty string")
            try:
                decode_keyset_cursor(cursor, width=2)
            except ValueError as exc:
                raise BridgeBodyError(str(exc)) from None
        page = self._generation_repository().page(
            self._writer,
            self.resolve_project_id(slug),
            limit=limit,
            cursor=cursor,
            starred_only=bool(starred),
        )
        generations = [
            {
                "generation_id": row.id,
                "name": row.name,
                "type": row.type,
                "starred": row.starred,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "primary": (
                    {
                        "media_id": row.primary_media_id,
                        "variant_type": row.primary_variant_type,
                    }
                    if row.primary_media_id is not None
                    else None
                ),
                "variant_count": row.variant_count,
            }
            for row in page.rows
        ]
        return {"generations": generations, "next_cursor": page.next_cursor}

    def generation_detail(
        self, *, slug: str, generation_id: str
    ) -> dict[str, Any]:
        """Full generation detail: row, variants, and shot placements."""
        from astrid.core.repositories.errors import RepositoryError

        project_id = self.resolve_project_id(slug)
        try:
            model = self._generation_repository().show(
                self._writer, project_id, generation_id
            )
        except RepositoryError as exc:
            # Plugin law: the kernel adapter cannot name pack exception
            # classes, so the miss family is narrowed by its stable class
            # names under the kernel repository-error base.
            if type(exc).__name__ in (
                "GenerationNotFoundError",
                "GenerationDeletedError",
            ):
                raise BridgeGenerationNotFoundError(
                    f"generation {generation_id!r} was not found"
                ) from None
            raise
        # Wire order is recency-first (doc 27 §4.1 gallery posture):
        # created_at DESC with id ASC as the deterministic tiebreak.
        by_id = sorted(model.variants, key=lambda variant: variant.id)
        variants = sorted(
            by_id, key=lambda variant: variant.created_at, reverse=True
        )
        return {
            "generation": {
                "generation_id": model.id,
                "project_id": model.project_id,
                "task_id": model.task_id,
                "type": model.type,
                "name": model.name,
                "based_on_generation_id": model.based_on_generation_id,
                "parent_generation_id": model.parent_generation_id,
                "child_order": model.child_order,
                "params": dict(model.params),
                "starred": model.starred,
                "deleted_at": model.deleted_at,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
                "variants": [variant.to_dict() for variant in variants],
                "items": self._generation_placements(
                    project_id, model.id
                ),
            }
        }

    def _generation_placements(
        self, project_id: str, generation_id: str
    ) -> list[dict[str, Any]]:
        """Document-native shot placements of one generation.

        Placement state lives in the CAS-versioned timeline documents
        (doc 17 §8.3), never in relational rows; this read-only scan
        walks each project timeline's parsed ``document_json`` and
        collects every placement node naming the generation.
        """
        import json

        placements: list[dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, Mapping):
                if (
                    node.get("generation_id") == generation_id
                    and isinstance(node.get("shot_id"), str)
                    and node["shot_id"]
                ):
                    placements.append(
                        {
                            "shot_id": node["shot_id"],
                            "timeline_frame": node.get("timeline_frame"),
                        }
                    )
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            rows = conn.execute(
                "SELECT document_json FROM timelines WHERE project_id = ? "
                "ORDER BY created_at ASC, id ASC",
                (project_id,),
            ).fetchall()
        for row in rows:
            try:
                document = json.loads(str(row["document_json"]))
            except ValueError:
                continue
            walk(document)
        return placements

    @staticmethod
    def _task_summary(row: Mapping[str, Any]) -> dict[str, Any]:
        import json

        try:
            spec = json.loads(str(row["spec_json"]))
        except (KeyError, TypeError, ValueError):
            spec = None
        summary = {
            "task_id": str(row["id"]),
            "project_id": str(row["project_id"]),
            "capability": str(row["capability"]),
            "status": str(row["status"]),
            "spec": spec if isinstance(spec, dict) else None,
            "priority": int(row["priority"]),
            "max_attempts": int(row["max_attempts"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "finished_at": row["finished_at"],
            "winning_attempt_id": row["winning_attempt_id"],
        }
        if str(row["status"]) == "running":
            summary["current_attempt"] = None
        return summary

    def _conflict_from_transition(self, exc) -> BridgeConflictError:
        return BridgeConflictError(
            str(getattr(exc, "reason", "conflict")),
            attempt=self._current_attempt_extra(
                getattr(exc, "attempt_id", None)
            ),
        )


def _cleanup_staged(staged_files: list[Any]) -> None:
    for staged in staged_files:
        try:
            Path(staged.path).unlink(missing_ok=True)
        except OSError:
            pass


def _sqlite_row_factory(cursor: Any, row: Any) -> Any:
    import sqlite3

    return sqlite3.Row(cursor, row)


__all__ = [
    "BridgeCapabilityUnavailableError",
    "BridgeChildAdmissionForbiddenError",
    "BridgeConflictError",
    "BridgeGenerationNotFoundError",
    "BridgeNotFoundError",
    "BridgeTaskMismatchError",
    "ReighTaskBridge",
]
