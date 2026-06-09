"""Combined current-run pointer + session-lease state.

These helpers join the project's ``current_run.json`` pointer (owned by
``astrid.core.project.current_run``) with the run's ``lease.json`` metadata
(owned by ``astrid.core.session.lease``). They live in the session package
because that is the side that owns the lease; ``current_run`` stays a pure
pointer primitive that the session/task tiers consume.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.foundation.project_paths import project_dir, validate_run_id
from astrid.core.project.current_run import (
    CurrentRunError,
    legacy_active_run_path,
    read_current_run,
    write_current_run,
)
from astrid.core._shared.jsonio import read_json


def read_current_run_state(
    slug: str, *, root: str | Path | None = None
) -> dict[str, str] | None:
    """Return ``{run_id, plan_hash}`` from canonical current-run + lease state."""

    run_id = read_current_run(slug, root=root)
    if run_id is None:
        return None
    # Lazy import: session.lease pulls in task.events, which (via task/__init__)
    # re-enters this module at import time. Deferring keeps module init acyclic.
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
