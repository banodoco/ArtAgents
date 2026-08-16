"""Kernel execution service: injected local handlers outside SQLite (T16).

The service turns one fenced, started attempt into verified prepared media
descriptors — or routes the failure through the repository — without ever
opening its own writer or transaction and without importing packs or remote
execution paths:

1. **Start + staging record (short caller UoW).** The attempt is started
   through :meth:`TaskRepository.start` (receipt-protected, version-fenced)
   and the assigned per-transaction staging id is recorded under the
   reserved ``progress_json`` key :data:`STAGING_TXN_ID_KEY` in the same
   transaction, so startup staging GC preserves the quarantine of every
   live attempt (m2 plan step 3/4). This is runtime state only — like
   heartbeat, it carries no event and no receipt.

2. **Handler execution (outside SQLite).** No transaction is open while the
   injected :class:`TaskHandler` writes files under the assigned staging
   directory and returns a universal result manifest.

3. **Strict manifest validation.** The manifest is validated by
   :func:`astrid.core._shared.result_manifest.validate_result_manifest`
   (T15): concrete contained files, exact byte SHA-256 hashes, unique
   ordinals, at most one primary.

4. **Media descriptors.** Every validated output is prepared into an
   immutable :class:`~astrid.core.io.media_import.PreparedMedia` record
   (hashing/probing outside any transaction), ready for the completion
   command (plan step 10) to materialize.

5. **Failure routing.** Any handler, manifest, or preparation failure is
   routed through :meth:`TaskRepository.fail` (receipt-protected, fenced on
   the post-start status version) with a bounded error payload, and the
   service returns the typed :class:`ExecutionResult` — it never raises for
   handler errors and never writes semantic state itself.

The caller owns the unit of work and the writer; the service only submits
short repository operations through them (single-writer architecture).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from astrid.core._shared.result_manifest import (
    ValidatedResultManifest,
    validate_result_manifest,
)
from astrid.core.contracts.errors import AstridError
from astrid.core.io.media_import import (
    PreparedMedia,
    prepare_media_file,
    staging_path,
)
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
)
from astrid.core.repositories.tasks import (
    DEFAULT_LEASE_SECONDS,
    TaskAttemptReadModel,
    TaskFailReadModel,
    TaskReadModel,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.util.time import utc_now_iso

STAGING_TXN_ID_KEY = "staging_txn_id"
"""The reserved ``progress_json`` key recording an attempt's staging id.

Startup staging GC (m2 plan step 3/4) reads this key on live attempts to
preserve their quarantined staging directories; the value is a kernel
transaction id (``uuid.uuid4().hex``). The key string is the same reserved
        value the standard composition reads (the live-attempt staging key);
kernel code never imports packs, so the constant is declared here.
"""

MAX_ERROR_PAYLOAD_CHARS = 4000
"""Upper bound for the failure message recorded on the attempt."""


class TaskExecutorError(AstridError):
    """Base error for the kernel task-executor boundary (m2 plan step 9)."""


class HandlerExecutionError(TaskExecutorError):
    """Raised when the injected handler itself fails.

    The service normally converts handler failures into the typed
    ``failed`` :class:`ExecutionResult` through the repository failure
    command; this error type exists so callers can catch the handler
    failure family separately from repository outcomes.
    """


class TaskHandler(Protocol):
    """The injected local-handler protocol (kernel/pack boundary).

    A pack-owned adapter implements this protocol. ``execute`` runs
    **outside SQLite**: it writes concrete files under ``staging_dir`` and
    returns a universal result manifest (a JSON object with ``outputs``
    declaring ``path``/``content_hash``/``bytes``/``ordinal``/``is_primary``
    per concrete file). The service strictly validates the manifest and
    prepares media descriptors from it; kernel code never imports the pack.
    """

    def execute(
        self, *, task: TaskReadModel, staging_dir: Path
    ) -> Mapping[str, Any]:
        """Run the capability and return a universal result manifest."""
        ...


@dataclass(frozen=True, slots=True)
class PreparedOutput:
    """One validated handler output plus its prepared media descriptor.

    ``path`` is the staging-relative posix path; ``prepared`` is the
    immutable :class:`PreparedMedia` record (byte SHA-256 identity) the
    completion command materializes into the media repository (plan step 10).
    """

    ordinal: int
    is_primary: bool
    path: str
    prepared: PreparedMedia
    role: str | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe descriptor for logs and receipts."""
        descriptor: dict[str, Any] = {
            "ordinal": self.ordinal,
            "is_primary": self.is_primary,
            "path": self.path,
            "content_hash": self.prepared.digest,
            "byte_size": self.prepared.byte_size,
            "media_kind": self.prepared.media_kind,
            "mime_type": self.prepared.mime_type,
            "rel_path": self.prepared.rel_path,
        }
        if self.role is not None:
            descriptor["role"] = self.role
        if self.label is not None:
            descriptor["label"] = self.label
        return descriptor


