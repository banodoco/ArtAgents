"""Durable, versioned experiment-review draft state.

A small, explicit state document shared by ``iteration.experiment_review_session``
(which initializes it) and ``editorial.human_review`` (which applies saves
server-side).  It lives in core so both packs share one shape without a
pack-to-pack import — importing another pack's ``run.py`` would trip that
pack's canonical-entrypoint guard.

Shape::

    {"schema_version": 1, "kind": "experiment_review_state",
     "experiment_id": "...", "state_version": 0,
     "updated_at": "...", "draft": {}}

The ``draft`` is a flat map of reviewer-entered values (rubric scores, verdicts,
notes) keyed by ``case_id``.  It is deliberately separate from the dataset
``review_decisions`` map so the two review kinds never overload each other's
fields.

The document is **bound to exactly one experiment**: its ``experiment_id`` is
canonical-validated on read, and every save must carry the same id.  Reusing a
state file for a different experiment fails closed (the existing file is left
untouched) instead of silently clobbering another review's draft.

Saves are versioned: a save must carry the ``base_state_version`` it was built
from; the server increments ``state_version`` and rejects a stale base with
:class:`StaleStateConflict` (HTTP 409) so concurrent editors cannot silently
clobber one another.  The read-check-increment-write transaction is serialized
by a small POSIX file lock so the compare-and-swap is safe across **two server
processes**, not merely threads in one process.
"""

from __future__ import annotations

import contextlib
import os
import threading
from pathlib import Path
from typing import Any, Iterator

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.contracts.errors import AstridError
from astrid.core.experiments.schema import (
    ExperimentValidationError,
    validate_experiment_id,
)
from astrid.core.util.time import utc_now_iso

EXPERIMENT_REVIEW_STATE_KIND = "experiment_review_state"

try:  # POSIX only — Windows has no fcntl; see ``_state_file_lock``.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback path
    _fcntl = None


class StaleStateConflict(Exception):
    """Raised when a save was based on an older ``state_version``."""


def make_initial_experiment_review_state(
    experiment_id: str, *, now: str | None = None
) -> dict[str, Any]:
    """Return a fresh experiment-review state document (version 0, empty draft)."""
    _require_canonical_experiment_id(experiment_id, where="requested experiment id")
    timestamp = now or utc_now_iso()
    return {
        "schema_version": 1,
        "kind": EXPERIMENT_REVIEW_STATE_KIND,
        "experiment_id": experiment_id,
        "state_version": 0,
        "updated_at": timestamp,
        "draft": {},
    }


