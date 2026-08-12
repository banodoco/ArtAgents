#!/usr/bin/env python3
"""Package the read-only timeline visualization pipeline as an executor."""

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("rendering.timeline_visualize")

import argparse
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
from astrid.packs.rendering.executors.timeline_visualize.layout import (
    LayoutPage,
    layout_timeline,
)
from astrid.packs.rendering.executors.timeline_visualize.model import build_model
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
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
    if args.from_view is not None:
        raise ValueError(
            "snapshot-safe --from-view/--focus execution is introduced by R16; "
            "use a cold selector for this executor version"
        )
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
    filmstrips = {}
    sampled_assets: set[str] = set()
    for page in pages:
        refs = _page_asset_refs(page, model, identity_map)
        if not refs:
            continue
        # Deterministic per-page budget: assets are ordered by display
        # ordinal; the first min(k, MAX_FRAMES_PER_PAGE) assets are sampled,
        # each with per_page_frame_budget(k) frames, so the page never carries
        # more than 12 filmstrip frames.  An asset already sampled on an
        # earlier page is not re-sampled (its frames satisfy every page it
        # appears on).
        budget = per_page_frame_budget(len(refs))
        for ref in refs[:MAX_FRAMES_PER_PAGE]:
            if ref in sampled_assets:
                continue
            sampled_assets.add(ref)
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
            filmstrips[ref] = sample_filmstrip(
                source,
                n_candidates=budget,
                n_frames=budget,
                out_dir=sample_root,
                page_id=ref.replace(".", "_"),
                integrity=fresh,
                project_root=project_root,
            )
    return filmstrips


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
        return write_evidence_pack(
            out_root=pack_root,
            page_id_prefix="PG",
            model=model,
            identity_map=identity_map,
            snapshot=snapshot,
            scope=scope,
            ground_truth=emit_ground_truth(model, identity_map, snapshot, scope),
            action_index=emit_action_index(
                model, identity_map, snapshot, pack_root / "manifest.json", scope
            ),
            asset_index=emit_asset_index(model, identity_map, snapshot),
            transcript_index=emit_transcript_index(model, identity_map, snapshot),
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
    selected = _select_timelines(args, project_root)
    timeline_ids = sorted({row.timeline_ulid for row in selected})
    out_root = args.out.expanduser().resolve()
    pack_root = out_root / "agent-view"
    if pack_root.exists() and any(pack_root.iterdir()):
        raise ValueError(f"evidence pack output is not empty: {pack_root}")
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
