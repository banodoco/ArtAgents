"""Explicit kernel timeline binding for managed pack/worker writers.

The SDK and pack processes are clients of the workspace runtime. They must
not compose a local application merely to discover a kernel writer. A caller
that already owns an attempt-local writer/repository may pass those handles
through the binding seam; otherwise the write gateway remains eventlog-only and
the runtime owns canonical timeline mutations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any


TIMELINE_STREAM_TYPE = "timeline.timeline"
"""The timeline pack's stream type, mirrored as a protocol constant."""

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
    """Explicit kernel handles for one managed timeline write."""

    app: Any | None
    """Optional caller-owned close handle; no application is composed here."""

    writer: Any
    """:class:`~astrid.core.store.writer.DatabaseWriter` supplied by caller."""

    repository: Any
    """Timeline repository supplied by caller."""

    stream_type: str
    """The timeline stream type used by the gateway."""


def gateway_kernel_kwargs(binding: KernelTimelineBinding | None) -> dict:
    """Map an explicit binding onto ``pack_write_gateway`` arguments."""
    if binding is None:
        return {}
    return {
        "writer": binding.writer,
        "timeline_repository": binding.repository,
        "timeline_stream_type": binding.stream_type,
    }


def close_kernel_binding(binding: KernelTimelineBinding | None) -> None:
    """Close an explicitly supplied owner, if it exposes ``close``."""
    if binding is None or binding.app is None:
        return
    try:
        close = getattr(binding.app, "close", None)
        if callable(close):
            close()
    except Exception:  # noqa: BLE001 - close must never mask the real result
        _LOGGER.warning(
            "kernel timeline binding owner close failed", exc_info=True
        )


def kernel_timeline_writer_for(
    project_slug: str,
    timeline_slug: str,
    *,
    stream_type: str = TIMELINE_STREAM_TYPE,
    writer: Any | None = None,
    repository: Any | None = None,
    owner: Any | None = None,
) -> KernelTimelineBinding | None:
    """Build a binding only from explicit attempt-local kernel inputs.

    ``project_slug`` and ``timeline_slug`` remain in the signature for source
    compatibility and diagnostics, but are never used to discover or open
    storage. Supplying only one of ``writer``/``repository`` is malformed and
    fails closed; supplying neither is the normal runtime-owned path and
    returns ``None``.
    """
    from ._edit_helpers import TimelineEditError

    has_writer = writer is not None
    has_repository = repository is not None
    if has_writer != has_repository:
        raise TimelineEditError(
            "kernel timeline binding requires both explicit writer and "
            "timeline_repository inputs"
        )
    if not has_writer:
        _LOGGER.debug(
            "kernel timeline binding omitted for runtime-owned %s/%s",
            project_slug,
            timeline_slug,
        )
        return None
    if not stream_type:
        raise TimelineEditError("kernel timeline binding requires stream_type")
    return KernelTimelineBinding(
        app=owner,
        writer=writer,
        repository=repository,
        stream_type=stream_type,
    )
