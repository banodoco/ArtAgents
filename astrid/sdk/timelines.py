"""Typed timeline SDK service (m4 plan step 8, task T9).

Exposes repository-backed ``create``, ``list``, ``show``, ``save``,
``archive``, ``history``, and ``diff`` over the timeline pack's
:class:`~astrid.packs.timeline.repository.TimelineRepository` (the Step 6–7
command and read surface) with the frozen SDK envelope
(``docs/contracts/astrid-sdk-v10.md``):

- **create** resolves the addressed project (id or slug) through the
  project repository, derives a **deterministic** timeline id from
  ``(command kind, project scope, idempotency key)`` so a retry under the
  same key derives the same id and replays with zero new rows, and returns
  the committed receipt;
- **save** is the whole-document CAS command: the caller-visible
  idempotency key (generated if absent, always returned in the envelope) is
  passed through to the Step 6 repository command, and a stale expected
  head maps to ``stale_version`` through the centralized error mapper;
- **archive** is the event-backed terminal mutation; a later ``save`` on an
  archived timeline returns ``terminal_state``;
- **list** / **show** / **history** / **diff** are transaction-free reads;
  ``show``/``history``/``diff`` resolve the timeline address (UUID, ULID,
  or slug) within the project;
- every mutation returns exactly one :class:`DomainResult` envelope with the
  five frozen keys, the committed :class:`CommandReceipt`, and the key used;
  every failure returns the frozen three-key error object via the
  centralized :func:`map_error`.

Addressing is repository-driven and project-scoped throughout: the project
is addressed by id or slug (``ProjectRepository.resolve``) and the timeline
by canonical UUID, lowercase ULID, or immutable slug
(``TimelineRepository.resolve``). This module adds **no** convenience
columns and **no** ``copy`` verb (the reserved route is documented in Step 2
and implemented in m6); it contains no SQL and holds no writer of its own.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.timeline.repository import (
    TIMELINE_CREATE_COMMAND_KIND,
    TimelineArchivedError,
    TimelineRepository,
)
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import (
    ServiceTerminalStateError,
    ServiceValidationError,
    map_error,
)

__all__ = ["TimelinesService"]

_CROCKFORD_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
"""Lowercase Crockford base32 alphabet (no I, L, O, U)."""


def _derive_timeline_ulid(timeline_id: str) -> str:
    """Derive a deterministic lowercase Crockford ULID from a stable id.

    The timeline's ULID alias is a 26-character lowercase Crockford-base32
    string derived from the already-stable ``timeline_id``, so an identical
    retry under the same idempotency key derives the same alias and replays
    with zero new rows while remaining a valid ULID address form.
    """
    digest = hashlib.sha256(timeline_id.encode("utf-8")).digest()
    value = int.from_bytes(digest, "big") & ((1 << 130) - 1)
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


class TimelinesService:
    """Repository-backed timeline create/list/show/save/archive/history/diff.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the project repository (for project id/slug resolution), the
    timeline repository (for all timeline commands and reads), and the
    receipt service (for read-only committed-receipt lookup). It holds no
    SQL and opens no writer of its own.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        timelines: TimelineRepository,
        receipts: ReceiptService,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._timelines = timelines
        self._receipts = receipts

    # -- create ------------------------------------------------------------

    def create(
        self,
        *,
        project: str,
        slug: str,
        name: str,
        config: Mapping[str, Any] | None = None,
        registry: Mapping[str, Any] | None = None,
        set_default: bool = False,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Create one timeline in *project* and return its receipt envelope.

        The project is resolved by id or slug; the timeline id is derived
        deterministically from ``(command kind, project scope, key)`` so an
        identical retry replays the committed result with zero new rows and
        a changed request under the same key returns
        ``idempotency_mismatch`` before any mutation.
        """
        key = self._caller_key_or_empty(idempotency_key)
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        timeline_id = derive_stable_id(
            command_kind=TIMELINE_CREATE_COMMAND_KIND,
            scope=project_id,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._timelines.create(
                    uow,
                    project_id=project_id,
                    slug=slug,
                    name=name,
                    config=dict(config) if config is not None else {},
                    registry=registry,
                    idempotency_key=key,
                    timeline_id=timeline_id,
                    timeline_ulid=_derive_timeline_ulid(timeline_id),
                    set_default=set_default,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- list --------------------------------------------------------------

    def list(
        self, project: str, *, include_archived: bool = False
    ) -> DomainResult[list[dict[str, Any]]]:
        """Return timelines in *project*, optionally including archived work."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            rows = self._timelines.list(self._writer, project_id, include_archived=include_archived)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([row.to_dict() for row in rows])

    # -- show --------------------------------------------------------------

    def show(self, project: str, ref: str) -> DomainResult[dict[str, Any]]:
        """Return one timeline's frozen load shape by UUID/ULID/slug."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            model = self._timelines.show(self._writer, project_id, ref)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(model.to_dict())

    # -- save (whole-document CAS) -----------------------------------------

    def save(
        self,
        project: str,
        ref: str,
        *,
        config: Mapping[str, Any],
        registry: Mapping[str, Any],
        expected_version: int,
        set_default: bool = False,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Whole-document CAS save of *ref* in *project* and its receipt.

        The caller-visible idempotency key (generated when absent) is passed
        to the Step 6 repository command; a stale ``expected_version`` maps
        to ``stale_version`` and changes zero rows.
        """
        key = self._caller_key_or_empty(idempotency_key)
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._timelines.save(
                    uow,
                    project_id=project_id,
                    ref=ref,
                    config=config,
                    registry=registry,
                    expected_version=expected_version,
                    idempotency_key=key,
                )
            )
        except TimelineArchivedError as exc:
            return DomainResult.failure(self._archived_error(exc), idempotency_key=key)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- archive -----------------------------------------------------------

    def archive(
        self,
        project: str,
        ref: str,
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Archive *ref* in *project* (event-backed terminal mutation)."""
        key = self._caller_key_or_empty(idempotency_key)
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._timelines.archive(
                    uow,
                    project_id=project_id,
                    ref=ref,
                    idempotency_key=key,
                )
            )
        except TimelineArchivedError as exc:
            return DomainResult.failure(self._archived_error(exc), idempotency_key=key)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    def unarchive(
        self,
        project: str,
        ref: str,
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Restore *ref* to active state; repeat calls are successful no-ops."""
        key = self._caller_key_or_empty(idempotency_key)
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._timelines.unarchive(
                    uow,
                    project_id=project_id,
                    ref=ref,
                    idempotency_key=key,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- history -----------------------------------------------------------

    def history(self, project: str, ref: str) -> DomainResult[list[dict[str, Any]]]:
        """Return the ordered lifecycle event history for *ref*."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            entries = self._timelines.history(self._writer, project_id, ref)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([entry.to_dict() for entry in entries])

    # -- diff --------------------------------------------------------------

    def diff(self, project: str, ref: str) -> DomainResult[list[dict[str, Any]]]:
        """Return the deterministic adjacent-version diffs for *ref*."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            entries = self._timelines.diff(self._writer, project_id, ref)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([entry.to_dict() for entry in entries])

    # -- private helpers ---------------------------------------------------

    @staticmethod
    def _caller_key_or_empty(idempotency_key: object) -> str:
        """Return a safe caller key for failures before key resolution.

        Once a missing key is generated, callers must receive that generated
        key even when a later pre-mutation step (such as project resolution)
        fails. Invalid non-string caller values use the only valid
        pre-resolution envelope value: the empty string.
        """
        return idempotency_key if isinstance(idempotency_key, str) else ""

    @staticmethod
    def _archived_error(exc: TimelineArchivedError) -> Any:
        """Map an archived-timeline mutation to the frozen terminal_state code.

        ``TimelineArchivedError`` is a mutation fence while a timeline remains
        archived. The centralized
        mapper does not yet carry this pack error, so the service maps it
        narrowly to the frozen ``terminal_state`` error object (SDK contract
        section 2) without leaking the internal timeline id.
        """
        return map_error(
            ServiceTerminalStateError(
                "the timeline is archived and cannot be mutated",
                details={"timeline_id": exc.timeline_id},
            )
        )

    @staticmethod
    def _resolve_key(idempotency_key: str | None) -> str:
        """Return the caller key or a fresh generated key.

        An empty or non-string caller key is a typed validation error (SDK
        contract section 4.2), raised before any mutation.
        """
        try:
            return resolve_idempotency_key(idempotency_key)
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc

    def _committed_receipt(self, project_id: str, idempotency_key: str) -> CommandReceipt | None:
        """Read-only lookup of the committed receipt for a mutation."""
        with self._writer.read_only_connection() as conn:
            return self._receipts.lookup_committed(
                conn, project_id=project_id, idempotency_key=idempotency_key
            )
