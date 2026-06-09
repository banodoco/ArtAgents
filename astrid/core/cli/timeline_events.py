"""Timeline event and history command handlers.

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
These handlers implement the event-level query and inspection commands
(history, diff, audit, preview, who-edited, migrate-events).  To preserve
legacy monkeypatch seams, every handler imports shared session helpers from
``.cli`` at call time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError

from astrid.core.timeline.events.schema import TimelineActor


# ---------------------------------------------------------------------------
# Shared helpers (used only by event/history handlers in this module)
# ---------------------------------------------------------------------------


def _redact_actor(actor: TimelineActor) -> str:
    """Return a safe display string for an actor (no via/session/token)."""
    if actor.display:
        return actor.display
    return actor.id


def _format_history_row(version: int, event: TimelineEvent, backend_name: str) -> str:
    """Format one event row for the history table."""
    actor_display = _redact_actor(event.actor)
    return (
        f"  v{version:<6} {event.event_id}  "
        f"kind={event.kind:<28}  actor={actor_display}"
    )


def _summarize_event_payload(event: TimelineEvent) -> str:
    """Produce a short operation-level summary of an event's payload."""
    payload = event.payload
    if isinstance(payload, dict):
        # Show a few key fields
        keys = sorted(payload.keys())
        if len(keys) <= 4:
            brief = {k: payload[k] for k in keys}
        else:
            brief = {k: payload[k] for k in keys[:4]}
            brief["..."] = f"+{len(keys) - 4} more fields"
        try:
            return json.dumps(brief, default=str)
        except Exception:
            return str(brief)
    return str(payload)


