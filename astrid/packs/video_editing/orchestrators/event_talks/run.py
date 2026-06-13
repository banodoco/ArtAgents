"""Sprint 5b: event_talks orchestrator — plan v2 emission + task gate loop."""


from __future__ import annotations

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('video_editing.event_talks')
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

from astrid.core.foundation.hash import sha256_file
from astrid.core.foundation.project_paths import project_dir, validate_project_slug
from astrid.core.media import ffprobe_duration_seconds
from astrid.core.project.run import (
    finalize_project_run,
    prepare_project_run,
    reject_project_with_out,
)
from astrid.core.task import env as task_env
from astrid.core.task import gate as task_gate
from astrid.packs.video_editing.orchestrators.event_talks.plan_template import (
    build_plan_v2,
    emit_plan_json,
)

# ---------------------------------------------------------------------------
# Constants — preserved from the legacy orchestrator
# ---------------------------------------------------------------------------

ADOS_SUNDAY_SPEAKERS: list[dict[str, str]] = json.loads(
    (Path(__file__).with_name("data") / "ados_sunday_speakers.json").read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fold(text: str) -> str:
    """Lower-case + collapse whitespace for case-insensitive matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _slugify(text: str) -> str:
    """Turn a human-readable string into a URL-ish slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _fmt_time(seconds: float) -> str:
    """Format a float second count as ``HH:MM:SS.mmm``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ---------------------------------------------------------------------------
# Orchestrator-level parser (plan v2, no subcommand)
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the orchestrator-level argument parser.

    When invoked *without* a subcommand, this emits a plan v2 and
    optionally drives the task gate.  When invoked *with* a subcommand
    (e.g. ``ados-sunday-template``) it acts as a step executor called
    by the local adapter.
    """
    parser = argparse.ArgumentParser(
        description="Build and render individual event talk videos from long recordings.",
    )

    # Orchestrator flags
    parser.add_argument(
        "--source",
        help="Source video file path.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--transcript",
        help="Pre-computed transcript JSON path (for search-transcript step).",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output directory for the run.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--project",
        help="Project slug for a persistent project run.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--python-exec",
        help="Python executable for child commands.",
        default=sys.executable,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream subprocess output while logging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit plan.json without executing steps.",
    )

    # Step-level subcommands (used when the local adapter invokes a step)
    subparsers = parser.add_subparsers(dest="command")

    # ados-sunday-template
    tmpl = subparsers.add_parser(
        "ados-sunday-template",
        help="Write the ADOS Paris Sunday speaker template.",
    )
    tmpl.add_argument("--out", type=Path, required=True)

    # search-transcript
    search = subparsers.add_parser(
        "search-transcript",
        help="Search a Whisper JSON transcript for speaker/title phrases.",
    )
    search.add_argument("--transcript", type=Path, required=True)
    search.add_argument("--out", type=Path, required=True)
    search.add_argument("--phrases", nargs="*", default=[])

    # find-holding-screens
    holding = subparsers.add_parser(
        "find-holding-screens",
        help="Sample video frames and OCR likely wait/holding/title-card screens.",
    )
    holding.add_argument("--video", type=Path, required=True)
    holding.add_argument("--out", type=Path, required=True)

    # render
    render = subparsers.add_parser(
        "render",
        help="Render each manifest talk with ADOS intro, lower-third, and outro.",
    )
    render.add_argument("--manifest", type=Path, required=True)
    render.add_argument("--out-dir", type=Path, required=True)
    render.add_argument("--dry-run", action="store_true")

    return parser


def resolve_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parsed = build_parser().parse_args(argv)
    cli_values = vars(parsed)
    merged = dict(cli_values)

    args = argparse.Namespace(**merged)
    args.python_exec = str(getattr(args, "python_exec", sys.executable))
    args.verbose = bool(getattr(args, "verbose", False))
    args.dry_run = bool(getattr(args, "dry_run", False))

    out = getattr(args, "out", None)
    if out is not None:
        args.out = Path(out).expanduser().resolve()

    source = getattr(args, "source", None)
    if source is not None:
        args.source = Path(source).expanduser().resolve()
        if not args.source.exists():
            raise AstridError(
                f"source not found: {args.source}",
                recovery_command="verify the source path and rerun with --source <path>",
            )

    return args


# ---------------------------------------------------------------------------
# Step executors — invoked by the local adapter for each step
# ---------------------------------------------------------------------------


def _exec_ados_sunday_template(args: argparse.Namespace) -> int:
    """Write the static ADOS Sunday speaker template JSON."""
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "event": "ADOS Paris 2026",
        "day": "Sunday",
        "talks": [
            {
                "slug": _slugify(f"{entry['speaker']} {entry['title']}"),
                **entry,
                "source": "",
                "start": None,
                "end": None,
            }
            for entry in ADOS_SUNDAY_SPEAKERS
        ],
    }
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"event_talks: wrote={out}")
    return 0


