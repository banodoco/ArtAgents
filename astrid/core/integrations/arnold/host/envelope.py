"""Astrid -> Arnold RuntimeEnvelope projection helpers.

The Arnold host never mints a second run identity.  It projects the
existing Astrid run directory, lease, and event stream into Arnold's
validated ``RuntimeEnvelope`` shape at read time.

Design constraints (SD1):
- Arnold cursor files live under the Astrid run directory, which becomes
  ``RuntimeEnvelope.artifact_root``.
- Astrid owns run identity, lease state, and the rich event log.
- Arnold receives a deterministic projection only; it does not become a
  second source of truth for lease or event lineage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.foundation.project_paths import run_dir
from astrid.core.io.cas import canonical_json_digest
from astrid.core.project.current_run import read_current_run
from astrid.core.session.lease import LeaseError, read_lease
from astrid.core.task.events import EVENTS_FILENAME, read_events

HOST_PLUGIN_ID = "astrid.arnold.host"
HOST_PLUGIN_STATE_SCHEMA_VERSION = 1


class ArnoldEnvelopeProjectionError(RuntimeError):
    """Raised when Astrid state cannot be projected into an Arnold envelope."""


def resolve_run_root(
    project_slug: str,
    *,
    run_id: str | None = None,
    root: str | Path | None = None,
) -> Path:
    """Return the concrete Astrid run directory for *project_slug*."""
    resolved_run_id = run_id or read_current_run(project_slug, root=root)
    if not resolved_run_id:
        raise ArnoldEnvelopeProjectionError(
            f"project {project_slug!r} has no current run to project"
        )
    return run_dir(project_slug, resolved_run_id, root=root)


def project_runtime_envelope(
    project_slug: str,
    *,
    workflow_id: str,
    run_id: str | None = None,
    root: str | Path | None = None,
) -> Any:
    """Project Astrid run state into Arnold's validated RuntimeEnvelope."""
    from astrid.core.integrations.arnold.host.compat import compat, read_resume_cursor

    run_root = resolve_run_root(project_slug, run_id=run_id, root=root)
    resolved_run_id = run_root.name

    try:
        lease = read_lease(run_root)
    except LeaseError as exc:
        raise ArnoldEnvelopeProjectionError(str(exc)) from exc

    events = read_events(run_root / EVENTS_FILENAME)
    lineage = _project_lineage(events)
    lease_projection = _project_lease(lease)
    manifest_payload = {
        "artifact_root": str(run_root),
        "lease": lease_projection,
        "lineage": list(lineage),
        "plugin_id": HOST_PLUGIN_ID,
        "plugin_state_schema_version": HOST_PLUGIN_STATE_SCHEMA_VERSION,
        "project_slug": project_slug,
        "run_id": resolved_run_id,
        "workflow_id": workflow_id,
    }
    manifest_hash = canonical_json_digest(manifest_payload)

    runtime_envelope_type = compat.RuntimeEnvelope
    envelope = runtime_envelope_type(
        plugin_id=HOST_PLUGIN_ID,
        manifest_hash=manifest_hash,
        plugin_state_schema_version=HOST_PLUGIN_STATE_SCHEMA_VERSION,
        run_id=resolved_run_id,
        artifact_root=str(run_root),
        resume_cursor=_read_resume_cursor(read_resume_cursor, run_root),
        created_at=_project_created_at(events),
        cross_cutting=_build_cross_cutting(
            runtime_envelope_type=runtime_envelope_type,
            lease_projection=lease_projection,
            lineage=lineage,
        ),
    )
    return envelope


def project_envelope_manifest(
    project_slug: str,
    *,
    workflow_id: str,
    run_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the deterministic manifest payload used for manifest_hash."""
    run_root = resolve_run_root(project_slug, run_id=run_id, root=root)
    lease = read_lease(run_root)
    events = read_events(run_root / EVENTS_FILENAME)
    return {
        "artifact_root": str(run_root),
        "lease": _project_lease(lease),
        "lineage": list(_project_lineage(events)),
        "plugin_id": HOST_PLUGIN_ID,
        "plugin_state_schema_version": HOST_PLUGIN_STATE_SCHEMA_VERSION,
        "project_slug": project_slug,
        "run_id": run_root.name,
        "workflow_id": workflow_id,
    }


def _build_cross_cutting(
    *,
    runtime_envelope_type: type[Any],
    lease_projection: dict[str, Any],
    lineage: tuple[str, ...],
) -> Any:
    prototype = _runtime_envelope_prototype(runtime_envelope_type)
    base = getattr(prototype, "cross_cutting")
    cross_cutting_type = type(base)
    return cross_cutting_type(
        taint=tuple(getattr(base, "taint", ()) or ()),
        cost={"astrid": lease_projection},
        lineage=lineage,
        deadline=getattr(base, "deadline", None),
        cancellation=getattr(base, "cancellation", None),
        retry_budget=dict(getattr(base, "retry_budget", {}) or {}),
        error_class=getattr(base, "error_class", None),
    )


def _project_created_at(events: list[dict[str, Any]]) -> str:
    for event in events:
        ts = event.get("ts")
        if isinstance(ts, str) and ts:
            return ts
    return ""


def _project_lease(lease: dict[str, Any]) -> dict[str, Any]:
    projection = {
        "attached_session_id": lease.get("attached_session_id"),
        "plan_hash": lease.get("plan_hash", ""),
        "writer_epoch": lease.get("writer_epoch", 0),
    }
    if "timeline_id" in lease:
        projection["timeline_id"] = lease.get("timeline_id")
    return projection


def _project_lineage(events: list[dict[str, Any]]) -> tuple[str, ...]:
    lineage: list[str] = []
    for event in events:
        event_hash = event.get("hash")
        if isinstance(event_hash, str) and event_hash:
            lineage.append(event_hash)
    return tuple(lineage)


def _read_resume_cursor(read_resume_cursor: Any, run_root: Path) -> Any:
    try:
        return read_resume_cursor(str(run_root))
    except FileNotFoundError:
        return None


def _runtime_envelope_prototype(runtime_envelope_type: type[Any]) -> Any:
    try:
        return runtime_envelope_type()
    except TypeError:
        return runtime_envelope_type(
            run_id="",
            artifact_root="",
            resume_cursor=None,
        )


__all__ = [
    "ArnoldEnvelopeProjectionError",
    "HOST_PLUGIN_ID",
    "HOST_PLUGIN_STATE_SCHEMA_VERSION",
    "project_envelope_manifest",
    "project_runtime_envelope",
    "resolve_run_root",
]