def _diff_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return keys that differ between two dicts (top-level only)."""
    keys = sorted(set(before.keys()) | set(after.keys()))
    diffs: list[str] = []
    for k in keys:
        if before.get(k) != after.get(k):
            diffs.append(k)
    return diffs


# ---------------------------------------------------------------------------
# Handler: migrate-events (m8)
# ---------------------------------------------------------------------------


def cmd_migrate_events(args: argparse.Namespace) -> int:
    """Run timeline event-stream migration (dry-run or --apply).

    Supports --project <slug> or --all-projects.  --dry-run is the default;
    --apply actually writes event-stream imports.  --json emits structured
    output instead of pretty-print.

    Returns nonzero on parity failures or unreadable source blobs.
    """
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
    from astrid.core.timeline.events.schema import TimelineActor
    from astrid.core.timeline.migration import (
        MigrationResult,
        SkippedTimeline,
        discover_projects_for_migration,
        discover_timelines_for_project,
        import_from_legacy_local,
    )

    write_mode = bool(getattr(args, "apply", False))
    json_out = bool(getattr(args, "json_out", False))
    all_projects = bool(getattr(args, "all_projects", False))
    project_slug: str | None = getattr(args, "project_slug", None)

    # --- Resolve project list ---
    if all_projects:
        slugs = discover_projects_for_migration()
    elif project_slug:
        slugs = [project_slug]
    else:
        raise AstridError(
            "timelines migrate-events: must specify --project or --all-projects",
            valid_options=["--project <slug>", "--all-projects"],
            recovery_command="astrid timelines migrate-events --project <slug>",
        )

    if not slugs:
        print("(no projects discovered)")
        return 0

    result = MigrationResult()

    for slug in slugs:
        timelines = discover_timelines_for_project(slug)
        for ulid, classification in timelines:
            if classification == "already_event_sourced":
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason="Already event-sourced — skipping",
                        classification=classification,
                    )
                )
                continue

            if classification == "malformed_incomplete":
                result.malformed.append(ulid)
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason="Malformed or incomplete timeline directory",
                        classification=classification,
                    )
                )
                continue

            # classification == "legacy_local"
            if not write_mode:
                # Dry-run: just report what would happen
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason="Would import (dry-run)",
                        classification=classification,
                    )
                )
                continue

            # --apply mode: actually import
            from astrid.core.timeline.paths import timeline_dir

            tdir = timeline_dir(slug, ulid)
            backend = LocalFsBackend(timeline_home=tdir, timeline_id=ulid)
            actor = TimelineActor(type="agent", id="cli:migrate-events", display="migrate-events")

            import_result = import_from_legacy_local(
                backend=backend,
                timeline_home=tdir,
                actor=actor,
            )

            if import_result.get("imported"):
                result.imported.append(ulid)
                if not import_result.get("parity_ok"):
                    from astrid.core.timeline.migration import ParityFailure
                    result.parity_failures.append(
                        ParityFailure(
                            project_slug=slug,
                            timeline_ulid=ulid,
                            source_hash="",
                            projected_hash="",
                            detail=import_result.get("detail", "Parity check failed"),
                        )
                    )
            else:
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason=import_result.get("detail", "Import skipped"),
                        classification=classification,
                    )
                )

    # --- Output ---
    if json_out:
        output = {
            "imported_count": len(result.imported),
            "skipped_count": len(result.skipped),
            "parity_failure_count": len(result.parity_failures),
            "malformed_count": len(result.malformed),
            "imported": result.imported,
            "skipped": [
                {
                    "project_slug": s.project_slug,
                    "timeline_ulid": s.timeline_ulid,
                    "reason": s.reason,
                    "classification": s.classification,
                }
                for s in result.skipped
            ],
            "parity_failures": [
                {
                    "project_slug": f.project_slug,
                    "timeline_ulid": f.timeline_ulid,
                    "detail": f.detail,
                }
                for f in result.parity_failures
            ],
            "malformed": result.malformed,
            "ok": result.ok,
        }
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    else:
        mode_label = "dry-run" if not write_mode else "applied"
        print(f"Migration {mode_label} — {len(result.imported)} imported, "
              f"{len(result.skipped)} skipped, "
              f"{len(result.parity_failures)} parity failures, "
              f"{len(result.malformed)} malformed")

        if result.skipped:
            print("\nSkipped:")
            for s in result.skipped:
                print(f"  [{s.project_slug}] {s.timeline_ulid or '?'}: {s.reason}")

        if result.parity_failures:
            print(f"\nParity failures ({len(result.parity_failures)}):")
            for f in result.parity_failures:
                print(f"  [{f.project_slug}] {f.timeline_ulid}: {f.detail}")

        if result.malformed:
            print(f"\nMalformed ({len(result.malformed)}):")
            for ulid in result.malformed:
                print(f"  {ulid}")

        if result.imported:
            print(f"\nImported ({len(result.imported)}):")
            for ulid in result.imported:
                print(f"  {ulid}")

    return 0 if result.ok else 1


# ---------------------------------------------------------------------------
# Handler: history (m7)
# ---------------------------------------------------------------------------


def cmd_history(args: argparse.Namespace) -> int:
    """Read and pretty-print the event history of a timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.eventlog import select_timeline_backend
    from astrid.core.timeline.observability import resolve_timeline_target

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    events = backend.read_events(
        after=getattr(args, "since_event_id", None),
        limit=getattr(args, "limit", 50),
    )

    backend_label = backend.backend_name()

    if not events:
        print(f"(no events — backend={backend_label}, timeline={target.timeline_id})")
        return 0

    print(f"Backend:    {backend_label}")
    print(f"Timeline:   {target.timeline_id}  (slug: {target.slug})")
    print(f"Event count in this page: {len(events)}")
    print()

    # Determine starting version: if --since was given, find its index.
    if getattr(args, "since_event_id", None):
        all_events = backend.read_events()
        base_idx = next(
            (i for i, e in enumerate(all_events) if e.event_id == args.since_event_id),
            None,
        )
        base_version = (base_idx + 1) if base_idx is not None else 0
    else:
        base_version = 0

    for i, event in enumerate(events, start=1):
        version = base_version + i
        print(_format_history_row(version, event, backend_label))

    return 0


# ---------------------------------------------------------------------------
# Handler: diff (m7)
# ---------------------------------------------------------------------------


