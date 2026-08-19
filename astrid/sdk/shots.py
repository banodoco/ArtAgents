"""Typed shot SDK service (m4 plan step 16, task T17).

Exposes repository-backed ``list``, ``show``, ``create``, ``add``, ``remove``,
and ``reorder`` over the shots pack
:class:`~astrid.packs.shots.repository.ShotRepository` with the frozen SDK
envelope (``docs/contracts/astrid-sdk-v10.md`` section 1):

- **create** accepts an optional caller idempotency key (a fresh key is
  generated before mutation when absent) and derives a **deterministic** shot
  id from ``(shot.create, project scope, key)`` so an identical retry
  derives the same id and replays with zero new rows;
- **add** inserts one exact same-project kernel media id at a validated
  position (the deterministic 0-based insertion domain, ``0 .. count``) and
  derives a deterministic item id from ``(shot.add_item, project scope, key)``;
- **remove** deletes only the ``shot_items`` row — the kernel media row, its
  location, and its bytes are preserved;
- **reorder** accepts exactly one whole-shot permutation of the shot's
  current item ids (omissions, duplicates, extras, and foreign-shot items are
  rejected before any write) and stores the exact item/media order;
- **list** / **show** are transaction-free reads ordered by the deterministic
  ``sort_key``/``id`` (shots) and ``sort_key``/``id`` (items).

Every mutation returns exactly one :class:`DomainResult` envelope with the
five frozen keys, the committed :class:`CommandReceipt`, and the key used;
every failure returns the frozen three-key error object via the centralized
:func:`map_error`. This module contains **no SQL** and holds **no writer of
its own**; every read and mutation is delegated to the project and shot
repositories.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_CREATE_COMMAND_KIND,
    ShotRepository,
)
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import ServiceValidationError, map_error

__all__ = ["ShotsService"]


class ShotsService:
    """Repository-backed shot list/show/create/add/remove/reorder surface.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the project repository (for project id/slug resolution), the
    shots pack repository (for every shot command and read), and the receipt
    service (for read-only committed-receipt lookup). It holds no SQL and
    opens no writer of its own.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        shots: ShotRepository,
        receipts: ReceiptService,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._shots = shots
        self._receipts = receipts

    # -- create ------------------------------------------------------------

    def create(
        self,
        *,
        project: str,
        name: str,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Create one empty shot and return its committed receipt envelope.

        The idempotency key is the caller's when supplied, otherwise a fresh
        key generated before mutation. The shot id is derived
        deterministically from ``(shot.create, project scope, key)``, so an
        identical retry replays the committed result with zero new rows and a
        changed request under the same key returns ``idempotency_mismatch``
        before any mutation.
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
        shot_id = derive_stable_id(
            command_kind=SHOT_CREATE_COMMAND_KIND,
            scope=project_id,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._shots.create(
                    uow,
                    project_id=project_id,
                    name=name,
                    metadata=metadata,
                    idempotency_key=key,
                    shot_id=shot_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- add ---------------------------------------------------------------

    def add_item(
        self,
        project: str,
        shot_id: str,
        *,
        media_id: str,
        position: int | None = None,
        source_frame: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Insert one exact-media item at a validated position atomically.

        The item id is derived deterministically from
        ``(shot.add_item, project scope, key)`` so an identical retry replays
        with zero new rows. The position domain (``0 .. count``), exact-media
        same-project rule, and out-of-range rejection are delegated to the
        repository before any write.
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
        item_id = derive_stable_id(
            command_kind=SHOT_ADD_ITEM_COMMAND_KIND,
            scope=project_id,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._shots.add_item(
                    uow,
                    project_id=project_id,
                    shot_id=shot_id,
                    media_id=media_id,
                    position=position,
                    source_frame=source_frame,
                    metadata=metadata,
                    idempotency_key=key,
                    item_id=item_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- remove ------------------------------------------------------------

    def remove_item(
        self,
        project: str,
        shot_id: str,
        item_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Remove one exact item, preserving its kernel media, atomically.

        Only the ``shot_items`` row is deleted; the kernel media row and its
        bytes are preserved (the DDL ``ON DELETE RESTRICT`` pins the media
        row and this command never touches media).
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
                lambda uow: self._shots.remove_item(
                    uow,
                    project_id=project_id,
                    shot_id=shot_id,
                    item_id=item_id,
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

    # -- reorder -----------------------------------------------------------

    def reorder(
        self,
        project: str,
        shot_id: str,
        item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Reorder a whole shot to one exact permutation of its item ids.

        Omissions, duplicates, extras, and foreign-shot items are rejected
        before any write; the receipt carries the exact ordered item and
        media ids after the reorder.
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
                lambda uow: self._shots.reorder(
                    uow,
                    project_id=project_id,
                    shot_id=shot_id,
                    item_ids=item_ids,
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

    def list(self, project: str) -> DomainResult[list[dict[str, Any]]]:
        """Return every shot in *project* (sort_key, then id order)."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            rows = self._shots.list(self._writer, project_id)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(
            [
                {
                    "id": row.id,
                    "project_id": row.project_id,
                    "name": row.name,
                    "sort_key": row.sort_key,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ]
        )

    # -- show --------------------------------------------------------------

    def show(self, project: str, shot_id: str) -> DomainResult[dict[str, Any]]:
        """Return one shot's full read model with items in stable order.

        A missing or foreign shot is a typed ``not_found``.
        """
        try:
            project_id = self._projects.resolve(self._writer, project)
            model = self._shots.show(self._writer, project_id, shot_id)
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