def _exec_search_transcript(args: argparse.Namespace) -> int:
    """Search a Whisper JSON transcript for speaker/title phrases."""
    transcript: Path = args.transcript
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(transcript.read_text(encoding="utf-8"))
    segments = data.get("segments") or []

    phrases: list[str] = args.phrases or []
    if not phrases:
        phrases = [e["speaker"] for e in ADOS_SUNDAY_SPEAKERS] + [
            e["title"] for e in ADOS_SUNDAY_SPEAKERS
        ]

    compiled = [
        (phrase, re.compile(re.escape(_fold(phrase)), re.IGNORECASE))
        for phrase in phrases
    ]

    found = 0
    lines: list[str] = []
    for segment in segments:
        text = str(segment.get("text") or "")
        folded = _fold(text)
        matches = [phrase for phrase, pattern in compiled if pattern.search(folded)]
        if matches:
            found += 1
            start = float(segment.get("start") or 0.0)
            end = float(segment.get("end") or start)
            lines.append(
                f"{_fmt_time(start)}-{_fmt_time(end)} | "
                f"{', '.join(matches)} | {text.strip()}"
            )
    lines.append(f"matches={found}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"event_talks: wrote={out} matches={found}")
    return 0


def _exec_find_holding_screens(args: argparse.Namespace) -> int:
    """Sample video frames and OCR for holding/title-card screens.

    This is a lightweight port — writes a placeholder manifest when
    ffmpeg/tesseract are unavailable, and does the real work when they
    are.
    """
    import shutil
    import subprocess as sp

    video: Path = args.video
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)

    # When ffmpeg/tesseract aren't available (CI, test envs), emit a
    # minimal placeholder so the pipeline can proceed.
    if shutil.which("ffmpeg") is None or shutil.which("tesseract") is None:
        payload = {
            "video": str(video),
            "sample_sec": 10.0,
            "hits": [],
            "intervals": [],
            "note": "placeholder — ffmpeg/tesseract unavailable",
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"event_talks: placeholder wrote={out}")
        return 0

    # Real implementation
    work_dir = out.parent / f"{out.stem}.frames"
    work_dir.mkdir(parents=True, exist_ok=True)

    duration = ffprobe_duration_seconds(video)
    phrases = ["LUNCH BREAK", "WE'LL BE BACK", "THANK YOU", "BREAK"]
    folded_phrases = [_fold(p) for p in phrases]
    hits: list[dict[str, Any]] = []
    t = 0.0
    sample_sec = 10.0
    while t <= duration:
        frame = work_dir / f"frame_{int(round(t)):06d}.jpg"
        if not frame.is_file():
            sp.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", str(frame),
                ],
                check=True,
            )
        text = sp.run(
            ["tesseract", str(frame), "stdout", "--psm", "6"],
            check=False, capture_output=True, text=True,
        ).stdout.strip()
        folded = _fold(text)
        matched = [p for p, fp in zip(phrases, folded_phrases) if fp in folded]
        if matched:
            hits.append({
                "time": round(t, 3),
                "timecode": _fmt_time(t),
                "matched": matched,
                "text": text,
                "frame": str(frame),
            })
        t += sample_sec

    intervals = _coalesce_hit_intervals(hits, sample_sec)
    payload = {
        "video": str(video),
        "sample_sec": sample_sec,
        "phrases": phrases,
        "hits": hits,
        "intervals": intervals,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"event_talks: wrote={out} hits={len(hits)} intervals={len(intervals)}")
    return 0


