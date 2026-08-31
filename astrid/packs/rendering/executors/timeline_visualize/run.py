#!/usr/bin/env python3
"""Package the read-only timeline visualization pipeline as an executor."""

# The canonical-entrypoint guard intentionally runs before imports.
# ruff: noqa: E402

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("rendering.timeline_visualize")

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from copy import deepcopy
from dataclasses import replace
from operator import itemgetter
from pathlib import Path
from typing import Any, Iterable, Mapping

from astrid.core._shared.jsonio import ProjectJsonError, read_json
from astrid.core._shared.result_manifest import build_manifest, write_manifest
from astrid.core.cli_choices import StaticChoices
from astrid.sdk.workspace_client import page_pair
from astrid.sdk.pagination import paged_rows
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent, with_event_hash
from astrid.core.timeline.resolution import classify_registry
from astrid.core.timeline.snapshot import TimelineSnapshot, snapshot_from_runtime
from astrid.packs.rendering.executors.timeline_visualize.assets import (
    guard_sampling,
    verify_now,
)
from astrid.packs.rendering.executors.timeline_visualize.emit import (
    FROZEN_AT_SENTINEL,
    emit_action_index,
    emit_asset_index,
    emit_diagnostics,
    emit_ground_truth,
    emit_metric_definitions,
    emit_reading_guide,
    emit_structure_md,
    emit_transcript_index,
)
from astrid.packs.rendering.executors.timeline_visualize.evidence_pack import (
    PackLayout,
    write_evidence_pack,
)
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    FrozenView,
    discard_rehydrated_pack,
    load_frozen_view,
    model_from_frozen,
    resolve_focus,
    snapshot_from_frozen,
)
from astrid.packs.rendering.executors.timeline_visualize.ids import parse_qualified_ref
from astrid.packs.rendering.executors.timeline_visualize.layout import (
    LayoutPage,
    layout_timeline,
)
from astrid.packs.rendering.executors.timeline_visualize.model import build_model
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    assign_range_ids,
    assign_transcript_ids,
    build_identity_map,
)
from astrid.packs.rendering.executors.timeline_visualize.render_png import (
    render_page_png,
)
from astrid.packs.rendering.executors.timeline_visualize.render_svg import (
    render_page_svg_bytes,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import select_scope
from astrid.packs.rendering.executors.timeline_visualize.select import (
    KernelTimeline,
    ManagedTimeline,
    select_kernel_timelines,
)
from astrid.packs.rendering.executors.timeline_visualize.thumbnails import (
    MAX_FRAMES_PER_PAGE,
    per_page_frame_budget,
    sample_filmstrip,
    sample_rendered_filmstrip,
    verify_rendered_output,
)
from astrid.packs.rendering.executors.timeline_visualize.transcript_attach import (
    TranscriptAttachment,
    discover_attachment,
)
from astrid.packs.rendering.executors.timeline_visualize.transcripts import (
    SpeechOccurrence,
    TranscriptSegment,
    map_occurrences,
    normalize_transcript,
    resolve_attachment_asset_key,
    speech_occurrence_authored_id,
    with_occurrence_ids,
)

_AUTHORITY_CONTEXT_ENV = "ASTRID_TIMELINE_VISUALIZE_AUTHORITY_CONTEXT"
_RUNTIME_MEDIA_PAGE_LIMIT = 50
_RUNTIME_MEDIA_MAX_PAGES = 10_000


def _runtime_media_row_value(row: Any, *keys: str) -> Any:
    """Read a generated-client row without requiring a mapping conversion."""

    if isinstance(row, Mapping):
        for key in keys:
            if key in row:
                return row[key]
        return None
    for key in keys:
        try:
            return getattr(row, key)
        except AttributeError:
            continue
    return None


def _runtime_media_page(result: Any) -> tuple[list[Any], str | None] | None:
    """Validate the generated client's canonical JSON page pair."""

    page = page_pair(result)
    if page is None:
        return None
    items, next_cursor = page
    if not isinstance(items, list):
        return None
    # The runtime call is explicitly bounded.  A response larger than the
    # requested page is malformed: accepting it would make the snapshot
    # boundary depend on an untrusted adapter rather than the pagination
    # contract we requested.
    if len(items) > _RUNTIME_MEDIA_PAGE_LIMIT:
        return None
    if next_cursor is not None:
        # ``None`` is the only terminal marker.  Empty/whitespace/control
        # strings are malformed cursors, not alternate spellings of it.
        if (
            not isinstance(next_cursor, str)
            or not next_cursor
            or any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
                   for character in next_cursor)
        ):
            return None
    return list(items), next_cursor


def _runtime_media_snapshot_rows(
    rows: Iterable[Any], *, project_id: str, project_slug: str
) -> list[Any] | None:
    """Validate ownership and make a cursor-assembled snapshot deterministic."""

    unique: list[Any] = []
    seen_object_ids: set[str] = set()
    seen_digests: set[str] = set()
    seen_rows: set[str] = set()
    for row in rows:
        # The current ManagedObject schema is project-scoped and omits an owner
        # field.  If a newer/ test-double row includes one, fail closed rather
        # than allowing a cross-project admission into a child-process snapshot.
        row_project_id = _runtime_media_row_value(
            row, "project_id", "owner_project_id", "owning_project_id"
        )
        if row_project_id is not None and str(row_project_id) != project_id:
            return None
        row_project = _runtime_media_row_value(row, "project")
        if row_project is not None:
            if isinstance(row_project, Mapping):
                candidate = row_project.get("project_id") or row_project.get("id")
                candidate_slug = row_project.get("slug")
                if candidate is not None and str(candidate) != project_id:
                    return None
                if candidate_slug is not None and str(candidate_slug) != project_slug:
                    return None
            elif str(row_project) not in {project_id, project_slug}:
                return None

        object_id = _runtime_media_row_value(row, "object_id", "media_id", "id")
        digest = _runtime_media_row_value(
            row, "content_hash", "content_sha256", "sha256", "digest"
        )
        object_key = str(object_id) if isinstance(object_id, str) and object_id else None
        digest_key = str(digest) if isinstance(digest, str) and digest else None
        if object_key is not None and object_key in seen_object_ids:
            continue
        if digest_key is not None and digest_key in seen_digests:
            continue
        if object_key is None and digest_key is None:
            # Malformed rows are retained for the resolver's existing
            # fail-closed normalization, but exact duplicates are suppressed.
            try:
                row_key = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
            except (TypeError, ValueError):
                row_key = repr(row)
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
        if object_key is not None:
            seen_object_ids.add(object_key)
        if digest_key is not None:
            seen_digests.add(digest_key)
        unique.append(row)

    def sort_key(row: Any) -> tuple[str, str, str]:
        object_id = _runtime_media_row_value(row, "object_id", "media_id", "id")
        digest = _runtime_media_row_value(
            row, "content_hash", "content_sha256", "sha256", "digest"
        )
        try:
            stable = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            stable = repr(row)
        return (
            str(object_id) if object_id is not None else "",
            str(digest) if digest is not None else "",
            stable,
        )

    return sorted(unique, key=sort_key)


