#!/usr/bin/env python3
"""Package the read-only timeline visualization pipeline as an executor."""

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("rendering.timeline_visualize")

import argparse
from copy import deepcopy
import hashlib
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core._shared.result_manifest import build_manifest, write_manifest
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.schema import validate_run_record
from astrid.core.timeline.resolution import classify_registry
from astrid.core.timeline.snapshot import acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.assets import (
    guard_sampling,
    verify_now,
    verified_source_path,
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
    ManagedTimeline,
    select_timeline,
)
from astrid.packs.rendering.executors.timeline_visualize.thumbnails import (
    MAX_FRAMES_PER_PAGE,
    per_page_frame_budget,
    sample_filmstrip,
    sample_rendered_filmstrip,
    verify_rendered_output,
)

_LAYOUTS = ("time-scaled", "linear")
_FORMATS = frozenset({"png", "svg", "md"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rendering.timeline_visualize",
        description="Build a deterministic agent evidence pack from managed timeline event logs.",
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project-slug", required=True)
    parser.add_argument("--timeline-source", action="append", type=Path, default=[])
    parser.add_argument("--timeline-slug")
    parser.add_argument("--all", action="store_true", dest="select_all")
    parser.add_argument(
        "--scope",
        choices=("project", "timeline", "shot", "range", "clip", "asset", "timestamp"),
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
    parser.add_argument("--layout", choices=(*_LAYOUTS, "both"), default="both")
    parser.add_argument("--format", action="append", choices=(*sorted(_FORMATS), "all"))
    parser.add_argument(
        "--filmstrip", choices=("auto", "off", "assets", "rendered"), default="auto"
    )
    parser.add_argument("--rendered-video", type=Path)
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
    if args.timeline_source and (args.timeline_slug is not None or args.select_all):
        raise ValueError(
            "--timeline-source cannot be combined with --timeline-slug or --all"
        )
    if (args.from_view is None) != (args.focus is None):
        raise ValueError("--from-view and --focus must be supplied together")
    if args.refresh_root and args.from_view is None:
        raise ValueError("--refresh-root requires --from-view and --focus")
    if args.from_view is not None:
        conflicts = [
            name
            for name, value in (
                ("--timeline-source", bool(args.timeline_source)),
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
            raise ValueError(
                "--from-view/--focus cannot be combined with " + ", ".join(conflicts)
            )
        if args.refresh_root and parse_qualified_ref(args.focus).kind != "TL":
            raise ValueError("--refresh-root focus must be the frozen timeline reference")
    if args.rendered_video is not None and args.filmstrip not in {"auto", "rendered"}:
        raise ValueError("--rendered-video requires --filmstrip auto or rendered")
    if args.filmstrip == "rendered" and args.rendered_video is None:
        raise ValueError("--filmstrip rendered requires --rendered-video")


def _contained_timeline_sources(
    project_root: Path,
    sources: Iterable[Path],
) -> tuple[list[ManagedTimeline], list[str]]:
    timelines_root = (project_root / "timelines").resolve()
    discovered, diagnostics = select_timeline(project_root, all=True)
    by_path = {
        row.timeline_dir.resolve(): row
        for row in discovered
        if row.timeline_dir is not None
    }
    selected: list[ManagedTimeline] = []
    missing: list[str] = []
    for raw in sources:
        candidate = raw.expanduser().resolve()
        if candidate.parent != timelines_root:
            raise ValueError(
                f"timeline_source escapes the project's direct timelines directory: {raw}"
            )
        row = by_path.get(candidate)
        if row is None:
            missing.append(str(candidate))
            continue
        selected.append(row)
    if missing:
        detail = "; ".join(diagnostics) if diagnostics else "not a live managed timeline"
        raise ValueError(f"invalid timeline_source {', '.join(missing)}: {detail}")
    deduped = {row.timeline_ulid: row for row in selected}
    return [deduped[key] for key in sorted(deduped)], diagnostics


def _select_timelines(args: argparse.Namespace, project_root: Path) -> list[ManagedTimeline]:
    if args.timeline_source:
        selected, diagnostics = _contained_timeline_sources(project_root, args.timeline_source)
    else:
        selected, diagnostics = select_timeline(
            project_root,
            slug=args.timeline_slug,
            all=args.select_all,
            default=not args.timeline_slug and not args.select_all,
        )
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
    authored_id = (
        f"range:{format(start_seconds, '.17g')}:{format(end_seconds, '.17g')}"
    )
    effective_map = assign_range_ids(
        identity_map,
        [(authored_id, start_seconds, end_seconds)],
    )
    display_ref = effective_map.lookup_semantic("range", authored_id)
    if display_ref is None:
        raise ValueError(f"failed to allocate a display id for range {authored_id!r}")
    return effective_map, replace(scope, ref=display_ref)


def _pages_for(args: argparse.Namespace, model: Any, identity_map: Any, scope: Any) -> tuple[LayoutPage, ...]:
    layouts = _LAYOUTS if args.layout == "both" else (args.layout,)
    pages = tuple(
        page
        for layout_name in layouts
        for page in layout_timeline(model, identity_map, scope, layout=layout_name)
    )
    return tuple(
        replace(page, page_index=index, page_id=f"PG{index:03d}")
        for index, page in enumerate(pages, start=1)
    )


def _normalized_formats(raw: list[str] | None) -> frozenset[str]:
    if not raw or "all" in raw:
        return _FORMATS
    return frozenset(raw)


def _rendered_expected_hash(
    snapshot: Any,
    rendered_video: Path,
    project_root: Path,
) -> str | None:
    """Expected sha256 for the supplied rendered output, or None.

    The R12 rendered contract verifies the supplied rendered output against a
    *recorded* provenance hash.  The only trusted record is a
    ``rendered_sample`` asset in the frozen registry whose contained path
    resolves to the supplied path.  No record means ``None`` — which
    ``verify_rendered_output`` turns into ``hash_unrecorded`` (refused): an
    arbitrary path is never self-verified.
    """

    target = rendered_video.expanduser().resolve()
    classified = classify_registry(snapshot.registry, project_root=project_root)
    for asset_key in sorted(classified):
        integrity = classified[asset_key]
        if integrity.role != "rendered_sample" or not isinstance(integrity.path, str):
            continue
        try:
            same = Path(integrity.path).resolve() == target
        except OSError:
            same = False
        if same:
            return integrity.expected_sha256
    return None


def _page_asset_refs(
    page: LayoutPage, model: Any, identity_map: Any
) -> list[str]:
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
) -> dict[str, list[Path]]:
    if mode == "off":
        return {}
    if mode == "rendered" or (mode == "auto" and rendered_video is not None):
        # Rendered sampling is a separate, opt-in path (the plan's
        # --rendered-video flag): verify the supplied rendered output against
        # the recorded provenance hash, then sample — never fall back to
        # source sampling.  Each page receives its own strip of at most
        # MAX_FRAMES_PER_PAGE frames.
        expected = _rendered_expected_hash(snapshot, rendered_video, project_root)
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
    classified = classify_registry(snapshot.registry, project_root=project_root)
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
            fresh = verify_now(integrity, project_root=project_root)
            if guard_sampling(fresh) is not None:
                continue
            source = verified_source_path(fresh)
            if source is None:
                continue
            key = f"{page.page_id}::{ref}"
            filmstrips[key] = sample_filmstrip(
                source,
                n_candidates=budget,
                n_frames=budget,
                out_dir=sample_root,
                page_id=f"{page.page_id}_{ref.replace('.', '_')}",
                integrity=fresh,
                project_root=project_root,
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
            str(frozen.pack_root / "manifest.json"),
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
) -> PackLayout:
    pages = _pages_for(args, model, identity_map, scope)
    formats = _normalized_formats(args.format)
    png_bytes = (
        {page.page_id: render_page_png(page) for page in pages}
        if "png" in formats
        else {}
    )
    svg_bytes = (
        {page.page_id: render_page_svg_bytes(page) for page in pages}
        if "svg" in formats
        else {}
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
        )
        ground_truth = emit_ground_truth(model, identity_map, snapshot, scope)
        action_index = emit_action_index(
            model, identity_map, snapshot, pack_root / "manifest.json", scope
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
            from_view = (
                frozen_parent.pack_root / "manifest.json"
            ).relative_to(project_root).as_posix()
            focus = args.focus
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
                else emit_transcript_index(model, identity_map, snapshot)
            ),
            diagnostics=emit_diagnostics(model, identity_map, snapshot, scope),
            reading_guide=emit_reading_guide(model, identity_map, snapshot),
            structure_md=(
                emit_structure_md(model, identity_map, snapshot)
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
        )


def _render_one(
    *,
    args: argparse.Namespace,
    selected: ManagedTimeline,
    project_root: Path,
    pack_root: Path,
) -> PackLayout:
    if selected.timeline_dir is None:
        raise ValueError("cold visualization requires a managed timeline directory")
    snapshot = acquire_snapshot(
        selected.timeline_dir,
        project_slug=args.project_slug,
        project_root=project_root,
        retries=2,
    )
    model = build_model(snapshot, project_root=project_root)
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
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
    )


def refresh_root(
    *,
    args: argparse.Namespace,
    frozen: FrozenView,
    project_root: Path,
    pack_root: Path,
) -> PackLayout:
    """The sole frozen-lineage transition to current managed timeline state."""

    timelines_root = (project_root / "timelines").resolve(strict=True)
    declared_timeline_dir = timelines_root / frozen.timeline_ulid
    if declared_timeline_dir.is_symlink():
        raise ValueError("the frozen timeline path must not be a symlink")
    timeline_dir = declared_timeline_dir.resolve(strict=True)
    if timeline_dir.parent != timelines_root or not timeline_dir.is_dir():
        raise ValueError("the frozen timeline is no longer a contained managed timeline")
    snapshot = acquire_snapshot(
        timeline_dir,
        project_slug=args.project_slug,
        project_root=project_root,
        retries=2,
    )
    if snapshot.timeline_id != frozen.timeline_uuid or snapshot.timeline_ulid != frozen.timeline_ulid:
        raise ValueError("current managed timeline identity disagrees with the frozen lineage")
    model = build_model(snapshot, project_root=project_root)
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    return _materialize_view(
        args=args,
        project_root=project_root,
        pack_root=pack_root,
        snapshot=snapshot,
        model=model,
        identity_map=identity_map,
        scope=select_scope(model, kind="timeline"),
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
        }
        for index in range(1, len(children) + 1)
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
    run_path = out_root / "run.json"
    if not run_path.is_file():
        return
    record = validate_run_record(read_json(run_path))
    if record.get("project_slug") != project_slug:
        raise ValueError("managed run project does not match project_slug input")
    metadata = dict(record.get("metadata", {}))
    metadata.update({"evidence": True, "timeline_ids": timeline_ids})
    record["metadata"] = metadata
    write_json_atomic(run_path, validate_run_record(record))


def execute(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(argv)
    _validate_selectors(args)
    env_project = os.environ.get("ASTRID_PROJECT_SLUG")
    if env_project and env_project != args.project_slug:
        raise ValueError(
            f"project_slug {args.project_slug!r} does not match managed project {env_project!r}"
        )
    project_root = project_dir(args.project_slug).resolve()
    if not project_root.is_dir():
        raise ValueError(f"project not found: {args.project_slug}")
    out_root = args.out.expanduser().resolve()
    pack_root = out_root / "agent-view"
    if pack_root.exists() and any(pack_root.iterdir()):
        raise ValueError(f"evidence pack output is not empty: {pack_root}")

    if args.from_view is not None:
        frozen = load_frozen_view(args.from_view, project_root=project_root)
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
            )
        else:
            model = model_from_frozen(frozen)
            snapshot = snapshot_from_frozen(frozen, model)
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
            )
        manifest_path = layout.manifest_path
        pages = list(layout.pages)
        file_hashes = dict(layout.file_hashes)
        outputs: dict[str, Any] = {
            "pack_root": str(pack_root),
            "manifest_path": str(manifest_path),
            "pages": [str(path) for path in pages],
            "file_hashes": file_hashes,
        }
        return {
            "returncode": 0,
            "run_root": str(out_root),
            "manifest_path": str(manifest_path),
            "timeline_ids": timeline_ids,
            "outputs": outputs,
        }

    selected = _select_timelines(args, project_root)
    timeline_ids = sorted({row.timeline_ulid for row in selected})
    _mark_run_metadata(out_root, args.project_slug, timeline_ids)

    if len(selected) == 1:
        layout = _render_one(
            args=args,
            selected=selected[0],
            project_root=project_root,
            pack_root=pack_root,
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
    except Exception as exc:  # executor boundary: return a process-like diagnostic
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
