"""Per-project active-run pointer (Sprint 1 replacement for active_run.json).

Legacy migration ordering contract:

    Legacy ``active_run.json``/thread-era current-run state is migrated into
    ``current_run.json`` plus ``runs/<id>/lease.json`` before normal
    writer-auth runs. Once migration has had that chance, missing or malformed
    canonical lease state is a hard error rather than an implicit orphan.

Lease-first write ordering contract:

    Producers (``cmd_start``) MUST write ``runs/<id>/lease.json`` first, then
    ``<project>/current_run.json``. Readers (the WriterContext auto-rebind
    path in particular) read ``current_run.json`` first and rely on the lease
    being present — without lease-first ordering a reader could observe a
    fresh run pointer while the lease is still missing and incorrectly treat
    the run as orphaned.

Schema: ``{"run_id": "<run-id>"}``. Lease metadata (epoch, writer, plan_hash)
lives in the run's ``lease.json`` — keeping it out of this pointer avoids a
two-writer race on the same file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import read_json, write_json_atomic
from astrid.core.project.paths import project_dir, validate_run_id

LEGACY_ACTIVE_RUN_FILENAME = "active_run.json"


class CurrentRunError(ValueError):
    """Raised when current_run.json is malformed."""


def current_run_path(slug: str, *, root: str | Path | None = None) -> Path:
    return project_dir(slug, root=root) / "current_run.json"


def legacy_active_run_path(slug: str, *, root: str | Path | None = None) -> Path:
    return project_dir(slug, root=root) / LEGACY_ACTIVE_RUN_FILENAME


def read_current_run(slug: str, *, root: str | Path | None = None) -> str | None:
    """Return the bound run id, or ``None`` when the project is detached."""

    path = current_run_path(slug, root=root)
    try:
        payload = read_json(path)
    except FileNotFoundError:
        return None
    return _validate_payload(payload, path)


def write_current_run(
    slug: str,
    run_id: str,
    *,
    root: str | Path | None = None,
) -> str:
    """Atomically point the project at ``run_id``.

    Callers MUST already have written ``runs/<run_id>/lease.json`` (see
    module docstring for the lease-first ordering contract).
    """

    validated = validate_run_id(run_id)
    write_json_atomic(current_run_path(slug, root=root), {"run_id": validated})
    return validated


def clear_current_run(slug: str, *, root: str | Path | None = None) -> None:
    current_run_path(slug, root=root).unlink(missing_ok=True)


def read_current_run_state(
    slug: str, *, root: str | Path | None = None
) -> dict[str, str] | None:
    """Return ``{run_id, plan_hash}`` from canonical current-run + lease state."""

    run_id = read_current_run(slug, root=root)
    if run_id is None:
        return None
    # Lazy import avoids project/session/task package cycles during startup.
    from astrid.core.session.lease import read_lease

    run_dir = project_dir(slug, root=root) / "runs" / run_id
    lease = read_lease(run_dir)
    plan_hash = lease.get("plan_hash") or ""
    return {"run_id": run_id, "plan_hash": plan_hash}


def migrate_legacy_active_run_before_writer_auth(
    slug: str,
    *,
    root: str | Path | None = None,
    session_id: str,
) -> str | None:
    """Migrate provable legacy ``active_run.json`` state to canonical files.

    This function is intentionally narrow and runs before WriterContext's
    lease/auth check. It only migrates when the project has no canonical
    ``current_run.json`` and the legacy payload proves both the run id and
    plan hash. The canonical lease is written before the current-run pointer,
    then both files are re-read before the legacy file is deleted.
    """

    if read_current_run(slug, root=root) is not None:
        return None

    legacy_path = legacy_active_run_path(slug, root=root)
    try:
        payload = read_json(legacy_path)
    except FileNotFoundError:
        return None
    if not isinstance(payload, dict):
        raise CurrentRunError(f"{legacy_path} must be a JSON object")

    run_id_raw = payload.get("run_id")
    if not isinstance(run_id_raw, str) or not run_id_raw:
        raise CurrentRunError(f"{legacy_path} run_id must be a non-empty string")
    run_id = validate_run_id(run_id_raw)

    plan_hash = payload.get("plan_hash")
    if not isinstance(plan_hash, str):
        raise CurrentRunError(f"{legacy_path} plan_hash must be a string")

    run_dir = project_dir(slug, root=root) / "runs" / run_id
    if not run_dir.is_dir():
        raise CurrentRunError(
            f"{legacy_path} points at missing run directory {run_dir}"
        )

    from astrid.core.session.lease import LEASE_FILENAME, read_lease, write_lease_init

    lease_path = run_dir / LEASE_FILENAME
    if lease_path.exists():
        lease = read_lease(run_dir)
        if lease.get("plan_hash", "") != plan_hash:
            raise CurrentRunError(
                f"{legacy_path} plan_hash does not match existing lease.json"
            )
    else:
        write_lease_init(run_dir, session_id=session_id, plan_hash=plan_hash)

    write_current_run(slug, run_id, root=root)
    state = read_current_run_state(slug, root=root)
    if state != {"run_id": run_id, "plan_hash": plan_hash}:
        raise CurrentRunError(f"failed to verify migrated current-run state for {slug!r}")
    legacy_path.unlink()
    return run_id


def _validate_payload(payload: Any, path: Path) -> str:
    if not isinstance(payload, dict):
        raise CurrentRunError(f"{path} must be a JSON object")
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise CurrentRunError(f"{path} run_id must be a non-empty string")
    return validate_run_id(run_id)
