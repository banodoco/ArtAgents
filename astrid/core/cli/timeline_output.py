"""Timeline cost and export command handlers and helpers.

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
Contains ``cmd_export``, ``cmd_cost``, and their shared helper functions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.foundation.project_paths import project_dir
from astrid.core.task.events import read_events
from astrid.core.task.run.audit import _cost_by_source, _run_status

from astrid.core.timeline import crud


# ---------------------------------------------------------------------------
# Handler: export (Sprint 5b)
# ---------------------------------------------------------------------------


def cmd_export(args: argparse.Namespace) -> int:
    """Export a timeline as a self-contained tarball bundle."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    data = crud.show_timeline(session.project, args.slug)
    if data is None:
        raise AstridError(
            f"timeline '{args.slug}' not found",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        )

    ulid = data["ulid"]
    manifest = data["manifest"]
    proj_root = project_dir(session.project)
    timelines_dir = proj_root / "timelines" / ulid
    runs_dir = proj_root / "runs"

    include_aborted = bool(getattr(args, "include_aborted", False))
    out_path = Path(args.out).expanduser().resolve()

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        manifest_entries: list[tuple[str, str]] = []

        def _add_file(src: Path, rel: str) -> None:
            dst = tmpdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            sha = hashlib.sha256(dst.read_bytes()).hexdigest()
            manifest_entries.append((rel, sha))

        def _add_bytes(data: bytes, rel: str) -> None:
            dst = tmpdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            manifest_entries.append((rel, sha))

        # Repair assembly.json from the event log before export (ensures the
        # exported tarball carries the current projected state even when the
        # on-disk compatibility file is stale).
        from astrid.core.timeline.paths import load_assembly_json_with_repair

        load_assembly_json_with_repair(timelines_dir)

        # Copy timeline container files
        for name in ("assembly.json", "manifest.json", "display.json"):
            src = timelines_dir / name
            if src.is_file():
                _add_file(src, name)

        # Copy contributing runs
        for run_id in _timeline_contributing_runs(proj_root, manifest.contributing_runs, include_aborted=include_aborted):
            run_root = runs_dir / run_id
            if not run_root.is_dir():
                continue

            # Copy the run's own plan snapshot. Older runs may only have the
            # initial plan embedded in events.jsonl; export that snapshot
            # rather than the mutable project-level plan cache.
            plan_path = run_root / "plan.json"
            if plan_path.is_file():
                _add_file(plan_path, f"runs/{run_id}/plan.json")
            else:
                plan_payload = _run_initial_plan_payload(run_root / "events.jsonl")
                if plan_payload is not None:
                    data = json.dumps(
                        plan_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    _add_bytes(
                        data,
                        f"runs/{run_id}/plan.json",
                    )

            # Copy events.jsonl
            events_path = run_root / "events.jsonl"
            if events_path.is_file():
                _add_file(events_path, f"runs/{run_id}/events.jsonl")

            # Copy produces/ tree
            produces_root = run_root / "produces"
            if produces_root.is_dir():
                for src_file in produces_root.rglob("*"):
                    if src_file.is_file():
                        rel = str(Path("runs") / run_id / "produces" / src_file.relative_to(produces_root))
                        _add_file(src_file, rel)

            # Copy run.json if present
            run_json = run_root / "run.json"
            if run_json.is_file():
                _add_file(run_json, f"runs/{run_id}/run.json")

        # Write MANIFEST.txt
        manifest_txt = tmpdir / "MANIFEST.txt"
        lines = [f"{sha}  {rel}" for rel, sha in sorted(manifest_entries)]
        manifest_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Build tarball
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out_path, "w:gz") as tar:
            for member in sorted(tmpdir.iterdir()):
                tar.add(member, arcname=member.name)

    print(f"exported timeline '{args.slug}' to {out_path}")
    return 0


def _run_initial_plan_payload(events_path: Path) -> dict[str, object] | None:
    if not events_path.is_file():
        return None
    from astrid.core.task.events import read_events

    for event in read_events(events_path):
        if event.get("kind") == "plan_initialized" and isinstance(
            event.get("plan"), dict
        ):
            return event["plan"]
    return None


# ---------------------------------------------------------------------------
# Handler: cost (Sprint 5b)
# ---------------------------------------------------------------------------


def cmd_cost(args: argparse.Namespace) -> int:
    """Aggregate cost across all contributing runs in a timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    data = crud.show_timeline(session.project, args.slug)
    if data is None:
        raise AstridError(
            f"timeline '{args.slug}' not found",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        )

    manifest = data["manifest"]
    proj_root = project_dir(session.project)
    runs_dir = proj_root / "runs"
    include_aborted = bool(getattr(args, "include_aborted", False))

    # Aggregate costs across all contributing runs
    by_source: dict[str, dict[str, Any]] = {}
    grand_total = 0.0
    run_ids = _timeline_contributing_runs(
        proj_root,
        manifest.contributing_runs,
        include_aborted=include_aborted,
    )

    for run_id in run_ids:
        events_path = runs_dir / run_id / "events.jsonl"
        events = read_events(events_path)
        cost_summary = _cost_by_source(events)
        grand_total += _merge_cost_summaries(by_source, cost_summary)

    json_out = bool(getattr(args, "json_out", False))
    if json_out:
        payload: dict[str, Any] = {
            "slug": args.slug,
            "project": session.project,
            "contributing_runs": len(run_ids),
            "total_runs_in_manifest": len(manifest.contributing_runs),
            "include_aborted": include_aborted,
            "grand_total": round(grand_total, 6),
            "by_source": by_source,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Cost rollup for timeline '{args.slug}' ({len(run_ids)} contributing runs):")
    print()
    if not by_source:
        print("  (no cost data)")
    else:
        for source in sorted(by_source):
            amt = float(by_source[source].get("amount", 0.0))
            print(f"  {source:<20} ${amt:>10.4f}")
    print(f"  {'─' * 32}")
    print(f"  {'TOTAL':<20} ${grand_total:>10.4f}")
    return 0


def _timeline_contributing_runs(
    proj_root: Path,
    run_ids: list[str] | tuple[str, ...],
    *,
    include_aborted: bool,
) -> list[str]:
    runs_dir = proj_root / "runs"
    selected: list[str] = []
    seen: set[str] = set()
    for run_id in run_ids:
        if run_id in seen:
            continue
        seen.add(run_id)
        run_root = runs_dir / run_id
        if not run_root.is_dir():
            continue
        events_path = run_root / "events.jsonl"
        if events_path.exists():
            events = read_events(events_path)
            if _run_status(events) == "aborted" and not include_aborted:
                continue
        selected.append(run_id)
    return selected


def _merge_cost_summaries(
    target: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> float:
    added_total = 0.0
    for source, info in incoming.items():
        if not isinstance(info, dict):
            continue
        amount = float(info.get("amount", 0.0))
        currency = str(info.get("currency", "USD"))
        bucket = target.setdefault(
            source,
            {"amount": 0.0, "currency": currency, "source": source},
        )
        bucket["amount"] = round(float(bucket.get("amount", 0.0)) + amount, 6)
        bucket["currency"] = currency
        bucket["source"] = source
        added_total += amount
    return added_total
