"""Per-run audit verbs: show / artifacts / trace / cost (Sprint 5a)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

from astrid.core.contracts.run_status import RunStatus
from astrid.core.project.paths import project_dir, validate_project_slug
from astrid.core.task.events import canonical_event_json, read_events, verify_chain
from astrid.core.task.operator_render import _path_tuple_from_event
from astrid.core.task.plan import load_plan
from astrid.core.task.plan_verbs import (
    PLAN_MUTATED_KIND,
    apply_mutations,
    initial_plan_from_events,
    initial_plan_hash_from_events,
)


def cmd_run_show(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Pretty-print a run summary; ``--json`` for structured output."""
    parser = argparse.ArgumentParser(prog="astrid runs show", add_help=True)
    parser.add_argument("run_id", help="run identifier")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--json", dest="json_out", action="store_true", help="emit JSON instead of pretty-print")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"run show: {exc}", file=sys.stderr)
        return 1

    proj_root = project_dir(slug, root=projects_root)
    run_root = proj_root / "runs" / args.run_id
    if not run_root.is_dir():
        print(f"run show: run {args.run_id!r} not found in project {slug!r}", file=sys.stderr)
        return 1

    events_path = run_root / "events.jsonl"
    plan_path = proj_root / "plan.json"
    run_json_path = run_root / "run.json"

    events = read_events(events_path) if events_path.exists() else []
    run_json = _read_run_json(run_json_path)
    cached_plan = load_plan(plan_path) if plan_path.exists() else None
    plan = apply_mutations(cached_plan, events) if cached_plan is not None else initial_plan_from_events(events)

    # Run status
    run_status = _run_status(events) if events_path.exists() else _run_status_from_record(run_json)

    # Plan info
    plan_hash_val = initial_plan_hash_from_events(events) or "unknown"
    initial_steps = len(plan.steps) if plan else 0
    mutation_count = sum(1 for e in events if e.get("kind") in {"plan_mutated"})
    skipped_steps = sum(
        1 for e in events if e.get("kind") in {"step_skipped", "item_skipped"}
    )

    # Step list
    step_rows = _build_step_rows(events, run_root)

    # Cost
    cost_summary = _cost_by_source(events)

    # Acks
    ack_count = sum(1 for e in events if e.get("kind") == "step_attested")
    attested_decisions = sum(1 for e in events if e.get("kind") in {"step_attested", "item_attested"})

    # Consumes
    consumes: list[dict[str, Any]] = []
    consumes = run_json.get("consumes", [])

    # Timestamps
    started_ts = ""
    completed_ts = ""
    for e in events:
        if e.get("kind") == "run_started":
            started_ts = str(e.get("ts", ""))
        if e.get("kind") == "run_completed":
            completed_ts = str(e.get("ts", ""))

    total_cost = sum(c.get("amount", 0) for c in cost_summary.values() if isinstance(c, dict))

    if args.json_out:
        payload: dict[str, Any] = {
            "run_id": args.run_id,
            "status": run_status,
            "project": slug,
            "started": started_ts,
            "completed": completed_ts or None,
            "plan_hash": plan_hash_val,
            "initial_steps": initial_steps,
            "mutations": mutation_count,
            "skipped_steps": skipped_steps,
            "effective_steps": len(step_rows),
            "total_cost": total_cost,
            "cost_by_source": cost_summary,
            "ack_count": ack_count,
            "attested_decisions": attested_decisions,
            "consumes": consumes,
            "steps": step_rows,
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    # Pretty-print
    print(f"Run {args.run_id} [{run_status}]")
    print(f"Project: {slug}")
    started_label = f"Started: {started_ts}" if started_ts else "Started: (unknown)"
    if completed_ts:
        print(f"{started_label}  Completed: {completed_ts}")
    else:
        print(f"{started_label}  In-flight")
    cost_line = f"Cost: ${total_cost:.2f}"
    if cost_summary:
        cost_line += "  (" + ", ".join(f"{s}: ${c.get('amount', 0):.2f}" for s, c in cost_summary.items() if isinstance(c, dict)) + ")"
    print(cost_line)
    print()
    print(f"Initial plan: {initial_steps} steps, plan_hash={plan_hash_val}")
    effective_label = f"Effective plan: {len(step_rows)} steps"
    if mutation_count:
        effective_label += f" after {mutation_count} mutations"
    print(effective_label)
    print()
    if step_rows:
        print("Steps (path, version, state, cost):")
        for sr in step_rows:
            sid = sr.get("step_id", "?")
            ver = sr.get("version", 1)
            state = sr.get("state", "?")
            cost_amount = sr.get("cost")
            cost_str = f"${cost_amount:.2f}" if isinstance(cost_amount, (int, float)) else "-"
            extras = sr.get("extras", "")
            print(f"  {sid:30s} v{ver:<3d} {state:20s} {cost_str:>8s}  {extras}")
    else:
        print("Steps: (none)")
    print()
    print(f"Acks: {ack_count} events; {attested_decisions} attested decisions")
    if skipped_steps:
        print(f"Skipped: {skipped_steps} step/item skip events")
    if consumes:
        print(f"Consumes: {len(consumes)} input dependencies")
        for c in consumes:
            src = c.get("source", "?")
            sha = c.get("sha256", "")[:16] if c.get("sha256") else "-"
            print(f"  {src}  sha256={sha}...")
    return 0


def cmd_run_artifacts(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Flat tabular list of artifacts produced by a run."""
    parser = argparse.ArgumentParser(prog="astrid runs artifacts", add_help=True)
    parser.add_argument("run_id", help="run identifier")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--step", dest="step_filter", default=None, help="filter by step id")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"run artifacts: {exc}", file=sys.stderr)
        return 1

    proj_root = project_dir(slug, root=projects_root)
    run_root = proj_root / "runs" / args.run_id
    if not run_root.is_dir():
        print(f"run artifacts: run {args.run_id!r} not found", file=sys.stderr)
        return 1

    steps_root = run_root / "steps"
    if not steps_root.is_dir():
        return 0

    header = f"{'step_id':30s} {'ver':>4s} {'iter':>6s} {'item':>10s} {'name':>20s} {'path':>40s} {'check':>12s} {'sha256':>18s} {'cost':>10s}"
    print(header)

    for step_path, vdir in _iter_step_version_dirs(steps_root):
        if args.step_filter and not _step_filter_matches(step_path, args.step_filter):
            continue
        version = vdir.name[1:]  # strip 'v'
        step_label = "/".join(step_path)
        _emit_artifact_rows(vdir, step_label, version, "")
        for sub in [vdir / "iterations", vdir / "items"]:
            if sub.is_dir():
                for child in sorted(sub.iterdir()):
                    if child.is_dir():
                        label = child.name
                        _emit_artifact_rows(child, step_label, version, label)
    return 0


def _emit_artifact_rows(adir: Path, step_id: str, version: str, sub_label: str) -> None:
    """Print artifact rows for a single step version directory."""
    produces_dir = adir / "produces"
    if not produces_dir.is_dir():
        return
    remote_state_path = adir / "remote_state.json"
    declared: dict[str, str] = {}
    missing: set[str] = set()
    mismatched: set[str] = set()
    if remote_state_path.exists():
        try:
            state = json.loads(remote_state_path.read_text(encoding="utf-8"))
            declared = state.get("manifest", {})
            if isinstance(declared, dict):
                declared = {k: v for k, v in declared.items() if isinstance(v, str)}
            else:
                declared = {}
            missing = set(state.get("missing", []))
            mismatched = set(state.get("mismatched", []))
        except (json.JSONDecodeError, OSError):
            pass

    # Walk produces directory for artifact files (skip subdirs like cost.json)
    for art_path in sorted(produces_dir.rglob("*")):
        if art_path.is_dir():
            continue
        if art_path.name == "cost.json":
            continue
        rel = art_path.relative_to(produces_dir)
        name = str(rel)
        short_path = str(rel)
        check_status = "ok"
        if name in missing:
            check_status = "missing"
        elif name in mismatched:
            check_status = "mismatched"
        sha256_val = ""
        try:
            import hashlib
            sha256_val = hashlib.sha256(art_path.read_bytes()).hexdigest()[:16]
        except OSError:
            sha256_val = "unreadable"

        cost_str = "-"
        cost_path = produces_dir / "cost.json"
        if cost_path.exists():
            try:
                cost_data = json.loads(cost_path.read_text(encoding="utf-8"))
                amount = cost_data.get("amount")
                if isinstance(amount, (int, float)):
                    cost_str = f"${amount:.2f}"
            except (json.JSONDecodeError, OSError):
                pass

        iter_label = sub_label if adir.parent and adir.parent.name == "iterations" else ""
        item_label = sub_label if adir.parent and adir.parent.name == "items" else ""
        print(
            f"{step_id:30s} {version:>4s} {iter_label:>6s} {item_label:>10s} "
            f"{name:20s} {short_path:40s} {check_status:>12s} {sha256_val:>18s} {cost_str:>10s}"
        )


def _iter_step_version_dirs(steps_root: Path) -> list[tuple[tuple[str, ...], Path]]:
    """Return canonical nested step version dirs below ``runs/<id>/steps``."""

    found: list[tuple[tuple[str, ...], Path]] = []
    for vdir in sorted(steps_root.rglob("v[0-9]*")):
        if not vdir.is_dir():
            continue
        rel_parent = vdir.parent.relative_to(steps_root)
        parts = rel_parent.parts
        if not parts or "iterations" in parts or "items" in parts:
            continue
        found.append((tuple(parts), vdir))
    return found


def _step_filter_matches(step_path: tuple[str, ...], step_filter: str) -> bool:
    normalized = step_filter.strip("/")
    return normalized == "/".join(step_path) or normalized == step_path[-1]


def cmd_run_trace(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Chronological event dump for a step (including supersede/tombstone history)."""
    parser = argparse.ArgumentParser(prog="astrid runs trace", add_help=True)
    parser.add_argument("run_id", help="run identifier")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--step", required=True, dest="step_id", help="step id to trace")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"run trace: {exc}", file=sys.stderr)
        return 1

    proj_root = project_dir(slug, root=projects_root)
    run_root = proj_root / "runs" / args.run_id
    if not run_root.is_dir():
        print(f"run trace: run {args.run_id!r} not found", file=sys.stderr)
        return 1

    events_path = run_root / "events.jsonl"
    if not events_path.exists():
        print("(no events)", file=sys.stderr)
        return 0

    events = read_events(events_path)
    step_id = args.step_id

    for event in events:
        path_list = event.get("plan_step_path")
        plan_step_id = event.get("plan_step_id")
        # Match: plan_step_path last element == step_id, or plan_step_id matches
        if isinstance(path_list, list) and path_list:
            last = str(path_list[-1])
            if last != step_id:
                continue
        elif isinstance(plan_step_id, str):
            if plan_step_id != step_id and not plan_step_id.endswith(f"/{step_id}"):
                continue
        else:
            continue

        ts = event.get("ts", "")
        kind = event.get("kind", "")
        rc = event.get("returncode")
        reason = event.get("reason", "")
        cost = event.get("cost")
        line = f"{ts}  {kind}"
        if rc is not None:
            line += f"  returncode={rc}"
        if reason:
            line += f"  reason={reason!r}"
        if cost is not None:
            line += f"  cost={cost}"
        print(line)
        # Also print the full JSON for traceability
    return 0


def cmd_run_cost(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Per-run cost aggregation grouped by source."""
    parser = argparse.ArgumentParser(prog="astrid runs cost", add_help=True)
    parser.add_argument("run_id", help="run identifier")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--json", dest="json_out", action="store_true", help="emit JSON instead of pretty-print")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"run cost: {exc}", file=sys.stderr)
        return 1

    proj_root = project_dir(slug, root=projects_root)
    run_root = proj_root / "runs" / args.run_id
    if not run_root.is_dir():
        print(f"run cost: run {args.run_id!r} not found", file=sys.stderr)
        return 1

    events_path = run_root / "events.jsonl"
    events = read_events(events_path) if events_path.exists() else []
    run_status = _run_status(events)
    if not events_path.exists():
        run_status = _run_status_from_record(_read_run_json(run_root / "run.json"))

    by_source = _cost_by_source(events)
    total = sum(c.get("amount", 0) for c in by_source.values() if isinstance(c, dict))

    if args.json_out:
        print(
            json.dumps(
                {
                    "run_id": args.run_id,
                    "project": slug,
                    "status": run_status,
                    "grand_total": total,
                    "by_source": by_source,
                },
                indent=2,
            )
        )
        return 0

    print(f"Run: {args.run_id}")
    print(f"Total cost: ${total:.2f}")
    if not by_source:
        print("(no cost events)")
        return 0

    print()
    print(f"{'Source':20s} {'Amount':>10s} {'Currency':>8s}")
    for source, info in sorted(by_source.items()):
        if isinstance(info, dict):
            amount = info.get("amount", 0)
            currency = info.get("currency", "USD")
            print(f"{source:20s} ${amount:>9.2f} {currency:>8s}")
        else:
            print(f"{source:20s} {info!s:>10s}")
    return 0


# ---------------------------------------------------------------------------
# events verify (Sprint 5b T5)
# ---------------------------------------------------------------------------


def cmd_events_verify(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Verify the hash chain for a run's events.jsonl.

    Thin CLI wrapper around :func:`astrid.core.task.events.verify_chain`.
    On success prints ``verified: N events, plan_hash=<...>``.
    On failure prints ``broken at line N: <reason>`` and exits 1.

    ``--strict`` additionally replays ``plan_mutated`` events through
    :func:`astrid.core.task.validator.validate_mutation` to check that
    every mutation passes the six-invariant gate.
    """
    parser = argparse.ArgumentParser(prog="astrid events verify", add_help=True)
    parser.add_argument("--run", required=True, dest="run_id", help="run identifier")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also validate plan_mutated events against the six-invariant validator",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"events verify: {exc}", file=sys.stderr)
        return 1

    proj_root = project_dir(slug, root=projects_root)
    run_root = proj_root / "runs" / args.run_id
    if not run_root.is_dir():
        print(
            f"events verify: run {args.run_id!r} not found in project {slug!r}",
            file=sys.stderr,
        )
        return 1

    events_path = run_root / "events.jsonl"
    if not events_path.exists():
        print("verified: 0 events, plan_hash=(no events)")
        return 0

    ok, line_idx, err_msg = verify_chain(events_path)

    events = read_events(events_path)
    n_events = len(events)

    plan_hash = initial_plan_hash_from_events(events) or "unknown"

    if not ok:
        if line_idx == -1:
            print(f"broken: {err_msg}")
        else:
            print(f"broken at line {line_idx + 1}: {err_msg}")
        return 1

    # ── --strict: replay plan mutations through the validator ──────────
    strict_failures = 0
    if args.strict:
        strict_failures += _strict_verify_run_events(proj_root, events)

    print(f"verified: {n_events} events, plan_hash={plan_hash}")
    if args.strict:
        if strict_failures == 0:
            print("strict: all mutation events pass invariant checks")
        else:
            print(
                f"strict: {strict_failures} mutation event(s) failed validation"
            )
            return 1
    return 0


# ---------------------------------------------------------------------------
# events tail (Sprint 5b T6)
# ---------------------------------------------------------------------------


def cmd_events_tail(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Print the last *N* events from a run's ``events.jsonl``.

    ``-f`` polls the file every second for new lines (follow mode).
    ``-n`` controls how many lines to show (default: 20).
    """
    parser = argparse.ArgumentParser(prog="astrid events tail", add_help=True)
    parser.add_argument("--run", required=True, dest="run_id", help="run identifier")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument(
        "-n",
        type=int,
        default=20,
        help="number of lines to print (default: 20)",
    )
    parser.add_argument(
        "-f",
        dest="follow",
        action="store_true",
        help="follow the file, polling every second for new lines",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        print(f"events tail: {exc}", file=sys.stderr)
        return 1

    proj_root = project_dir(slug, root=projects_root)
    run_root = proj_root / "runs" / args.run_id
    if not run_root.is_dir():
        print(
            f"events tail: run {args.run_id!r} not found in project {slug!r}",
            file=sys.stderr,
        )
        return 1

    events_path = run_root / "events.jsonl"
    if not events_path.exists():
        print("(no events)")
        return 0

    _print_tail(events_path, n=args.n)
    if args.follow:
        last_mtime = events_path.stat().st_mtime
        try:
            while True:
                time.sleep(1)
                try:
                    cur_mtime = events_path.stat().st_mtime
                except FileNotFoundError:
                    break
                if cur_mtime > last_mtime:
                    last_mtime = cur_mtime
                    _print_tail(events_path, n=args.n)
        except KeyboardInterrupt:
            pass  # quiet exit on SIGINT
    return 0


def _print_tail(events_path: Path, *, n: int) -> None:
    """Print the last *n* events as one-line summaries."""
    events = read_events(events_path)
    if not events:
        print("(no events)")
        return
    bounded = max(int(n), 0)
    if bounded == 0:
        return
    tail = events[-bounded:] if len(events) > bounded else events
    for ev in tail:
        ts = str(ev.get("ts", ""))[:19]  # truncate fractional seconds
        kind = ev.get("kind", "?")
        plan_step_path = ev.get("plan_step_path")
        step_id = ""
        if isinstance(plan_step_path, list) and plan_step_path:
            step_id = str(plan_step_path[-1])
        elif isinstance(plan_step_path, str):
            step_id = plan_step_path
        rc = ev.get("returncode")
        rc_str = f" rc={rc}" if rc is not None else ""
        line = f"{ts}  {kind:24s}  {step_id}{rc_str}"
        print(line)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run_status(events: list[dict[str, Any]]) -> str:
    """Derive run status from terminal events via the canonical RunStatus.

    The audit surface keeps its historical ``in-flight`` spelling for the
    running state; every other state serializes to the canonical token.
    """
    status = RunStatus.from_run_events(events)
    if status is RunStatus.RUNNING:
        return "in-flight"
    return status.value


def _run_status_from_record(record: dict[str, Any]) -> str:
    raw_status = record.get("status")
    if isinstance(raw_status, str):
        try:
            status = RunStatus.from_run_record_status(raw_status)
        except ValueError:
            return "in-flight"
        return "in-flight" if status is RunStatus.RUNNING else status.value
    return "in-flight"


def _read_run_json(run_json_path: Path) -> dict[str, Any]:
    if run_json_path.exists():
        try:
            loaded = json.loads(run_json_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _build_step_rows(
    events: list[dict[str, Any]],
    run_root: Path,
) -> list[dict[str, Any]]:
    """Build per-step summary rows from events and on-disk state."""
    steps_root = run_root / "steps"
    latest_by_path: dict[str, dict[str, Any]] = {}
    cost_by_path: dict[str, float] = {}

    for event in events:
        path_list = event.get("plan_step_path")
        if not isinstance(path_list, list) or not path_list:
            continue
        path_str = "/".join(str(p) for p in path_list)
        kind = event.get("kind")
        # Track latest event kind for state determination
        if kind in {
            "step_dispatched", "step_completed", "step_failed",
            "step_awaiting_fetch", "step_attested",
        }:
            latest_by_path[path_str] = {"kind": kind, "ts": event.get("ts", "")}
        # Accumulate costs from completed events
        if kind == "step_completed":
            cost = event.get("cost")
            if isinstance(cost, dict):
                amount = cost.get("amount")
                if isinstance(amount, (int, float)):
                    cost_by_path[path_str] = cost_by_path.get(path_str, 0) + float(amount)

    rows: list[dict[str, Any]] = []
    if steps_root.is_dir():
        for step_path, vdir in _iter_step_version_dirs(steps_root):
            version = int(vdir.name[1:])
            path_str = "/".join(step_path)
            info = latest_by_path.get(path_str)
            if info is None:
                for ps, candidate in latest_by_path.items():
                    if _step_filter_matches(tuple(ps.split("/")), path_str):
                        info = candidate
                        break
            state = info.get("kind", "pending") if info is not None else "pending"
            cost_val = cost_by_path.get(path_str)
            extras = ""
            if state == "step_awaiting_fetch":
                remote_path = vdir / "remote_state.json"
                if remote_path.exists():
                    try:
                        st = json.loads(remote_path.read_text(encoding="utf-8"))
                        missing = st.get("missing", [])
                        mismatched = st.get("mismatched", [])
                        if missing or mismatched:
                            extras = f"({len(missing)} missing, {len(mismatched)} mismatched)"
                    except (json.JSONDecodeError, OSError):
                        pass
            rows.append({
                "step_id": path_str,
                "version": version,
                "state": state,
                "cost": cost_val,
                "extras": extras,
            })
    return rows


def _cost_by_source(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate costs from events grouped by cost.source field."""
    by_source: dict[str, dict[str, Any]] = {}
    for event in events:
        kind = event.get("kind", "")
        if kind not in {"step_completed", "step_failed"}:
            continue
        cost = event.get("cost")
        if not isinstance(cost, dict):
            continue
        amount = cost.get("amount")
        currency = cost.get("currency", "USD")
        source = cost.get("source", "unknown")
        if not isinstance(amount, (int, float)):
            continue
        if source not in by_source:
            by_source[source] = {"amount": 0.0, "currency": currency, "source": source}
        by_source[source]["amount"] += float(amount)
        by_source[source]["currency"] = currency
    return by_source


def _strict_verify_run_events(proj_root: Path, events: list[dict[str, Any]]) -> int:
    from astrid.core.task.plan import TaskPlan, compute_plan_hash, iter_steps_with_path
    from astrid.core.task.plan_verbs import _apply_diff as plan_apply_diff
    from astrid.core.task.validator import MutationInvariantError, validate_mutation

    strict_failures = 0
    plan_path = proj_root / "plan.json"
    cached_plan = load_plan(plan_path) if plan_path.exists() else None
    initialized_payload = next(
        (
            ev.get("plan")
            for ev in events
            if isinstance(ev, dict)
            and ev.get("kind") == "plan_initialized"
            and isinstance(ev.get("plan"), dict)
        ),
        None,
    )

    initial_plan = initial_plan_from_events(events) or cached_plan
    initial_hash = initial_plan_hash_from_events(events)
    if initial_plan is None:
        print("strict: could not resolve initial plan from events or project plan")
        return 1

    if isinstance(initialized_payload, dict):
        computed_initial_hash = (
            "sha256:"
            + hashlib.sha256(
                canonical_event_json(initialized_payload).encode("utf-8")
            ).hexdigest()
        )
    elif plan_path.exists():
        computed_initial_hash = compute_plan_hash(plan_path)
    else:
        computed_initial_hash = (
            "sha256:"
            + hashlib.sha256(
                canonical_event_json(initial_plan.to_dict()).encode("utf-8")
            ).hexdigest()
        )
    if initial_hash and initial_hash != computed_initial_hash:
        strict_failures += 1
        print(
            "strict: initial plan hash mismatch: "
            f"events={initial_hash} computed={computed_initial_hash}"
        )

    current: TaskPlan = initial_plan
    for index, ev in enumerate(events, start=1):
        kind = ev.get("kind")
        if kind == "plan_initialized":
            payload = ev.get("plan")
            if not isinstance(payload, dict):
                strict_failures += 1
                print(f"strict: event {index} plan_initialized missing plan payload")
                continue
            event_hash = ev.get("plan_hash")
            payload_hash = (
                "sha256:"
                + hashlib.sha256(
                    canonical_event_json(payload).encode("utf-8")
                ).hexdigest()
            )
            if isinstance(event_hash, str) and event_hash != payload_hash:
                strict_failures += 1
                print(
                    f"strict: event {index} plan_initialized hash mismatch: "
                    f"event={event_hash} computed={payload_hash}"
                )
            continue
        if kind == PLAN_MUTATED_KIND:
            diff = ev.get("diff")
            if not isinstance(diff, dict):
                strict_failures += 1
                print(f"strict: mutation event {index} missing diff field")
                continue
            try:
                proposed = plan_apply_diff(current, diff)
                validate_mutation(
                    prior=current,
                    proposed=proposed,
                    lease_epoch_actual=0,
                    lease_epoch_expected=0,
                )
                current = proposed
            except (MutationInvariantError, Exception) as exc:
                strict_failures += 1
                print(f"strict: mutation event {index} failed: {exc}")
            continue

        if kind in {
            "step_dispatched",
            "step_completed",
            "step_failed",
            "step_skipped",
            "step_attested",
            "item_attested",
            "item_completed",
            "item_skipped",
            "for_each_expanded",
        }:
            path_tuple = _event_step_path(ev)
            if path_tuple is None:
                strict_failures += 1
                print(f"strict: event {index} missing step path for {kind}")
                continue
            effective_index = {path: step for path, step in iter_steps_with_path(current)}
            target = effective_index.get(path_tuple)
            if target is None:
                strict_failures += 1
                print(
                    f"strict: event {index} references unknown step path "
                    f"{'/'.join(path_tuple)!r}"
                )
                continue
            if kind == "step_skipped" and not getattr(target, "optional", False):
                strict_failures += 1
                print(
                    f"strict: skip event {index} targets non-optional step "
                    f"{'/'.join(path_tuple)!r}"
                )
    return strict_failures


def _event_step_path(event: dict[str, Any]) -> tuple[str, ...] | None:
    result = _path_tuple_from_event(event)
    return result if result else None


__all__ = [
    "cmd_events_tail",
    "cmd_events_verify",
    "cmd_run_artifacts",
    "cmd_run_cost",
    "cmd_run_show",
    "cmd_run_trace",
]
