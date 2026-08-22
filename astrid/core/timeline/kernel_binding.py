"""Kernel timeline binding for managed-mode pack/worker writers (m2 fix).

``pack_write_gateway`` commits ``timeline.config_replaced`` events to the
kernel timeline store only when a kernel writer is injected. Historically no
production caller injected one, so kernel timelines could silently diverge
from the eventlog. This module is the sanctioned resolution seam those
callers use: it composes the standard application for the caller's projects
root and resolves the kernel project + timeline + stream head.

Resolution outcomes:

- **bound** — the kernel project row, timeline row, and event stream all
  exist. The caller passes :attr:`writer` / :attr:`repository` /
  :attr:`stream_type` into ``pack_write_gateway``, which then commits the
  kernel command (receipt key ``timeline.replace_config:{id}:{version}``)
  *before* the eventlog append — no divergence path.
- **None** — genuinely kernel-less context: the kernel has no database at
  the resolved projects root, or the kernel project/timeline rows do not
  exist (nothing to diverge from). Callers keep the documented
  eventlog-only escape and log a warning.
- **raise** — fail-closed states that must not downgrade to eventlog-only:
  the kernel DB file exists but another process owns it (composition is
  unavailable — e.g. a running bridge/server), or the kernel project and
  timeline rows exist but the event stream row is missing (stream head
  ``None``). Both raise :class:`TimelineEditError`.

This module lives under ``astrid.core`` and never imports ``astrid.packs``:
the timeline repository is reached structurally through the composed
application (``app.timelines``) and the pack stream type is a mirrored
protocol constant (``TIMELINE_STREAM_TYPE``, pinned equal to the pack's by a
sync test). Callers pass plain values through the gateway's existing
writer/repository/stream-type injection seam.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.application import StandardApplication, compose_standard_application


TIMELINE_STREAM_TYPE = "timeline.timeline"
"""The timeline pack's stream type, mirrored here as the kernel-side
protocol constant. The pack declares the same value in its schema-pack /
repository; a sync test pins the two equal."""
TIMELINE_CREATED_EVENT_KIND = "timeline.created"
"""Mirrored pack event kind, used only by the forensic existence probe in
:func:`kernel_timeline_writer_for` (the stream row may be missing in the
inconsistent states this module diagnoses, so the repository's own
event-sourced slug resolution cannot be reused there)."""

__all__ = [
    "KernelTimelineBinding",
    "TIMELINE_STREAM_TYPE",
    "close_kernel_binding",
    "gateway_kernel_kwargs",
    "kernel_timeline_writer_for",
]

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class KernelTimelineBinding:
    """A resolved kernel write path for one managed timeline.

    Attributes mirror the ``pack_write_gateway`` injection parameters so a
    resolved binding maps 1:1 onto the gateway's kernel commit branch.
    """

    app: StandardApplication
    """The composed standard application owning the writer (caller closes it)."""

    writer: Any
    """:class:`~astrid.core.store.writer.DatabaseWriter` (one writer queue)."""

    repository: Any
    """:class:`~astrid.packs.timeline.repository.TimelineRepository`."""

    stream_type: str
    """The pack stream type (``timeline.timeline``)."""


def gateway_kernel_kwargs(binding: KernelTimelineBinding | None) -> dict:
    """Map a binding onto ``pack_write_gateway`` keyword arguments."""
    if binding is None:
        return {}
    return {
        "writer": binding.writer,
        "timeline_repository": binding.repository,
        "timeline_stream_type": binding.stream_type,
    }


def close_kernel_binding(binding: KernelTimelineBinding | None) -> None:
    """Close a binding's composed application (deterministic and idempotent)."""
    if binding is not None:
        try:
            binding.app.close()
        except Exception:  # noqa: BLE001 - close must never mask the real result
            _LOGGER.warning(
                "kernel_timeline_writer_for: closing composed application failed",
                exc_info=True,
            )