def _runtime_media_snapshot(project_slug: str) -> list[Any] | None:
    """Read the project's admitted media facts from the workspace runtime.

    Visualization runs in a child process and must not open the local kernel
    database.  The returned rows are an attempt-local read snapshot: callers
    pass them to the resolver, which still verifies project ownership, CAS
    location, and bytes.  Runtime unavailability is deliberately represented
    as ``None`` so ordinary project-source visualization remains usable while
    managed CAS media fails closed.
    """

    try:
        from astrid.sdk.workspace_client import WorkspaceClient, resolve_runtime_connection

        endpoint, token = resolve_runtime_connection()
        client = WorkspaceClient(endpoint, token)
        rows = paged_rows(client.list_projects)
        if rows is None:
            return None
        project = next(
            (
                row
                for row in rows or []
                if isinstance(row, Mapping) and row.get("slug") == project_slug
            ),
            None,
        )
        if not isinstance(project, Mapping):
            return None
        project_id = project.get("project_id") or project.get("id")
        if not isinstance(project_id, str) or not project_id:
            return None
        rows = paged_rows(
            client.list_project_objects,
            project_id,
            limit=_RUNTIME_MEDIA_PAGE_LIMIT,
            max_pages=_RUNTIME_MEDIA_MAX_PAGES,
        )
        if rows is None:
            return None
        return _runtime_media_snapshot_rows(
            rows, project_id=project_id, project_slug=project_slug
        )
    except Exception:  # noqa: BLE001 - managed media reads fail closed
        return None


def _execution_authority_context() -> dict[str, Any] | None:
    raw = os.environ.get(_AUTHORITY_CONTEXT_ENV)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("timeline visualization execution authority is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("timeline visualization execution authority must be an object")
    return value


def _verify_frozen_execution_authority(
    manifest_path: Path,
    frozen: FrozenView,
    authority: Mapping[str, Any] | None,
) -> None:
    if authority is None:
        return
    if authority.get("mode") != "frozen_view":
        raise ValueError("timeline visualization authority mode changed before execution")
    expected_digest = authority.get("manifest_sha256")
    actual_digest = hashlib.sha256(Path(manifest_path).expanduser().read_bytes()).hexdigest()
    if expected_digest != actual_digest:
        raise ValueError("frozen visualization manifest changed after admission")
    if authority.get("snapshot_sns") != frozen.snapshot_sns:
        raise ValueError("frozen visualization snapshot changed after admission")


def _verify_selected_execution_authority(
    selected: list[ManagedTimeline],
    authority: Mapping[str, Any] | None,
) -> None:
    if authority is None:
        return
    mode = authority.get("mode")
    expected_rows = authority.get("timelines")
    if mode != "kernel" or not isinstance(expected_rows, list):
        raise ValueError("timeline visualization authority mode changed before execution")
    actual_rows = [
        {
            "timeline_id": row.timeline_id,
            "head_version": row.kernel_head_version,
            "head_event_id": row.kernel_source_event_id,
            "head_hash": row.kernel_head_hash,
        }
        for row in selected
    ]
    sort_field = "timeline_id"
    if sorted(expected_rows, key=itemgetter(sort_field)) != sorted(
        actual_rows, key=itemgetter(sort_field)
    ):
        raise ValueError("timeline authority changed after admission; retry visualization")


_LAYOUTS = ("time-scaled", "linear")
_FORMATS = frozenset({"png", "svg", "md"})
_CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _stable_kernel_event_ulid(seed: str) -> str:
    """Return a deterministic schema-valid id for a private kernel projection."""

    value = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:16], "big")
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD32[value & 31]
        value >>= 5
    return "".join(chars)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rendering.timeline_visualize",
        description="Build a deterministic agent evidence pack from managed timeline event logs.",
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--project-slug",
        required=True,
        help="Owning project slug issued by the workspace runtime.",
    )
    parser.add_argument("--timeline-slug")
    parser.add_argument("--all", action="store_true", dest="select_all")
    parser.add_argument(
        "--scope",
        choices=StaticChoices(
            ("project", "timeline", "shot", "range", "clip", "asset", "timestamp")
        ),
        default="timeline",
    )
    parser.add_argument("--shot")
    parser.add_argument("--range", dest="range_value")
    parser.add_argument("--at")
    parser.add_argument("--clip")
    parser.add_argument("--asset")
    parser.add_argument("--context", type=float, default=3.0)
    parser.add_argument("--neighbors", type=int, default=0)
    parser.add_argument("--from-view", type=Path)
    parser.add_argument("--focus")
    parser.add_argument("--refresh-root", action="store_true")
    parser.add_argument("--layout", choices=StaticChoices((*_LAYOUTS, "both")), default="both")
    parser.add_argument(
        "--format",
        action="append",
        type=_format_argument,
        metavar="FORMAT[,FORMAT...]",
        help="Repeatable presentation format(s): png, svg, md, or all (default all).",
    )
    parser.add_argument(
        "--filmstrip", choices=StaticChoices(("auto", "off", "assets", "rendered")), default="auto"
    )
    parser.add_argument("--rendered-video", type=Path)
    parser.add_argument("--materialized-root", type=Path)
    parser.add_argument("--materialized-objects")
    return parser


def _parse_time(value: str) -> float:
    raw = value.strip()
    try:
        seconds = float(raw)
    except ValueError:
        parts = raw.split(":")
        if len(parts) not in (2, 3):
            raise ValueError(f"invalid time {value!r}; use seconds or [HH:]MM:SS[.fff]") from None
        try:
            numbers = [float(part) for part in parts]
        except ValueError:
            raise ValueError(f"invalid time {value!r}; use seconds or [HH:]MM:SS[.fff]") from None
        if len(numbers) == 2:
            minutes, tail = numbers
            hours = 0.0
        else:
            hours, minutes, tail = numbers
        if hours < 0 or minutes < 0 or minutes >= 60 or tail < 0 or tail >= 60:
            raise ValueError(f"invalid time {value!r}; minute/second fields must be within 0..59")
        seconds = hours * 3600.0 + minutes * 60.0 + tail
    if seconds < 0:
        raise ValueError("time values must be non-negative")
    return seconds


def _parse_range(value: str) -> tuple[float, float]:
    start_raw, separator, end_raw = value.partition("..")
    if not separator or not start_raw or not end_raw:
        raise ValueError("range must be START..END")
    return _parse_time(start_raw), _parse_time(end_raw)