def _exec_render_manifest(args: argparse.Namespace) -> int:
    raise NotImplementedError(
        "event_talks.render_manifest: not implemented; see SPRINT_1 milestone D"
    )


def _coalesce_hit_intervals(
    hits: list[dict[str, Any]], threshold: float
) -> list[dict[str, Any]]:
    """Merge adjacent hit timestamps into contiguous intervals."""
    if not hits:
        return []
    sorted_hits = sorted(hits, key=lambda h: h["time"])
    intervals: list[dict[str, Any]] = []
    cur_start = sorted_hits[0]["time"]
    cur_end = cur_start
    cur_matched: set[str] = set(sorted_hits[0]["matched"])

    for hit in sorted_hits[1:]:
        if hit["time"] - cur_end <= threshold * 1.5:
            cur_end = hit["time"]
            cur_matched.update(hit["matched"])
        else:
            intervals.append({
                "start": cur_start,
                "end": cur_end,
                "start_timecode": _fmt_time(cur_start),
                "end_timecode": _fmt_time(cur_end),
                "matched": sorted(cur_matched),
            })
            cur_start = hit["time"]
            cur_end = hit["time"]
            cur_matched = set(hit["matched"])

    intervals.append({
        "start": cur_start,
        "end": cur_end,
        "start_timecode": _fmt_time(cur_start),
        "end_timecode": _fmt_time(cur_end),
        "matched": sorted(cur_matched),
    })
    return intervals


# ---------------------------------------------------------------------------
# Orchestrator run (plan v2 emission + task gate loop)
# ---------------------------------------------------------------------------


