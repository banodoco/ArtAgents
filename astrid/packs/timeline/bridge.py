"""Timeline bridge adapter over the project and timeline SDK services.

(m4 plan step 20, task T21.) This adapter is the service-backed bridge's
read/CAS surface: it translates the frozen HTTP contract
(``docs/contracts/astrid-bridge-v10.md``) into **typed SDK service methods**
and maps every stable service error onto the frozen bridge DTOs
(``400 invalid_project``/``invalid_timeline``, ``404 project_not_found``/
``timeline_not_found``, ``409 timeline_version_conflict`` with the current
``config_version``, ``422 schema_incompatible`` with ``issues[]``). It is
composed over the standard application's project and timeline services at
the gateway serve composition root (``astrid.packs.compose_standard_bridge``)
and holds no SQL and no writer of its own; there is no legacy authority
fallback anywhere in this module.

Mapping rules kept here:

- ``:slug`` is validated against the project slug grammar before any read
  (``400 invalid_project``); a missing project is ``404 project_not_found``
  (never an empty authority-dependent view);
- ``:ref`` is validated as canonical UUID, lowercase ULID, or slug before
  any read (``400 invalid_timeline``); the service resolves it project-scoped
  in §8 order;
- ``POST .../save`` bodies are parsed by
  :class:`~astrid.core.integrations.reigh.bridge_service.TimelineSaveRequest`
  (``400 invalid_body/invalid_config/invalid_registry/invalid_expected_version``);
  a stale expected head maps to ``409 timeline_version_conflict`` with the
  current ``config_version`` re-read through the service (the CAS changed
  zero rows);
- **bridge saves supply the hidden deterministic bridge save key** (bridge
  §6.1 derivation: command kind + project/timeline identity + integer
  expected head + canonical payload digest). The key is passed through the
  service's caller-key slot into the same receipt-gated atomic save the SDK
  uses with its caller-visible keys, so a lost response replays the exact
  committed result with zero new rows — identical to an SDK retry under its
  own key. The key itself never appears in any response;
- every response is a frozen DTO whose serialization can never include a
  receipt field or an idempotency key (receipt secrecy, §7, enforced by
  construction).

Compatibility note (temporary, removed by the T22 constructor-injection
cutover): the constructor also accepts the repository pair
(``ProjectRepository``/``TimelineRepository``) used by the pre-T22
repository-provider fixtures. That legacy path is exercised only by those
fixtures and is migrated to services in plan step 21.
"""

from __future__ import annotations

import base64
import hmac
import json
import re
import secrets
import sqlite3
from collections.abc import Mapping
from typing import Any