def _format_argument(value: str) -> str:
    """Validate one CLI format token while accepting comma-separated lists.

    Discovery exposes the SDK field as plural ``formats`` while the runtime
    command uses repeatable singular ``--format``.  Accepting both
    ``--format png --format svg`` and the common ``--format png,svg`` spelling
    keeps the two public forms semantically identical.
    """

    values = [part.strip().lower() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("format must name one or more of png, svg, md, or all")
    invalid = sorted(set(values) - (_FORMATS | {"all"}))
    if invalid:
        raise argparse.ArgumentTypeError(
            f"invalid format(s): {', '.join(invalid)}; choose png, svg, md, or all"
        )
    if "all" in values and len(values) > 1:
        raise argparse.ArgumentTypeError(
            "format 'all' cannot be combined with another format; omit the others"
        )
    return ",".join(values)


def _validate_selectors(args: argparse.Namespace) -> None:
    cold = [
        name
        for name, value in (
            ("--all", args.select_all),
            ("--shot", args.shot),
            ("--range", args.range_value),
            ("--at", args.at),
            ("--clip", args.clip),
            ("--asset", args.asset),
        )
        if value not in (None, False, "")
    ]
    if len(cold) > 1:
        raise ValueError(f"cold selectors are mutually exclusive: {', '.join(cold)}")
    if args.timeline_slug is not None and args.select_all:
        raise ValueError("--timeline-slug and --all are mutually exclusive")
    if (args.from_view is None) != (args.focus is None):
        raise ValueError("--from-view and --focus must be supplied together")
    if args.refresh_root and args.from_view is None:
        raise ValueError("--refresh-root requires --from-view and --focus")
    if args.from_view is not None:
        conflicts = [
            name
            for name, value in (
                ("--timeline-slug", args.timeline_slug),
                ("--all", args.select_all),
                ("--shot", args.shot),
                ("--range", args.range_value),
                ("--at", args.at),
                ("--clip", args.clip),
                ("--asset", args.asset),
            )
            if value not in (None, False, "")
        ]
        if conflicts:
            raise ValueError("--from-view/--focus cannot be combined with " + ", ".join(conflicts))
        if args.refresh_root and parse_qualified_ref(args.focus).kind != "TL":
            raise ValueError("--refresh-root focus must be the frozen timeline reference")
    if args.rendered_video is not None and args.filmstrip not in {"auto", "rendered"}:
        raise ValueError("--rendered-video requires --filmstrip auto or rendered")
    if args.filmstrip == "rendered" and args.rendered_video is None:
        raise ValueError("--filmstrip rendered requires --rendered-video")


def _materialize_kernel_timeline(
    row: KernelTimeline,
    *,
    project_root: Path,
    project_slug: str,
    destination: Path,
) -> ManagedTimeline:
    """Normalize one runtime row into an attempt-local visualization input."""

    del project_root, project_slug, destination
    timeline_ulid = row.timeline_ulid.upper()
    config = dict(row.config)
    if not isinstance(config.get("clips"), list) or not isinstance(config.get("tracks"), list):
        raise ValueError(
            f"kernel timeline {row.slug!r} at version {row.config_version} cannot be "
            "visualized: canonical config must contain top-level tracks and clips arrays; "
            "save a renderable timeline config and retry"
        )
    registry = row.registry.get("assets", {}) if isinstance(row.registry, Mapping) else {}
    if not isinstance(registry, dict):
        registry = {}
    actor = TimelineActor(type="system", id="astrid.kernel", display="Astrid kernel")
    timestamp = row.head_created_at
    events: list[TimelineEvent] = []
    for kind, payload in (
        ("timeline.config_replaced", {"config": config, "source": "other"}),
        ("timeline.asset_registry_replaced", {"registry": {"assets": registry}, "source": "other"}),
    ):
        event = TimelineEvent(
            event_id=_stable_kernel_event_ulid(f"{row.head_event_id}:{kind}"),
            timeline_id=row.timeline_id,
            ts=timestamp,
            actor=actor,
            prev_hash=None,
            hash=None,
            kind=kind,
            payload=payload,
            expected_version=len(events),
            source_backend="astrid.kernel",
            source_timeline_id=row.timeline_id,
            source_event_id=row.head_event_id,
            source_version=row.config_version,
            source_hash=row.head_hash,
        )
        event = with_event_hash(event, prev_hash=events[-1].hash if events else None)
        events.append(event)
    return ManagedTimeline(
        timeline_dir=None,
        timeline_id=row.timeline_id,
        timeline_ulid=timeline_ulid,
        slug=row.slug,
        is_default=row.is_default,
        is_tombstoned=False,
        kernel_head_version=row.config_version,
        kernel_head_event_id=_stable_kernel_event_ulid(f"kernel:{row.head_event_id}"),
        kernel_head_hash=row.head_hash,
        kernel_source_event_id=row.head_event_id,
        runtime_config=config,
        runtime_registry={"assets": registry},
        runtime_events=tuple(event.to_json_obj() for event in events),
    )


def _select_timelines(
    args: argparse.Namespace,
    project_root: Path,
    *,
    kernel_materialization_root: Path | None = None,
) -> list[ManagedTimeline]:
    kernel_rows, diagnostics = select_kernel_timelines(
        project_root,
        project_slug=args.project_slug,
        slug=args.timeline_slug,
        all=args.select_all,
        default=not args.timeline_slug and not args.select_all,
    )
    selected = []
    if kernel_rows and kernel_materialization_root is not None:
        selected = [
            _materialize_kernel_timeline(
                row,
                project_root=project_root,
                project_slug=args.project_slug,
                destination=kernel_materialization_root / row.timeline_ulid.upper(),
            )
            for row in kernel_rows
        ]
    if not selected:
        detail = "; ".join(diagnostics) or "no eligible managed timeline was selected"
        raise ValueError(detail)
    if len(selected) > 1 and any(
        value not in (None, False, "")
        for value in (args.shot, args.range_value, args.at, args.clip, args.asset)
    ):
        raise ValueError("shot, range, timestamp, clip, and asset scopes require one timeline")
    return sorted(selected, key=lambda row: row.timeline_ulid)


def _scope_for(args: argparse.Namespace, model: Any):
    kwargs: dict[str, Any] = {
        "context_seconds": args.context,
        "neighbors": args.neighbors,
    }
    if args.shot is not None:
        kind, kwargs["ref"] = "shot", args.shot
    elif args.range_value is not None:
        kind = "range"
        kwargs["start"], kwargs["end"] = _parse_range(args.range_value)
    elif args.at is not None:
        kind, kwargs["at_seconds"] = "timestamp", _parse_time(args.at)
    elif args.clip is not None:
        kind, kwargs["clip_id"] = "clip", args.clip
        # A bare clip zoom is a weird crop without its same-track neighbors
        # (Grok UX: "neighbor clips vanish"). Default to one neighbor each
        # side; --neighbors still overrides.
        kwargs.setdefault("neighbors", 1)
    elif args.asset is not None:
        kind, kwargs["asset_key"] = "asset", args.asset
    else:
        kind = "project" if args.select_all else args.scope
    if kind != "clip":
        kwargs["neighbors"] = 0
    return select_scope(model, kind=kind, **kwargs)


def _mint_cold_range_root(
    model: Any,
    identity_map: Any,
    scope: Any,
) -> tuple[Any, Any]:
    """Allocate the root RG id from the selected frozen frame bounds.

    The authored key uses canonical seconds derived from the quantized scope,
    rather than the caller's spelling, so equivalent selectors (``5`` and
    ``00:05``) resolve to the same semantic identity.  The returned scope
    carries the qualified display ref consumed by every emitter and renderer.
    """

    if scope.kind != "range":
        return identity_map, scope
    if scope.start_frame is None or scope.end_frame is None:
        raise ValueError("cold range scope must have frozen frame bounds")
    start_seconds = scope.start_frame / model.fps
    end_seconds = scope.end_frame / model.fps
    authored_id = f"range:{format(start_seconds, '.17g')}:{format(end_seconds, '.17g')}"
    effective_map = assign_range_ids(
        identity_map,
        [(authored_id, start_seconds, end_seconds)],
    )
    display_ref = effective_map.lookup_semantic("range", authored_id)
    if display_ref is None:
        raise ValueError(f"failed to allocate a display id for range {authored_id!r}")
    return effective_map, replace(scope, ref=display_ref)


def _snapshot_head_version(snapshot: Any) -> int | None:
    """Event-head version for either a TimelineSnapshot or a Mapping twin."""
    version = getattr(snapshot, "head_version", None)
    if version is None and isinstance(snapshot, Mapping):
        head = snapshot.get("event_head") or {}
        version = head.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


def _pages_for(
    args: argparse.Namespace,
    model: Any,
    identity_map: Any,
    scope: Any,
    *,
    segments: list[TranscriptSegment] | None = None,
    occurrences: list[SpeechOccurrence] | None = None,
    snapshot_version: int | None = None,
) -> tuple[LayoutPage, ...]:
    layouts = _LAYOUTS if args.layout == "both" else (args.layout,)
    pages = tuple(
        page
        for layout_name in layouts
        for page in layout_timeline(
            model,
            identity_map,
            scope,
            layout=layout_name,
            transcript_segments=segments,
            speech_occurrences=occurrences,
            snapshot_version=snapshot_version,
        )
    )
    return tuple(
        replace(page, page_index=index, page_id=f"PG{index:03d}")
        for index, page in enumerate(pages, start=1)
    )


def _normalized_formats(raw: list[str] | None) -> frozenset[str]:
    if not raw or "all" in raw:
        return _FORMATS
    values = {
        part.strip().lower() for token in raw for part in str(token).split(",") if part.strip()
    }
    if "all" in values:
        return _FORMATS
    return frozenset(values)


def _rendered_expected_hash(
    snapshot: Any,
    rendered_video: Path,
    project_root: Path,
    media_snapshot: Any | None = None,
) -> str | None:
    """Expected sha256 for the supplied rendered output, or None.

    The R12 rendered contract verifies the supplied rendered output against a
    *recorded* provenance hash.  The only trusted record is a
    ``rendered_sample`` asset in the frozen registry whose contained path
    resolves to the supplied path.  No record means ``None`` — which
    ``verify_rendered_output`` turns into ``hash_unrecorded`` (refused): an
    arbitrary path is never self-verified.
    """

    # A caller-supplied rendered path is not a media identity. Rendered
    # sampling is admitted only when the host supplies a managed object
    # digest; this legacy path comparison has no live equivalent.
    del snapshot, rendered_video, project_root, media_snapshot
    return None


def _page_asset_refs(page: LayoutPage, model: Any, identity_map: Any) -> list[str]:
    """Asset display refs on one page, deduped in reading order.

    The layout emits ``clip`` objects carrying clip display ids (``CL01``);
    each clip's referenced assets come from the frozen model
    (``ClipModel.asset_refs``, authored asset keys).  The selection rule is
    deterministic: page objects in reading order, then clip asset refs in
    model order.
    """

    seen: list[str] = []
    clip_by_id: dict[str, Any] = {}
    for clip in model.clips:
        identity = identity_map.lookup_semantic("clip", clip.clip_id)
        if identity is not None:
            clip_by_id[identity] = clip
    for item in page.objects:
        if item.kind != "clip":
            continue
        clip = clip_by_id.get(item.display_id)
        if clip is None:
            continue
        for asset_key in clip.asset_refs:
            asset_display = identity_map.lookup_semantic("asset", asset_key)
            if asset_display is not None and asset_display not in seen:
                seen.append(asset_display)
    return seen


def _asset_filmstrips(
    *,
    mode: str,
    rendered_video: Path | None,
    snapshot: Any,
    model: Any,
    identity_map: Any,
    project_root: Path,
    sample_root: Path,
    pages: tuple[LayoutPage, ...],
    media_snapshot: Any | None = None,
    materialized_objects: Mapping[str, Any] | None = None,
    materialized_root: Path | None = None,
) -> dict[str, list[Path]]:
    if mode == "off":
        return {}
    if mode == "rendered" or (mode == "auto" and rendered_video is not None):
        # Rendered sampling is a separate, opt-in path (the plan's
        # --rendered-video flag): verify the supplied rendered output against
        # the recorded provenance hash, then sample — never fall back to
        # source sampling.  Each page receives its own strip of at most
        # MAX_FRAMES_PER_PAGE frames.
        expected = _rendered_expected_hash(
            snapshot,
            rendered_video,
            project_root,
            media_snapshot=media_snapshot,
        )
        reason = verify_rendered_output(rendered_video, expected_sha256=expected)
        if reason is not None:
            raise ValueError(f"rendered filmstrip refused: {reason}")
        filmstrips: dict[str, list[Path]] = {}
        for page in pages:
            filmstrips[page.page_id] = sample_rendered_filmstrip(
                rendered_video,
                n_frames=MAX_FRAMES_PER_PAGE,
                out_dir=sample_root,
                page_id=page.page_id,
                expected_sha256=expected,
            )
        return filmstrips
    classified = classify_registry(
        snapshot.registry,
        project_ref=snapshot.project_slug,
        media_snapshot=media_snapshot,
    )
    raw_assets = (
        snapshot.registry.get("assets", {}) if isinstance(snapshot.registry, Mapping) else {}
    )
    filmstrips: dict[str, list[Path]] = {}
    for page in pages:
        refs = _page_asset_refs(page, model, identity_map)
        if not refs:
            continue
        # Deterministic per-page budget (R13 hard cap): the PAGE never carries
        # more than MAX_FRAMES_PER_PAGE filmstrip frames, so budgets are
        # derived from THIS page's ref count and frames are keyed per page —
        # an asset that appears on two pages is sampled once per page, so a
        # dense page can never inherit a strip that overflows its budget.
        budget = per_page_frame_budget(len(refs))
        for ref in refs[:MAX_FRAMES_PER_PAGE]:
            identity = identity_map.lookup_display(ref)
            asset_key = identity[2] if identity is not None else None
            integrity = classified.get(asset_key) if asset_key is not None else None
            if integrity is None:
                continue
            # TOCTOU guard: re-verify immediately before sampling so the bytes
            # Pillow/ffmpeg open are the bytes just verified.
            fresh = verify_now(
                integrity,
                media_snapshot=media_snapshot,
                materialized_objects=materialized_objects,
                materialized_root=materialized_root,
            )
            if guard_sampling(fresh) is not None:
                continue
            source_value = None
            if isinstance(raw_assets, Mapping) and asset_key is not None:
                raw_entry = raw_assets.get(asset_key)
                if isinstance(raw_entry, Mapping):
                    object_id = raw_entry.get("object_id") or raw_entry.get("media_id")
                    digest = raw_entry.get("digest") or raw_entry.get("content_sha256") or raw_entry.get("sha256")
                    for candidate_key in (object_id, digest, str(digest).removeprefix("sha256:") if digest else None):
                        if candidate_key and isinstance(materialized_objects, Mapping) and candidate_key in materialized_objects:
                            source_value = materialized_objects[candidate_key]
                            break
            if source_value is None:
                continue
            source = Path(str(source_value)).expanduser()
            media_type: str | None = None
            registry_entry = (
                raw_assets.get(asset_key)
                if isinstance(raw_assets, Mapping) and asset_key is not None
                else None
            )
            if isinstance(registry_entry, Mapping):
                raw_type = registry_entry.get("type")
                if isinstance(raw_type, str) and raw_type.strip():
                    media_type = raw_type.strip().lower().split("/", 1)[0]
            key = f"{page.page_id}::{ref}"
            filmstrips[key] = sample_filmstrip(
                source,
                n_candidates=budget,
                n_frames=budget,
                out_dir=sample_root,
                page_id=f"{page.page_id}_{ref.replace('.', '_')}",
                media_type=media_type,
                integrity=fresh,
                project_root=project_root,
                media_snapshot=media_snapshot,
                materialized_objects=materialized_objects,
                materialized_root=materialized_root,
            )
    return filmstrips


def _parent_action_index(
    action_index: dict[str, Any],
    frozen: FrozenView,
) -> dict[str, Any]:
    """Attach one exact-parent action without mutating the emitted graph."""

    result = deepcopy(action_index)
    timeline_ref = frozen.manifest["snapshots"][0]["timeline"]["qualified_ref"]
    scope = frozen.manifest.get("scope", {})
    parent_ref = scope.get("ref") if isinstance(scope, Mapping) else None
    if not isinstance(parent_ref, str) or not parent_ref:
        parent_ref = timeline_ref
    parent_kind = scope.get("kind") if isinstance(scope, Mapping) else None
    if parent_kind not in {
        "project",
        "timeline",
        "shot",
        "range",
        "clip",
        "asset",
        "timestamp",
        "text",
        "speech",
    }:
        parent_kind = "timeline"
    entry = result.get("entries", {}).get(timeline_ref)
    if not isinstance(entry, dict) or not isinstance(entry.get("actions"), dict):
        raise ValueError("child action index has no timeline navigation entry")
    entry["actions"]["parent_view"] = {
        "kind": "visualize",
        "argv": [
            "python3",
            "-m",
            "astrid",
            "timelines",
            "visualize",
            "--from-view",
            str(frozen.source_manifest or (frozen.pack_root / "manifest.json")),
            "--focus",
            parent_ref,
        ],
        "focus": parent_ref,
        "result_scope": parent_kind,
        "available": True,
        "unavailable_reason": None,
        "reads": "snapshot",
    }
    return result


def _frozen_transcript_evidence(
    frozen: FrozenView,
) -> tuple[
    TranscriptAttachment | None,
    list[TranscriptSegment],
    list[SpeechOccurrence],
    str | None,
]:
    """Rehydrate only hashed transcript facts; never reopen source content."""

    timeline = frozen.ground_truth.get("frozen_timeline", {})
    block = timeline.get("transcript_attachment") if isinstance(timeline, dict) else None
    if not isinstance(block, dict):
        return None, [], [], None
    attachment = TranscriptAttachment(
        source_id=block["source_id"],
        source_version=block["source_version"],
        transcript_sha256=block["transcript_sha256"],
        media_identity=block["media_identity"],
        media_sha256=block["media_sha256"],
        producer=block["producer"],
        producer_version=block["producer_version"],
        model=block["model"],
        schema_version=block["schema_version"],
        integrity=block["integrity"],
    )
    segments: list[TranscriptSegment] = []
    for row in frozen.transcript_index.get("sources", []):
        words = row.get("words")
        segments.append(
            TranscriptSegment(
                segment_id=row["source_segment_id"],
                source_start=float(row["source_interval"]["start_seconds"]),
                source_end=float(row["source_interval"]["end_seconds"]),
                text=row["text"],
                speaker=row["speaker"],
                word_timing=(
                    tuple(
                        (
                            float(word["start_seconds"]),
                            float(word["end_seconds"]),
                            word["text"],
                        )
                        for word in words
                    )
                    if isinstance(words, list)
                    else None
                ),
                speaker_state=row["speaker_state"],
            )
        )
    asset_key: str | None = None
    occurrences: list[SpeechOccurrence] = []
    for row in frozen.transcript_index.get("speech_occurrences", []):
        source_identity = frozen.identity_map.lookup_display(row["source_ref"])
        clip_identity = frozen.identity_map.lookup_display(row["clip_ref"])
        asset_identity = frozen.identity_map.lookup_display(row["asset_ref"])
        if source_identity is None or clip_identity is None or asset_identity is None:
            raise ValueError("frozen transcript occurrence has an unresolved TS/CL/AS ref")
        source_row = next(
            item
            for item in frozen.transcript_index["sources"]
            if item["qualified_ref"] == row["source_ref"]
        )
        authored = row["authored_mapping"]
        effective = row["effective_mapping"]
        authored_interval = authored["interval"]
        effective_interval = effective["interval"]
        if authored_interval is None:
            continue
        asset_key = asset_identity[2]
        occurrences.append(
            SpeechOccurrence(
                occurrence_id=row["qualified_ref"],
                segment_id=source_row["source_segment_id"],
                clip_id=clip_identity[2],
                timeline_start=float(authored_interval["start_seconds"]),
                timeline_end=float(authored_interval["end_seconds"]),
                clip_start=0.0,
                clip_end=float(authored_interval["end_seconds"])
                - float(authored_interval["start_seconds"]),
                effective_start=(
                    float(effective_interval["start_seconds"])
                    if effective_interval is not None
                    else None
                ),
                effective_end=(
                    float(effective_interval["end_seconds"])
                    if effective_interval is not None
                    else None
                ),
                mapping_state=authored["state"],
                effective_state=effective["state"],
                asset_key=asset_identity[2],
            )
        )
    if asset_key is None and frozen.transcript_index.get("sources"):
        asset_identity = frozen.identity_map.lookup_display(
            frozen.transcript_index["sources"][0]["asset_ref"]
        )
        if asset_identity is not None:
            asset_key = asset_identity[2]
    return attachment, segments, occurrences, asset_key


def _materialize_view(
    *,
    args: argparse.Namespace,
    project_root: Path,
    pack_root: Path,
    snapshot: Any,
    model: Any,
    identity_map: Any,
    scope: Any,
    pack_snapshot: Any | None = None,
    frozen_parent: FrozenView | None = None,
    transcript_attachment: TranscriptAttachment | None = None,
    transcript_segments: list[TranscriptSegment] | None = None,
    speech_occurrences: list[SpeechOccurrence] | None = None,
    transcript_asset_key: str | None = None,
    media_snapshot: Any | None = None,
    materialized_objects: Mapping[str, Any] | None = None,
    materialized_root: Path | None = None,
) -> PackLayout:
    pages = _pages_for(
        args,
        model,
        identity_map,
        scope,
        segments=transcript_segments,
        occurrences=speech_occurrences,
        snapshot_version=_snapshot_head_version(snapshot),
    )
    formats = _normalized_formats(args.format)
    png_bytes = {page.page_id: render_page_png(page) for page in pages} if "png" in formats else {}
    svg_bytes = (
        {page.page_id: render_page_svg_bytes(page) for page in pages} if "svg" in formats else {}
    )
    pack_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".timeline-visualize-samples-", dir=pack_root.parent
    ) as raw_sample_root:
        filmstrips = _asset_filmstrips(
            mode=args.filmstrip,
            rendered_video=args.rendered_video,
            snapshot=snapshot,
            model=model,
            identity_map=identity_map,
            project_root=project_root,
            sample_root=Path(raw_sample_root),
            pages=pages,
            media_snapshot=media_snapshot,
            materialized_objects=materialized_objects,
            materialized_root=materialized_root,
        )
        ground_truth = emit_ground_truth(
            model,
            identity_map,
            snapshot,
            scope,
            transcript_attachment,
            speech_occurrences,
        )
        action_index = emit_action_index(
            model,
            identity_map,
            snapshot,
            pack_root / "manifest.json",
            scope,
            transcript_attachment,
            speech_occurrences,
        )
        from_view: str | None = None
        focus: str | None = None
        if frozen_parent is not None:
            # Complete lineage facts are copied exactly; scoped presentation
            # facts above remain specific to this child.
            for key in (
                "frozen_objects",
                "frozen_timeline",
                "frozen_shots",
                "frozen_ranges",
            ):
                if key in frozen_parent.ground_truth:
                    ground_truth[key] = deepcopy(frozen_parent.ground_truth[key])
            action_index = _parent_action_index(action_index, frozen_parent)
            parent_manifest = frozen_parent.source_manifest or (
                frozen_parent.pack_root / "manifest.json"
            )
            try:
                from_view = parent_manifest.relative_to(project_root).as_posix()
            except ValueError:
                from_view = str(parent_manifest)
            focus = args.focus
        resolved_project: dict[str, str] = {"slug": args.project_slug}
        if args.from_view is not None or frozen_parent is not None:
            source_mode = "frozen"
        else:
            source_mode = "kernel"
        return write_evidence_pack(
            out_root=pack_root,
            page_id_prefix="PG",
            model=model,
            identity_map=identity_map,
            # serialize_view_map accepts a verified snapshot block directly.
            # Frozen children therefore never recompute the SNS from the
            # synthetic emitter adapter's placeholder component hashes.
            snapshot=(pack_snapshot if pack_snapshot is not None else snapshot),
            scope=scope,
            ground_truth=ground_truth,
            action_index=action_index,
            asset_index=(
                deepcopy(frozen_parent.asset_index)
                if frozen_parent is not None
                else emit_asset_index(model, identity_map, snapshot)
            ),
            transcript_index=(
                deepcopy(frozen_parent.transcript_index)
                if frozen_parent is not None
                else emit_transcript_index(
                    model,
                    identity_map,
                    snapshot,
                    transcript_attachment,
                    transcript_segments,
                    speech_occurrences,
                    transcript_asset_key,
                )
            ),
            diagnostics=emit_diagnostics(model, identity_map, snapshot, scope),
            reading_guide=emit_reading_guide(model, identity_map, snapshot),
            structure_md=(
                emit_structure_md(
                    model,
                    identity_map,
                    snapshot,
                    transcript_attachment,
                    transcript_segments,
                    speech_occurrences,
                )
                if "md" in formats
                else None
            ),
            metric_definitions=emit_metric_definitions(model, identity_map, snapshot),
            pages=pages,
            svg_bytes=svg_bytes,
            png_bytes=png_bytes,
            filmstrips=filmstrips,
            from_view=from_view,
            focus=focus,
            resolved_project=resolved_project,
            source_mode=source_mode,
        )


