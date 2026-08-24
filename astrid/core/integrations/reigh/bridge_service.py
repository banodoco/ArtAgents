"""Repository-neutral bridge DTOs and errors (m1 plan step 18).

The repository-backed bridge (frozen ``docs/contracts/astrid-bridge-v10.md``)
is implemented as two layers:

- this module — **repository-neutral** frozen DTOs (health, project row,
  timeline row, timeline load, save request) and the typed bridge error
  family with the exact frozen status codes and error codes, plus the
  ``${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`` path derivation;
- ``astrid/packs/timeline/bridge.py`` — the pack adapter that maps
  repository reads/CAS saves and repository errors onto these DTOs/errors.

Nothing in this module imports a repository, an event service, or a pack:
the DTOs and errors are pure wire contracts, so any future repository
adapter (shots, references) reuses them unchanged. Internal receipt fields
(``txn_id``, ``request_hash``, ``idempotency_key``, project/stream
sequences, event ids) are deliberately absent from every DTO — receipt
secrecy (contract §7) is enforced by construction, not by filtering.
"""

from __future__ import annotations

import dataclasses
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar

# ---------------------------------------------------------------------------
# Wire constants (frozen contract §2, §9)
# ---------------------------------------------------------------------------

ASTROID_DIR_NAME = ".astrid"
"""Managed-data directory under the projects root (decision artifact §5)."""

ASTROID_DATABASE_NAME = "astrid.sqlite3"
"""The repository-backed bridge database file (decision artifact §5)."""

BRIDGE_ERROR_ENVELOPE_KEYS: tuple[str, ...] = ("error", "detail")
"""Every error body is exactly ``{"error", "detail"}`` plus status extras."""

RECEIPT_SECRECY_FIELDS: frozenset[str] = frozenset(
    {
        "txn_id",
        "request_hash",
        "idempotency_key",
        "first_project_seq",
        "last_project_seq",
        "event_ids_json",
        "result_json",
        "event_ids",
        "project_seq",
        "stream_seq",
    }
)
"""Receipt/event internals that must never appear in any bridge response."""

# ---------------------------------------------------------------------------
# Path derivation
# ---------------------------------------------------------------------------


def derive_database_path(projects_root: str | Path) -> Path:
    """Return the repository-backed database path for a projects root.

    ``${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`` (decision artifact
    §5). The parent directory is *not* created here — the serve composition
    root creates it when the writer opens the database.
    """
    return Path(projects_root) / ASTROID_DIR_NAME / ASTROID_DATABASE_NAME


# ---------------------------------------------------------------------------
# Frozen DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """``GET /health`` payload (contract §3)."""

    ok: bool
    projects_root: str

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "projects_root": self.projects_root}


@dataclass(frozen=True, slots=True)
class ProjectRow:
    """One sorted ``GET /projects`` row (contract §4)."""

    slug: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "name": self.name}


@dataclass(frozen=True, slots=True)
class TimelineRow:
    """One timeline discovery row (contract §5.1)."""

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "slug": self.slug,
            "name": self.name,
            "is_default": self.is_default,
        }


@dataclass(frozen=True, slots=True)
class TimelineLoad:
    """The frozen load shape (contract §5.2) and save response (§6.2)."""

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool
    config: Mapping[str, Any]
    registry: Mapping[str, Any]
    config_version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "slug": self.slug,
            "name": self.name,
            "is_default": self.is_default,
            "config": dict(self.config),
            "registry": dict(self.registry),
            "config_version": self.config_version,
        }


_MISSING = object()


