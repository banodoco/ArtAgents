"""Timeline backend command handlers.

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
These handlers implement the push/pull, branch, undo, erase, and recover
commands.  To preserve legacy monkeypatch seams, every handler imports
shared session helpers from ``.cli`` at call time.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.timeline._shared import (
    _resolve_optional_session,
    _resolve_project_slug,
    _timeline_actor_from_session,
)

# ---------------------------------------------------------------------------
# Handler: push (m9)
# ---------------------------------------------------------------------------


def _format_sync_fields(result: Any, prefix: str = "  ") -> list[str]:
    """Format S5 sync classification fields for CLI output.

    Returns a list of strings to be printed line-by-line by the caller.
    """
    lines: list[str] = []

    if result.sync_action is not None:
        lines.append(f"{prefix}sync action: {result.sync_action}")

    if result.divergent:
        lines.append(f"{prefix}divergent: True")

    if result.divergence_artifact is not None:
        art = result.divergence_artifact
        if hasattr(art, "path"):
            lines.append(f"{prefix}divergence artifact path: {art.path}")
        elif hasattr(art, "entry_id"):
            entry_id = art.entry_id
            lines.append(f"{prefix}divergence artifact id: {entry_id}")
        else:
            lines.append(f"{prefix}divergence artifact: {art}")

    if result.bookmark_error:
        lines.append(f"{prefix}bookmark error: {result.bookmark_error}")

    return lines


def cmd_push(args: argparse.Namespace) -> int:
    """Push a local timeline to Supabase via event-log replay."""
    session = _resolve_optional_session(args)
    project_slug = _resolve_project_slug(args, session)

    from astrid.core.timeline.transfer import push_timeline

    try:
        result = push_timeline(
            project_slug,
            args.slug_or_id,
            destination_actor=_timeline_actor_from_session(session) if session else None,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines push: {exc}",
            recovery_command="astrid timelines push <slug-or-id>",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    print(f"Push: {result.direction} {result.source_backend_name} → {result.destination_backend_name}")
    print(f"  source timeline: {result.source_timeline_id}")
    print(f"  destination timeline: {result.destination_timeline_id}")
    print(f"  scanned: {result.scanned}")
    print(f"  appended: {result.appended}")
    print(f"  skipped (idempotent): {result.skipped_idempotent}")
    print(f"  failed: {result.failed}")
    print(f"  destination version: {result.destination_version}")
    print(f"  projection regenerated: {result.projection_regenerated}")
    for line in _format_sync_fields(result):
        print(line)

    if result.failed > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Handler: pull (m9)
# ---------------------------------------------------------------------------


def cmd_pull(args: argparse.Namespace) -> int:
    """Pull a Supabase timeline to a local destination via event-log replay."""
    project_slug = args.project  # --project is required for pull

    from astrid.core.timeline.transfer import pull_timeline

    try:
        result = pull_timeline(
            project_slug,
            args.slug_or_id,
            into=args.into_slug,
            create_as=args.create_as_slug,
            create=args.create,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines pull: {exc}",
            recovery_command="astrid timelines pull --project <slug> <slug-or-id>",
            state_snapshot={"project": project_slug, "timeline": args.slug_or_id},
        ) from exc

    print(f"Pull: {result.direction} {result.source_backend_name} → {result.destination_backend_name}")
    print(f"  source timeline: {result.source_timeline_id}")
    print(f"  destination timeline: {result.destination_timeline_id}")
    print(f"  scanned: {result.scanned}")
    print(f"  appended: {result.appended}")
    print(f"  skipped (idempotent): {result.skipped_idempotent}")
    print(f"  failed: {result.failed}")
    print(f"  destination version: {result.destination_version}")
    print(f"  projection regenerated: {result.projection_regenerated}")
    for line in _format_sync_fields(result):
        print(line)

    if result.failed > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Handler: sync (S5)
# ---------------------------------------------------------------------------


def cmd_sync(args: argparse.Namespace) -> int:
    """Unified push-then-pull: push local changes to Supabase, then pull back.

    Runs push first. If push succeeds, immediately runs pull to fetch any
    remote-only changes. If push fails, the error is reported and sync stops.
    When pull reports a destination-only outcome (no new source events), the
    reverse-direction result is surfaced so the operator can see remote-only
    changes that were pulled down.

    Returns exit code 0 when both directions succeed (or are no-ops). Returns
    non-zero when either direction reports failures.
    """
    session = _resolve_optional_session(args)
    project_slug = _resolve_project_slug(args, session)

    from astrid.core.timeline.transfer import pull_timeline, push_timeline

    # ── Phase 1: Push (local → Supabase) ──
    try:
        push_result = push_timeline(
            project_slug,
            args.slug_or_id,
            destination_actor=_timeline_actor_from_session(session) if session else None,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines sync push phase: {exc}",
            recovery_command="astrid timelines sync <slug-or-id> --project <slug>",
            state_snapshot={"timeline": args.slug_or_id, "phase": "push"},
        ) from exc

    print(f"Sync ── push: {push_result.direction} {push_result.source_backend_name} → {push_result.destination_backend_name}")
    print(f"  source timeline: {push_result.source_timeline_id}")
    print(f"  destination timeline: {push_result.destination_timeline_id}")
    print(f"  scanned: {push_result.scanned}")
    print(f"  appended: {push_result.appended}")
    print(f"  skipped (idempotent): {push_result.skipped_idempotent}")
    print(f"  failed: {push_result.failed}")
    print(f"  destination version: {push_result.destination_version}")
    for line in _format_sync_fields(push_result, prefix="  "):
        print(line)

    push_failed = push_result.failed > 0

    # ── Phase 2: Pull (Supabase → local) ──
    pull_failed = False
    try:
        pull_result = pull_timeline(
            project_slug,
            args.slug_or_id,
            into=args.slug_or_id,  # pull back into the same local timeline
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines sync pull phase: {exc}",
            recovery_command="astrid timelines sync <slug-or-id> --project <slug>",
            state_snapshot={"timeline": args.slug_or_id, "phase": "pull"},
        ) from exc

    print(f"Sync ── pull: {pull_result.direction} {pull_result.source_backend_name} → {pull_result.destination_backend_name}")
    print(f"  source timeline: {pull_result.source_timeline_id}")
    print(f"  destination timeline: {pull_result.destination_timeline_id}")
    print(f"  scanned: {pull_result.scanned}")
    print(f"  appended: {pull_result.appended}")
    print(f"  skipped (idempotent): {pull_result.skipped_idempotent}")
    print(f"  failed: {pull_result.failed}")
    print(f"  destination version: {pull_result.destination_version}")
    for line in _format_sync_fields(pull_result, prefix="  "):
        print(line)

    pull_failed = pull_result.failed > 0

    # ── Summary ──
    if push_failed and pull_failed:
        print("Sync: both push and pull reported failures.")
        return 1
    if push_failed:
        print("Sync: push reported failures (pull succeeded).")
        return 1
    if pull_failed:
        print("Sync: pull reported failures (push succeeded).")
        return 1

    # Surface any bookmark-level issues that the transfer surfaced
    bookmark_issues: list[str] = []
    if push_result.bookmark_error:
        bookmark_issues.append(f"push bookmark: {push_result.bookmark_error}")
    if pull_result.bookmark_error:
        bookmark_issues.append(f"pull bookmark: {pull_result.bookmark_error}")

    if push_result.divergent:
        bookmark_issues.append(
            f"push divergence preserved (action={push_result.sync_action})"
        )
    if pull_result.divergent:
        bookmark_issues.append(
            f"pull divergence preserved (action={pull_result.sync_action})"
        )

    if bookmark_issues:
        print("Sync: completed with bookmark notices:")
        for issue in bookmark_issues:
            print(f"  - {issue}")

    print("Sync: complete (local ↔ Supabase).")
    return 0


# ---------------------------------------------------------------------------
# Handler: branch create (m9)
# ---------------------------------------------------------------------------


def cmd_branch_create(args: argparse.Namespace) -> int:
    """Create a branch timeline from a source timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))

    from astrid.core.timeline.branch import create_branch_timeline
    from astrid.core.timeline.projection import ProjectionError

    try:
        result = create_branch_timeline(
            session.project,
            args.source_slug_or_id,
            args.branch_slug,
            from_event_id=args.from_event_id,
            actor=_timeline_actor_from_session(session),
            reason=args.reason,
        )
    except (ValueError, ProjectionError) as exc:
        raise AstridError(
            f"timelines branch create: {exc}",
            recovery_command="astrid timelines branch create <source> <branch-slug>",
            state_snapshot={
                "source": args.source_slug_or_id,
                "branch": args.branch_slug,
            },
        ) from exc

    print(f"Branch created: {result.branch_slug}")
    print(f"  branch timeline ID: {result.branch_timeline_id}")
    print(f"  branch timeline ULID: {result.branch_timeline_ulid}")
    print(f"  anchor event: {result.anchor_event_id} (hash: {result.source_anchor_hash})")
    print(f"  seed event: {result.seed_event_id}")
    print(f"  source branched_from event: {result.source_branched_from_event_id}")
    print(f"  projection: clips={result.branch_projection_summary.get('clip_count', 0)}, "
          f"tracks={result.branch_projection_summary.get('track_count', 0)}")
    return 0