@dataclass(frozen=True, slots=True)
class PreparedExecution:
    """One successfully prepared handler execution.

    The attempt is ``running`` (started through the repository), the
    staging transaction id is recorded in its ``progress_json``, and every
    validated concrete output has a prepared media descriptor ready for
    atomic materialization by the completion command.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel
    staging_txn_id: str
    staging_dir: Path
    manifest: ValidatedResultManifest
    outputs: tuple[PreparedOutput, ...]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """The typed outcome of one :meth:`ExecutionService.execute` call.

    ``outcome`` is ``"prepared"`` (handler succeeded and every output is
    validated and prepared) or ``"failed"`` (a handler/manifest/
    preparation failure was routed through the repository failure command;
    ``failure`` carries the fenced failure receipt and ``error`` the
    bounded payload). Only these two typed outcomes are ever produced —
    never a raw SQLite busy error and never an un-routed handler error.
    """

    outcome: str
    prepared: PreparedExecution | None = None
    failure: TaskFailReadModel | None = None
    error: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.outcome not in ("prepared", "failed"):
            raise TaskExecutorError(
                f"execution outcome must be 'prepared' or 'failed', "
                f"got {self.outcome!r}"
            )
        if self.outcome == "prepared" and self.prepared is None:
            raise TaskExecutorError(
                "a prepared outcome must carry the prepared execution"
            )
        if self.outcome == "failed" and self.failure is None:
            raise TaskExecutorError(
                "a failed outcome must carry the routed failure receipt"
            )


def _bounded_message(exc: BaseException) -> str:
    message = str(exc) or type(exc).__name__
    if len(message) > MAX_ERROR_PAYLOAD_CHARS:
        return message[:MAX_ERROR_PAYLOAD_CHARS]
    return message


@dataclass(frozen=True, slots=True)
class _StartedAttempt:
    """Internal post-start state: task model, attempt model, staging id."""

    task: TaskReadModel
    attempt: TaskAttemptReadModel
    staging_txn_id: str


class ExecutionService:
    """Kernel execution service: start, run outside SQLite, prepare, or fail.

    Stateless apart from the projects root and the task repository; a
    single instance is safe to share across callers. The caller owns the
    writer and the unit of work: ``execute`` receives the caller's
    :class:`UnitOfWork` and submits only short repository operations
    through it (no second writer, no own transaction).
    """

    def __init__(
        self,
        *,
        projects_root: str | Path,
        task_repo: TaskRepository,
    ) -> None:
        if not isinstance(task_repo, TaskRepository):
            raise TaskExecutorError(
                "task_repo must be a TaskRepository instance, got "
                f"{type(task_repo).__name__}"
            )
        self._projects_root = Path(projects_root)
        self._task_repo = task_repo

    def execute(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        lease_id: str,
        expected_status_version: int,
        idempotency_key: str,
        handler: TaskHandler,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str | None = None,
    ) -> ExecutionResult:
        """Execute one started attempt through the injected handler.

        Returns :class:`ExecutionResult` with outcome ``"prepared"`` or
        ``"failed"``. Repository-level misuse (unknown task, stale
        status version, lease mismatch, foreign attempt) surfaces as the
        typed repository error from the start/fail command.
        """
        if not hasattr(handler, "execute") or not callable(handler.execute):
            raise TaskExecutorError(
                "handler must implement the TaskHandler protocol "
                "(an execute(task=..., staging_dir=...) method), got "
                f"{type(handler).__name__}"
            )
        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskExecutorError("now must be a non-empty string")

        # 1. Short caller UoW: start the fenced attempt and record its
        #    staging id (runtime state, no event or receipt).
        started = self._start_with_staging(
            uow,
            project_id=project_id,
            task_id=task_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            expected_status_version=expected_status_version,
            idempotency_key=idempotency_key,
            actor_kind=actor_kind,
            now=stamp,
            command_kind=command_kind,
        )

        # 2. Outside SQLite: the handler writes under the assigned staging
        #    directory and returns a universal result manifest. No
        #    transaction is open here.
        staging_dir = staging_path(self._projects_root, started.staging_txn_id)
        try:
            staging_dir.mkdir(parents=True, exist_ok=True)
            raw_manifest = handler.execute(task=started.task, staging_dir=staging_dir)
            manifest = validate_result_manifest(
                raw_manifest, staging_root=staging_dir
            )
            outputs = tuple(
                PreparedOutput(
                    ordinal=output.ordinal,
                    is_primary=output.is_primary,
                    role=output.role,
                    label=output.label,
                    path=output.path,
                    prepared=prepare_media_file(
                        staging_dir / output.path, root=staging_dir
                    ),
                )
                for output in manifest.outputs
            )
        except Exception as exc:  # noqa: BLE001 - routed through fail
            # 3. Short caller UoW: route the failure through the fenced
            #    repository failure command (post-start status version).
            failure = self._route_failure(
                uow,
                project_id=project_id,
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                status_version=started.attempt.status_version,
                # The start receipt already consumed the caller-supplied key
                # (kind core.task.start); the failure command must use a
                # distinct key or the receipt service rejects the second
                # request as an idempotency-key reuse with a different kind.
                idempotency_key=f"{idempotency_key}:fail",
                actor_kind=actor_kind,
                now=stamp,
                exc=exc,
                command_kind=command_kind,
            )
            error = {
                "reason": "handler_failed",
                "type": type(exc).__name__,
                "message": _bounded_message(exc),
            }
            return ExecutionResult(outcome="failed", failure=failure, error=error)

        return ExecutionResult(
            outcome="prepared",
            prepared=PreparedExecution(
                task=started.task,
                attempt=started.attempt,
                staging_txn_id=started.staging_txn_id,
                staging_dir=staging_dir,
                manifest=manifest,
                outputs=outputs,
            ),
        )

    # -- internal orchestration -------------------------------------------

    def _start_with_staging(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        lease_id: str,
        expected_status_version: int,
        idempotency_key: str,
        actor_kind: str,
        now: str,
        command_kind: str | None,
    ) -> PreparedExecution:
        """Start the attempt and record its staging id in one short UoW."""
        staging_txn_id = uuid.uuid4().hex

        def run(u: UnitOfWork) -> _StartedAttempt:
            started = self._task_repo.start(
                u,
                project_id=project_id,
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                expected_status_version=expected_status_version,
                idempotency_key=idempotency_key,
                actor_kind=actor_kind,
                now=now,
                command_kind=command_kind
                if command_kind is not None
                else "core.task.start",
            )
            # Runtime state only: the reserved staging key in progress_json.
            # No event, no receipt — the startup GC reads this key to keep
            # the quarantine of live attempts.
            progress = dict(started.progress)
            progress[STAGING_TXN_ID_KEY] = staging_txn_id
            try:
                progress_json = canonical_json(progress)
            except CanonicalizationError as exc:  # pragma: no cover - dict-only
                raise TaskExecutorError(
                    f"cannot serialize attempt progress: {exc}"
                ) from exc
            cursor = u.execute(
                "UPDATE execution_attempts SET progress_json = ?, "
                "updated_at = ? "
                "WHERE id = ? AND task_id = ? AND status = 'running' "
                "AND status_version = ?",
                (
                    progress_json,
                    now,
                    attempt_id,
                    task_id,
                    started.status_version,
                ),
            )
            if cursor.rowcount != 1:
                raise TaskExecutorError(
                    "cannot record staging id: attempt changed between "
                    "start and the progress update"
                )
            fresh = u.query_one(
                "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
            )
            if fresh is None:  # pragma: no cover - rows cannot vanish
                raise TaskExecutorError(
                    f"attempt {attempt_id!r} disappeared after start"
                )
            # The refreshed task model (same projection the repository's
            # internal helper builds) so the handler sees post-start state.
            task_row = u.query_one(
                "SELECT t.*, p.event_head_seq AS event_head_seq FROM tasks t "
                "JOIN projects p ON p.id = t.project_id "
                "WHERE t.id = ? AND t.project_id = ?",
                (task_id, project_id),
            )
            if task_row is None:  # pragma: no cover - rows cannot vanish
                raise TaskExecutorError(f"task {task_id!r} disappeared after start")
            dependency_rows = u.query(
                "SELECT task_id, depends_on_task_id, kind, ordinal "
                "FROM task_dependencies WHERE task_id = ? "
                "ORDER BY ordinal ASC, depends_on_task_id ASC",
                (task_id,),
            )
            task_model = self._task_repo._row_to_read_model(  # noqa: SLF001
                task_row, [dict(dep) for dep in dependency_rows]
            )
            return _StartedAttempt(
                task=task_model,
                attempt=TaskAttemptReadModel.from_mapping(dict(fresh)),
                staging_txn_id=staging_txn_id,
            )

        return uow.run(run)

    def _route_failure(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        lease_id: str,
        status_version: int,
        idempotency_key: str,
        actor_kind: str,
        now: str,
        exc: BaseException,
        command_kind: str | None,
    ) -> TaskFailReadModel:
        """Route one handler failure through the fenced failure command."""
        error = {
            "reason": "handler_failed",
            "type": type(exc).__name__,
            "message": _bounded_message(exc),
        }

        def run(u: UnitOfWork) -> TaskFailReadModel:
            return self._task_repo.fail(
                u,
                project_id=project_id,
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                expected_status_version=status_version,
                idempotency_key=idempotency_key,
                actor_kind=actor_kind,
                error=error,
                now=now,
                command_kind=command_kind
                if command_kind is not None
                else "core.task.fail",
            )

        return uow.run(run)