def _write_run_json(args: argparse.Namespace) -> None:
    """Write ``run.json`` with ``consumes`` populated from source media."""
    run_json = args.out / "run.json"

    consumes: list[dict[str, str]] = []
    source = getattr(args, "source", None)
    if source is not None and isinstance(source, Path) and source.is_file():
        consumes.append({"source": str(source), "sha256": sha256_file(source)})
    transcript = getattr(args, "transcript", None)
    if transcript is not None and isinstance(transcript, Path) and transcript.is_file():
        consumes.append(
            {"source": str(transcript), "sha256": sha256_file(transcript)}
        )

    fields: dict[str, Any] = {
        "consumes": consumes,
        "orchestrator": "video_editing.event_talks",
    }

    if run_json.exists():
        try:
            existing = json.loads(run_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
        existing.update(fields)
        run_json.write_text(
            json.dumps(existing, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        run_json.parent.mkdir(parents=True, exist_ok=True)
        run_json.write_text(
            json.dumps(fields, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _append_pack_run_started(run_root: Path) -> None:
    """Append a pack-local audit event.

    This log is intentionally not the task-run ``events.jsonl`` ledger. Canonical
    task-run events are written through the task gate's WriterContext.
    """
    events_path = run_root / "pack_events.jsonl"
    ev: dict[str, Any] = {
        "kind": "pack_run_started",
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev, sort_keys=True, separators=(",", ":")) + "\n")


def run_orchestrator(args: argparse.Namespace) -> int:
    """Emit plan v2, write run.json, and execute via task gate."""
    args.out.mkdir(parents=True, exist_ok=True)

    # 1. Emit plan v2
    project_slug = getattr(args, "project", None)
    if project_slug is not None:
        proj_root = project_dir(project_slug)
        plan_path = proj_root / "plan.json"
    else:
        plan_path = args.out / "plan.json"

    plan = build_plan_v2(
        python_exec=args.python_exec,
        run_root=args.out,
        source=getattr(args, "source", None),
    )
    emit_plan_json(plan, plan_path)

    # 2. Compute plan hash
    from astrid.core.task.plan import compute_plan_hash

    plan_hash = compute_plan_hash(plan_path)

    # 3. Write run.json with consumes
    _write_run_json(args)

    # 4. Append pack-local audit event
    _append_pack_run_started(args.out)

    if args.dry_run:
        print(f"event_talks: plan emitted to {plan_path} (plan_hash={plan_hash})")
        return 0

    # 5. Execute through task gate
    if project_slug is None:
        raise AstridError(
            "task-gate execution requires --project",
            recovery_command="rerun with --project <slug> to enable task-gate execution",
        )

    slug = validate_project_slug(project_slug)
    return _execute_via_task_gate(slug, args)


def _execute_via_task_gate(slug: str, args: argparse.Namespace) -> int:
    """Advance through the task-gate plan by peeking at each step, dispatching
    via ``gate_command`` with the step's rendered canonical command, and
    waiting for the dispatched subprocess to complete.

    Every dispatched step is a local-adapter subprocess that re-enters the
    task gate through ``_run_step_subcommand``, which calls
    ``record_dispatch_complete`` so the gate sees step completion on the
    next iteration.
    """
    import os
    import time

    from astrid.core.foundation.project_paths import project_dir
    from astrid.core.session.current_run_state import read_current_run_state
    from astrid.core.command_render import render_task_command
    from astrid.core.events import read_events
    from astrid.core.task.gate import peek_current_step
    from astrid.core.task.plan import load_plan
    from astrid.core.task.plan.verbs import apply_mutations

    active_run = read_current_run_state(slug)
    if active_run is None:
        raise AstridError(
            f"no active run found for project {slug!r}",
            recovery_command=f"astrid start --engine arnold --from-plan plan.json --project {slug}",
        )

    run_id: str = active_run["run_id"]
    proj_root = project_dir(slug)
    events_path = proj_root / "runs" / run_id / "events.jsonl"

    while True:
        events = read_events(events_path)
        base_plan = load_plan(proj_root / "plan.json")
        plan = apply_mutations(base_plan, events)

        peek = peek_current_step(
            plan, events, slug,
            project_root=proj_root,
            run_id=run_id,
        )

        if peek.exhausted:
            return 0

        step = peek.step
        path_tuple = peek.path_tuple

        # Render the step's canonical command so it matches the
        # task-gate's own rendering (same produces_root / step_dir).
        rendered = render_task_command(
            step,
            slug=slug,
            run_id=run_id,
            project_root=proj_root,
            plan_step_path=path_tuple,
            iteration=peek.iteration,
            item_id=peek.item_id,
        )

        try:
            decision = task_gate.gate_command(
                slug,
                rendered.canonical_command,
                list(rendered.canonical_argv),
                reentry=True,
            )
        except task_gate.TaskRunGateError as exc:
            raise AstridError(
                str(exc),
                recovery_command=getattr(exc, "recovery", "check project state and retry"),
            ) from exc

        if not decision.active:
            return 0

        # The local adapter has spawned a subprocess.  Wait for it to
        # exit so the reentry path can write step_completed before we
        # peek at the next step.
        if decision.pid:
            print(
                f"event_talks: waiting for pid={decision.pid} "
                f"(step={step.id})",
                flush=True,
            )
            while True:
                try:
                    os.kill(decision.pid, 0)
                    time.sleep(0.5)
                except (ProcessLookupError, OSError):
                    break
        else:
            # No PID means the adapter handled the step inline (e.g.
            # a no-op or an already-satisfied produces check).  Give
            # the filesystem a moment to settle.
            time.sleep(0.1)

    return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _run_step_subcommand(
    *,
    effective_argv: list[str],
    args: argparse.Namespace,
    runner: Callable[[argparse.Namespace], int],
) -> int:
    """Run one local-adapter step, recording task-gate completion in task mode."""
    slug = task_env.task_project_env()
    decision = None
    if slug is not None and task_env.is_in_task_run(slug):
        try:
            decision = task_gate.gate_command(
                slug,
                task_gate.command_for_argv(
                    ["python3", "-m", "astrid.packs.video_editing.orchestrators.event_talks.run", *effective_argv]
                ),
                effective_argv,
                reentry=True,
            )
        except task_gate.TaskRunGateError as exc:
            raise AstridError(
                str(exc),
                recovery_command=getattr(exc, "recovery", "check project state and retry"),
            ) from exc

    returncode = runner(args)
    if decision is not None:
        task_gate.record_dispatch_complete(decision, returncode)
    return returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for the event_talks orchestrator.

    Two modes:

    1. **Step executor** — when a subcommand is present (e.g.
       ``ados-sunday-template``), execute that step directly.  This
       is the path taken by the local adapter.

    2. **Orchestrator** — when no subcommand is given, emit a plan v2
       and optionally drive the task gate loop.
    """
    effective_argv = list(sys.argv[1:] if argv is None else argv)

    # Fast-path: detect a step-execution subcommand before any
    # project/gate setup, so the local adapter can invoke steps
    # without session/project context.
    step_commands = {
        "ados-sunday-template",
        "search-transcript",
        "find-holding-screens",
        "render",
    }
    if effective_argv and effective_argv[0] in step_commands:
        args = build_parser().parse_args(effective_argv)
        cmd = args.command
        if cmd == "ados-sunday-template":
            return _run_step_subcommand(
                effective_argv=effective_argv,
                args=args,
                runner=_exec_ados_sunday_template,
            )
        if cmd == "search-transcript":
            return _run_step_subcommand(
                effective_argv=effective_argv,
                args=args,
                runner=_exec_search_transcript,
            )
        if cmd == "find-holding-screens":
            return _run_step_subcommand(
                effective_argv=effective_argv,
                args=args,
                runner=_exec_find_holding_screens,
            )
        if cmd == "render":
            return _run_step_subcommand(
                effective_argv=effective_argv,
                args=args,
                runner=_exec_render_manifest,
            )
        # Should not reach here — subparser dispatch guarantees `command`
        raise AstridError(
            f"unknown subcommand: {cmd}",
            recovery_command="use one of: ados-sunday-template, search-transcript, find-holding-screens, render",
        )

    # Orchestrator path — full project/gate setup
    project_context = None

    try:
        # Pre-parse for project slug
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument("--project")
        pre_parser.add_argument("--out")
        parsed, _unknown = pre_parser.parse_known_args(effective_argv)

        if parsed.project and task_env.is_in_task_run(parsed.project):
            try:
                task_gate.gate_command(
                    parsed.project,
                    task_gate.command_for_argv(
                        ["python3", "-m", "astrid", "event_talks", *effective_argv]
                    ),
                    effective_argv,
                    reentry=True,
                )
            except task_gate.TaskRunGateError as exc:
                raise AstridError(
                    str(exc),
                    recovery_command=getattr(exc, "recovery", "check project state and retry"),
                ) from exc

        # Prepare project run if --project is set
        if parsed.project:
            reject_project_with_out(parsed.project, parsed.out)
            project_context = prepare_project_run(
                parsed.project,
                tool_id="video_editing.event_talks",
                kind="orchestrator",
                argv=["event_talks", *effective_argv],
                metadata={"entrypoint": "direct"},
            )
            effective_argv = [*effective_argv, "--out", str(project_context.run_root)]

        args = resolve_args(effective_argv)
        if project_context is not None:
            args.project = project_context.project_slug

        returncode = run_orchestrator(args)

        if project_context is not None:
            finalize_project_run(
                project_context,
                status="success" if returncode == 0 else "failed",
                returncode=returncode,
                metadata={"dry_run": args.dry_run},
            )

        return returncode
    except SystemExit as exc:
        if project_context is not None:
            finalize_project_run(
                project_context,
                status="error",
                returncode=exc.code if isinstance(exc.code, int) else 1,
                error=exc,
            )
        if isinstance(exc.code, int):
            return exc.code
        return 1
    except Exception as exc:
        if project_context is not None:
            finalize_project_run(
                project_context,
                status="error",
                returncode=-1,
                error=exc,
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
