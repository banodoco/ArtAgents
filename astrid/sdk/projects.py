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

This module contains **no SQL**; every read and mutation is delegated to the
project repository (the read model lives only in the kernel database), and the
repository itself performs **no filesystem writes** (v10 conformance). The
*service* composes one bounded filesystem side effect on top of a committed
create: it materializes the per-project workspace binding skeleton
(``<root>/<slug>/plan.md`` plus a lightweight ``project.json`` binding file)
so direct-mode executors can resolve the project. The kernel row stays the
sole authority; the skeleton is best-effort (a materialization failure logs a
warning and never fails the committed create) and never overwrites existing
files. The service holds a reference to the shared writer solely to open one
unit of work per mutation and to run transaction-free reads; it never opens
its own writer or connection.
"""

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.core.foundation.atomic_io import write_json_atomic, write_text_atomic
from astrid.core.foundation.project_paths import project_dir
from astrid.core.preferences import (
    ConfigError,
    resolve_default_project_info,
    set_default_project,
)
from astrid.core.project.workspace import materialize_project_workspace
from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.projects import (
    CORE_PROJECT_CREATE_COMMAND_KIND,
    ProjectRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.log_and_swallow import swallowing
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import ServiceNotFoundError, ServiceValidationError, map_error

__all__ = ["ProjectsService"]

_LOGGER = logging.getLogger(__name__)

_PROJECT_GLOBAL_SCOPE = "global"
"""The scope for project creation: projects are top-level, so their
deterministic ids derive from ``(command kind, "global", key)`` (SDK contract
section 4.4 — project/global scope)."""


def _materialize_workspace(
    *,
    slug: str,
    name: str,
    project_id: str,
    projects_root: str | Path | None,
) -> None:
    """Materialize the per-project filesystem binding skeleton.

    Creates ``<root>/<slug>/`` with ``plan.md`` (the documented empty
    skeleton) and a lightweight ``project.json`` binding file carrying the
    kernel project id and ``kernel_authority: true``. The binding file is
    **not** an authority — the kernel row is; it exists only so direct-mode
    executors (:func:`astrid.core.project.project.require_project` and
    ``require_project_owned_artifact``) resolve the project and land runs
    under ``<root>/<slug>/runs/``. Existing files are never overwritten:
    ``plan.md`` may carry human edits and ``project.json`` may carry fields
    enriched by other flows (e.g. ``default_timeline_id``).
    """
    materialize_project_workspace(
        slug=slug,
        name=name,
        project_id=project_id,
        projects_root=projects_root,
        # Keep the service-level materialization seam patchable for callers
        # that need to exercise the committed-row/failed-filesystem boundary.
        write_json=write_json_atomic,
        write_text=write_text_atomic,
    )


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
        *,
        projects_root: str | Path | None = None,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._receipts = receipts
        # Root of the binding workspace materialized on create (``None``
        # resolves the standard precedence — arg, ASTRID_PROJECTS_ROOT,
        # default — at materialization time).
        self._projects_root = projects_root

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
        # The kernel row is committed and authoritative. Materialize the
        # binding workspace (plan.md + project.json skeleton) so direct-mode
        # executors resolve the project. Best-effort: a materialization
        # failure logs a warning and never fails the committed create.
        with swallowing(
            (
                f"projects.create: workspace materialization for {slug!r} "
                f"failed (kernel row {model.id} remains authoritative)"
            ),
            level=logging.WARNING,
            logger=_LOGGER,
        ):
            _materialize_workspace(
                slug=slug,
                name=name,
                project_id=model.id,
                projects_root=self._projects_root,
            )
        return DomainResult.success(
            self._model_dict(model),
            receipt=self._committed_receipt(model.id, key),
            idempotency_key=key,
        )

    # -- list --------------------------------------------------------------

    def list(self) -> DomainResult[list[dict[str, str]]]:
        """Return every project with its canonical filesystem path."""
        try:
            rows = self._projects.list(self._writer)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(
            [
                {
                    **row.to_dict(),
                    "path": str(project_dir(row.slug, root=self._projects_root).resolve()),
                }
                for row in rows
            ]
        )

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
        return DomainResult.success(self._model_dict(model))

    # -- current -----------------------------------------------------------

    def current(
        self, *, cwd: str | Path | None = None
    ) -> DomainResult[dict[str, Any]]:
        """Read the selected project and the preference scope that supplied it.

        Workspace selection wins over user selection. The preference is only
        a routing hint; the project is resolved against the kernel before the
        successful read is returned, so stale selections fail closed.
        """
        selection: dict[str, str] | None = None
        try:
            selection = resolve_default_project_info(cwd)
            if selection is None:
                raise ServiceValidationError(
                    "no current project is selected; select one before routing project-scoped commands"
                )
            project_id = self._projects.resolve(self._writer, selection["ref"])
            model = self._projects.show(self._writer, project_id)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(
                    exc
                    if getattr(exc, "details", None)
                    else ServiceValidationError(
                        str(exc),
                        details={
                            "field": "project",
                            "reason": "no_current_project",
                            "recovery": "run `astrid projects select <slug-or-id>`",
                        },
                    )
                )
            )
        except ConfigError as exc:
            details = {
                "field": "project",
                "reason": "invalid_selection_preference",
                "recovery": "repair or remove the malformed preference, then run `astrid projects select <slug-or-id>`",
            }
            if exc.scope is not None:
                details["scope"] = exc.scope
            if exc.path is not None:
                details["path"] = exc.path
            return DomainResult.failure(
                map_error(
                    ServiceValidationError(
                        "the current project preference is invalid",
                        details=details,
                    )
                )
            )
        except Exception as exc:  # noqa: BLE001 - stale preference gets context
            if selection is not None and getattr(exc, "project_id", None):
                preference_path = selection.get("path")
                scope = selection.get("scope")
                reselect = "astrid projects select <slug-or-id>"
                if scope in {"workspace", "user"}:
                    reselect += f" --scope {scope}"
                if scope == "workspace" and preference_path:
                    # workspace_config_path(cwd) is the explicit workspace
                    # config, or ASTRID_PROJECTS_ROOT/.astrid/config.json
                    # when the caller isolates a projects root; include the
                    # exact workspace when the stale preference came from
                    # another root/shell location.
                    workspace_dir = Path(preference_path).parent.parent
                    reselect += f" --cwd {workspace_dir}"
                return DomainResult.failure(
                    map_error(
                        ServiceNotFoundError(
                            "the selected project no longer exists in this projects root",
                            details={
                                "entity": "project",
                                "ref": selection["ref"],
                                "scope": scope,
                                "preference_path": preference_path,
                                "reason": "stale_selection",
                                "recovery": (
                                    "run `astrid projects list --json`, then run "
                                    f"`{reselect}` with a listed project"
                                ),
                            },
                        )
                    )
                )
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(
            {
                "project": self._model_dict(model),
                "selection": {
                    "ref": selection["ref"],
                    "scope": selection["scope"],
                    "path": selection.get("path"),
                },
            }
        )

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
            self._model_dict(model),
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
            preference_path = set_default_project(model.slug, scope=scope, cwd=cwd)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(
            {
                "project": self._model_dict(model),
                "selection": {
                    "ref": model.slug,
                    "scope": scope,
                    "path": str(preference_path.resolve()),
                },
            }
        )

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

    def _model_dict(self, model: Any) -> dict[str, Any]:
        """Decorate a project read model with its canonical workspace path."""
        return {
            **model.to_dict(),
            "path": str(project_dir(model.slug, root=self._projects_root).resolve()),
        }