def kernel_timeline_writer_for(
    project_slug: str,
    timeline_slug: str,
    *,
    stream_type: str = TIMELINE_STREAM_TYPE,
    projects_root: str | Path | None = None,
) -> KernelTimelineBinding | None:
    """Resolve the kernel write path for one project/timeline pair.

    Returns a bound :class:`KernelTimelineBinding`, or ``None`` when this is
    a genuinely kernel-less context: the kernel has no database at the
    resolved projects root, or it has no such project or timeline (nothing
    to diverge from — eventlog-only is correct). Any other resolution error
    propagates: an ambiguous failure must not silently downgrade to
    eventlog-only.

    Raises
    ------
    TimelineEditError
        When the kernel DB file exists but another process owns it
        (composition reports unavailable — binding refuses to silently
        downgrade an existing kernel timeline), or when the kernel project
        and timeline exist but the event stream row is missing (head
        ``None``) — both inconsistent states that must fail closed instead
        of unbounding into eventlog-only writes.
    """
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.integrations.reigh.bridge_service import (
        derive_database_path,
    )
    from astrid.core.repositories.projects import ProjectNotFoundError
    from astrid.sdk.exceptions import ServiceUnavailableError

    from ._edit_helpers import TimelineEditError

    try:
        app = compose_standard_application(projects_root)
    except ServiceUnavailableError as exc:
        db_path = derive_database_path(resolve_projects_root(projects_root))
        if not db_path.exists():
            # Genuinely kernel-less: with no database file there are no
            # kernel rows to diverge from; keep the documented escape.
            _LOGGER.warning(
                "kernel timeline binding for %s/%s skipped: no kernel "
                "database at %s (%s); keeping the documented "
                "eventlog-only escape",
                project_slug,
                timeline_slug,
                db_path,
                exc,
            )
            return None
        # The database exists but another process owns it (e.g. a running
        # bridge/server). A kernel timeline may live in there; silently
        # downgrading this managed write to eventlog-only would diverge it.
        # Fail closed and let the caller abort the managed write.
        raise TimelineEditError(
            f"kernel database {db_path} exists but is owned by another "
            f"process ({exc}); refusing to downgrade the kernel timeline "
            f"{project_slug!r}/{timeline_slug!r} to eventlog-only writes"
        ) from exc

    def _unbound(reason: str) -> None:
        _LOGGER.debug(
            "kernel timeline binding skipped (%s): %s/%s",
            reason,
            project_slug,
            timeline_slug,
        )
        app.close()

    try:
        try:
            project_id = app.projects.resolve(app.writer, project_slug)
        except ProjectNotFoundError:
            _unbound("no kernel project")
            return None
        with app.writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            try:
                timeline_id = app.timelines._resolve_id(
                    conn, project_id, timeline_slug
                )
            except Exception as exc:  # noqa: BLE001 - structural probe below
                if type(exc).__name__ != "TimelineNotFoundError":
                    raise
                # Event-sourced slug resolution joins ``event_streams``, so
                # a timeline whose stream row was lost masquerades as
                # absent. Probe the timelines row through the surviving
                # created-event payload before accepting the unbound
                # escape; a genuinely absent slug still probes empty.
                row = conn.execute(
                    "SELECT t.id AS timeline_id FROM timelines t "
                    "JOIN events e ON json_extract(e.payload_json, "
                    "'$.data.timeline_id') = t.id "
                    "WHERE t.project_id = ? AND e.kind = ? "
                    "AND json_extract(e.payload_json, '$.data.slug') = ? "
                    "LIMIT 1",
                    (project_id, TIMELINE_CREATED_EVENT_KIND, timeline_slug),
                ).fetchone()
                if row is None:
                    _unbound("no kernel timeline")
                    return None
                timeline_id = str(row["timeline_id"])
            head = conn.execute(
                "SELECT head_seq FROM event_streams WHERE id = ?",
                (f"{timeline_id}:{stream_type}",),
            ).fetchone()
        if head is None:
            # Inconsistent kernel state: the project and timeline rows exist
            # but the event stream row does not. This must fail loudly —
            # silently unbounding here would append eventlog-only and diverge
            # from a kernel timeline that half-exists.
            raise TimelineEditError(
                f"kernel timeline {timeline_slug!r} in project "
                f"{project_slug!r} exists but has no event stream row; "
                "refusing to bind or unbound (inconsistent kernel state)"
            )
        return KernelTimelineBinding(
            app=app,
            writer=app.writer,
            repository=app.timelines,
            stream_type=stream_type,
        )
    except BaseException:
        app.close()
        raise
