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
        if event.kind == "timeline.imported":
            raise ValueError(
                "timeline.imported is migration-only legacy; display projection "
                "does not unwrap runtime snapshots"
            )
        elif event.kind == "timeline.created":
            display = Display(
                schema_version=TIMELINE_SCHEMA_VERSION,
                slug=event.payload.slug,
                name=event.payload.name,
                is_default=False,
            )
            deleted = False
        elif event.kind == "timeline.saved":
            # Whole-document save: payload carries config/registry (and for
            # kernel saves also timeline_id/expected_version). Display derives
            # from payload slug/name when present, otherwise preserves the
            # prior display but clears deleted. Mirrors timeline.created.
            payload_raw = None
            try:
                if hasattr(event.payload, "to_json_obj"):
                    payload_raw = event.payload.to_json_obj()  # type: ignore[union-attr]
                elif hasattr(event.payload, "_d"):
                    payload_raw = getattr(event.payload, "_d")
                elif isinstance(event.payload, dict):
                    payload_raw = event.payload
                else:
                    # Typed payload model
                    payload_raw = event.payload  # type: ignore[assignment]
            except Exception:
                payload_raw = None
            saved_slug = None
            saved_name = None
            if isinstance(payload_raw, dict):
                # Direct slug/name on payload
                if isinstance(payload_raw.get("slug"), str):
                    saved_slug = payload_raw["slug"]
                if isinstance(payload_raw.get("name"), str):
                    saved_name = payload_raw["name"]
                # Fallback: slug/name inside config object (kernel saved envelope)
                cfg = payload_raw.get("config")
                if saved_slug is None and isinstance(cfg, dict) and isinstance(cfg.get("slug"), str):
                    saved_slug = cfg["slug"]
                if saved_name is None and isinstance(cfg, dict) and isinstance(cfg.get("name"), str):
                    saved_name = cfg["name"]
            else:
                # Attribute access for typed/wrapper payloads
                try:
                    v = getattr(payload_raw, "slug", None)
                    if isinstance(v, str):
                        saved_slug = v
                except Exception:
                    pass
                try:
                    v = getattr(payload_raw, "name", None)
                    if isinstance(v, str):
                        saved_name = v
                except Exception:
                    pass
                try:
                    cfg = getattr(payload_raw, "config", None)
                    if saved_slug is None and isinstance(cfg, dict) and isinstance(cfg.get("slug"), str):
                        saved_slug = cfg["slug"]
                    if saved_name is None and isinstance(cfg, dict) and isinstance(cfg.get("name"), str):
                        saved_name = cfg["name"]
                except Exception:
                    pass
            if saved_slug is not None or saved_name is not None:
                display = Display(
                    schema_version=TIMELINE_SCHEMA_VERSION,
                    slug=saved_slug if saved_slug is not None else (display.slug if display is not None else ""),
                    name=saved_name if saved_name is not None else (display.name if display is not None else ""),
                    is_default=display.is_default if display is not None else False,
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