def _require_canonical_experiment_id(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AstridError(
            f"{where} must be a non-empty experiment_id string",
            recovery_command="pass the canonical experiment_id from experiment.json",
        )
    try:
        return validate_experiment_id(value)
    except ExperimentValidationError as exc:
        raise AstridError(
            f"{where} is not a canonical experiment_id: {exc}",
            recovery_command="pass an id matching ^[a-z0-9][a-z0-9._-]*$",
        ) from exc


def validate_experiment_review_state(data: Any) -> dict[str, Any]:
    """Validate the complete persisted state shape; return it on success.

    Raises :class:`AstridError` (fail-closed) on any deviation: schema version,
    kind, canonical non-empty ``experiment_id``, a non-negative integer
    ``state_version`` (a bool is rejected), a string ``updated_at``, and an
    object ``draft``.
    """
    if not isinstance(data, dict):
        raise AstridError(
            "experiment review state must be a JSON object",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        )
    if (
        type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
    ):
        raise AstridError(
            f"experiment review state schema_version must be 1, got {data.get('schema_version')!r}",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        )
    if data.get("kind") != EXPERIMENT_REVIEW_STATE_KIND:
        raise AstridError(
            f"experiment review state kind must be {EXPERIMENT_REVIEW_STATE_KIND!r}, "
            f"got {data.get('kind')!r}",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        )
    _require_canonical_experiment_id(
        data.get("experiment_id"), where="experiment review state experiment_id"
    )
    version = data.get("state_version")
    # ``bool`` is a subclass of ``int`` — reject it explicitly so True/False
    # can never masquerade as a state version.
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise AstridError(
            f"experiment review state state_version must be a non-negative integer, got {version!r}",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        )
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise AstridError(
            "experiment review state updated_at must be a non-empty string",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        )
    if not isinstance(data.get("draft"), dict):
        raise AstridError(
            "experiment review state draft must be an object",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        )
    return data


def init_experiment_review_state(
    state_path: Path, experiment_id: str
) -> dict[str, Any]:
    """Idempotently initialize ``review.state.json`` bound to *experiment_id*.

    Contract (the entire check/validate/create transaction runs under the same
    cross-process lock as :func:`apply_experiment_review_save`):

    - No file exists → create one atomically, bound to *experiment_id*.
    - A valid state for the **same** experiment → returned untouched, so
      re-running the orchestrator preserves an in-flight draft.
    - A valid state for a **different** experiment → fail closed with an
      actionable :class:`AstridError`; the existing file is preserved.
    - Any existing file that is unreadable, non-object, wrong-kind, malformed,
      or otherwise invalid → fail closed; the bytes are **never** silently
      overwritten.  Resetting another review's draft (or garbage) is the
      caller's explicit decision, not this function's.

    On a platform without the POSIX locking primitive, initialization fails
    closed rather than claiming init/CAS safety it cannot provide.
    """
    requested_id = _require_canonical_experiment_id(
        experiment_id, where="requested experiment id"
    )
    with _state_file_lock(state_path):
        if not state_path.is_file():
            # Nothing exists under the lock — create once, atomically.
            state = make_initial_experiment_review_state(requested_id)
            write_json_atomic(state_path, state)
            return state
        # A file exists.  Read it strictly: any problem (unreadable,
        # non-object, wrong-kind, malformed) fails closed and the bytes are
        # left untouched.  We never silently reset an existing document.
        try:
            data = read_json(state_path)
        except (OSError, ValueError) as exc:
            raise AstridError(
                f"experiment review state at {state_path} exists but is unreadable: {exc}",
                recovery_command=(
                    "inspect review.state.json; remove it only if it is genuinely "
                    "corrupt, then re-run the review session to initialize it"
                ),
            ) from exc
        # Strict-validate before deciding to reuse.  A malformed, wrong-kind,
        # or otherwise invalid document is a real integrity problem — surface
        # it and preserve the bytes rather than silently resetting a review.
        validate_experiment_review_state(data)
        bound_id = data["experiment_id"]
        if bound_id != requested_id:
            raise AstridError(
                f"refusing to reuse experiment-review state bound to {bound_id!r} "
                f"for experiment {requested_id!r}",
                recovery_command=(
                    "point --out at a fresh directory for this experiment, or remove "
                    "the existing review.state.json to start a new review"
                ),
            )
        return data


def read_experiment_review_state(state_path: Path) -> dict[str, Any] | None:
    """Loosely read an experiment-review state file.

    Returns the parsed object when the file exists and carries the
    ``experiment_review_state`` kind; returns ``None`` when the file is
    absent, unparseable, or a different kind.  This is the *loose* read used
    to decide whether to initialize; callers that need the full contract use
    :func:`validate_experiment_review_state` /
    :func:`load_experiment_review_state`.
    """
    if not state_path.is_file():
        return None
    try:
        data = read_json(state_path)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("kind") != EXPERIMENT_REVIEW_STATE_KIND:
        return None
    return data


def load_experiment_review_state(
    state_path: Path, *, expected_experiment_id: str
) -> dict[str, Any]:
    """Strictly load and validate the state bound to *expected_experiment_id*.

    Raises :class:`AstridError` when the file is missing, malformed, or bound
    to a different experiment.  Used by the save path so a cross-experiment
    write can never land in another review's state file.
    """
    expected_id = _require_canonical_experiment_id(
        expected_experiment_id, where="expected experiment id"
    )
    if not state_path.is_file():
        raise AstridError(
            "experiment review state not initialized",
            recovery_command="re-run the review session to initialize review.state.json",
        )
    try:
        data = read_json(state_path)
    except (OSError, ValueError) as exc:
        raise AstridError(
            f"experiment review state at {state_path} is unreadable: {exc}",
            recovery_command="remove review.state.json and re-run the review session to initialize it",
        ) from exc
    validate_experiment_review_state(data)
    if data["experiment_id"] != expected_id:
        raise AstridError(
            f"experiment review state is bound to {data['experiment_id']!r}, "
            f"but a save for {expected_id!r} was submitted",
            recovery_command="submit the save against the correct experiment's review.state.json",
        )
    return data


def is_experiment_review_save(body: Any) -> bool:
    """An experiment-review draft save: ``base_state_version`` + ``draft``.

    Distinct from the dataset diff shape (``base_state_version`` + ``revisions``)
    so the server can dispatch on body shape without ambiguity.
    """
    return (
        isinstance(body, dict)
        and "base_state_version" in body
        and "draft" in body
        and "revisions" not in body
    )


@contextlib.contextmanager
def _state_file_lock(state_path: Path) -> Iterator[None]:
    """Cross-process exclusive lock around a state transaction.

    A dedicated, stable sibling lock file (``<state_path>.lock``) is flock'd so
    the read-check-increment-write CAS — and state initialization — are
    serialized across independent server processes, not merely threads in one
    process.  The lock file is never renamed, so the lock is held on a stable
    inode even though the state file itself is atomically replaced on each
    write.

    Portability contract: on POSIX this is a genuine blocking exclusive
    ``flock``.  On platforms without ``fcntl`` (e.g. Windows) this **fails
    closed** with an actionable :class:`AstridError` rather than degrading to
    a no-op: a no-op lock would let two processes both initialize (or both win
    a CAS), silently corrupting a review.  POSIX is the supported deployment
    target.
    """
    if _fcntl is None:  # pragma: no cover - non-POSIX fallback path
        raise AstridError(
            "experiment-review state requires POSIX cross-process locking (fcntl), "
            "which is unavailable on this platform",
            recovery_command=(
                "run the review session on a POSIX host (the supported deployment target)"
            ),
        )
    lock_path = Path(str(state_path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        yield
    finally:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def apply_experiment_review_save(
    state_path: Path,
    body: dict[str, Any],
    *,
    lock: threading.Lock | None = None,
) -> dict[str, Any]:
    """Apply an experiment-review draft save and return the next state.

    Requires:

    - a ``draft`` object,
    - a canonical ``experiment_id`` equal to the persisted state's id, and
    - a non-negative integer ``base_state_version`` (a bool is rejected).

    Rejects stale writes (``base_state_version`` ≠ current) with
    :class:`StaleStateConflict`.  The read-check-increment-write transaction
    runs under a POSIX file lock so it is a genuine compare-and-swap across
    processes.  The optional in-process *lock* is retained for callers that
    already hold one (harmless redundancy; the file lock is authoritative).
    """
    if not isinstance(body, dict):
        raise AstridError(
            "experiment review /save requires a JSON object body",
            recovery_command="POST {experiment_id, base_state_version, draft}",
        )
    draft = body.get("draft")
    if not isinstance(draft, dict):
        raise AstridError(
            "experiment review /save requires a 'draft' object",
            recovery_command="POST {experiment_id, base_state_version, draft} with the working draft",
        )
    experiment_id = _require_canonical_experiment_id(
        body.get("experiment_id"), where="experiment review /save experiment_id"
    )
    base_version = body.get("base_state_version")
    if not isinstance(base_version, int) or isinstance(base_version, bool) or base_version < 0:
        raise AstridError(
            f"experiment review /save base_state_version must be a non-negative integer, "
            f"got {base_version!r}",
            recovery_command="POST the current state_version (from /state.json) as base_state_version",
        )

    def _commit() -> dict[str, Any]:
        state = load_experiment_review_state(
            state_path, expected_experiment_id=experiment_id
        )
        current_version = state["state_version"]
        if base_version != current_version:
            raise StaleStateConflict(
                f"base_state_version {base_version} does not match current "
                f"state_version {current_version}"
            )
        next_state = dict(state)
        next_state["draft"] = {str(k): v for k, v in draft.items()}
        next_state["state_version"] = current_version + 1
        next_state["updated_at"] = utc_now_iso()
        write_json_atomic(state_path, next_state)
        return next_state

    # Cross-process file lock is authoritative; the thread lock (when given)
    # only adds in-process serialization on top.
    with _state_file_lock(state_path):
        if lock is None:
            return _commit()
        with lock:
            return _commit()


__all__ = [
    "EXPERIMENT_REVIEW_STATE_KIND",
    "StaleStateConflict",
    "apply_experiment_review_save",
    "init_experiment_review_state",
    "is_experiment_review_save",
    "load_experiment_review_state",
    "make_initial_experiment_review_state",
    "read_experiment_review_state",
    "validate_experiment_review_state",
]
