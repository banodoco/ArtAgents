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
- **verify** resolves the media id project-scoped, hashes every matching local
  location's bytes **outside** the transaction
  (:func:`~astrid.core.repositories.media.prepare_media_fingerprint`), then
  delegates the race-safe re-stat/re-hash command (Step 10). Selectors are
  available for precise retries; missing or mutated locations never stamp
  their own rows;
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

import os
import shutil
import sqlite3
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from astrid.core.io.media_import import (
    MediaPathError,
    managed_media_path,
    prepare_media_directory,
    prepare_media_file,
)
from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.media import (
    CORE_MEDIA_IMPORT_COMMAND_KIND,
    EXTERNAL_LOCAL_REALM,
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
    ErrorObject,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import (
    ServiceIntegrityError,
    ServiceValidationError,
    map_error,
)

__all__ = ["MediaService"]

MAX_VERIFY_LOCATION_RESULTS = 32
"""Maximum per-location records returned by one aggregate verification."""


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
        inside one unit of work. Extension-classified video/audio containers
        require a successful strict ffprobe with the corresponding stream;
        undecodable or ffprobe-unavailable inputs return a typed validation
        envelope before any media/event/receipt write. The media id is derived deterministically
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
                def import_prepared(uow: UnitOfWork) -> Any:
                    return self._media.import_prepared(
                        uow,
                        project_id=project_id,
                        prepared=prepared,
                        idempotency_key=child_key,
                        media_id=media_id,
                        realm=realm,
                    )

                model = UnitOfWork(self._writer).run(
                    import_prepared
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
        location_id: str | None = None,
        locator: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Fingerprint-verified verification of one or all local locations.

        Without a selector, every location in the realm is verified in
        deterministic creation/id order. Successful locations commit their
        own verification stamp; failures include per-location evidence and
        explicitly report this partial-success policy. ``location_id`` or
        ``locator`` selects one location for a precise retry.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project)
            media_id = self._resolve_media_id(project_id, ref)
            if location_id is not None and locator is not None:
                raise ServiceValidationError(
                    "pass at most one of --location-id or --locator"
                )
            if realm not in (MANAGED_LOCAL_REALM, EXTERNAL_LOCAL_REALM):
                raise ServiceValidationError(
                    "verify supports only managed_local and external_local realms"
                )
            model = self._media.show(self._writer, media_id)
            matching = [loc for loc in model.locations if loc.realm == realm]
            if location_id is not None:
                matching = [loc for loc in matching if loc.id == location_id]
            elif locator is not None:
                matching = [loc for loc in matching if loc.locator == locator]
            if not matching:
                raise MediaLocationNotFoundError(media_id=media_id, realm=realm)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )

        # Preserve the historical full-media result for an unambiguous call.
        if len(matching) == 1:
            selected = matching[0]
            try:
                fingerprint = prepare_media_fingerprint(selected.locator)
            except MediaPathError:
                return DomainResult.failure(
                    self._location_missing_error(
                        project=project,
                        media_id=media_id,
                        realm=realm,
                        location_id=selected.id,
                    ),
                    idempotency_key=key,
                )
            try:
                verified = UnitOfWork(self._writer).run(
                    lambda uow: self._media.verify(
                        uow,
                        project_id=project_id,
                        media_id=media_id,
                        realm=realm,
                        location_id=(
                            selected.id if location_id is not None else None
                        ),
                        locator=(
                            selected.locator if locator is not None else None
                        ),
                        idempotency_key=key,
                        fingerprint=fingerprint,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
                return DomainResult.failure(map_error(exc), idempotency_key=key)
            return DomainResult.success(
                verified.to_dict(),
                receipt=self._committed_receipt(project_id, key),
                idempotency_key=key,
            )

        # Multiple locations: prepare all fingerprints first so a missing
        # source is represented alongside healthy locations.
        entries: list[dict[str, Any]] = []
        prepared: list[tuple[Any, Any]] = []
        for selected in matching:
            entry: dict[str, Any] = {
                "location_id": selected.id,
                "realm": selected.realm,
                "locator": selected.locator,
                "ok": False,
            }
            try:
                fingerprint = prepare_media_fingerprint(selected.locator)
            except MediaPathError:
                entry["error"] = self._location_missing_error(
                    project=project,
                    media_id=media_id,
                    realm=realm,
                    location_id=selected.id,
                ).as_dict()
            else:
                prepared.append((selected, fingerprint))
            entries.append(entry)

        receipt = None
        for selected, fingerprint in prepared:
            subkey = f"{key}:location:{selected.id}"
            try:
                verified = UnitOfWork(self._writer).run(
                    lambda uow: self._media.verify(
                        uow,
                        project_id=project_id,
                        media_id=media_id,
                        realm=realm,
                        location_id=selected.id,
                        idempotency_key=subkey,
                        fingerprint=fingerprint,
                    )
                )
                if receipt is None:
                    receipt = self._committed_receipt(project_id, subkey)
                item = next(
                    item for item in entries if item["location_id"] == selected.id
                )
                item["ok"] = True
                item["verified_at"] = next(
                    loc["verified_at"]
                    for loc in verified.to_dict()["locations"]
                    if loc["id"] == selected.id
                )
            except Exception as exc:  # noqa: BLE001 - per-location evidence
                item = next(
                    item for item in entries if item["location_id"] == selected.id
                )
                item["error"] = map_error(exc).as_dict()

        successful = sum(1 for item in entries if item["ok"])
        failed = len(entries) - successful
        reported_entries = entries[:MAX_VERIFY_LOCATION_RESULTS]
        aggregate = {
            "media_id": media_id,
            "realm": realm,
            "locations": reported_entries,
            "locations_total": len(entries),
            "locations_truncated": max(0, len(entries) - len(reported_entries)),
            "verified_count": successful,
            "failed_count": failed,
            "partial_success": bool(successful and failed),
        }
        if failed:
            error = ErrorObject(
                code="integrity_error",
                message=(
                    f"verified {successful} of {len(entries)} {realm} locations; "
                    f"{failed} failed"
                ),
                details={
                    **aggregate,
                    "recovery": (
                        "Retry with --location-id <location-id> or --locator "
                        "<source-file> after repairing each failed location"
                    ),
                    "mutation_policy": (
                        "successful locations are committed independently; failed "
                        "locations are unchanged"
                    ),
                },
            )
            return DomainResult.failure(error, idempotency_key=key)
        aggregate["media"] = self._media.show(self._writer, media_id).to_dict()
        return DomainResult.success(
            aggregate,
            receipt=receipt,
            idempotency_key=key,
        )

    # -- relocate ----------------------------------------------------------

    def relocate(
        self,
        project: str,
        ref: str,
        *,
        realm: str,
        locator: str | None = None,
        source: str | Path | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Replace one location projection atomically (identity unchanged).

        ``external_local`` keeps its reference-in-place behavior and requires
        ``locator``. For ``managed_local``, ``source`` is a recovery input:
        Astrid verifies the source SHA-256 against the immutable media
        identity, atomically publishes it to the canonical digest path, and
        only then updates the location projection. A missing or mismatching
        source leaves both the file and database untouched.
        """
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

        backup: Path | None = None
        canonical: Path | None = None
        had_original = False
        published = False
        try:
            model_before = self._media.show(self._writer, media_id)
            if realm == MANAGED_LOCAL_REALM:
                canonical = managed_media_path(
                    self._media._projects_root, model_before.content_hash
                )
                if locator is None:
                    locator = str(canonical)
                if source is not None:
                    if not isinstance(source, (str, Path)) or not str(source):
                        raise ServiceValidationError(
                            "managed_local --source must be a non-empty file path"
                        )
                    try:
                        source_fingerprint = prepare_media_fingerprint(source)
                    except MediaPathError:
                        raise ServiceIntegrityError(
                            f"media {media_id} managed_local recovery source is "
                            "unavailable; no write occurred",
                            details={
                                "media_id": media_id,
                                "realm": realm,
                                "recovery": self._rehydrate_command(
                                    project=project, media_id=media_id
                                ),
                            },
                        ) from None
                    if source_fingerprint.digest != model_before.content_hash:
                        raise ServiceIntegrityError(
                            "managed media source bytes do not match the existing "
                            "media identity; no write occurred",
                            details={
                                "media_id": media_id,
                                "realm": realm,
                                "expected_sha256": model_before.content_hash,
                                "source_sha256": source_fingerprint.digest,
                                "recovery": self._rehydrate_command(
                                    project=project, media_id=media_id
                                ),
                            },
                        )
                    backup, had_original = self._publish_managed_source(
                        source=Path(source),
                        destination=canonical,
                        expected_digest=model_before.content_hash,
                    )
                    published = True
                else:
                    # A managed replacement without a source is a verified
                    # canonical refresh, never a way to bless missing or
                    # mutated bytes as healthy.
                    try:
                        fingerprint = prepare_media_fingerprint(canonical)
                    except MediaPathError:
                        raise ServiceIntegrityError(
                            f"media {media_id} managed_local locator is unavailable; "
                            "provide the original bytes with the public rehydrate "
                            "command; no write occurred",
                            details={
                                "media_id": media_id,
                                "realm": realm,
                                "recovery": self._rehydrate_command(
                                    project=project, media_id=media_id
                                ),
                            },
                        ) from None
                    if fingerprint.digest != model_before.content_hash:
                        raise ServiceIntegrityError(
                            "managed media canonical bytes do not match the existing "
                            "media identity; no write occurred",
                            details={
                                "media_id": media_id,
                                "realm": realm,
                                "expected_sha256": model_before.content_hash,
                                "actual_sha256": fingerprint.digest,
                                "recovery": self._rehydrate_command(
                                    project=project, media_id=media_id
                                ),
                            },
                        )
            elif source is not None:
                raise ServiceValidationError(
                    "--source is supported only for managed_local rehydration; "
                    "external_local uses --locator"
                )
            elif locator is None:
                raise ServiceValidationError(
                    "external_local relocation requires --locator"
                )
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
            if canonical is not None and backup is not None:
                self._restore_managed_source(
                    destination=canonical,
                    backup=backup,
                    had_original=had_original,
                )
                backup = None
            elif canonical is not None and source is not None and published:
                # No original canonical file existed; remove the published
                # copy if the DB command failed before commit.
                self._remove_published_source(canonical)
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        if backup is not None:
            backup.unlink(missing_ok=True)
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

    @staticmethod
    def _rehydrate_command(*, project: str, media_id: str) -> str:
        return (
            "python3 -m astrid media relocate "
            f"{media_id} --project {project} --realm managed_local "
            "--source <source-file>"
        )

    @classmethod
    def _missing_locator_error(
        cls, *, project: str, media_id: str, realm: str
    ) -> Any:
        return ServiceIntegrityError(
            f"media {media_id} {realm} locator is unavailable; no write occurred",
            details={
                "media_id": media_id,
                "realm": realm,
                "recovery": cls._rehydrate_command(
                    project=project, media_id=media_id
                )
                if realm == MANAGED_LOCAL_REALM
                else (
                    "restore the external file, or run media relocate with "
                    "--realm external_local --locator <source-file>"
                ),
            },
        ).to_error_object()

    @classmethod
    def _location_missing_error(
        cls, *, project: str, media_id: str, realm: str, location_id: str
    ) -> ErrorObject:
        """Add the stable location identity to a bounded missing error."""
        base = cls._missing_locator_error(
            project=project, media_id=media_id, realm=realm
        )
        return ErrorObject(
            code=base.code,
            message=base.message,
            details={**dict(base.details), "location_id": location_id},
        )

    @staticmethod
    def _publish_managed_source(
        *, source: Path, destination: Path, expected_digest: str
    ) -> tuple[Path | None, bool]:
        """Publish verified source bytes, returning a rollback backup."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged_fd, staged_name = tempfile.mkstemp(
            prefix=".rehydrate-", dir=str(destination.parent)
        )
        os.close(staged_fd)
        staged = Path(staged_name)
        try:
            shutil.copyfile(source, staged)
            copied = prepare_media_fingerprint(staged)
            if copied.digest != expected_digest:
                raise ServiceIntegrityError(
                    "managed media source changed while copying; no write occurred",
                    details={"expected_sha256": expected_digest},
                )
            backup: Path | None = None
            had_original = destination.is_file() and not destination.is_symlink()
            if had_original:
                backup_fd, backup_name = tempfile.mkstemp(
                    prefix=".rehydrate-backup-", dir=str(destination.parent)
                )
                os.close(backup_fd)
                backup = Path(backup_name)
                shutil.copyfile(destination, backup)
            os.replace(staged, destination)
            return backup, had_original
        finally:
            staged.unlink(missing_ok=True)

    @staticmethod
    def _restore_managed_source(
        *, destination: Path, backup: Path, had_original: bool
    ) -> None:
        if had_original:
            os.replace(backup, destination)
        else:
            destination.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)

    @staticmethod
    def _remove_published_source(destination: Path) -> None:
        destination.unlink(missing_ok=True)

    def _committed_receipt(
        self, project_id: str, idempotency_key: str
    ) -> CommandReceipt | None:
        """Read-only lookup of the committed receipt for a mutation."""
        with self._writer.read_only_connection() as conn:
            return self._receipts.lookup_committed(
                conn, project_id=project_id, idempotency_key=idempotency_key
            )
