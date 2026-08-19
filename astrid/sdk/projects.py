"""Typed project SDK service (m4 plan step 5, task T6).

Exposes repository-backed ``create``, ``list``, ``show``, and ``update`` over
the kernel :class:`~astrid.core.repositories.projects.ProjectRepository` with
the frozen SDK envelope (``docs/contracts/astrid-sdk-v10.md`` section 1):

- **create** accepts an optional caller idempotency key (a fresh key is
  generated before mutation when absent), derives a **deterministic** project
  id from ``(command kind, global scope, key)`` so a retry under the same key
  derives the same id and replays with zero new rows, and returns the
  committed receipt;
- **update** resolves the addressed project by id or slug through the
  repository, then mutates name/settings under one unit of work with the same
  receipt gate (replay / mismatch-before-mutation);
- **list** and **show** are transaction-free reads; ``show`` resolves the
  address by id or slug and returns the full read model, raising a typed
  ``not_found`` for a missing project;
- every mutation returns exactly one :class:`DomainResult` envelope with the
  five frozen keys, the committed :class:`CommandReceipt`, and the key used;
  every failure returns the frozen three-key error object via the centralized
  :func:`map_error` (not-found → ``not_found``, duplicate/slug conflict →
  ``conflict``, validation → ``validation_error``, mismatch →
  ``idempotency_mismatch``).

This module contains **no SQL** and performs **no filesystem project writes**;
every read and mutation is delegated to the project repository (the read model
lives only in the kernel database). The service holds a reference to the
shared writer solely to open one unit of work per mutation and to run
transaction-free reads; it never opens its own writer or connection.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.core.preferences import set_default_project
from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.projects import (
    CORE_PROJECT_CREATE_COMMAND_KIND,
    ProjectRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import ServiceValidationError, map_error

__all__ = ["ProjectsService"]

_PROJECT_GLOBAL_SCOPE = "global"
"""The scope for project creation: projects are top-level, so their
deterministic ids derive from ``(command kind, "global", key)`` (SDK contract
section 4.4 — project/global scope)."""


class ProjectsService:
    """Repository-backed project create/list/show/update SDK surface.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the project repository, and the receipt service; it holds no SQL
    and opens no writer of its own.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        receipts: ReceiptService,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._receipts = receipts

    # -- create ------------------------------------------------------------

    def create(
        self,
        *,
        slug: str,
        name: str,
        settings: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Create one project and return its committed receipt envelope.

        The idempotency key is the caller's when supplied, otherwise a fresh
        key generated before mutation. The project id is derived
        deterministically from the key, so an identical retry replays the
        committed result with zero new rows and a changed request under the
        same key returns ``idempotency_mismatch`` before any mutation.
        """
        try:
            key = self._resolve_key(idempotency_key)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        project_id = derive_stable_id(
            command_kind=CORE_PROJECT_CREATE_COMMAND_KIND,
            scope=_PROJECT_GLOBAL_SCOPE,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._projects.create(
                    uow,
                    slug=slug,
                    name=name,
                    settings=dict(settings) if settings is not None else {},
                    idempotency_key=key,
                    project_id=project_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(model.id, key),
            idempotency_key=key,
        )

    # -- list --------------------------------------------------------------

    def list(self) -> DomainResult[list[dict[str, str]]]:
        """Return every project (slug ascending) as ``{slug, name}`` rows."""
        try:
            rows = self._projects.list(self._writer)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([row.to_dict() for row in rows])

    # -- show --------------------------------------------------------------

    def show(self, ref: str) -> DomainResult[dict[str, Any]]:
        """Return one project's full read model by id or slug.

        Resolves *ref* (exact id first, then immutable slug) through the
        repository; a missing project is a typed ``not_found`` and a
        malformed address is a typed ``validation_error``.
        """
        try:
            project_id = self._projects.resolve(self._writer, ref)
            model = self._projects.show(self._writer, project_id)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(model.to_dict())

    # -- update ------------------------------------------------------------

    def update(
        self,
        ref: str,
        *,
        name: str | None = None,
        settings: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Update a project's name and/or settings and return its receipt.

        Resolves *ref* (id or slug) to the project id, then mutates inside one
        unit of work with the same receipt gate as create: an identical retry
        replays, a changed request under the same key returns
        ``idempotency_mismatch`` before mutation, and a missing project is a
        typed ``not_found``. ``name``/``settings`` are the provided delta;
        caller settings merge over current state but never touch
        repository-owned keys.
        """
        try:
            key = self._resolve_key(idempotency_key)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            project_id = self._projects.resolve(self._writer, ref)
            model = UnitOfWork(self._writer).run(
                lambda uow: self._projects.update(
                    uow,
                    project_id,
                    name=name,
                    settings=settings,
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

    # -- select (non-authoritative preference) -----------------------------

    def select(
        self,
        ref: str,
        *,
        scope: str = "workspace",
        cwd: str | Path | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Resolve *ref* and persist it as the non-authoritative default.

        Non-authoritative context resolution (plan step 5, task T6B): the
        addressed project is resolved by id or slug through the repository
        first (a missing project is a typed ``not_found``, a malformed
        address a typed ``validation_error``), then **only** the resolved
        slug is persisted as ``default_project`` in the retained config
        preference (workspace scope by default; ``scope="user"`` opts into
        the user scope).

        This is a file-side preference, never a receipted database mutation
        and never a sidecar authority: the kernel database is untouched and
        the returned envelope carries **no receipt** and **no idempotency
        key** — exactly the ``show`` envelope shape plus the persisted
        default. A later invocation resolves the same slug through
        :func:`astrid.core.preferences.resolve_default_project` (explicit >
        workspace > user).
        """
        try:
            project_id = self._projects.resolve(self._writer, ref)
            model = self._projects.show(self._writer, project_id)
            set_default_project(model.slug, scope=scope, cwd=cwd)
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
        """Read-only lookup of the committed receipt for a mutation.

        Runs exactly one SELECT on the writer's separate read-only
        connection (no transaction, no writes); returns the complete
        immutable :class:`CommandReceipt`.
        """
        with self._writer.read_only_connection() as conn:
            return self._receipts.lookup_committed(
                conn, project_id=project_id, idempotency_key=idempotency_key
            )
