"""Timeline bridge adapter over the project and timeline repositories.

(m1 plan step 18.) This adapter is the repository-backed bridge's read/CAS
surface: it translates the frozen HTTP contract
(``docs/contracts/astrid-bridge-v10.md``) into repository calls and maps
every repository outcome onto the repository-neutral DTOs and typed errors
of :mod:`astrid.core.integrations.reigh.bridge_service`.

The adapter is the **only** boundary that may import both the kernel
bridge contracts and the timeline pack repository. It is injected at the
gateway serve composition root (``astrid.core.gateway.dispatch``) through
``astrid.packs.compose_standard_bridge``; there is no legacy authority
fallback anywhere in this module — reads and CAS saves go exclusively to
the project and timeline repositories.

Mapping rules kept here:

- ``:slug`` is validated against the project slug grammar before any read
  (``400 invalid_project``); a missing project is ``404 project_not_found``
  (never an empty authority-dependent view);
- ``:ref`` is validated as canonical UUID, lowercase ULID, or slug before
  any read (``400 invalid_timeline``); the repository resolves it
  project-scoped in §8 order;
- ``POST .../save`` bodies are parsed by
  :class:`~astrid.core.integrations.reigh.bridge_service.TimelineSaveRequest`
  (``400 invalid_body/invalid_config/invalid_registry/invalid_expected_version``);
  a stale expected head maps to ``409 timeline_version_conflict`` with the
  current ``config_version``; the repository CAS changes zero rows;
- every response is a frozen DTO whose serialization can never include a
  receipt field (receipt secrecy, §7, enforced by construction).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from astrid.core.integrations.reigh.bridge_service import (
    BridgeError,
    BridgeInternalError,
    BridgeInvalidProjectError,
    BridgeInvalidTimelineError,
    BridgeProjectNotFoundError,
    BridgeTimelineNotFoundError,
    BridgeVersionConflictError,
    HealthStatus,
    ProjectRow,
    TimelineLoad,
    TimelineRow,
    TimelineSaveRequest,
)
from astrid.core.receipts import ReceiptMismatchError
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.projects import (
    ProjectNotFoundError,
    ProjectRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.timeline.repository import (
    TimelineNotFoundError,
    TimelineRepository,
    TimelineValidationError,
    TimelineVersionConflictError,
)

_PROJECT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
"""Project slug grammar, mirroring the project repository's immutable rule.

The bridge validates ``:slug`` before any read so a malformed slug is a
``400 invalid_project``, never a repository lookup.
"""

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
"""Canonical lowercase UUID grammar (bridge §8 order 1)."""

_ULID_RE = re.compile(r"^[0123456789abcdefghjkmnpqrstvwxyz]{26}$")
"""Lowercase 26-character Crockford ULID grammar (bridge §8 order 2)."""


def _is_timeline_ref(ref: str) -> bool:
    """Whether *ref* matches one of the three frozen address forms (§8)."""
    return (
        _UUID_RE.fullmatch(ref) is not None
        or _ULID_RE.fullmatch(ref) is not None
        or _PROJECT_SLUG_RE.fullmatch(ref) is not None
    )


class TimelineBridgeAdapter:
    """Stateless adapter composing the project + timeline repositories.

    A single instance is safe to share across HTTP requests. Reads run
    transaction-free on the writer's separate read-only connection; CAS
    saves run inside one ``BEGIN IMMEDIATE`` unit of work per request.
    """

    def __init__(
        self,
        *,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        timelines: TimelineRepository,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._timelines = timelines

    # -- health / projects -------------------------------------------------

    def health(self, projects_root: str) -> HealthStatus:
        """``GET /health``: liveness plus the resolved projects root."""
        return HealthStatus(ok=True, projects_root=projects_root)

    def list_projects(self) -> list[ProjectRow]:
        """``GET /projects``: sorted project rows (slug ascending)."""
        return [
            ProjectRow(slug=row.slug, name=row.name)
            for row in self._projects.list(self._writer)
        ]

    # -- timeline reads ----------------------------------------------------

    def list_timelines(self, project_slug: str) -> list[TimelineRow]:
        """``GET /projects/:slug/timelines`` (contract §5.1)."""
        project_id = self._resolve_project_id(project_slug)
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
        project_id = self._resolve_project_id(project_slug)
        self._validate_timeline_ref(ref)
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

        Runs the whole-document CAS save inside one ``BEGIN IMMEDIATE``
        unit of work: a stale expected head raises
        :class:`BridgeVersionConflictError` carrying the current head and
        changes zero rows; the committed response is the frozen load shape
        with the new ``config_version`` (head + 1).
        """
        project_id = self._resolve_project_id(project_slug)
        self._validate_timeline_ref(ref)
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
    def _to_load(model: Any) -> TimelineLoad:
        """Wrap a repository read model in the frozen load DTO."""
        return TimelineLoad(
            timeline_id=model.timeline_id,
            timeline_ulid=model.timeline_ulid,
            slug=model.slug,
            name=model.name,
            is_default=model.is_default,
            config=dict(model.config),
            registry=dict(model.registry),
            config_version=model.config_version,
        )


__all__ = ["TimelineBridgeAdapter"]