@dataclass(frozen=True, slots=True)
class TimelineSaveRequest:
    """The parsed ``POST .../save`` request body (contract §6.1).

    ``parse`` enforces the route-level validation before any repository
    call: ``config``/``registry`` must be JSON objects and
    ``expected_version`` must be an integer (a boolean is not a version).
    """

    config: Mapping[str, Any]
    registry: Mapping[str, Any]
    expected_version: int

    @classmethod
    def parse(cls, body: Any) -> TimelineSaveRequest:
        if not isinstance(body, Mapping):
            raise BridgeBodyError(
                "request body must be a JSON object"
            )
        config = body.get("config", _MISSING)
        registry = body.get("registry", _MISSING)
        expected_version = body.get("expected_version", _MISSING)
        if config is _MISSING or not isinstance(config, Mapping):
            raise BridgeConfigError("config must be a JSON object")
        if registry is _MISSING or not isinstance(registry, Mapping):
            raise BridgeRegistryError("registry must be a JSON object")
        if expected_version is _MISSING or isinstance(
            expected_version, bool
        ) or not isinstance(expected_version, int):
            raise BridgeExpectedVersionError(
                "expected_version must be an integer (a boolean is not a "
                "version)"
            )
        return cls(
            config=config,
            registry=registry,
            expected_version=expected_version,
        )


# ---------------------------------------------------------------------------
# Typed bridge errors (frozen contract §2.2)
# ---------------------------------------------------------------------------


class BridgeError(RuntimeError):
    """Base error for the repository-backed bridge.

    Every concrete error carries the frozen HTTP status and error code plus
    a human-readable detail; ``to_dict`` produces exactly the §2.2 envelope
    (``error``/``detail``) with the status-specific extras (``config_version``
    for 409, ``issues`` for 422). Internal receipt fields never appear.
    """

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "internal"

    def __init__(self, detail: str) -> None:
        self.detail: str = detail
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.code,
            "detail": self.detail,
        }
        return payload


class BridgeBodyError(BridgeError):
    """``400 invalid_body`` — body is not valid JSON or not an object."""

    status_code = 400
    code = "invalid_body"


class BridgeConfigError(BridgeError):
    """``400 invalid_config`` — config missing or not an object."""

    status_code = 400
    code = "invalid_config"


class BridgeRegistryError(BridgeError):
    """``400 invalid_registry`` — registry missing or not an object."""

    status_code = 400
    code = "invalid_registry"


class BridgeExpectedVersionError(BridgeError):
    """``400 invalid_expected_version`` — not an integer (or a boolean)."""

    status_code = 400
    code = "invalid_expected_version"


class BridgeInvalidProjectError(BridgeError):
    """``400 invalid_project`` — the ``:slug`` fails project slug grammar."""

    status_code = 400
    code = "invalid_project"


class BridgeInvalidTimelineError(BridgeError):
    """``400 invalid_timeline`` — ``:ref`` is not UUID/ULID/slug."""

    status_code = 400
    code = "invalid_timeline"


class BridgeProjectNotFoundError(BridgeError):
    """``404 project_not_found`` — no project row for the slug."""

    status_code = 404
    code = "project_not_found"


class BridgeTimelineNotFoundError(BridgeError):
    """``404 timeline_not_found`` — no timeline for the ref in the project."""

    status_code = 404
    code = "timeline_not_found"


class BridgeGenerationNotFoundError(BridgeError):
    """``404 generation_not_found`` — unknown, foreign, or deleted id."""

    status_code = 404
    code = "generation_not_found"


class BridgeVersionConflictError(BridgeError):
    """``409 timeline_version_conflict`` — stale expected head.

    Adds ``config_version`` (the current head) to the §2.2 envelope; the
    stale save changed zero rows.
    """

    status_code = 409
    code = "timeline_version_conflict"

    def __init__(self, detail: str, *, config_version: int) -> None:
        self.config_version: int = config_version
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["config_version"] = self.config_version
        return payload


@dataclass(frozen=True, slots=True)
class BridgeIssue:
    """One ``422 schema_incompatible`` issue (contract §2.2)."""

    pointer: str = ""
    code: str = "schema_incompatible"
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "pointer": self.pointer,
            "code": self.code,
            "message": self.message,
        }


class BridgeSchemaIncompatibleError(BridgeError):
    """``422 schema_incompatible`` — config/registry validation failed.

    Adds ``issues[]`` to the §2.2 envelope. A schema rejection is a typed
    422, never a connection-close 500 (contract §6.2).
    """

    status_code = 422
    code = "schema_incompatible"

    def __init__(
        self,
        detail: str,
        *,
        issues: list[BridgeIssue] | None = None,
    ) -> None:
        self.issues: list[BridgeIssue] = list(issues or [])
        if not self.issues:
            self.issues.append(BridgeIssue(message=detail))
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["issues"] = [issue.to_dict() for issue in self.issues]
        return payload


