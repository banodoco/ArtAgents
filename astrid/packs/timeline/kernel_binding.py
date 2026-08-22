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
- **None** — genuinely kernel-less context: the kernel project/timeline does
  not exist (nothing to diverge from), or the database is owned by another
  process (e.g. a running bridge/server) so composition is unavailable.
  Callers keep the documented eventlog-only escape and log a warning.

This module lives under ``astrid.packs`` because resolving the binding needs
:class:`~astrid.packs.timeline.repository.TimelineRepository` internals
(kernel modules must not import ``astrid.packs``); callers pass plain values
through the gateway's existing writer/repository/stream-type injection seam.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.application import StandardApplication, compose_standard_application

__all__ = [
    "KernelTimelineBinding",
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
    projects_root: str | Path | None = None,
) -> KernelTimelineBinding | None:
    """Resolve the kernel write path for one project/timeline pair.

    Returns a bound :class:`KernelTimelineBinding`, or ``None`` when this is
    a genuinely kernel-less context: the kernel has no such project or
    timeline (nothing to diverge from — eventlog-only is correct), or the
    kernel DB is owned by another process (composition fails closed with the
    typed unavailable error). Any other resolution error propagates: an
    ambiguous failure must not silently downgrade to eventlog-only.
    """
    from astrid.core.repositories.projects import ProjectNotFoundError
    from astrid.packs.timeline.repository import (
        TIMELINE_STREAM_TYPE,
        TimelineNotFoundError,
    )
    from astrid.sdk.exceptions import ServiceUnavailableError

    try:
        app = compose_standard_application(projects_root)
    except ServiceUnavailableError as exc:
        _LOGGER.warning(
            "kernel timeline binding for %s/%s unavailable (%s); "
            "keeping the documented eventlog-only escape",
            project_slug,
            timeline_slug,
            exc,
        )
        return None

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
        try:
            with app.writer.read_only_connection() as conn:
                conn.row_factory = sqlite3.Row
                timeline_id = app.timelines._resolve_id(
                    conn, project_id, timeline_slug
                )
                head = conn.execute(
                    "SELECT head_seq FROM event_streams WHERE id = ?",
                    (f"{timeline_id}:{TIMELINE_STREAM_TYPE}",),
                ).fetchone()
        except TimelineNotFoundError:
            _unbound("no kernel timeline")
            return None
        if head is None:
            _unbound("kernel timeline has no event stream yet")
            return None
        return KernelTimelineBinding(
            app=app,
            writer=app.writer,
            repository=app.timelines,
            stream_type=TIMELINE_STREAM_TYPE,
        )
    except BaseException:
        app.close()
        raise