def _read_mapping(path: Path) -> dict[str, Any] | None:
    try:
        value = read_json(path)
    except (OSError, ValueError, ProjectJsonError):
        return None
    return value if isinstance(value, dict) else None


def _pipeline_metadata_for_timeline(
    project_root: Path,
    timeline_dir: Path,
) -> tuple[Mapping | None, Path | None, Path | None]:
    """Return no legacy run-file metadata.

    Producer artifacts must be obtained from the runtime result API.  That API
    does not yet expose transcript attachments, so the old ``runs/*/run.json``
    walk is retired instead of becoming a second authority.
    """

    del project_root, timeline_dir
    return None, None, None


def _has_pipeline_transcript_reference(metadata: Mapping) -> bool:
    if "transcript" in metadata:
        return True
    sources = metadata.get("sources")
    if not isinstance(sources, Mapping):
        return False
    return any(
        isinstance(source, Mapping) and ("transcript" in source or "transcript_ref" in source)
        for source in sources.values()
    )


def _discover_snapshot_attachment(
    *,
    project_root: Path,
    timeline_dir: Path,
    snapshot: TimelineSnapshot,
) -> tuple[TranscriptAttachment | None, TimelineSnapshot]:
    pipeline_metadata, pipeline_base, pipeline_root = _pipeline_metadata_for_timeline(
        project_root,
        timeline_dir,
    )
    timeline_metadata = snapshot.assembly.get("app")
    attachment = discover_attachment(
        project_root,
        timeline_dir=timeline_dir,
        timeline_metadata=(timeline_metadata if isinstance(timeline_metadata, Mapping) else None),
        pipeline_metadata=pipeline_metadata,
        pipeline_metadata_base=pipeline_base,
        pipeline_root=pipeline_root,
    )
    if attachment is None or attachment.integrity != "uncontained":
        return attachment, snapshot
    diagnostic = "TRANSCRIPT_PATH_UNCONTAINED: declared transcript path escaped its owning root"
    return None, replace(
        snapshot,
        diagnostics=tuple(dict.fromkeys((*snapshot.diagnostics, diagnostic))),
    )


