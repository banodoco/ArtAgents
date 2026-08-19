"""Typed media SDK service (m4 plan step 11, task T12).

Exposes repository-backed ``import``, ``list``, ``show``, ``verify``,
``relocate``, and ``relate`` over the kernel
:class:`~astrid.core.repositories.media.MediaRepository` (the Step 9-10
project-scoped resolution and stable-fingerprint-verification surface) with
the frozen SDK envelope (``docs/contracts/astrid-sdk-v10.md`` section 1):

- **import_file** prepares one file's bytes outside any transaction
  (:func:`~astrid.core.io.media_import.prepare_media_file`), derives a
  deterministic media id from ``(core.media.import, project scope, key)`` so
  an identical retry replays with zero new rows, and returns the committed
  receipt;
- **import_directory** is a deterministic sequence of exact-file commands:
  files are walked in sorted depth-first order
  (:func:`~astrid.core.io.media_import.prepare_media_directory`), each child
  derives a child idempotency key (``parent#index``) and its own deterministic
  media id, and the result carries one media read model plus one committed
  receipt per file (statement-boundary atomicity is per file);
- **list** / **show** are transaction-free reads; ``show`` resolves the media
  id **project-scoped** (a cross-project id is indistinguishable from an
  unknown one, SDK contract §5.2);
- **verify** resolves the media id project-scoped, hashes the selected local
  location's bytes **outside** the transaction
  (:func:`~astrid.core.repositories.media.prepare_media_fingerprint`), then
  delegates the race-safe re-stat/re-hash command (Step 10) so a missing or
  mutated location changes zero rows;
- **relocate** delegates the location-replacement command (paths and
  locators are replaceable aliases, never identity, SD2);
- **relate** accepts only the five frozen kinds and delegates every
  direction, self-edge, duplicate, single-parent, and acyclic-variant rule to
  the repository (Step 9; no invented direction matrix, SDK contract §5.3).

Every mutation returns exactly one :class:`DomainResult` envelope with the
five frozen keys, the committed :class:`CommandReceipt`, and the key used;
every failure returns the frozen three-key error object via the centralized
:func:`map_error`. This module contains **no SQL** and holds **no writer of
its own**; every read and mutation is delegated to the project and media
repositories.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from astrid.core.io.media_import import prepare_media_directory, prepare_media_file
from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.media import (
    CORE_MEDIA_IMPORT_COMMAND_KIND,
    MANAGED_LOCAL_REALM,
    MediaConflictError,
    MediaLocationNotFoundError,
    MediaRepository,
    prepare_media_fingerprint,
)
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import ServiceValidationError, map_error

__all__ = ["MediaService"]


class MediaService:
    """Repository-backed media import/list/show/verify/relocate/relate surface.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the project repository (for project id/slug resolution), the
    media repository (for every media command and read), and the receipt
    service (for read-only committed-receipt lookup). It holds no SQL and
    opens no writer of its own.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        media: MediaRepository,
        receipts: ReceiptService,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._media = media
        self._receipts = receipts

    # -- import (single file) ----------------------------------------------

    def import_file(
        self,
        *,
        project: str,
        path: str | Path,
        realm: str = MANAGED_LOCAL_REALM,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Import one prepared file into *project* and return its receipt.

        The file is hashed/probed outside any transaction, then imported
        inside one unit of work. The media id is derived deterministically
        from ``(core.media.import, project scope, key)``, so an identical
        retry replays the committed result with zero new rows and a changed
        request under the same key returns ``idempotency_mismatch`` before
        any mutation.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
            prepared = prepare_media_file(path)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        media_id = derive_stable_id(
            command_kind=CORE_MEDIA_IMPORT_COMMAND_KIND,
            scope=project_id,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._media.import_prepared(
                    uow,
                    project_id=project_id,
                    prepared=prepared,
                    idempotency_key=key,
                    media_id=media_id,
                    realm=realm,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- import (directory fan-out) ----------------------------------------

    def import_directory(
        self,
        *,
        project: str,
        directory: str | Path,
        realm: str = MANAGED_LOCAL_REALM,
        idempotency_key: str | None = None,
    ) -> DomainResult[list[dict[str, Any]]]:
        """Import every file under *directory* as one exact-media command each.

        Files are prepared in deterministic sorted depth-first walk order; a
        child idempotency key (``parent#index``) and a deterministic media id
        are derived per file, and each file commits its own receipt. The
        envelope's ``data`` is one entry per file carrying the file's
        relative path, media read model, committed receipt, and child key.
        Replaying an identical directory import under the same key returns
        the same entries with zero new rows.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
            prepared_files = prepare_media_directory(directory)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )

        entries: list[dict[str, Any]] = []
        for index, prepared in enumerate(prepared_files):
            child_key = f"{key}#{index}"
            media_id = derive_stable_id(
                command_kind=CORE_MEDIA_IMPORT_COMMAND_KIND,
                scope=project_id,
                idempotency_key=child_key,
                ordinal=0,
            )
            try:
                model = UnitOfWork(self._writer).run(
                    lambda uow, p=prepared, ck=child_key, mid=media_id: (
                        self._media.import_prepared(
                            uow,
                            project_id=project_id,
                            prepared=p,
                            idempotency_key=ck,
                            media_id=mid,
                            realm=realm,
                        )
                    )
                )
            except Exception as exc:  # noqa: BLE001 - centralized mapping
                return DomainResult.failure(map_error(exc), idempotency_key=key)
            receipt = self._committed_receipt(project_id, child_key)
            entries.append(
                {
                    "path": prepared.rel_path,
                    "media": model.to_dict(),
                    "receipt": receipt.as_dict() if receipt is not None else None,
                    "idempotency_key": child_key,
                }
            )
        return DomainResult.success(entries, idempotency_key=key)

    # -- list --------------------------------------------------------------

    def list(self, project: str) -> DomainResult[list[dict[str, Any]]]:
        """Return every media row in *project* (created_at then id)."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            rows = self._media.list(self._writer, project_id)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([row.to_dict() for row in rows])

    # -- show --------------------------------------------------------------

    def show(self, project: str, ref: str) -> DomainResult[dict[str, Any]]:
        """Return one media's frozen read model by project-scoped media id."""
        try:
            project_id = self._projects.resolve(self._writer, project)
            media_id = self._resolve_media_id(project_id, ref)
            model = self._media.show(self._writer, media_id)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(model.to_dict())

    # -- verify ------------------------------------------------------------

    def verify(
        self,
        project: str,
        ref: str,
        *,
        realm: str,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Fingerprint-verified verification of one local location.

        Resolves the media id project-scoped, hashes the selected ``realm``
        location's bytes **outside** any transaction, then delegates the
        race-safe re-stat/re-hash command inside one unit of work. A missing
        or mutated location changes zero rows (no event, head, projection,
        or receipt).
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
            media_id = self._resolve_media_id(project_id, ref)
            locator = self._resolve_locator(media_id, realm)
            fingerprint = prepare_media_fingerprint(locator)
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
                lambda uow: self._media.verify(
                    uow,
                    project_id=project_id,
                    media_id=media_id,
                    realm=realm,
                    idempotency_key=key,
                    fingerprint=fingerprint,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- relocate ----------------------------------------------------------

    def relocate(
        self,
        project: str,
        ref: str,
        *,
        realm: str,
        locator: str,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Replace one location projection atomically (identity unchanged)."""
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
            media_id = self._resolve_media_id(project_id, ref)
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
                lambda uow: self._media.replace_location(
                    uow,
                    project_id=project_id,
                    media_id=media_id,
                    realm=realm,
                    locator=locator,
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

    # -- relate ------------------------------------------------------------

    def relate(
        self,
        project: str,
        *,
        relations: Sequence[Mapping[str, Any]],
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Materialize media relation edges atomically (frozen five kinds).

        Every relation-domain rule — the frozen kind vocabulary, self-edge
        rejection, exact-duplicate rejection, the one ``variant_of`` parent
        limit, and the acyclic variant graph — is delegated to the
        repository, which evaluates it before any SQL write. No direction
        matrix is invented here (SDK contract §5.3).
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
                lambda uow: self._media.relate(
                    uow,
                    project_id=project_id,
                    relations=relations,
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

    # -- private helpers ---------------------------------------------------

    @staticmethod
    def _resolve_key(idempotency_key: str | None) -> str:
        """Return the caller key or a fresh generated key."""
        try:
            return resolve_idempotency_key(idempotency_key)
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc

    def _resolve_media_id(self, project_id: str, ref: str) -> str:
        """Resolve a media id project-scoped on a separate read-only connection."""
        with self._writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            return self._media.resolve_media(
                conn, project_id=project_id, media_id=ref
            )

    def _resolve_locator(self, media_id: str, realm: str) -> str:
        """Return the single locator for ``(media_id, realm)`` (read-only)."""
        model = self._media.show(self._writer, media_id)
        matching = [loc for loc in model.locations if loc.realm == realm]
        if not matching:
            raise MediaLocationNotFoundError(media_id=media_id, realm=realm)
        if len(matching) > 1:
            raise MediaConflictError(
                media_id=media_id,
                reason="multiple_locations",
                detail=(
                    f"realm={realm!r} has {len(matching)} locations; "
                    "verification requires an unambiguous single location"
                ),
            )
        return matching[0].locator

    def _committed_receipt(
        self, project_id: str, idempotency_key: str
    ) -> CommandReceipt | None:
        """Read-only lookup of the committed receipt for a mutation."""
        with self._writer.read_only_connection() as conn:
            return self._receipts.lookup_committed(
                conn, project_id=project_id, idempotency_key=idempotency_key
            )