from astrid.core.integrations.reigh.bridge_service import (
    BridgeCursorError,
    BridgeInternalError,
    BridgeInvalidProjectError,
    BridgeInvalidTimelineError,
    BridgeIssue,
    BridgeProjectNotFoundError,
    BridgeSchemaIncompatibleError,
    BridgeTimelineNotFoundError,
    BridgeVersionConflictError,
    HealthStatus,
    ProjectRow,
    RunawayTransitionPage,
    TimelineLoad,
    TimelineRow,
    TimelineSaveRequest,
)
from astrid.core.receipts import ReceiptMismatchError
from astrid.core.receipts.canonical import CanonicalizationError, request_hash
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.projects import (
    ProjectNotFoundError,
    ProjectRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.timeline.repository import (
    TIMELINE_SAVE_COMMAND_KIND,
    TimelineNotFoundError,
    TimelineRepository,
    TimelineValidationError,
    TimelineVersionConflictError,
)
from astrid.sdk.projects import ProjectsService
from astrid.sdk.timelines import TimelinesService

_PROJECT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
"""Project slug grammar, mirroring the project repository's immutable rule.

The bridge validates ``:slug`` before any read so a malformed slug is a
``400 invalid_project``, never a service lookup.
"""

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
"""Canonical lowercase UUID grammar (bridge §8 order 1)."""

_ULID_RE = re.compile(r"^[0123456789abcdefghjkmnpqrstvwxyz]{26}$")
"""Lowercase 26-character Crockford ULID grammar (bridge §8 order 2)."""

_RUNAWAY_CURSOR_VERSION = 1
_MAX_CURSOR_BYTES = 2_048


def _encode_runaway_cursor(payload: Mapping[str, Any], *, key: bytes) -> str:
    raw = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    digest = hmac.digest(key, raw, "sha256")[:18]
    return base64.urlsafe_b64encode(raw + b"." + digest).rstrip(b"=").decode("ascii")


def _decode_runaway_cursor(cursor: str, *, key: bytes) -> dict[str, Any]:
    if not isinstance(cursor, str) or not cursor or len(cursor) > _MAX_CURSOR_BYTES:
        raise BridgeCursorError("cursor must be a bounded non-empty string")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        raw, supplied = decoded.rsplit(b".", 1)
        expected = hmac.digest(key, raw, "sha256")[:18]
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("cursor authentication mismatch")
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - one typed wire error
        raise BridgeCursorError("cursor is malformed or has been altered") from exc
    if not isinstance(payload, dict) or payload.get("v") != _RUNAWAY_CURSOR_VERSION:
        raise BridgeCursorError("cursor version is unsupported")
    return payload


def _is_timeline_ref(ref: str) -> bool:
    """Whether *ref* matches one of the three frozen address forms (§8)."""
    return (
        _UUID_RE.fullmatch(ref) is not None
        or _ULID_RE.fullmatch(ref) is not None
        or _PROJECT_SLUG_RE.fullmatch(ref) is not None
    )


class TimelineBridgeAdapter:
    """Stateless adapter composing the project + timeline services.

    A single instance is safe to share across HTTP requests. In the
    service-backed composition every read and mutation runs through the
    typed SDK services (which open one unit of work over the single shared
    writer per mutation); the adapter itself never executes SQL and never
    constructs a service. The repository pair accepted by the constructor
    is the temporary pre-T22 compatibility path only.
    """

    def __init__(
        self,
        *,
        writer: DatabaseWriter,
        projects: ProjectRepository | ProjectsService,
        timelines: TimelineRepository | TimelinesService,
        runaway: Any | None = None,
        runaway_evidence: Any | None = None,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._timelines = timelines
        self._runaway = runaway
        self._runaway_evidence = runaway_evidence
        # Process-local signing makes cursors opaque and tamper-evident. A
        # server restart intentionally invalidates outstanding read cursors.
        self._runaway_cursor_key = secrets.token_bytes(32)
        self._service_mode = isinstance(projects, ProjectsService) and isinstance(
            timelines, TimelinesService
        )

    def list_runaway_transitions(
        self, project_slug: str, *, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return project-scoped typed Runaway transitions for editor viewers."""
        project_id = self._resolve_project_id(project_slug)
        if self._runaway is None:
            raise BridgeInternalError("the Runaway repository is not composed")
        try:
            with self._writer.read_only_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = self._runaway.list(
                    conn, project_id=project_id, run_id=run_id
                )
        except Exception as exc:  # noqa: BLE001 - normalize local read errors
            raise BridgeInternalError(str(exc)) from exc
        return [row.to_dict() for row in rows]

    def page_runaway_transitions(
        self,
        project_slug: str,
        *,
        run_id: str | None = None,
        limit: int = 1_000,
        cursor: str | None = None,
    ) -> RunawayTransitionPage:
        """Return a bounded, opaque-cursor page from one immutable snapshot."""

        project_id = self._resolve_project_id(project_slug)
        if self._runaway is None:
            raise BridgeInternalError("the Runaway repository is not composed")

        snapshot_rowid = None
        after_ordinal = after_run_id = after_id = None
        if cursor is not None:
            payload = _decode_runaway_cursor(
                cursor, key=self._runaway_cursor_key
            )
            if payload.get("p") != project_id or payload.get("r") != run_id:
                raise BridgeCursorError(
                    "cursor does not belong to this project and run filter"
                )
            snapshot_rowid = payload.get("s")
            after_ordinal = payload.get("o")
            after_run_id = payload.get("q")
            after_id = payload.get("i")
            if (
                isinstance(snapshot_rowid, bool)
                or not isinstance(snapshot_rowid, int)
                or snapshot_rowid < 0
                or isinstance(after_ordinal, bool)
                or not isinstance(after_ordinal, int)
                or after_ordinal < 0
                or not isinstance(after_run_id, str)
                or not after_run_id
                or not isinstance(after_id, str)
                or not after_id
            ):
                raise BridgeCursorError("cursor position is malformed")

        try:
            with self._writer.read_only_connection() as conn:
                conn.row_factory = sqlite3.Row
                page = self._runaway.list_page(
                    conn,
                    project_id=project_id,
                    run_id=run_id,
                    limit=limit,
                    snapshot_rowid=snapshot_rowid,
                    after_ordinal=after_ordinal,
                    after_run_id=after_run_id,
                    after_id=after_id,
                )
        except Exception as exc:  # noqa: BLE001 - normalize pack read errors
            raise BridgeInternalError(str(exc)) from exc

        next_cursor = None
        if page.has_more:
            next_cursor = _encode_runaway_cursor(
                {
                    "v": _RUNAWAY_CURSOR_VERSION,
                    "p": project_id,
                    "r": run_id,
                    "s": page.snapshot_rowid,
                    "o": page.next_ordinal,
                    "q": page.next_run_id,
                    "i": page.next_id,
                },
                key=self._runaway_cursor_key,
            )
        summary = self.get_runaway_timing_summary(project_slug, run_id=run_id)
        return RunawayTransitionPage(
            project=project_slug,
            transitions=tuple(row.to_dict() for row in page.transitions),
            timing_summary=summary,
            snapshot=f"runaway-v1:{project_id}:{page.snapshot_rowid}",
            total_count=page.total_count,
            limit=limit,
            next_cursor=next_cursor,
        )

    def get_runaway_timing_summary(
        self, project_slug: str, *, run_id: str | None = None
    ) -> dict[str, Any] | None:
        """Return the typed migration evidence that declares all regions."""
        project_id = self._resolve_project_id(project_slug)
        if self._runaway_evidence is None:
            return None
        try:
            rows = self._runaway_evidence.list(self._writer, project_id=project_id)
        except Exception as exc:  # noqa: BLE001 - normalize local read errors
            raise BridgeInternalError(str(exc)) from exc
        candidates = [
            row
            for row in rows
            if row.kind == "measurement"
            and row.data.get("subtype") == "runaway_timing_migrated"
            and (run_id is None or row.run_id == run_id)
        ]
        if not candidates:
            return None
        latest = candidates[-1]
        return {
            "evidence_id": latest.id,
            "run_id": latest.run_id,
            "summary": latest.summary,
            "data": dict(latest.data),
            "created_at": latest.created_at,
        }

    # -- health / projects -------------------------------------------------

    def health(self, projects_root: str) -> HealthStatus:
        """``GET /health``: liveness plus the resolved projects root."""
        return HealthStatus(ok=True, projects_root=projects_root)

    def list_projects(self) -> list[ProjectRow]:
        """``GET /projects``: sorted project rows (slug ascending)."""
        if self._service_mode:
            result = self._projects.list()
            self._raise_service_failure(result)
            return [
                ProjectRow(slug=row["slug"], name=row["name"])
                for row in result.data
            ]
        return [
            ProjectRow(slug=row.slug, name=row.name)
            for row in self._projects.list(self._writer)
        ]

    # -- timeline reads ----------------------------------------------------

    def list_timelines(self, project_slug: str) -> list[TimelineRow]:
        """``GET /projects/:slug/timelines`` (contract §5.1)."""
        project_id = self._resolve_project_id(project_slug)
        if self._service_mode:
            result = self._timelines.list(project_slug)
            self._raise_service_failure(result, timeline=True)
            return [
                TimelineRow(
                    timeline_id=row["timeline_id"],
                    timeline_ulid=row["timeline_ulid"],
                    slug=row["slug"],
                    name=row["name"],
                    is_default=row["is_default"],
                )
                for row in result.data
            ]
        return [
            TimelineRow(
                timeline_id=row.timeline_id,
                timeline_ulid=row.timeline_ulid,
                slug=row.slug,
                name=row.name,
                is_default=row.is_default,
            )
            for row in self._timelines.list(self._writer, project_id)
        ]

    def load_timeline(self, project_slug: str, ref: str) -> TimelineLoad:
        """``GET /projects/:slug/timelines/:ref`` (contract §5.2)."""
        self._validate_timeline_ref(ref)
        if self._service_mode:
            return self._service_load(project_slug, ref)
        project_id = self._resolve_project_id(project_slug)
        try:
            model = self._timelines.show(self._writer, project_id, ref)
        except TimelineNotFoundError as exc:
            raise BridgeTimelineNotFoundError(str(exc)) from exc
        except ProjectNotFoundError as exc:
            raise BridgeProjectNotFoundError(str(exc)) from exc
        except TimelineValidationError as exc:
            raise BridgeInvalidTimelineError(str(exc)) from exc
        except RepositoryError as exc:
            raise BridgeInternalError(str(exc)) from exc
        return self._to_load(model)

    # -- whole-document CAS save -------------------------------------------

    def save_timeline(
        self, project_slug: str, ref: str, request: TimelineSaveRequest
    ) -> TimelineLoad:
        """``POST /projects/:slug/timelines/:ref/save`` (contract §6).

        Service-backed: resolves the project and timeline through the typed
        services, derives the hidden deterministic bridge save key (§6.1),
        and runs the whole-document CAS save through the timeline service
        inside one ``BEGIN IMMEDIATE`` unit of work. A stale expected head
        raises :class:`BridgeVersionConflictError` carrying the current
        ``config_version`` (re-read through the service) and changes zero
        rows; the committed response is the frozen load shape with the new
        ``config_version`` (head + 1). Receipts and the derived key are
        stripped by construction.
        """
        if self._service_mode:
            return self._service_save(project_slug, ref, request)
        project_id = self._resolve_project_id(project_slug)
        try:
            model = UnitOfWork(self._writer).run(
                lambda u: self._timelines.save(
                    u,
                    project_id=project_id,
                    ref=ref,
                    config=request.config,
                    registry=request.registry,
                    expected_version=request.expected_version,
                )
            )
        except TimelineVersionConflictError as exc:
            raise BridgeVersionConflictError(
                str(exc), config_version=exc.current_version
            ) from exc
        except TimelineNotFoundError as exc:
            raise BridgeTimelineNotFoundError(str(exc)) from exc
        except ProjectNotFoundError as exc:
            raise BridgeProjectNotFoundError(str(exc)) from exc
        except TimelineValidationError as exc:
            raise BridgeInvalidTimelineError(str(exc)) from exc
        except ReceiptMismatchError as exc:
            # Unreachable on the bridge (the route derives its own key), but
            # never let a receipt detail leak into a response.
            raise BridgeInternalError(
                "internal idempotency mismatch on the save route"
            ) from exc
        except RepositoryError as exc:
            raise BridgeInternalError(str(exc)) from exc
        return self._to_load(model)

    # -- service-backed helpers (plan step 20) ------------------------------

    def _service_load(self, project_slug: str, ref: str) -> TimelineLoad:
        """Load one timeline through the timeline service."""
        self._resolve_project_id(project_slug)
        result = self._timelines.show(project_slug, ref)
        self._raise_service_failure(result, timeline=True)
        return self._to_load(result.data)

    def _service_save(
        self, project_slug: str, ref: str, request: TimelineSaveRequest
    ) -> TimelineLoad:
        """CAS-save one timeline through the service with the derived key."""
        project_id = self._resolve_project_id(project_slug)
        shown = self._timelines.show(project_slug, ref)
        self._raise_service_failure(shown, timeline=True)
        derived_key = self._derive_bridge_save_key(
            project_id=project_id,
            timeline_id=shown.data["timeline_id"],
            request=request,
        )
        result = self._timelines.save(
            project_slug,
            ref,
            config=request.config,
            registry=request.registry,
            expected_version=request.expected_version,
            idempotency_key=derived_key,
        )
        if not result.ok:
            self._raise_save_failure(result, project_slug=project_slug, ref=ref)
        return self._to_load(result.data)

    def _raise_save_failure(
        self,
        result: Any,
        *,
        project_slug: str,
        ref: str,
    ) -> None:
        """Map a failed save envelope onto the frozen bridge DTOs."""
        error = result.error
        code = error.code if error is not None else "internal_error"
        message = error.message if error is not None else "unexpected internal error"
        if code == "not_found":
            raise BridgeTimelineNotFoundError(message)
        if code == "validation_error":
            # Route-level parse/schema guards already produced the frozen
            # 400/422 envelopes; a service-level validation on the save is
            # the invalid_timeline surface (unchanged from the repository
            # adapter's mapping).
            raise BridgeInvalidTimelineError(message)
        if code == "stale_version":
            current = self._service_current_version(project_slug, ref)
            raise BridgeVersionConflictError(message, config_version=current)
        if code == "idempotency_mismatch":
            # Unreachable on the bridge (the derived key includes the request
            # digest, so a changed payload derives a different key), but
            # never let a receipt detail leak into a response.
            raise BridgeInternalError(
                "internal idempotency mismatch on the save route"
            )
        if code == "unavailable":
            raise BridgeInternalError(
                "the timeline service is temporarily unavailable"
            )
        raise BridgeInternalError(message)

    def _service_current_version(self, project_slug: str, ref: str) -> int:
        """Re-read the current head after a stale CAS (zero rows changed)."""
        result = self._timelines.show(project_slug, ref)
        if not result.ok:
            raise BridgeInternalError("cannot read the current timeline version")
        return int(result.data["config_version"])

    def _derive_bridge_save_key(
        self,
        *,
        project_id: str,
        timeline_id: str,
        request: TimelineSaveRequest,
    ) -> str:
        """Derive the hidden deterministic bridge save key (bridge §6.1).

        Mirrors the repository's derivation exactly — command kind +
        project/timeline identity + integer expected head + canonical
        payload digest — so bridge retries and SDK retries share one atomic,
        receipt-gated save implementation. The key is supplied through the
        service's caller-key slot and is never returned to any caller.
        """
        assets = request.registry.get("assets", {})
        if not isinstance(assets, Mapping):
            raise BridgeSchemaIncompatibleError(
                "config/registry failed schema validation",
                issues=[
                    BridgeIssue(
                        pointer="/registry/assets",
                        code="schema_incompatible",
                        message="registry.assets must be a JSON object",
                    )
                ],
            )
        payload = {
            "config": dict(request.config),
            "registry": {"assets": dict(assets)},
            "expected_version": request.expected_version,
        }
        try:
            digest = request_hash(TIMELINE_SAVE_COMMAND_KIND, payload)
        except CanonicalizationError as exc:
            raise BridgeSchemaIncompatibleError(
                "config/registry failed schema validation",
                issues=[
                    BridgeIssue(
                        pointer="/config",
                        code="schema_incompatible",
                        message=str(exc),
                    )
                ],
            ) from exc
        return (
            f"{TIMELINE_SAVE_COMMAND_KIND}:{project_id}:{timeline_id}:"
            f"{request.expected_version}:{digest}"
        )

    def _raise_service_failure(
        self, result: Any, *, timeline: bool = False
    ) -> None:
        """Map a failed service envelope onto the frozen bridge DTOs.

        ``timeline=False`` (the default) maps project-context failures;
        ``timeline=True`` maps timeline-context failures. ``stale_version``
        is handled by :meth:`_raise_save_failure` only (it needs the route's
        project/ref context to re-read the current head).
        """
        if result.ok:
            return
        error = result.error
        code = error.code if error is not None else "internal_error"
        message = error.message if error is not None else "unexpected internal error"
        if code == "not_found":
            if timeline:
                raise BridgeTimelineNotFoundError(message)
            raise BridgeProjectNotFoundError(message)
        if code == "validation_error":
            if timeline:
                raise BridgeInvalidTimelineError(message)
            raise BridgeInvalidProjectError(message)
        if code == "unavailable":
            raise BridgeInternalError(
                "the timeline service is temporarily unavailable"
            )
        raise BridgeInternalError(message)

    # -- private helpers ----------------------------------------------------

    def _resolve_project_id(self, project_slug: str) -> str:
        """Resolve a validated ``:slug`` to the internal project id.

        ``400 invalid_project`` for a malformed slug, ``404
        project_not_found`` for a missing project (never an empty
        authority-dependent view).
        """
        if not isinstance(project_slug, str) or not project_slug:
            raise BridgeInvalidProjectError(
                "project slug must be a non-empty string"
            )
        if _PROJECT_SLUG_RE.fullmatch(project_slug) is None:
            raise BridgeInvalidProjectError(
                "project slug must be lowercase letters/digits joined by "
                f"single hyphens, got {project_slug!r}"
            )
        if self._service_mode:
            result = self._projects.show(project_slug)
            self._raise_service_failure(result)
            return str(result.data["id"])
        with self._writer.read_only_connection() as conn:
            row = conn.execute(
                "SELECT id FROM projects WHERE slug = ?", (project_slug,)
            ).fetchone()
        if row is None:
            raise BridgeProjectNotFoundError(
                f"unknown project: {project_slug!r}"
            )
        return str(row[0])

    def _validate_timeline_ref(self, ref: str) -> str:
        """Reject a ``:ref`` matching none of the frozen address forms."""
        if not isinstance(ref, str) or not ref:
            raise BridgeInvalidTimelineError(
                "timeline ref must be a non-empty string"
            )
        if not _is_timeline_ref(ref):
            raise BridgeInvalidTimelineError(
                "timeline ref must be a canonical UUID, lowercase ULID, "
                f"or immutable slug, got {ref!r}"
            )
        return ref

    @staticmethod
    def _to_load(data: Any) -> TimelineLoad:
        """Wrap a read model (service dict or repository dataclass) in the
        frozen load DTO."""
        if isinstance(data, Mapping):
            return TimelineLoad(
                timeline_id=data["timeline_id"],
                timeline_ulid=data["timeline_ulid"],
                slug=data["slug"],
                name=data["name"],
                is_default=bool(data.get("is_default", False)),
                config=dict(data["config"]),
                registry=dict(data["registry"]),
                config_version=int(data["config_version"]),
            )
        return TimelineLoad(
            timeline_id=data.timeline_id,
            timeline_ulid=data.timeline_ulid,
            slug=data.slug,
            name=data.name,
            is_default=data.is_default,
            config=dict(data.config),
            registry=dict(data.registry),
            config_version=data.config_version,
        )


__all__ = ["TimelineBridgeAdapter"]
