"""Minimal read-side projection helpers for timeline lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass

from astrid.core.timeline.events.schema import TimelineEvent
from astrid.core.timeline.model import TIMELINE_SCHEMA_VERSION, Display


@dataclass(frozen=True)
class DisplayProjection:
    display: Display | None
    deleted: bool


def project_display(
    events: list[TimelineEvent], *, fallback_display: Display | None = None
) -> DisplayProjection:
    display: Display | None = fallback_display
    deleted = False

    for event in events:
        if event.kind == "timeline.created":
            display = Display(
                schema_version=TIMELINE_SCHEMA_VERSION,
                slug=event.payload.slug,
                name=event.payload.name,
                is_default=False,
            )
            deleted = False
        elif event.kind == "timeline.renamed" and display is not None:
            display = Display(
                schema_version=TIMELINE_SCHEMA_VERSION,
                slug=event.payload.new_slug,
                name=display.name,
                is_default=display.is_default,
            )
        elif event.kind == "timeline.default_set" and display is not None:
            display = Display(
                schema_version=TIMELINE_SCHEMA_VERSION,
                slug=display.slug,
                name=display.name,
                is_default=True,
            )
        elif event.kind == "timeline.deleted":
            display = None
            deleted = True

    return DisplayProjection(display=display, deleted=deleted)
