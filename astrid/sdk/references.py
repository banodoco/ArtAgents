"""Typed reference SDK service (m4 plan step 15, task T16).

Exposes repository-backed ``create``, ``update``, ``archive``, ``associate``,
``set_primary``, ``link``, ``list``, and ``show`` over the references pack
:class:`~astrid.packs.references.repository.ReferenceRepository` with the
frozen SDK envelope (``docs/contracts/astrid-sdk-v10.md`` section 1):

- **create** accepts an optional caller idempotency key (a fresh key is
  generated before mutation when absent) and derives a **deterministic**
  reference id from ``(reference.create, project scope, key)`` so an
  identical retry derives the same id and replays with zero new rows;
- **update** mutates only the mutable ``name``/``description``/``metadata``
  fields through the Step 14 repository command (``kind`` and ``project_id``
  stay immutable by construction, archived references are rejected);
- **archive** is the receipt-backed soft archive (associations, links,
  events, media rows, and bytes are preserved — never cascaded);
- **associate** delegates every exact-media and context-task rule (same
  project, exact provenance, role vocabulary, duplicate rejection) to the
  repository;
- **set_primary** delegates primary-replacement (clear-then-set collision
  safety, canonical-only target, archived rejection) to the repository;
- **link** delegates the frozen five-kind link vocabulary, self-edge
  rejection, same-project pair, symmetric ``related_to`` canonicalization,
  and duplicate rejection to the repository;
- **list** / **show** are transaction-free reads; ``show`` always returns
  archived references (SD1 — archive hides rows only from ordinary lists).

Every mutation returns exactly one :class:`DomainResult` envelope with the
five frozen keys, the committed :class:`CommandReceipt`, and the key used;
every failure returns the frozen three-key error object via the centralized
:func:`map_error`. This module contains **no SQL** and holds **no writer of
its own**; every read and mutation is delegated to the project and reference
repositories.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.references.repository import (
    REFERENCE_CREATE_COMMAND_KIND,
    ReferenceRepository,
)
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import ServiceValidationError, map_error

__all__ = ["ReferencesService"]


class ReferencesService:
    """Repository-backed reference lifecycle SDK surface.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the project repository (for project id/slug resolution), the
    references pack repository (for every reference command and read), and
    the receipt service (for read-only committed-receipt lookup). It holds no
    SQL and opens no writer of its own.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        references: ReferenceRepository,
        receipts: ReceiptService,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._references = references
        self._receipts = receipts

    # -- create ------------------------------------------------------------

    def create(
        self,
        *,
        project: str,
        kind: str,
        name: str,
        media_id: str,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Create one active reference with its primary canonical media.

        The idempotency key is the caller's when supplied, otherwise a fresh
        key generated before mutation. The reference id is derived
        deterministically from ``(reference.create, project scope, key)``, so
        an identical retry replays the committed result with zero new rows
        and a changed request under the same key returns
        ``idempotency_mismatch`` before any mutation. The exact-media and
        same-project rules are delegated to the repository.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        reference_id = derive_stable_id(
            command_kind=REFERENCE_CREATE_COMMAND_KIND,
            scope=project_id,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._references.create(
                    uow,
                    project_id=project_id,
                    kind=kind,
                    name=name,
                    media_id=media_id,
                    description=description,
                    metadata=metadata,
                    idempotency_key=key,
                    reference_id=reference_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- update ------------------------------------------------------------

    def update(
        self,
        project: str,
        ref: str,
        *,
        name: str | None = None,
        description: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Mutate a reference's name/description/metadata and return its receipt.

        ``kind`` and ``project_id`` are immutable and never change; an
        archived reference is a typed ``terminal_state``. An identical retry
        replays and a changed delta under the same key returns
        ``idempotency_mismatch`` before any mutation.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._references.update(
                    uow,
                    project_id=project_id,
                    reference_id=ref,
                    name=name,
                    description=description,
                    metadata=metadata,
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

    # -- archive -----------------------------------------------------------

    def archive(
        self,
        project: str,
        ref: str,
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Soft-archive one reference atomically, preserving every byte.

        Archive hides the reference from ordinary lists but never deletes or
        cascades any association, link, event, media row, or byte (SD1). An
        already-archived reference rejects further mutation with a typed
        ``terminal_state``.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._references.archive(
                    uow,
                    project_id=project_id,
                    reference_id=ref,
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

    # -- associate ---------------------------------------------------------

    def associate(
        self,
        project: str,
        ref: str,
        *,
        media_id: str,
        role: str,
        context_task_id: str | None = None,
        ordinal: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Associate one exact media row with an active reference atomically.

        Every exact-media and context-task rule (same-project ownership, role
        vocabulary, exact provenance through ``task_outputs``, duplicate
        rejection) is delegated to the repository, which evaluates it before
        any SQL write.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._references.associate(
                    uow,
                    project_id=project_id,
                    reference_id=ref,
                    media_id=media_id,
                    role=role,
                    context_task_id=context_task_id,
                    ordinal=ordinal,
                    metadata=metadata,
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

    # -- set_primary -------------------------------------------------------

    def set_primary(
        self,
        project: str,
        ref: str,
        *,
        media_reference_id: str,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Replace the primary canonical media atomically, collision-safely.

        The repository clears the current primary before setting the new one
        (so the one-primary unique index never sees two primaries at a
        statement boundary) and rejects missing/foreign/non-canonical targets
        before any write.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._references.set_primary(
                    uow,
                    project_id=project_id,
                    reference_id=ref,
                    media_reference_id=media_reference_id,
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

    # -- link --------------------------------------------------------------

    def link(
        self,
        project: str,
        *,
        from_reference_id: str,
        to_reference_id: str,
        kind: str,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Create one typed reference link atomically and idempotently.

        The frozen five-kind vocabulary, self-edge rejection, same-project
        pair, symmetric ``related_to`` canonicalization, and duplicate
        rejection are all delegated to the repository.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._references.link(
                    uow,
                    project_id=project_id,
                    from_reference_id=from_reference_id,
                    to_reference_id=to_reference_id,
                    kind=kind,
                    metadata=metadata,
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

    # -- list --------------------------------------------------------------

    def list(
        self, project: str, *, include_archived: bool = False
    ) -> DomainResult[list[dict[str, Any]]]:
        """Return every active reference in *project* (kind, name, id order).

        Archived references are hidden by default; ``include_archived=True``
        is the explicit inclusive list that preserves history.
        """
        try:
            project_id = self._projects.resolve(self._writer, project)
            rows = self._references.list(
                self._writer, project_id, include_archived=include_archived
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([row.to_dict() for row in rows])

    # -- show --------------------------------------------------------------

    def show(self, project: str, ref: str) -> DomainResult[dict[str, Any]]:
        """Return one reference's full read model by id.

        ``show`` always returns archived references (SD1 — archive hides rows
        only from ordinary lists). A missing or foreign reference is a typed
        ``not_found``.
        """
        try:
            project_id = self._projects.resolve(self._writer, project)
            model = self._references.show(self._writer, project_id, ref)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(model.to_dict())

    # -- private helpers ---------------------------------------------------

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

    def _committed_receipt(
        self, project_id: str, idempotency_key: str
    ) -> CommandReceipt | None:
        """Read-only lookup of the committed receipt for a mutation."""
        with self._writer.read_only_connection() as conn:
            return self._receipts.lookup_committed(
                conn, project_id=project_id, idempotency_key=idempotency_key
            )