# ---------------------------------------------------------------------------
# Handler: branch list (m9)
# ---------------------------------------------------------------------------


def cmd_branch_list(args: argparse.Namespace) -> int:
    """List branches of a source timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))

    from astrid.core.timeline.branch import list_branches

    try:
        branches = list_branches(session.project, args.source_slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines branch list: {exc}",
            recovery_command="astrid timelines branch list <source>",
            state_snapshot={"source": args.source_slug_or_id},
        ) from exc

    if not branches:
        print(f"(no branches for timeline '{args.source_slug_or_id}')")
        return 0

    print(f"Branches of '{args.source_slug_or_id}':")
    for b in branches:
        reason_str = f"  reason: {b['reason']}" if b.get("reason") else ""
        print(f"  - branch: {b['branch_timeline_id']}")
        print(f"    anchor: {b['anchor_event_id']}")
        print(f"    at: {b['ts']}")
        if reason_str:
            print(f"   {reason_str}")
    return 0


# ---------------------------------------------------------------------------
# Handler: undo (m9)
# ---------------------------------------------------------------------------


def cmd_undo(args: argparse.Namespace) -> int:
    """Undo the latest undoable event on a timeline."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.inverses import plan_inverses
    from astrid.core.timeline.observability import resolve_timeline_target
    from astrid.core.timeline.projection import regenerate_projection, replay_projection

    # Resolve the timeline
    try:
        target = resolve_timeline_target(project_slug, args.slug)
    except ValueError as exc:
        raise AstridError(
            f"timelines undo: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        ) from exc

    preferred_backend = getattr(args, "from_backend", None) or target.backend

    from astrid.core.timeline.eventlog import select_timeline_backend

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=preferred_backend,
    )

    # Verify chain before undoing
    verification = backend.verify_chain()
    if not verification.ok:
        raise AstridError(
            f"timelines undo: chain verification failed: "
            f"{verification.error or 'unknown error'}; refusing to undo",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "verification_error": verification.error},
        )

    # Get all events
    all_events = backend.read_events()
    if not all_events:
        raise AstridError(
            "timelines undo: no events in timeline",
            recovery_command=f"astrid timelines history {args.slug}",
            state_snapshot={"timeline": args.slug},
        )

    # Find the latest undoable event (skip lifecycle/ops by default)
    # Also skip erased events
    from astrid.core.timeline.events.schema import ErasedPayload
    from astrid.core.timeline.inverses import _NON_REVERSIBLE_KINDS

    target_idx: int | None = None
    target_event = None
    for i in range(len(all_events) - 1, -1, -1):
        evt = all_events[i]
        # Skip lifecycle/ops events
        if evt.kind in _NON_REVERSIBLE_KINDS:
            continue
        # Skip already-erased events
        if isinstance(evt.payload, ErasedPayload):
            continue
        target_idx = i
        target_event = evt
        break

    if target_event is None or target_idx is None:
        print("timelines undo: no undoable events found (all are lifecycle/ops or erased)")
        return 0

    # Project before and after states
    before_events = all_events[:target_idx]  # events up to (not including) target
    after_events = all_events[: target_idx + 1]  # events up to and including target

    try:
        before_projection = replay_projection(backend, stop_at_event_id=before_events[-1].event_id) if before_events else {}
    except Exception as exc:
        raise AstridError(
            f"timelines undo: failed to project before state: {exc}",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug},
        ) from exc

    try:
        after_projection = replay_projection(backend, stop_at_event_id=target_event.event_id)
    except Exception as exc:
        raise AstridError(
            f"timelines undo: failed to project after state: {exc}",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "event_id": target_event.event_id},
        ) from exc

    # Plan inverses for the target event
    inverses = plan_inverses([target_event], before_projection, after_projection)

    if not inverses:
        print("timelines undo: no inverse planned for target event")
        return 0

    actor = _timeline_actor_from_session(session)
    appended_ids: list[str] = []

    for inv in inverses:
        if inv.invertible and inv.inverse_kind and inv.inverse_payload is not None:
            # Append the mechanical inverse event
            event = backend.append_event(
                target.timeline_id,
                inv.inverse_kind,
                inv.inverse_payload,
                actor=actor,
            )
            appended_ids.append(event.event_id)
        else:
            # Non-invertible: append timeline.reverted
            from astrid.core.timeline.events.schema import TimelineRevertedPayload
            revert_payload = TimelineRevertedPayload(
                target_event_id=target_event.event_id,
                reason=inv.revert_reason or f"undo of {target_event.kind}",
                before_projection=inv.before_projection,
                after_projection=inv.after_projection,
            ).to_json_obj()
            event = backend.append_event(
                target.timeline_id,
                "timeline.reverted",
                revert_payload,
                actor=actor,
            )
            appended_ids.append(event.event_id)

    # Regenerate projection
    try:
        regenerate_projection(
            target.timeline_id,
            backend,
            timeline_home=target.timeline_home,
        )
    except Exception as exc:
        print(f"timelines undo: warning — projection regeneration failed: {exc}")

    print(f"Undo: target event {target_event.event_id} (kind={target_event.kind})")
    print(f"  appended inverse events: {', '.join(appended_ids)}")
    return 0


