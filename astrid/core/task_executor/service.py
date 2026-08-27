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

6. **Fenced completion (plan step 10).** :meth:`ExecutionService.complete`
   passes the prepared outputs of :meth:`execute` into the repository's
   fenced completion command inside the caller's UoW, enforcing exactly one
   primary and ordered roles before the command runs, and returns the typed
   :class:`CompletionResult`: ``\"completed\"`` with the full stored
   :class:`~astrid.core.repositories.tasks.TaskCompleteReadModel` (exact
   replay included), or ``\"stale\"`` / ``\"losing\"`` with the typed error
   detail and zero semantic rows when the completion lost a fence or the
   single-winner race.

The caller owns the unit of work and the writer; the service only submits
short repository operations through them (single-writer architecture).
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Callable
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
    CORE_TASK_COMPLETE_COMMAND_KIND,
    TaskAttemptNotFoundError,
    TaskAttemptReadModel,
    TaskCompleteReadModel,
    TaskFailReadModel,
    TaskReadModel,
    TaskRepository,
    TaskTransitionError,
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

_TASK_HANDLER_FACTORIES: dict[str, Callable[[], TaskHandler]] = {}
"""Registered TaskHandler factories keyed by binding name.

Bindings are declared constants of the owning integration (e.g. the
Reigh ``vibecomfy`` binding); registration is an explicit import-time
act by the integration module — never plugin discovery, never a
filesystem scan (growth by declaration, doc 27 §3.3).
"""


def register_task_handler(binding: str, factory: Callable[[], TaskHandler]) -> None:
    """Register one TaskHandler factory under *binding*.

    Re-registering the same binding with a different factory is a
    programming error and raises :class:`TaskExecutorError` — one
    authority per binding, no silent overrides.
    """
    if not isinstance(binding, str) or not binding:
        raise TaskExecutorError("binding must be a non-empty string")
    if not callable(factory):
        raise TaskExecutorError("factory must be callable")
    existing = _TASK_HANDLER_FACTORIES.get(binding)
    if existing is not None and existing is not factory:
        raise TaskExecutorError(
            f"binding {binding!r} already has a registered handler factory"
        )
    _TASK_HANDLER_FACTORIES[binding] = factory