def _render_one(
    *,
    args: argparse.Namespace,
    selected: ManagedTimeline,
    project_root: Path,
    pack_root: Path,
    execution_authority: Mapping[str, Any] | None = None,
    media_snapshot: Any | None = None,
    materialized_objects: Mapping[str, Any] | None = None,
    materialized_root: Path | None = None,
) -> PackLayout:
    if selected.runtime_config is None or not selected.runtime_events:
        raise ValueError("runtime timeline materialization is incomplete")
    snapshot = snapshot_from_runtime(
        timeline_id=selected.timeline_id,
        timeline_ulid=selected.timeline_ulid,
        slug=selected.slug or selected.timeline_ulid,
        project_slug=args.project_slug,
        events=selected.runtime_events,
        project_ref=args.project_slug,
        media_snapshot=media_snapshot,
    )
    if selected.kernel_head_version is not None:
        snapshot = replace(
            snapshot,
            head_version=selected.kernel_head_version,
            last_event_id=selected.kernel_head_event_id,
            last_hash=selected.kernel_head_hash,
            diagnostics=tuple(
                dict.fromkeys(
                    (
                        *snapshot.diagnostics,
                        "KERNEL_AUTHORITY: visualization snapshot is pinned to "
                        f"stream version {selected.kernel_head_version}, event "
                        f"{selected.kernel_source_event_id}, hash {selected.kernel_head_hash}",
                    )
                )
            ),
        )
    attachment, snapshot = _discover_snapshot_attachment(
        project_root=project_root,
        timeline_dir=project_root,
        snapshot=snapshot,
    )
    if attachment is not None and attachment.integrity == "ok":
        snapshot = replace(snapshot, transcript_sha256=attachment.transcript_sha256)
    model = build_model(
        snapshot,
        media_snapshot=media_snapshot,
    )
    transcript_segments: list[TranscriptSegment] = []
    speech_occurrences: list[SpeechOccurrence] = []
    transcript_asset_key: str | None = None
    if attachment is not None and attachment.integrity == "ok" and attachment.file is not None:
        transcript_asset_key = resolve_attachment_asset_key(attachment, model)
        if transcript_asset_key is not None:
            transcript_segments = normalize_transcript(attachment, attachment.file)
            speech_occurrences = map_occurrences(
                transcript_segments, model, asset_key=transcript_asset_key
            )
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    if transcript_segments:
        identity_map = assign_transcript_ids(
            identity_map,
            transcript_segments,
            speech_occurrences,
            transcript_sha256=attachment.transcript_sha256,
        )
        speech_occurrences = with_occurrence_ids(
            speech_occurrences,
            [
                identity_map.lookup_semantic(
                    "speech_occurrence",
                    speech_occurrence_authored_id(
                        attachment.transcript_sha256,
                        occurrence.segment_id,
                        occurrence.clip_id,
                    ),
                )
                or occurrence.occurrence_id
                for occurrence in speech_occurrences
            ],
        )
    scope = _scope_for(args, model)
    identity_map, scope = _mint_cold_range_root(model, identity_map, scope)
    return _materialize_view(
        args=args,
        project_root=project_root,
        pack_root=pack_root,
        snapshot=snapshot,
        model=model,
        identity_map=identity_map,
        scope=scope,
        transcript_attachment=attachment,
        transcript_segments=transcript_segments,
        speech_occurrences=speech_occurrences,
        transcript_asset_key=transcript_asset_key,
        media_snapshot=media_snapshot,
        materialized_objects=materialized_objects,
        materialized_root=materialized_root,
    )


