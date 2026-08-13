"""Timeline registry sync CLI handler.

``timelines registry sync`` resolves a JSON manifest against project sources
and appends a ``timeline.asset_registry_replaced`` event.
"""

from __future__ import annotations

import argparse

from astrid.core.contracts.errors import AstridError
from astrid.core.timeline._shared import _expected_version_kwargs, _resolve_edit_context


def cmd_registry_sync(args: argparse.Namespace) -> int:
    """Handle ``timelines registry sync <slug>``."""
    from .timeline import (  # noqa: PLC0415
        _resolve_clip_backend_name,
    )
    from astrid.core.timeline.asset_registry_edits import sync_asset_registry

    if getattr(args, "expected_version", None) is None:
        raise AstridError(
            "registry sync requires --expected-version <N> (CAS guard)",
            recovery_command="pass --expected-version from the current timeline config_version",
        )

    actor, project_slug = _resolve_edit_context(getattr(args, "project", None), args)
    extra = _expected_version_kwargs(args)

    event = sync_asset_registry(
        project_slug,
        args.slug,
        manifest_path=args.manifest,
        actor=actor,
        **extra,
    )

    if event is None:
        print("registry: no changes (already up-to-date)")
        return 0

    backend_name = _resolve_clip_backend_name(project_slug, args.slug)
    print(
        f"registry: event {event.event_id}, kind={event.kind}, "
        f"timeline={event.timeline_id}, backend={backend_name}"
    )
    return 0