def resolve_task_handler(binding: str) -> TaskHandler:
    """Resolve the one registered handler for *binding*."""
    factory = _TASK_HANDLER_FACTORIES.get(binding)
    if factory is None:
        raise TaskExecutorError(
            f"no TaskHandler registered for binding {binding!r}"
        )
    return factory()


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
    bounded payload), or ``"cancelled"`` when an operator won the terminal
    cancellation fence while the handler was outside SQLite. Only these
    typed outcomes are ever produced —
    never a raw SQLite busy error and never an un-routed handler error.
    """

    outcome: str
    prepared: PreparedExecution | None = None
    failure: TaskFailReadModel | None = None
    error: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.outcome not in ("prepared", "failed", "cancelled"):
            raise TaskExecutorError(
                f"execution outcome must be 'prepared', 'failed', or "
                f"'cancelled', "
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
        if self.outcome == "cancelled" and self.failure is not None:
            raise TaskExecutorError(
                "a cancelled outcome does not carry a failure receipt"
            )


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """The typed outcome of one :meth:`ExecutionService.complete` call.

    ``outcome`` is ``\"completed\"`` (the fenced completion command won and
    ``completed`` carries the full stored :class:`TaskCompleteReadModel`,
    including every ordered materialized output), ``\"stale\"`` (the
    completion lost to a version/lease/ownership fence — the caller is
    behind the attempt's current state, so nothing was materialized), or
    ``\"losing\"`` (the task already reached a terminal state, so this
    completion lost the single-winner race and nothing was materialized).
    Stale and losing outcomes carry the typed error detail in ``error``;
    the repository guarantees zero semantic rows (no media, no
    ``task_outputs``, no receipt, no head advance) for both.
    """

    outcome: str
    completed: TaskCompleteReadModel | None = None
    error: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.outcome not in ("completed", "stale", "losing"):
            raise TaskExecutorError(
                f"completion outcome must be 'completed', 'stale', or "
                f"'losing', got {self.outcome!r}"
            )
        if self.outcome == "completed" and self.completed is None:
            raise TaskExecutorError(
                "a completed outcome must carry the stored completion"
            )
        if self.outcome in ("stale", "losing") and self.error is None:
            raise TaskExecutorError(
                "a stale or losing outcome must carry the typed error detail"
            )
        if self.outcome in ("stale", "losing") and self.completed is not None:
            raise TaskExecutorError(
                "a stale or losing outcome never carries a completion"
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
            try:
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
            except TaskTransitionError as transition:
                if transition.reason != "task_not_running":
                    raise
                self.cleanup_staging(staging_dir)
                return ExecutionResult(
                    outcome="cancelled",
                    error={
                        "reason": "cancelled",
                        "message": (
                            "operator cancellation won while the handler was "
                            "running; no artifact was published"
                        ),
                    },
                )
            # A failed attempt no longer owns its quarantine.  Remove only
            # the exact per-attempt directory created above; startup GC still
            # handles crash leftovers, while synchronous failures must not
            # leave a misleading doctor warning behind.
            self.cleanup_staging(staging_dir)
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

    @staticmethod
    def cleanup_staging(staging_dir: Path) -> None:
        """Best-effort removal of one terminal attempt's staging directory.

        This path is generated by the kernel and is never caller supplied.
        Refuse symlinks so cleanup cannot follow an executor-created escape;
        an unusual filesystem failure is left for the next startup GC pass.
        """
        try:
            if staging_dir.is_dir() and not staging_dir.is_symlink():
                shutil.rmtree(staging_dir)
        except OSError:
            # Failure state is already durably recorded.  Retaining an
            # unremovable directory is safer than masking that outcome.
            return

    # Kept as a private compatibility alias for callers that used the old
    # failure-specific helper while the service was still staging-only.
    _cleanup_failed_staging = cleanup_staging

    def complete(
        self,
        uow: UnitOfWork,
        *,
        prepared: PreparedExecution,
        media_repo: Any,
        idempotency_key: str,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str | None = None,
    ) -> CompletionResult:
        """Complete one prepared execution through the fenced command.

        Passes the prepared outputs of :meth:`execute` into the repository's
        fenced completion command (:meth:`TaskRepository.complete`, plan
        step 10): each output's immutable :class:`PreparedMedia` record is
        materialized through the caller's ``media_repo`` in the same UoW
        (verified bytes published or digest-reused), ordered ``task_outputs``
        rows are inserted, the attempt and task terminate ``succeeded`` with
        ``winning_attempt_id`` set, and **one** complete receipt records
        every ordered event id. The service enforces the output contract
        before the command runs — exactly one primary and ordered roles —
        and sorts the entries by ordinal so the stored output set is
        deterministic.

        The outcome is always the typed :class:`CompletionResult`:

        - ``\"completed\"`` — the command won; ``completed`` is the full
          stored :class:`TaskCompleteReadModel`. An identical retry under
          the same ``idempotency_key`` replays exactly the stored result,
          including the complete stored output set, with zero new rows.
        - ``\"stale\"`` — the completion lost a version/lease/ownership
          fence (the caller is behind the attempt's current state) or the
          attempt is unknown; ``error`` carries the typed reason and no
          semantic row is materialized.
        - ``\"losing\"`` — the task already reached a terminal state (the
          single-winner race was decided earlier); ``error`` carries the
          typed reason and no semantic row is materialized.

        The caller owns the unit of work and the writer, exactly as with
        :meth:`execute`; the service only submits the short repository
        command through them.
        """
        if not isinstance(prepared, PreparedExecution):
            raise TaskExecutorError(
                "prepared must be the PreparedExecution returned by "
                f"execute, got {type(prepared).__name__}"
            )
        if not hasattr(media_repo, "materialize_prepared"):
            raise TaskExecutorError(
                "media_repo must expose materialize_prepared for the "
                "in-UoW media primitive (T17), got "
                f"{type(media_repo).__name__}"
            )
        idempotency_key = str(idempotency_key).strip()
        if not idempotency_key:
            raise TaskExecutorError("idempotency_key must be a non-empty string")
        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskExecutorError("now must be a non-empty string")

        # Service-level output contract: exactly one primary, ordered roles,
        # deterministic ordinal order — enforced before the command runs.
        outputs = self._completion_entries(prepared)

        def run(u: UnitOfWork) -> TaskCompleteReadModel:
            return self._task_repo.complete(
                u,
                project_id=prepared.task.project_id,
                task_id=prepared.task.id,
                attempt_id=prepared.attempt.id,
                lease_id=prepared.attempt.lease_id,
                expected_status_version=prepared.attempt.status_version,
                idempotency_key=idempotency_key,
                outputs=outputs,
                media_repo=media_repo,
                actor_kind=actor_kind,
                now=stamp,
                command_kind=command_kind
                if command_kind is not None
                else CORE_TASK_COMPLETE_COMMAND_KIND,
            )

        try:
            completed = uow.run(run)
        except TaskTransitionError as exc:
            # A completion that lost to a terminal task is "losing"; every
            # other version/lease/ownership fence is a stale caller. Either
            # way the repository changed zero rows before raising.
            outcome = "losing" if exc.reason == "task_not_running" else "stale"
            return CompletionResult(
                outcome=outcome,
                error={
                    "reason": exc.reason,
                    "task_id": exc.task_id,
                    "attempt_id": exc.attempt_id,
                    "message": str(exc),
                },
            )
        except TaskAttemptNotFoundError as exc:
            return CompletionResult(
                outcome="stale",
                error={
                    "reason": "attempt_not_found",
                    "task_id": prepared.task.id,
                    "attempt_id": exc.attempt_id,
                    "message": str(exc),
                },
            )

        return CompletionResult(outcome="completed", completed=completed)

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
                update_run_projection=True,
            )

        return uow.run(run)

    @staticmethod
    def _completion_entries(
        prepared: PreparedExecution,
    ) -> list[dict[str, Any]]:
        """Enforce the output contract and order one completion's entries.

        The service-side mirror of the repository's request validation
        (``TaskRepository._normalize_completion_outputs``), run **before**
        the completion command so a malformed prepared execution never
        reaches SQL: exactly one primary output, the primary's role is
        ``\"result\"`` (the DDL CHECK ``role = 'result' OR is_primary = 0``
        mirror), and the entries are returned ordered by ordinal (ties
        impossible after the manifest's unique-ordinal validation). Role
        defaults follow the manifest convention: ``\"result\"`` for the
        primary, ``\"output\"`` for every other entry.
        """
        outputs = list(prepared.outputs)
        primaries = [output for output in outputs if output.is_primary]
        if len(primaries) != 1:
            raise TaskExecutorError(
                "complete requires exactly one primary output "
                f"(got {len(primaries)})"
            )
        primary = primaries[0]
        role = primary.role if primary.role is not None else "result"
        if role != "result":
            raise TaskExecutorError(
                "only a 'result' output may be primary "
                "(DDL CHECK role = 'result' OR is_primary = 0)"
            )
        entries: list[dict[str, Any]] = []
        for output in sorted(outputs, key=lambda out: out.ordinal):
            entry: dict[str, Any] = {
                "ordinal": output.ordinal,
                "is_primary": output.is_primary,
                "role": output.role if output.role is not None else (
                    "result" if output.is_primary else "output"
                ),
                "prepared": output.prepared,
            }
            if output.label is not None:
                entry["label"] = output.label
            if output.path is not None:
                entry["path"] = output.path
            entries.append(entry)
        return entries