def cmd_diff(args: argparse.Namespace) -> int:
    """Semantic diff between two events in a timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.eventlog import select_timeline_backend
    from astrid.core.timeline.observability import resolve_timeline_target
    from astrid.core.timeline.projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    all_events = backend.read_events()

    # Find from/to indices
    from_idx: int | None = None
    to_idx: int | None = None
    for i, event in enumerate(all_events):
        if event.event_id == args.from_event_id:
            from_idx = i
        if event.event_id == args.to_event_id:
            to_idx = i

    if from_idx is None:
        raise AstridError(
            f"timelines: event '{args.from_event_id}' not found in timeline '{target.slug}'",
            recovery_command=f"astrid timelines history {args.slug_or_id}",
            state_snapshot={"timeline": target.slug, "event_id": args.from_event_id},
        )
    if to_idx is None:
        raise AstridError(
            f"timelines: event '{args.to_event_id}' not found in timeline '{target.slug}'",
            recovery_command=f"astrid timelines history {args.slug_or_id}",
            state_snapshot={"timeline": target.slug, "event_id": args.to_event_id},
        )

    from_event = all_events[from_idx]
    to_event = all_events[to_idx]

    print(f"Diff:  {from_event.event_id}  →  {to_event.event_id}")
    print(f"Timeline: {target.timeline_id}  (slug: {target.slug})")
    print(f"Backend:  {backend.backend_name()}")
    print()

    print("From event:")
    print(f"  kind:    {from_event.kind}")
    print(f"  actor:   {_redact_actor(from_event.actor)}")
    print(f"  ts:      {from_event.ts}")
    print(f"  payload: {_summarize_event_payload(from_event)}")
    print()
    print("To event:")
    print(f"  kind:    {to_event.kind}")
    print(f"  actor:   {_redact_actor(to_event.actor)}")
    print(f"  ts:      {to_event.ts}")
    print(f"  payload: {_summarize_event_payload(to_event)}")
    print()

    # Show intervening events as operation-level summaries
    if to_idx - from_idx > 1:
        print(f"Intervening events ({to_idx - from_idx - 1}):")
        for i in range(from_idx + 1, to_idx):
            ev = all_events[i]
            print(
                f"  [{i + 1}] {ev.event_id}  kind={ev.kind}  "
                f"actor={_redact_actor(ev.actor)}"
            )
        print()

    if getattr(args, "with_state", False):
        try:
            from_state = replay_projection(backend, stop_at_event_id=from_event.event_id)
        except Exception as exc:
            raise AstridError(
                f"timelines: failed to project state at from event: {exc}",
                recovery_command=f"astrid timelines audit {args.slug_or_id}",
                state_snapshot={"timeline": target.slug, "event_id": from_event.event_id},
            ) from exc
        try:
            to_state = replay_projection(backend, stop_at_event_id=to_event.event_id)
        except Exception as exc:
            raise AstridError(
                f"timelines: failed to project state at to event: {exc}",
                recovery_command=f"astrid timelines audit {args.slug_or_id}",
                state_snapshot={"timeline": target.slug, "event_id": to_event.event_id},
            ) from exc

        print("Projected state at FROM event:")
        print(json.dumps(from_state, indent=2, default=str))
        print()
        print("Projected state at TO event:")
        print(json.dumps(to_state, indent=2, default=str))

    return 0


# ---------------------------------------------------------------------------
# Handler: audit (m7)
# ---------------------------------------------------------------------------


def cmd_audit(args: argparse.Namespace) -> int:
    """Verify event chain integrity and projection parity."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.eventlog import select_timeline_backend
    from astrid.core.timeline.observability import read_ops_log, resolve_timeline_target
    from astrid.core.timeline.projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    issues: list[str] = []

    # 1. Verify hash chain
    verification = backend.verify_chain()
    chain_ok = verification.ok
    chain_checked = verification.checked_events
    chain_error = verification.error

    # 2. Head
    head_ok = True
    head_error: str | None = None
    try:
        head = backend.head()
    except Exception as exc:
        head_ok = False
        head_error = str(exc)

    # 3. Projection parity: pure replay vs on-disk assembly.json
    projection_parity_ok: bool | None = None
    projection_parity_error: str | None = None
    try:
        replayed = replay_projection(backend)
    except Exception as exc:
        projection_parity_ok = False
        projection_parity_error = f"replay failed: {exc}"
    else:
        assembly_path = target.timeline_home / "assembly.json"
        if assembly_path.is_file():
            from astrid.core._shared.jsonio import read_json  # noqa: PLC0415

            try:
                existing = read_json(assembly_path)
            except Exception as exc:
                projection_parity_ok = False
                projection_parity_error = f"failed to read assembly.json: {exc}"
            else:
                existing_assembly = existing
                if existing_assembly != replayed:
                    projection_parity_ok = False
                    diff_keys = _diff_keys(
                        existing_assembly if isinstance(existing_assembly, dict) else {},
                        replayed if isinstance(replayed, dict) else {},
                    )
                    projection_parity_error = (
                        f"assembly.json does not match replay; "
                        f"differing keys: {diff_keys if diff_keys else '(structural mismatch)'}"
                    )
                else:
                    projection_parity_ok = True
        else:
            # No derived blob exists — parity check is not applicable.
            projection_parity_ok = None

    # 4. Ops log
    ops_entries = None
    ops_log_error: str | None = None
    if getattr(args, "include_ops", False):
        ops_entries = read_ops_log(target.timeline_home)
        if ops_entries is None:
            ops_log_error = "no operational failure logs"

    # --- Print results ---
    print(f"Audit for timeline '{target.slug}'")
    print(f"  Backend:     {backend.backend_name()}")
    print(f"  Timeline ID: {target.timeline_id}")
    print()

    # Chain
    status_chain = "OK" if chain_ok else "FAIL"
    print(f"  Hash chain:  {status_chain}  (checked {chain_checked} events)")
    if chain_error:
        issues.append(f"chain: {chain_error}")
        print(f"    Error: {chain_error}")

    # Head
    status_head = "OK" if head_ok else "FAIL"
    print(f"  Head:        {status_head}")
    if head_error:
        issues.append(f"head: {head_error}")
        print(f"    Error: {head_error}")
    elif head_ok:
        print(f"    timeline_id={head.timeline_id}, version={head.version}, "
              f"events={head.event_count}, last={head.last_event_id}")

    # Projection parity
    if projection_parity_ok is None:
        print("  Projection:  N/A  (no assembly.json to compare)")
    elif projection_parity_ok:
        print("  Projection:  OK  (assembly.json matches replay)")
    else:
        issues.append(f"projection: {projection_parity_error}")
        print("  Projection:  MISMATCH")
        if projection_parity_error:
            print(f"    {projection_parity_error}")

    # Ops log
    if ops_entries is not None:
        print(f"  Ops log:     {len(ops_entries)} entries")
        for entry in ops_entries:
            print(f"    - [{entry.ts}] event={entry.event_id} kind={entry.kind}: {entry.error}")
    elif ops_log_error is not None:
        print(f"  Ops log:     ({ops_log_error})")

    print()

    if issues:
        print(f"Summary: {len(issues)} issue(s) found")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("Summary: all checks passed")
    return 0


