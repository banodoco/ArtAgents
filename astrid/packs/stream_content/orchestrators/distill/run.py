#!/usr/bin/env python3
"""Distill long stream recordings into reviewable content."""

from __future__ import annotations

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.entrypoint import guard_canonical_entrypoint, run_pack_main

guard_canonical_entrypoint("stream_content.distill")
import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from astrid.packs.stream_content.orchestrators.distill.plan_template import (
    build_plan_v2,
    compute_plan_hash,
    emit_plan_json,
)

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Stream Content Review - {video_name}</title>
  <style>
    :root {{
      --bg: #101113;
      --fg: #eeeeef;
      --muted: #a7a9ad;
      --panel: #1a1c20;
      --border: #31343a;
      --accent: #69b56f;
      --warn: #e0b154;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 24px; background: var(--bg); color: var(--fg);
            font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    h1 {{ margin: 0 0 4px; font-size: 22px; font-weight: 650; }}
    h2 {{ margin: 28px 0 10px; font-size: 16px; font-weight: 650; }}
    a {{ color: var(--accent); }}
    .meta {{ color: var(--muted); margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--border); }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 600; }}
    tr:last-child td {{ border-bottom: 0; }}
    .kind {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .score {{ color: var(--warn); font-variant-numeric: tabular-nums; }}
    .candidates {{ display: grid; gap: 14px; }}
    .candidate {{ display: grid; grid-template-columns: minmax(260px, 380px) 1fr; gap: 14px;
                  padding: 12px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }}
    video {{ width: 100%; max-height: 230px; background: #000; border-radius: 4px; display: block; }}
    .text {{ margin: 6px 0 8px; }}
    .reasons {{ color: var(--muted); font-size: 12px; }}
    @media (max-width: 760px) {{
      body {{ padding: 16px; }}
      .candidate {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <h1>Stream Content Review - {video_name}</h1>
  <div class="meta">{duration} total - {segment_count} mapped segments - {candidate_count} candidates</div>
  <h2>Segments</h2>
  <table>
    <thead><tr><th>#</th><th>Time</th><th>Kind</th><th>Label</th><th>Duration</th><th>File</th></tr></thead>
    <tbody>{segment_rows}</tbody>
  </table>
  <h2>Candidates</h2>
  <div class="candidates">{candidate_cards}</div>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Distill a long stream/event recording into reviewable content.")
    parser.add_argument("--video", type=Path, help="Source stream recording.")
    parser.add_argument("--transcript", type=Path, help="Existing transcript.json; skips transcription.")
    parser.add_argument("--brief", type=Path, help="Optional markdown brief for clip scoring.")
    parser.add_argument("--out", type=Path, help="Output directory for the run.")
    parser.add_argument("--python-exec", default=sys.executable, help="Python executable for child commands.")
    parser.add_argument("--no-scenes", action="store_true", help="Skip editorial.scenes.")
    parser.add_argument("--dry-run", action="store_true", help="Write plan.json without executing steps.")

    subparsers = parser.add_subparsers(dest="command")
    extract = subparsers.add_parser("extract-segments", help="Extract content/screening segments from a segment map.")
    extract.add_argument("--video", type=Path, required=True)
    extract.add_argument("--segment-map", type=Path, required=True)
    extract.add_argument("--out-dir", type=Path, required=True)
    extract.add_argument("--manifest", type=Path, required=True)
    extract.add_argument("--dry-run", action="store_true")
    extract.add_argument("--python-exec", default=sys.executable)

    review = subparsers.add_parser("review", help="Render a static review.html page.")
    review.add_argument("--video", type=Path, required=True)
    review.add_argument("--segment-map", type=Path, required=True)
    review.add_argument("--candidates", type=Path, required=True)
    review.add_argument("--segments-manifest", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)

    return parser


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["ASTRID_INTERNAL_INVOCATION"] = "1"
    return env


def _run_subprocess(cmd: list[str], *, label: str) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_child_env())
    if proc.returncode != 0:
        raise AstridError(
            f"[stream_content.distill] {label} failed (exit {proc.returncode})",
            recovery_command=f"check the child command and rerun: {' '.join(cmd)}",
            state_snapshot={"stdout": proc.stdout, "stderr": proc.stderr, "command": " ".join(cmd)},
        )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    return proc.stdout


def _slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:70].strip("-") or fallback)


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _relpath(target: Path, base: Path) -> str:
    try:
        return os.path.relpath(target, base)
    except ValueError:
        return str(target)


def build_extract_manifest(
    *,
    video: Path,
    segment_map: Path,
    out_dir: Path,
    manifest: Path,
    python_exec: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    payload = json.loads(segment_map.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[dict[str, Any]] = []
    content_index = 1
    for segment in payload.get("segments", []):
        if segment.get("kind") not in {"content", "screening"}:
            continue
        start = float(segment["start"])
        end = float(segment["end"])
        dur = max(0.0, end - start)
        if dur <= 0.5:
            continue
        slug = _slugify(str(segment.get("label") or segment.get("kind") or ""), f"segment-{content_index:03d}")
        rel = Path(f"{content_index:03d}-{slug}.mp4")
        out_file = out_dir / rel
        if not dry_run:
            _run_subprocess(
                [
                    python_exec,
                    "-m",
                    "astrid.packs.media.executors.clip_extract.run",
                    "--input",
                    str(video),
                    "--start",
                    f"{start:.3f}",
                    "--dur",
                    f"{dur:.3f}",
                    "--output",
                    str(out_file),
                ],
                label=f"clip_extract({rel})",
            )
        extracted.append(
            {
                "index": content_index,
                "kind": segment.get("kind"),
                "label": segment.get("label", ""),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(dur, 3),
                "file": str(rel),
                "path": str(out_file),
            }
        )
        content_index += 1
    result = {"version": 1, "source": str(video), "segments": extracted}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"stream_content.distill: wrote={manifest} extracted={len(extracted)}")
    return result


def render_review(
    *,
    video: Path,
    segment_map: Path,
    candidates: Path,
    segments_manifest: Path,
    out: Path,
) -> None:
    segment_payload = json.loads(segment_map.read_text(encoding="utf-8"))
    candidate_payload = json.loads(candidates.read_text(encoding="utf-8"))
    extracted_payload = json.loads(segments_manifest.read_text(encoding="utf-8"))
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    extracted = list(extracted_payload.get("segments", []))
    extracted_by_key = {(round(float(item["start"]), 3), round(float(item["end"]), 3)): item for item in extracted}

    rows: list[str] = []
    for index, segment in enumerate(segment_payload.get("segments", []), start=1):
        start = float(segment["start"])
        end = float(segment["end"])
        extracted_item = extracted_by_key.get((round(start, 3), round(end, 3)))
        link = ""
        if extracted_item:
            href = html.escape(_relpath((segments_manifest.parent / extracted_item["file"]).resolve(), out.parent))
            link = f'<a href="{href}">{html.escape(str(extracted_item["file"]))}</a>'
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(_fmt_time(start))}-{html.escape(_fmt_time(end))}</td>"
            f"<td class=\"kind\">{html.escape(str(segment.get('kind', '')))}</td>"
            f"<td>{html.escape(str(segment.get('label', '')))}</td>"
            f"<td>{end - start:.1f}s</td>"
            f"<td>{link}</td>"
            "</tr>"
        )

    cards: list[str] = []
    for candidate in candidate_payload.get("candidates", []):
        cstart = float(candidate["start"])
        clip_src = _candidate_video_src(video, cstart, extracted, out.parent)
        reasons = ", ".join(str(reason) for reason in candidate.get("reasons", []))
        cards.append(
            '<section class="candidate">'
            f'<video src="{html.escape(clip_src)}" controls preload="metadata"></video>'
            "<div>"
            f'<div><span class="score">{float(candidate.get("score", 0.0)):.3f}</span> '
            f'{html.escape(_fmt_time(cstart))}-{html.escape(_fmt_time(float(candidate["end"])))} '
            f'{html.escape(str(candidate.get("segment_label", "")))}</div>'
            f'<div class="text">{html.escape(str(candidate.get("text", "")))}</div>'
            f'<div class="reasons">{html.escape(reasons)}</div>'
            "</div></section>"
        )

    page = PAGE_TEMPLATE.format(
        video_name=html.escape(video.name),
        duration=html.escape(_fmt_time(float(segment_payload.get("duration", 0.0)))),
        segment_count=len(segment_payload.get("segments", [])),
        candidate_count=len(candidate_payload.get("candidates", [])),
        segment_rows="\n".join(rows),
        candidate_cards="\n".join(cards) or "<p>No candidates produced.</p>",
    )
    out.write_text(page, encoding="utf-8")
    print(f"stream_content.distill: wrote={out}")


def _candidate_video_src(video: Path, start: float, extracted: list[dict[str, Any]], page_dir: Path) -> str:
    for segment in extracted:
        s = float(segment["start"])
        e = float(segment["end"])
        if s <= start < e:
            local = max(0.0, start - s)
            target = (Path(str(segment["path"]))).resolve()
            return f"{_relpath(target, page_dir)}#t={local:.3f}"
    return f"{_relpath(video.resolve(), page_dir)}#t={start:.3f}"


def run_full(args: argparse.Namespace) -> int:
    if args.video is None or args.out is None:
        raise AstridError("--video and --out are required", recovery_command="rerun with --video <file> --out <dir>")
    video = args.video.expanduser().resolve()
    if not video.is_file():
        raise AstridError(f"video not found: {video}", recovery_command="rerun with an existing --video file")
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    transcript = args.transcript.expanduser().resolve() if args.transcript else None
    if transcript is not None and not transcript.is_file():
        raise AstridError(f"transcript not found: {transcript}", recovery_command="rerun with an existing --transcript file")
    brief = args.brief.expanduser().resolve() if args.brief else None
    if brief is not None and not brief.is_file():
        raise AstridError(f"brief not found: {brief}", recovery_command="rerun with an existing --brief file")

    plan = build_plan_v2(
        python_exec=args.python_exec,
        run_root=out,
        video=video,
        transcript=transcript,
        brief=brief,
        include_scenes=not args.no_scenes,
    )
    plan_path = out / "plan.json"
    emit_plan_json(plan, plan_path)
    plan_hash = compute_plan_hash(plan_path)
    (out / "run.json").write_text(
        json.dumps(
            {
                "orchestrator": "stream_content.distill",
                "video": str(video),
                "transcript": str(transcript) if transcript else None,
                "brief": str(brief) if brief else None,
                "plan_hash": plan_hash,
                "authority": "local",
                "note": "non-authority local orchestrator metadata; kernel is status authority",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if args.dry_run:
        print(f"stream_content.distill: plan emitted to {plan_path} (plan_hash={plan_hash})")
        return 0
    transcript_path = transcript or (out / "transcript.json")
    if transcript is None:
        _run_subprocess(
            [
                args.python_exec,
                "-m",
                "astrid.packs.editorial.executors.transcribe.run",
                "--audio",
                str(video),
                "--out",
                str(out),
            ],
            label="editorial.transcribe",
        )

    scenes_path: Path | None = None
    if not args.no_scenes:
        scenes_path = out / "scenes.json"
        _run_subprocess(
            [
                args.python_exec,
                "-m",
                "astrid.packs.editorial.executors.scenes.run",
                "--video",
                str(video),
                "--out",
                str(scenes_path),
            ],
            label="editorial.scenes",
        )

    segment_map_path = out / "segment_map.json"
    cmd = [
        args.python_exec,
        "-m",
        "astrid.packs.stream_content.executors.segment_map.run",
        "--video",
        str(video),
        "--transcript",
        str(transcript_path),
        "--out",
        str(segment_map_path),
    ]
    if scenes_path is not None:
        cmd += ["--scenes", str(scenes_path)]
    _run_subprocess(cmd, label="stream_content.segment_map")

    segments_manifest = out / "segments" / "segments.json"
    build_extract_manifest(
        video=video,
        segment_map=segment_map_path,
        out_dir=out / "segments",
        manifest=segments_manifest,
        python_exec=args.python_exec,
    )

    candidates_path = out / "candidates.json"
    cmd = [
        args.python_exec,
        "-m",
        "astrid.packs.stream_content.executors.clip_candidates.run",
        "--transcript",
        str(transcript_path),
        "--segment-map",
        str(segment_map_path),
        "--out",
        str(candidates_path),
    ]
    if brief is not None:
        cmd += ["--brief", str(brief)]
    _run_subprocess(cmd, label="stream_content.clip_candidates")

    render_review(
        video=video,
        segment_map=segment_map_path,
        candidates=candidates_path,
        segments_manifest=segments_manifest,
        out=out / "review.html",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    def _run() -> int:
        args = build_parser().parse_args(argv)
        if args.command == "extract-segments":
            build_extract_manifest(
                video=args.video.expanduser().resolve(),
                segment_map=args.segment_map.expanduser().resolve(),
                out_dir=args.out_dir.expanduser().resolve(),
                manifest=args.manifest.expanduser().resolve(),
                python_exec=args.python_exec,
                dry_run=args.dry_run,
            )
            return 0
        if args.command == "review":
            render_review(
                video=args.video.expanduser().resolve(),
                segment_map=args.segment_map.expanduser().resolve(),
                candidates=args.candidates.expanduser().resolve(),
                segments_manifest=args.segments_manifest.expanduser().resolve(),
                out=args.out.expanduser().resolve(),
            )
            return 0
        return run_full(args)

    return run_pack_main("stream_content.distill", _run, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())