def refresh_root(
    *,
    args: argparse.Namespace,
    frozen: FrozenView,
    project_root: Path,
    pack_root: Path,
    media_snapshot: Any | None = None,
    materialized_objects: Mapping[str, Any] | None = None,
    materialized_root: Path | None = None,
) -> PackLayout:
    """The sole frozen-lineage transition to current managed timeline state."""

    kernel_rows, diagnostics = select_kernel_timelines(
        project_root,
        project_slug=args.project_slug,
        slug=frozen.timeline_uuid,
    )
    if len(kernel_rows) != 1:
        raise ValueError(
            "; ".join(diagnostics)
            or "frozen timeline is unavailable in the workspace runtime"
        )
    timeline_dir = project_root / ".runtime-timelines" / kernel_rows[0].timeline_ulid.upper()
    selected = _materialize_kernel_timeline(
        kernel_rows[0],
        project_root=project_root,
        project_slug=args.project_slug,
        destination=timeline_dir,
    )
    if selected.runtime_config is None or not selected.runtime_events:
        raise ValueError("runtime timeline materialization is incomplete")
    snapshot = snapshot_from_runtime(
        timeline_id=selected.timeline_id,
        timeline_ulid=selected.timeline_ulid,
        slug=selected.slug or selected.timeline_ulid,
        project_slug=args.project_slug,
        events=selected.runtime_events,
        project_ref=args.project_slug,
        media_snapshot=media_snapshot,
    )
    attachment, snapshot = _discover_snapshot_attachment(
        project_root=project_root,
        timeline_dir=project_root,
        snapshot=snapshot,
    )
    if attachment is not None and attachment.integrity == "ok":
        snapshot = replace(snapshot, transcript_sha256=attachment.transcript_sha256)
    if (
        snapshot.timeline_id != frozen.timeline_uuid
        or snapshot.timeline_ulid != frozen.timeline_ulid
    ):
        raise ValueError("current managed timeline identity disagrees with the frozen lineage")
    model = build_model(
        snapshot,
        media_snapshot=media_snapshot,
    )
    transcript_segments: list[TranscriptSegment] = []
    speech_occurrences: list[SpeechOccurrence] = []
    transcript_asset_key: str | None = None
    if attachment is not None and attachment.integrity == "ok" and attachment.file is not None:
        transcript_asset_key = resolve_attachment_asset_key(attachment, model)
        if transcript_asset_key is not None:
            transcript_segments = normalize_transcript(attachment, attachment.file)
            speech_occurrences = map_occurrences(
                transcript_segments, model, asset_key=transcript_asset_key
            )
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    if transcript_segments:
        identity_map = assign_transcript_ids(
            identity_map,
            transcript_segments,
            speech_occurrences,
            transcript_sha256=attachment.transcript_sha256,
        )
        speech_occurrences = with_occurrence_ids(
            speech_occurrences,
            [
                identity_map.lookup_semantic(
                    "speech_occurrence",
                    speech_occurrence_authored_id(
                        attachment.transcript_sha256,
                        occurrence.segment_id,
                        occurrence.clip_id,
                    ),
                )
                or occurrence.occurrence_id
                for occurrence in speech_occurrences
            ],
        )
    return _materialize_view(
        args=args,
        project_root=project_root,
        pack_root=pack_root,
        snapshot=snapshot,
        model=model,
        identity_map=identity_map,
        scope=select_scope(model, kind="timeline"),
        transcript_attachment=attachment,
        transcript_segments=transcript_segments,
        speech_occurrences=speech_occurrences,
        transcript_asset_key=transcript_asset_key,
        media_snapshot=media_snapshot,
        materialized_objects=materialized_objects,
        materialized_root=materialized_root,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all_file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_project_index(
    pack_root: Path,
    *,
    args: argparse.Namespace,
    timeline_ids: list[str],
    children: list[PackLayout],
) -> Path:
    outputs = [
        {
            "name": f"TL{index:02d}",
            "path": f"TL{index:02d}",
            "type": "directory",
            "manifest_sha256": hashlib.sha256(child.manifest_path.read_bytes()).hexdigest(),
        }
        for index, child in enumerate(children, start=1)
    ]
    manifest = build_manifest(
        kind="timeline_visualize_project",
        inputs={
            "project_slug": args.project_slug,
            "timeline_ids": timeline_ids,
            "scope": "project",
            "layout": args.layout,
            "formats": sorted(_normalized_formats(args.format)),
            "filmstrip": args.filmstrip,
        },
        outputs=outputs,
        created=FROZEN_AT_SENTINEL,
        timeline_ids=timeline_ids,
        reading_order=[f"TL{index:02d}/manifest.json" for index in range(1, len(children) + 1)],
        entrypoints={
            f"TL{index:02d}": f"TL{index:02d}/manifest.json"
            for index in range(1, len(children) + 1)
        },
    )
    path = pack_root / "manifest.json"
    write_manifest(path, manifest)
    return path


def _mark_run_metadata(out_root: Path, project_slug: str, timeline_ids: list[str]) -> None:
    # Run metadata is settled through the runtime task result.  The
    # visualization pack is an output projection and must not mutate a local
    # run.json ledger after admission.
    del out_root, project_slug, timeline_ids


def _execute_from_frozen(
    *,
    args: argparse.Namespace,
    project_root: Path,
    out_root: Path,
    pack_root: Path,
    execution_authority: Mapping[str, Any] | None,
    media_snapshot: Any | None = None,
    materialized_objects: Mapping[str, Any] | None = None,
    materialized_root: Path | None = None,
) -> dict[str, Any]:
    frozen = load_frozen_view(args.from_view, project_root=project_root)
    try:
        _verify_frozen_execution_authority(args.from_view, frozen, execution_authority)
        if execution_authority is not None and execution_authority.get("focus") != args.focus:
            raise ValueError("frozen visualization focus changed after admission")
        if frozen.ground_truth.get("project_slug") != args.project_slug:
            raise ValueError("frozen view project does not match project_slug input")
        timeline_ids = [frozen.timeline_ulid]
        _mark_run_metadata(out_root, args.project_slug, timeline_ids)
        if args.refresh_root:
            refresh_scope = resolve_focus(frozen, args.focus)
            if refresh_scope.kind != "timeline":
                raise ValueError("--refresh-root focus must resolve to the frozen timeline")
            layout = refresh_root(
                args=args,
                frozen=frozen,
                project_root=project_root,
                pack_root=pack_root,
                media_snapshot=media_snapshot,
                materialized_objects=materialized_objects,
                materialized_root=materialized_root,
            )
        else:
            model = model_from_frozen(frozen)
            snapshot = snapshot_from_frozen(frozen, model)
            (
                transcript_attachment,
                transcript_segments,
                speech_occurrences,
                transcript_asset_key,
            ) = _frozen_transcript_evidence(frozen)
            scope = resolve_focus(
                frozen,
                args.focus,
                context_seconds=args.context,
                neighbors=args.neighbors,
            )
            layout = _materialize_view(
                args=args,
                project_root=project_root,
                pack_root=pack_root,
                snapshot=snapshot,
                model=model,
                identity_map=frozen.identity_map.child_copy(),
                scope=scope,
                pack_snapshot={"snapshots": deepcopy(frozen.manifest["snapshots"])},
                frozen_parent=frozen,
                transcript_attachment=transcript_attachment,
                transcript_segments=transcript_segments,
                speech_occurrences=speech_occurrences,
                transcript_asset_key=transcript_asset_key,
                media_snapshot=media_snapshot,
                materialized_objects=materialized_objects,
                materialized_root=materialized_root,
            )
        manifest_path = layout.manifest_path
        outputs: dict[str, Any] = {
            "pack_root": str(pack_root),
            "manifest_path": str(manifest_path),
            "pages": [str(path) for path in layout.pages],
            "file_hashes": dict(layout.file_hashes),
        }
        return {
            "returncode": 0,
            "run_root": str(out_root),
            "manifest_path": str(manifest_path),
            "timeline_ids": timeline_ids,
            "outputs": outputs,
        }
    finally:
        discard_rehydrated_pack(frozen.pack_root)


def execute(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(argv)
    if args.materialized_objects:
        try:
            args.materialized_objects = json.loads(args.materialized_objects)
        except json.JSONDecodeError:
            raise ValueError("--materialized-objects must be a JSON object") from None
        if not isinstance(args.materialized_objects, Mapping):
            raise ValueError("--materialized-objects must be a JSON object")
    else:
        args.materialized_objects = None
    _validate_selectors(args)
    if not args.project_slug:
        raise ValueError(
            "project is required: pass --project-slug <slug> or select a current "
            "project in the workspace runtime"
        )
    # This process has no project-tree authority.  Runtime rows are selected
    # below and materialized beneath the disposable output workspace.
    out_root = args.out.expanduser().resolve()
    project_root = out_root / args.project_slug
    project_root.mkdir(parents=True, exist_ok=True)
    # The runtime is the only authority for managed media ownership.  Capture
    # one project-scoped snapshot for every selected timeline in this run;
    # local-source and offline migration callers remain unaffected when the
    # runtime is unavailable.
    media_snapshot = _runtime_media_snapshot(args.project_slug)
    pack_root = out_root / "agent-view"
    execution_authority = _execution_authority_context()
    if pack_root.exists() and any(pack_root.iterdir()):
        raise ValueError(f"evidence pack output is not empty: {pack_root}")

    if args.from_view is not None:
        return _execute_from_frozen(
            args=args,
            project_root=project_root,
            out_root=out_root,
            pack_root=pack_root,
            execution_authority=execution_authority,
            media_snapshot=media_snapshot,
            materialized_objects=args.materialized_objects,
            materialized_root=args.materialized_root,
        )

    kernel_materialization_root = out_root / ".kernel-timelines"
    selected = _select_timelines(
        args,
        project_root,
        kernel_materialization_root=kernel_materialization_root,
    )
    _verify_selected_execution_authority(selected, execution_authority)
    timeline_ids = sorted({row.timeline_ulid for row in selected})
    _mark_run_metadata(out_root, args.project_slug, timeline_ids)

    if len(selected) == 1:
        layout = _render_one(
            args=args,
            selected=selected[0],
            project_root=project_root,
            pack_root=pack_root,
            execution_authority=execution_authority,
            media_snapshot=media_snapshot,
            materialized_objects=args.materialized_objects,
            materialized_root=args.materialized_root,
        )
        manifest_path = layout.manifest_path
        pages = list(layout.pages)
        file_hashes = dict(layout.file_hashes)
    else:
        pack_root.mkdir(parents=True, exist_ok=True)
        children = [
            _render_one(
                args=args,
                selected=row,
                project_root=project_root,
                pack_root=pack_root / f"TL{index:02d}",
                execution_authority=execution_authority,
                media_snapshot=media_snapshot,
                materialized_objects=args.materialized_objects,
                materialized_root=args.materialized_root,
            )
            for index, row in enumerate(selected, start=1)
        ]
        manifest_path = _write_project_index(
            pack_root,
            args=args,
            timeline_ids=timeline_ids,
            children=children,
        )
        pages = [path for child in children for path in child.pages]
        file_hashes = _all_file_hashes(pack_root)

    outputs: dict[str, Any] = {
        "pack_root": str(pack_root),
        "manifest_path": str(manifest_path),
        "pages": [str(path) for path in pages],
        "file_hashes": file_hashes,
    }
    shutil.rmtree(kernel_materialization_root, ignore_errors=True)
    return {
        "returncode": 0,
        "run_root": str(out_root),
        "manifest_path": str(manifest_path),
        "timeline_ids": timeline_ids,
        "outputs": outputs,
    }


def run_sdk(argv: list[str] | None = None) -> dict[str, Any]:
    """Return a JSON-safe executor payload without writing to stdout."""
    try:
        return execute(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return {
            "returncode": int(code),
            "error": {"type": "SystemExit", "message": str(exc.code or "")},
        }
    except Exception as exc:  # noqa: BLE001 - executor boundary returns process-like diagnostics
        return {
            "returncode": 1,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def main(argv: list[str] | None = None) -> int:
    result = run_sdk(argv)
    returncode = int(result.get("returncode", 1))
    if returncode:
        error = result.get("error")
        if isinstance(error, Mapping):
            message = error.get("message") or error.get("type") or "timeline visualization failed"
        else:
            message = "timeline visualization failed"
        print(message, file=sys.stderr)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