# ---------------------------------------------------------------------------
# Handler: mass-undo (m9)
# ---------------------------------------------------------------------------


def cmd_mass_undo(args: argparse.Namespace) -> int:
    """Mass-undo events matching filter criteria (preview-first, chunked writes)."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.observability import resolve_timeline_target
    from astrid.core.timeline.undo import (
        MassUndoSelector,
        execute_mass_undo,
        plan_mass_undo,
    )

    # Validate: at least one filter criterion
    if not (args.ts_since or args.actor_id or args.actor_id_prefix):
        raise AstridError(
            "timelines mass-undo: at least one of --since, --actor, or --actor-prefix must be specified",
            valid_options=["--since", "--actor", "--actor-prefix"],
            recovery_command=f"astrid timelines mass-undo {args.slug} --since <timestamp>",
        )

    # Resolve the timeline
    try:
        target = resolve_timeline_target(project_slug, args.slug)
    except ValueError as exc:
        raise AstridError(
            f"timelines mass-undo: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        ) from exc

    preferred_backend = getattr(args, "from_backend", None) or target.backend

    from astrid.core.timeline.eventlog import select_timeline_backend

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=preferred_backend,
    )

    # Build selector
    selector = MassUndoSelector(
        ts_since=args.ts_since,
        actor_id=args.actor_id,
        actor_id_prefix=args.actor_id_prefix,
    )

    # Verify chain before any work
    verification = backend.verify_chain()
    if not verification.ok:
        raise AstridError(
            f"timelines mass-undo: chain verification failed: "
            f"{verification.error or 'unknown error'}; refusing to undo",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "verification_error": verification.error},
        )

    actor = _timeline_actor_from_session(session)

    if not args.yes:
        # --- Preview mode ---
        try:
            preview = plan_mass_undo(backend, selector)
        except ValueError as exc:
            raise AstridError(
                f"timelines mass-undo: {exc}",
                recovery_command=f"astrid timelines mass-undo {args.slug} --since <timestamp>",
                state_snapshot={"timeline": args.slug},
            ) from exc

        if preview.matched_count == 0:
            print("mass-undo: no matching events found (preview)")
            return 0

        print(f"mass-undo PREVIEW ({preview.matched_count} candidate(s) of {preview.total_events} total events):")
        print()
        for cand in preview.candidates:
            invertible_str = "MECHANICAL" if cand["invertible"] else "FALLBACK"
            print(f"  {cand['event_id']}  kind={cand['kind']}  →  {invertible_str}")
            if cand["invertible"]:
                print(f"    inverse: {cand['inverse_kind']}  payload={cand['inverse_payload']}")
            else:
                print(f"    reason: {cand['revert_reason']}")
        print()
        print("(Preview only — no writes performed.  Use --yes to execute.)")
        return 0

    # --- Execute mode (--yes) ---
    print("mass-undo: executing with --yes ...")
    try:
        result = execute_mass_undo(
            backend,
            selector,
            timeline_id=target.timeline_id,
            actor=actor,
            timeline_home=target.timeline_home,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines mass-undo: {exc}",
            recovery_command=f"astrid timelines mass-undo {args.slug} --since <timestamp>",
            state_snapshot={"timeline": args.slug},
        ) from exc

    print("mass-undo result:")
    print(f"  planned: {result.planned_count} inverses")
    print(f"  appended: {result.appended_count} events")
    print(f"  chunks: {result.chunk_count}")
    print(f"  projection regenerated: {result.projection_regenerated}")
    if result.appended_event_ids:
        print(f"  appended IDs: {', '.join(result.appended_event_ids)}")
    if not result.complete:
        raise AstridError(
            f"timelines mass-undo: partial failure: {result.error}",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "error": result.error},
        )
    if result.error:
        print(f"  warning: {result.error}")

    return 0


# ---------------------------------------------------------------------------
# Handler: erase (m9)
# ---------------------------------------------------------------------------


def cmd_erase(args: argparse.Namespace) -> int:
    """Erase (redact) event payloads matching a selector."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.erasure import (
        ErasureSelector,
        apply_erasure,
        query_erasure,
    )
    from astrid.core.timeline.observability import resolve_timeline_target

    # Resolve the timeline
    try:
        target = resolve_timeline_target(project_slug, args.slug)
    except ValueError as exc:
        raise AstridError(
            f"timelines erase: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        ) from exc

    from astrid.core.timeline.eventlog import select_timeline_backend

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    # Parse selector
    event_ids = None
    if args.event_ids_raw:
        event_ids = tuple(eid.strip() for eid in args.event_ids_raw.split(",") if eid.strip())

    kind_allowlist = None
    if args.kind_allowlist_raw:
        kind_allowlist = tuple(k.strip() for k in args.kind_allowlist_raw.split(",") if k.strip())

    selector = ErasureSelector(
        event_ids=event_ids,
        kind_allowlist=kind_allowlist,
        actor_id=args.actor_id,
        actor_id_prefix=args.actor_id_prefix,
        ts_after=args.ts_after,
        ts_before=args.ts_before,
    )

    # Always preview first
    try:
        preview = query_erasure(backend, selector)
    except ValueError as exc:
        raise AstridError(
            f"timelines erase: {exc}",
            recovery_command=f"astrid timelines erase {args.slug}",
            state_snapshot={"timeline": args.slug},
        ) from exc

    print(f"Erasure preview for timeline '{args.slug}':")
    print(f"  matched events: {preview.matched_count} of {preview.total_events_in_stream}")
    print(f"  selector: {json.dumps(preview.selector_summary, default=str)}")

    if preview.matched_count == 0:
        print("  (no events match — nothing to erase)")
        return 0

    if not args.yes:
        print()
        if preview.matched_count <= 20:
            print("  Matched event IDs:")
            for eid in preview.matched_event_ids:
                print(f"    - {eid}")
        else:
            print(f"  (showing first 20 of {preview.matched_count} matched event IDs)")
            for eid in preview.matched_event_ids[:20]:
                print(f"    - {eid}")
        print()
        print("  Re-run with --yes to perform the erasure.")
        return 0

    # --yes: perform erasure
    from astrid.core.timeline.projection import ProjectionError

    try:
        result = apply_erasure(
            backend,
            selector,
            timeline_id=target.timeline_id,
            actor=_timeline_actor_from_session(session),
            reason=args.reason,
            policy_ref=args.policy_ref,
            timeline_home=target.timeline_home,
        )
    except (ValueError, ProjectionError) as exc:
        raise AstridError(
            f"timelines erase: {exc}",
            recovery_command=f"astrid timelines erase {args.slug}",
            state_snapshot={"timeline": args.slug},
        ) from exc

    print("Erasure applied:")
    print(f"  audit event: {result.audit_event_id}")
    print(f"  payloads replaced: {result.replaced_count}")
    print(f"  downstream recomputed: {result.downstream_count}")
    print(f"  reason: {result.reason}")
    if result.policy_ref:
        print(f"  policy ref: {result.policy_ref}")
    print(f"  projection regenerated: {result.projection_regenerated}")
    print(f"  erased event IDs: {', '.join(result.erased_event_ids)}")
    return 0


# ---------------------------------------------------------------------------
# Handler: recover (m9)
# ---------------------------------------------------------------------------


def cmd_recover(args: argparse.Namespace) -> int:
    """Recover a timeline to a known-good anchor event."""
    from .timeline import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    project_slug = session.project

    from astrid.core.timeline.operations import recover_to_event
    from astrid.core.timeline.projection import ProjectionError

    try:
        result = recover_to_event(
            project_slug,
            args.slug,
            event_id=args.at_event_id,
            actor=_timeline_actor_from_session(session),
            reason=args.reason,
        )
    except (ValueError, ProjectionError) as exc:
        raise AstridError(
            f"timelines recover: {exc}",
            recovery_command=f"astrid timelines recover {args.slug} --at <event-id> --reason <reason>",
            state_snapshot={"timeline": args.slug, "event_id": args.at_event_id},
        ) from exc

    print("Recovery applied:")
    print(f"  anchor event: {result.anchor_event_id} (type={result.anchor_type})")
    print(f"  recovered event: {result.new_event_id}")
    print(f"  new version: {result.new_version}")
    print(f"  reason: {result.reason}")
    print(f"  projection summary: clips={result.projected_head_summary.get('clip_count', 0)}, "
          f"tracks={result.projected_head_summary.get('track_count', 0)}")
    print(f"  regenerated artifacts: {', '.join(result.regenerated_artifact_paths)}")
    return 0
