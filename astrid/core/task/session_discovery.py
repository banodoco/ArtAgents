"""Phase 5 lifecycle verbs: start/abort/status/runs ls/next; cmd_ack lives
in lifecycle_ack.py to keep both modules under the size budget.

cmd_runs_ls (FLAG-P5-006): natural completion does not clear active_run.json
in V1, so the lister surfaces only 'aborted' vs 'in-progress'.
cmd_start (SD-007): does not silently invoke compile when the pre-built JSON
manifest is missing — prints the compile recovery and returns non-zero.
Author-test replays are the exception: they deliberately use compiled smoke
plans even for orchestrators that normally build dynamic start plans.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shlex
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from astrid.core.project.current_run import (
    clear_current_run,
    read_current_run,
    read_current_run_state,
    write_current_run,
)
from astrid.core.project.jsonio import write_json_atomic
from astrid.core.project.paths import (
    project_dir,
    resolve_projects_root,
    validate_project_slug,
    validate_run_id,
)
from astrid.core.project.project import ProjectError, require_project
from astrid.core.alias_resolver import (
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)
from astrid.core.project.run import resolve_required_project_timeline
from astrid.core.project.schema import build_run_record
from astrid.core.pack import discover_packs
from astrid.core.session.lease import (
    release_writer_lease,
    write_lease_init,
)
from astrid.core.session.writer import writer_context_for_project
from astrid.core.task.claim import active_claims_by_step
from astrid.core.task.command_render import render_task_command
from astrid.core.task.env import task_actor_env
from astrid.core.task.events import (
    EventLogError,
    _run_is_complete,
    make_plan_initialized_event,
    make_run_aborted_event,
    make_run_completed_event,
    make_run_started_event,
    make_step_awaiting_fetch_event,
    make_step_completed_event,
    make_step_failed_event,
    read_events,
)
from astrid.core.task.gate import TaskRunGateError, peek_current_step
from astrid.core.task.inbox import consume_inbox_entry, pending_count, scan_inbox
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    compute_plan_hash,
    is_attested_kind,
    is_code_kind,
    is_group_step,
    is_leaf_step,
    iter_steps_with_path,
    load_plan,
    step_dir_for_path,
)
from astrid.core.task.plan_verbs import apply_mutations
from astrid.core.task.preamble import PROHIBITION_PREAMBLE
from astrid.core.timeline.crud import record_contributing_run
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_by_slug, find_timeline_slug_for_ulid

from astrid.core.task.orchestrator_resolver import _list_orchestrator_ids

def _list_project_slugs(projects_root: Optional[Path]) -> list[str]:
    """List on-disk project slugs at the projects_root (sorted, never raises)."""
    try:
        root = Path(projects_root) if projects_root is not None else resolve_projects_root()
    except Exception:
        return []
    if not root.is_dir():
        return []
    slugs: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "project.json").is_file():
            continue
        slugs.append(entry.name)
    return slugs

def _print_next_unbound_hint(
    projects_root: Optional[Path],
    *,
    target_slug: str | None = None,
) -> None:
    """Universal port-of-call (#13): no session bound.

    Print exactly one legal next command. Broader discovery belongs to
    ``astrid status``; ``next`` is the action surface.

    When ``target_slug`` is set (caller passed ``--project <slug>``), the
    hint targets that specific slug instead of listing discovered projects.
    Output deliberately matches the old gate's error wording (``no session
    bound``, ``astrid status``, ``astrid attach``) so existing tests +
    automation that grep stderr keep matching.
    """
    if target_slug:
        action = f"astrid attach {target_slug}"
        print("no session bound.")
        print()
        print("next:")
        print(f"  {action}")
        return

    slugs = _list_project_slugs(projects_root)
    action: str
    try:
        from astrid.core.session.config import resolve_default_project
        default = resolve_default_project()
    except Exception:
        default = None
    if default and default in slugs:
        action = "astrid attach"
    elif len(slugs) == 1:
        action = f"astrid attach {slugs[0]}"
    elif slugs:
        action = "astrid status"
    else:
        action = "astrid projects create <slug>"
    print("no session bound.")
    print()
    print("next:")
    print(f"  {action}")

def _print_next_no_run_hint(slug: str, projects_root: Optional[Path]) -> None:
    """Universal port-of-call (#13): session bound, project attached, but
    no active run. Print the `astrid start` template plus a top-N
    orchestrator suggestion list.
    """
    orchs, registry_err = _list_orchestrator_ids()
    print(f"session bound to {slug!r}, but no active task run.")
    print()
    print("start a new run:")
    print(f"  astrid start <orchestrator-id> --project {slug}")
    print()
    if orchs:
        print("available orchestrators:")
        for oid in orchs:
            print(f"  astrid start {oid} --project {slug}")
    elif registry_err is not None:
        print("orchestrator registry failed to load:")
        print(f"  {registry_err}")
        print("fix the broken manifest then re-run, or browse with "
              "`astrid orchestrators list`.")
    else:
        print("no orchestrators are registered for this checkout; "
              "see `astrid orchestrators list` or `astrid author new <pack>.<name>` "
              "to author one.")

def _os_environ_has_session() -> bool:
    """True iff ASTRID_SESSION_ID is set and non-empty in os.environ."""
    import os as _os
    return bool(_os.environ.get("ASTRID_SESSION_ID", "").strip())

def _most_recent_session_slug(projects_root: Optional[Path]) -> str | None:
    """Find the slug whose .astrid-session file was most recently written.

    Cross-shell session resolution (#24): when an agent has done `astrid
    attach <slug>` in a prior shell but the current shell doesn't have
    ASTRID_SESSION_ID set, scanning projects-root for the freshest
    .astrid-session is a cheap way to recover the same binding.

    Concurrency disambiguation (polish #32, hardened by agentic dogfood
    finding #DD): when multiple agents share one projects-root and each
    writes its own ``.astrid-session``, "the freshest" can be ANY of them,
    not necessarily the one this caller actually attached.

    The original fix (60s ambiguity window) was insufficient. A real
    Claude agent doing the agentic test concurrency probe reported the
    failure mode the 60s window misses: agent A attaches at T+0, agent
    B attaches at T+120 (outside the window), then agent A re-touches
    its ``.astrid-session`` at T+200 (re-attach, status read, whatever).
    Now A's file is fresher than B's, B's bare ``astrid next`` resolves
    to A's project — silently wrong binding. Window-based heuristics
    cannot catch mtime-crossings; they're a fundamental global race.

    Hardened policy: refuse auto-resolve when MORE THAN ONE
    ``.astrid-session`` exists in the projects-root, regardless of
    mtimes. The agent must be explicit (`--project`, `attach`, or
    `ASTRID_SESSION_ID`). Fail closed — the cost of a silently wrong
    binding is much higher than the cost of one extra `--project` flag.

    Single-project case still works: one ``.astrid-session`` → resolve
    it. Multi-project case forces explicit selection.

    This is a deliberate UX fallback in `cmd_next`, distinct from
    `resolve_current_session` itself (which by FLAG-S1-003 invariant
    never walks the filesystem to discover the slug).
    """
    try:
        root = Path(projects_root) if projects_root is not None else resolve_projects_root()
    except Exception:
        return None
    if not root.is_dir():
        return None
    candidates: list[tuple[float, str]] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / "project.json").is_file():
            continue
        session_file = entry / ".astrid-session"
        if not session_file.is_file():
            continue
        try:
            candidates.append((session_file.stat().st_mtime, entry.name))
        except OSError:
            continue
    if not candidates:
        return None
    if len(candidates) > 1:
        # Ambiguous: more than one bound project on disk. Print an
        # enumerated stderr nudge so the caller (often an agent reading
        # stderr) can pick the right project explicitly.
        candidates.sort(key=lambda t: t[0], reverse=True)  # freshest first
        print(
            f"_most_recent_session_slug: {len(candidates)} projects have a"
            f" bound session on disk — refusing to guess.",
            file=sys.stderr,
        )
        for mtime, pslug in candidates:
            print(f"  --project {pslug}", file=sys.stderr)
        return None
    return candidates[0][1]