# ---------------------------------------------------------------------------
# Handler: preview (m7)
# ---------------------------------------------------------------------------


def cmd_preview(args: argparse.Namespace) -> int:
    """Project a past state at a specific event."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.eventlog import select_timeline_backend
    from astrid.core.timeline.observability import resolve_timeline_target
    from astrid.core.timeline.projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    try:
        state = replay_projection(backend, stop_at_event_id=args.at_event_id)
    except Exception as exc:
        raise AstridError(
            f"timelines: failed to project state at '{args.at_event_id}': {exc}",
            recovery_command=f"astrid timelines audit {args.slug_or_id}",
            state_snapshot={"timeline": args.slug_or_id, "event_id": args.at_event_id},
        ) from exc

    out_path_raw = getattr(args, "out_path", None)
    if out_path_raw:
        out_path = Path(out_path_raw).expanduser().resolve()
        timeline_home_resolved = target.timeline_home.resolve()

        # Guard: reject --out paths inside the timeline home.
        try:
            out_path.relative_to(timeline_home_resolved)
        except ValueError:
            pass  # not inside timeline home — ok
        else:
            raise AstridError(
                f"timelines: --out path '{out_path_raw}' is inside the timeline home; "
                f"refusing to overwrite canonical files",
                recovery_command="choose an --out path outside the timeline home",
                state_snapshot={"out": out_path_raw, "timeline_home": timeline_home_resolved},
            )

        from astrid.core._shared.jsonio import write_json_atomic

        write_json_atomic(out_path, state)
        print(f"Projected state written to {out_path}")
    else:
        print(json.dumps(state, indent=2, default=str))

    return 0


# ---------------------------------------------------------------------------
# Handler: who-edited (m7)
# ---------------------------------------------------------------------------


def cmd_who_edited(args: argparse.Namespace) -> int:
    """Show actor rollup for a timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.eventlog import select_timeline_backend
    from astrid.core.timeline.observability import resolve_timeline_target

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    events = backend.read_events()

    if not events:
        print(f"(no events — backend={backend.backend_name()}, timeline={target.timeline_id})")
        return 0

    # Actor rollup: group by actor.id, count events by kind.
    rollup: dict[str, dict[str, Any]] = {}
    for event in events:
        actor = event.actor
        actor_key = actor.id
        if actor_key not in rollup:
            rollup[actor_key] = {
                "actor_id": actor.id,
                "actor_display": _redact_actor(actor),
                "kinds": {},
                "total": 0,
            }
        entry = rollup[actor_key]
        entry["kinds"][event.kind] = entry["kinds"].get(event.kind, 0) + 1
        entry["total"] += 1

    sorted_entries = sorted(rollup.values(), key=lambda e: e["total"], reverse=True)

    print(f"Actor rollup for timeline '{target.slug}'")
    print(f"  Backend:     {backend.backend_name()}")
    print(f"  Timeline ID: {target.timeline_id}")
    print(f"  Total actors: {len(sorted_entries)}")
    print()

    for entry in sorted_entries:
        print(f"  {entry['actor_display']}  (id: {entry['actor_id']})")
        print(f"    total events: {entry['total']}")
        for kind, count in sorted(entry["kinds"].items()):
            print(f"      {kind}: {count}")
        print()

    return 0