class BridgeInternalError(BridgeError):
    """``500 internal`` — an unexpected repository/service failure.

    Defensive only: the bridge surfaces typed 400/404/409/422 for every
    expected repository outcome. The body never includes exception details
    that could leak receipt or sequence internals.
    """

    status_code = 500
    code = "internal"


class BridgeNotFoundError(BridgeError):
    """``404 not_found`` — unknown task, attempt, or project."""

    status_code = 404
    code = "not_found"


class BridgeTaskMismatchError(BridgeError):
    """``409 idempotency_mismatch`` — key reused with different bytes."""

    status_code = 409
    code = "idempotency_mismatch"


class BridgeConflictError(BridgeError):
    """``409 conflict`` — a fenced transition was rejected.

    When the owning attempt is known, the ``attempt`` extra carries the
    current attempt read model (doc 27 §4.6: only the minimal resync data,
    never the full task/attempt model).
    """

    status_code = 409
    code = "conflict"

    def __init__(
        self,
        detail: str,
        *,
        attempt: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.attempt = dict(attempt) if attempt else None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        if self.attempt is not None:
            payload["attempt"] = self.attempt
        return payload


class BridgeCapabilityUnavailableError(BridgeError):
    """``422 capability_unavailable`` — unknown, dead, or unprobed."""

    status_code = 422
    code = "capability_unavailable"


class BridgeChildAdmissionForbiddenError(BridgeError):
    """``403 child_admission_forbidden`` — the executor-only gate."""

    status_code = 403
    code = "child_admission_forbidden"


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
            # Dual-use rows (doc 27 §3.1): join_clips_orchestrator and
            # travel_stitch are child_only AND publicly derivable through
            # their families. The §3.1 family-derivation table is the one
            # authority for what a browser may admit; executor-child-only
            # names never reach here because resolve_family_capability's
            # direct-name fallback rejects every child_only row with 403.
            check_available(entry)
            # Digest fence + provenance snapshot (pin the data, not the
            # code): verify the vendored workflow against its pinned SHA-256
            # BEFORE any write and carry the exact parsed bytes into the
            # attempt spec, so execution replays admitted bytes even if the
            # on-disk file drifts afterwards.
            workflow_snapshot = (
                load_workflow_snapshot(entry)
                if entry.template is not None
                else None
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
        manifest = self._resolve_materialized_inputs(project_id, materialized)
        spec = {
            "schema_version": 1,
            "family": entry.family,
            "source_task_type": entry.capability_id,
            "params": dict(task_input),
            "output_policy": dict(entry.output_policy),
        }
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

        replayed, task = UnitOfWork(self._writer).run(command)
        return (200 if replayed else 201), {"task": task.to_dict()}

    def admit_child(
        self,
        *,
        slug: str | None,
        body: Mapping[str, Any],
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]]:
        """T8 hard gate: fenced executor-only child admission (§3.5).

        Returns ``(201, {"task": ...})`` on first commit and ``(200,
        {"task": ...})`` on a deterministic-key replay — the SAME child
        row, never a duplicate.
        """
        from astrid.core.integrations.reigh.capabilities import (
            check_available,
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
        from astrid.core.integrations.reigh.orchestrator_transitions import (
            orch_child_key,
        )

        expected_key = orch_child_key(parent_task_id, str(role), index)
        if idempotency_key != expected_key:
            raise BridgeChildAdmissionForbiddenError(
                f"child admission requires the deterministic key "
                f"{expected_key!r}"
            )

        family = body.get("family")
        try:
            entry = resolve_child_capability(
                family if isinstance(family, str) else ""
            )
            # Same availability gate as public admission (review-N2
            # symmetry): a child whose binding prerequisite closure is
            # open is a typed 422, never a silent later failure.
            check_available(entry)
        except Exception as exc:  # noqa: BLE001 - narrowed below
            from astrid.core.integrations.reigh.capabilities import (
                CapabilityUnavailable,
                ChildAdmissionForbidden,
            )

            if isinstance(exc, ChildAdmissionForbidden):
                raise BridgeChildAdmissionForbiddenError(str(exc)) from None
            if isinstance(exc, CapabilityUnavailable):
                raise BridgeCapabilityUnavailableError(
                    f"{exc.identifier}: {exc.hint}"
                ) from None
            raise

        # Replay-first determinism: the deterministic key is the one
        # authority for child identity. A retry of an already-admitted
        # child returns the SAME row without re-paying the live parent
        # fence — the original admission already proved executor
        # authority, and a heartbeat between attempt N and retry N+1
        # advances status_version without changing the answer.
        replay = self._existing_child_receipt(idempotency_key)
        parent = (
            None if replay is not None else self._task_row(parent_task_id)
        )
        project_id = str(
            replay["project_id"]
            if replay is not None
            else parent["project_id"]
        )
        if slug is not None:
            resolved_slug_project = self.resolve_project_id(slug)
            if resolved_slug_project != project_id:
                raise BridgeNotFoundError(
                    f"parent task {parent_task_id!r} is not in project "
                    f"{slug!r}"
                )

        if replay is None:
            # Live parent fence (doc 27 §3.5.1): only NEW admissions pay
            # this gate. Collect the observable facts, then arbitrate
            # EXCLUSIVELY through the checked transition table — no
            # inline verdict logic beside it.
            parent_running = str(parent["status"]) == "running"
            attempt = self._attempt_row(parent_attempt_id)
            fence_valid = (
                attempt is not None
                and str(attempt["task_id"]) == parent_task_id
                and str(attempt["status"]) in ("claimed", "running")
                and str(attempt["executor_id"] or "") == executor_id
                and str(attempt["lease_id"] or "") == lease_id
                and int(attempt["status_version"]) == status_version
            )
            lease_unexpired = False
            if fence_valid:
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
                lease_unexpired = expiry_dt > now_dt
            from astrid.core.integrations.reigh.orchestrator_transitions import (
                FenceFacts,
                Verdict,
                classify_admission,
            )

            verdict = classify_admission(
                FenceFacts(
                    already_receipted=False,
                    parent_running=parent_running,
                    fence_valid=fence_valid,
                    lease_unexpired=lease_unexpired,
                )
            )
            if verdict is Verdict.CONFLICT_PARENT_NOT_RUNNING:
                raise BridgeConflictError(
                    "parent task is not running",
                    attempt=self._current_attempt_extra(parent_attempt_id),
                )
            if verdict is Verdict.CONFLICT_LEASE_EXPIRED:
                raise BridgeConflictError(
                    "parent lease has expired",
                    attempt=_attempt_wire_shape(attempt),
                )
            if verdict is not Verdict.ADMIT_NEW:
                raise BridgeChildAdmissionForbiddenError(
                    "the parent fence does not match the caller's live "
                    "attempt"
                )

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
        spec = {
            "schema_version": 1,
            "family": entry.family,
            "source_task_type": entry.capability_id,
            "params": dict(task_input),
            "output_policy": dict(entry.output_policy),
        }
        tasks, _media, _receipts = self._services()

        def command(uow):
            # Same stable-id replay contract as public admission: the
            # kernel receipt gate hashes task_id into the request, so a
            # fresh ULID under a retried key would mismatch. The lookup
            # runs INSIDE the writer-serialized unit of work, so two
            # concurrent admissions of one (role, index) converge on the
            # winner's row — exactly one child per deterministic key.
            existing = uow.query_one(
                "SELECT t.id AS task_id FROM tasks t "
                "JOIN command_receipts r "
                "ON r.primary_stream_id = t.event_stream_id "
                "WHERE r.project_id = ? AND r.idempotency_key = ?",
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
                actor_kind="executor",
                task_id=stable_id,
                max_attempts=3,
                dependencies=dependencies,
            )
            return existing is not None, task

        replayed, task = UnitOfWork(self._writer).run(command)
        return (200 if replayed else 201), {"task": task.to_dict()}

    def _existing_child_receipt(self, idempotency_key: str) -> dict | None:
        """Read-only probe: has this deterministic key admitted already?

        The deterministic child-key namespace (see
        ``orchestrator_transitions.orch_child_key``) is owned
        exclusively by child admission, so the create-kind receipt keyed
        by this string alone identifies the prior admission; the
        in-unit-of-work join in :meth:`admit_child` still scopes by
        project before any mutation.
        """
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _sqlite_row_factory
            row = conn.execute(
                "SELECT project_id FROM command_receipts "
                "WHERE idempotency_key = ? AND command_kind = ?",
                (idempotency_key, "core.task.create"),
            ).fetchone()
        return dict(row) if row is not None else None

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
        # Operator cancellation is deliberately cooperative: the operator
        # does not own executor-private attempt/lease/version facts.  The
        # single writer still atomically makes cancellation the terminal
        # winner, and a handler that is already outside SQLite can only lose
        # its later fenced completion.  Executor callers may provide the
        # complete fence, but the repository rejects partial fences before
        # mutation; keep that contract here by forwarding all supplied facts.
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
        from astrid.core.integrations.reigh.boot_manifest import (
            load_boot_manifest_hash,
        )
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

        # Doc 27 §5 publication half: every verified object is durably
        # published into the SHA-256 tree BEFORE ``BEGIN IMMEDIATE``; the
        # in-lock boundary is then O(stat) presence validation only.
        import json as _json
        import uuid as _uuid

        from astrid.core.io.media_import import publish_prepared_for_commit

        txn_id = _uuid.uuid4().hex

        publications = publish_prepared_for_commit(
            self._projects_root,
            txn_id,
            [entry["prepared"] for entry in entries],
        )
        for entry, publication in zip(entries, publications):
            entry["published"] = publication

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
        # B9 completion provenance: name the boot manifest that governed
        # this build in the attempt-completion result. The frozen nine-key
        # CommandReceipt shape is NOT extended — this rides the bridge
        # response only, and only when a manifest was stamped at boot.
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
                _attempt_wire_shape(dict(row))
                for row in conn.execute(
                    "SELECT * FROM execution_attempts WHERE task_id = ? "
                    "ORDER BY attempt_no ASC",
                    (task_id,),
                ).fetchall()
            ]
            outputs = [
                dict(row)
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
        import json as _json

        try:
            spec = _json.loads(str(row["spec_json"]))
        except (ValueError, TypeError):
            spec = {}
        if not isinstance(spec, dict):
            spec = {}
        summary = {
            "task_id": str(row["id"]),
            "project_id": str(row["project_id"]),
            "capability": str(row["capability"]),
            "status": str(row["status"]),
            # The admitted spec rides the polling read (doc 27 §4.1) so
            # a restarted executor re-derives its orchestration plan
            # from persisted state alone — crash replay never trusts
            # crashed-process memory.
            "spec": spec,
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


def _sqlite_row_factory(cursor, row):  # noqa: ANN001 - sqlite3 protocol
    import sqlite3

    return sqlite3.Row(cursor, row)


__all__ = [
    "ASTROID_DATABASE_NAME",
    "ASTROID_DIR_NAME",
    "BRIDGE_ERROR_ENVELOPE_KEYS",
    "BridgeBodyError",
    "BridgeGenerationNotFoundError",
    "BridgeCapabilityUnavailableError",
    "BridgeChildAdmissionForbiddenError",
    "BridgeConfigError",
    "BridgeConflictError",
    "BridgeError",
    "BridgeExpectedVersionError",
    "BridgeInternalError",
    "BridgeInvalidProjectError",
    "BridgeInvalidTimelineError",
    "BridgeIssue",
    "BridgeNotFoundError",
    "BridgeProjectNotFoundError",
    "BridgeRegistryError",
    "BridgeSchemaIncompatibleError",
    "BridgeTaskMismatchError",
    "BridgeTimelineNotFoundError",
    "BridgeVersionConflictError",
    "HealthStatus",
    "ProjectRow",
    "RECEIPT_SECRECY_FIELDS",
    "ReighTaskBridge",
    "TimelineLoad",
    "TimelineRow",
    "TimelineSaveRequest",
    "derive_database_path",
]
