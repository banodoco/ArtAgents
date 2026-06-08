"""Command-line interface for Astrid timelines (Sprint 2 / extended Sprint 5b)."""

from __future__ import annotations

import argparse
from typing import Any

from astrid.core.contracts.errors import AstridError, coerce_astrid_error
from astrid.core.cli_choices import AstridArgumentError
from astrid.core.session.binding import (
    SessionBindingError,
    resolve_current_session,
)

from . import (
    audio_edits,  # kept for monkeypatch seams (timeline_cli.audio_edits)
    clip_edits,  # kept for monkeypatch seams (timeline_cli.clip_edits)
    crud,
    effect_edits,  # kept for monkeypatch seams
    pool_edits,  # kept for monkeypatch seams
    theme_edits,  # kept for monkeypatch seams
    track_edits,  # kept for monkeypatch seams
    transition_edits,  # kept for monkeypatch seams
)
from ._edit_helpers import TimelineEditError
from .eventlog import EventLogError
from .events.schema import TimelineActor
from .projection import ErasedPayloadProjectionError, ProjectionError

_SESSION_GATE_HINT = (
    "A timeline command requires a bound session. "
    "Run 'astrid attach <project>' first."
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except AstridArgumentError as exc:
        raise AstridError(str(exc)) from exc
    except (crud.TimelineCrudError, TimelineEditError, SessionBindingError, EventLogError) as exc:
        raise coerce_astrid_error(exc) from exc
    except ErasedPayloadProjectionError as exc:
        raise AstridError(f"{exc} (erased payload)") from exc
    except (ProjectionError, ValueError) as exc:
        raise AstridError(str(exc)) from exc


# build_parser is now imported from cli_parser (M4 giant-file split).
# The original source lines occupied 787 lines of this module and have been
# moved into astrid.core.timeline.cli_parser to reduce this file below the
# 1,200-line M4 threshold.
from .cli_parser import build_parser  # noqa: E402, F401

# Legacy stub preserved for the parser-only helpers that were moved.
# These are re-exported so intra-module references (like the cmd_*
# handlers that import from .cli) don't break — but they are no longer
# defined here.
def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    from .cli_parser import _add_project_arg as _impl
    return _impl(parser)


def _add_expected_version_arg(parser: argparse.ArgumentParser) -> None:
    from .cli_parser import _add_expected_version_arg as _impl
    return _impl(parser)


# Original build_parser body (lines 72-857) is now in cli_parser.py.
# The parser construction was moved in its entirety to avoid a circular
# import: cli_parser lazily imports command handlers from this module.
# Original function signature start preserved below for diff context.
# def build_parser() -> argparse.ArgumentParser:
#     parser = RecoverableArgumentParser(
#         prog="python3 -m astrid timelines",
#         description="Create, inspect, and manage project timelines.",
#     )
#     subparsers = parser.add_subparsers(dest="command", required=True)
#     ...  # (787 lines total, now in cli_parser.py)


# ---------------------------------------------------------------------------
# Edit command handlers (clip, transition, effect, theme, track, audio,
# pool, arrangement) were extracted into cli_edits.py during M4 giant-file
# split.  Facade re-exports at the bottom of this module preserve legacy
# monkeypatch seams on ``astrid.core.timeline.cli.cmd_*`` names.
#
# _resolve_clip_backend_name stays here (not in cli_edits) so that
# monkeypatch seams on ``timeline_cli._resolve_clip_backend_name`` continue
# to work.  Handlers in cli_edits import it from .cli at call time.
# ---------------------------------------------------------------------------


def _resolve_clip_backend_name(project_slug: str, slug: str) -> str:
    """Read the identity sidecar to determine the backend name for a timeline.

    Returns ``"local_fs"`` when no explicit backend preference is set,
    or ``"supabase"`` when the sidecar requests it.
    """
    from astrid.core.project.jsonio import read_json  # noqa: PLC0415
    from .paths import assembly_identity_path, find_timeline_by_slug  # noqa: PLC0415
    from . import clip_edits  # noqa: PLC0415

    found = find_timeline_by_slug(project_slug, slug)
    if found is None:
        raise clip_edits.ClipEditError(
            f"timeline '{slug}' not found in project '{project_slug}'"
        )
    ulid, _ = found
    identity = read_json(assembly_identity_path(project_slug, ulid))
    if not isinstance(identity, dict):
        raise clip_edits.ClipEditError("timeline identity sidecar is malformed")
    preferred = identity.get("backend")
    if isinstance(preferred, str) and preferred.strip().lower() == "supabase":
        return "supabase"
    return "local_fs"


# ---------------------------------------------------------------------------
# Event/history command handlers (history, diff, audit, preview, who-edited,
# migrate-events) were extracted into cli_events.py during M4 giant-file
# split.  Backend command handlers (push, pull, branch, undo, mass-undo,
# erase, recover) were extracted into cli_backends.py.
# Facade re-exports at the bottom of this module preserve legacy
# monkeypatch seams on ``astrid.core.timeline.cli.cmd_*`` names.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_optional_session(args: argparse.Namespace) -> Any:
    """Resolve a session if possible, but don't raise when not found.

    Used by commands that accept --project as an alternative to session binding.
    """
    try:
        return resolve_current_session(slug=getattr(args, "project", None) or None)
    except Exception:
        return None


def _resolve_project_slug(args: argparse.Namespace, session: Any) -> str:
    """Resolve a project slug from args or session."""
    project_slug = getattr(args, "project", None)
    if project_slug:
        return project_slug
    if session is not None:
        return session.project
    raise AstridError(
        "no project specified; use --project <slug> or bind a session with 'astrid attach'",
        recovery_command="astrid attach <project>",
    )


def _require_session(slug: str | None = None) -> Any:
    # T9 / FLAG-S1-003: optional slug for file-bound fallback; env-only when
    # caller has no --project context to plumb.
    session = resolve_current_session(slug=slug)
    if session is None:
        raise SessionBindingError(_SESSION_GATE_HINT)
    return session


# _add_project_arg and _add_expected_version_arg are now defined in cli_parser.py.
# Stub wrappers at the top of this module delegate to the canonical definitions.


def _expected_version_kwargs(args: argparse.Namespace) -> dict[str, int]:
    expected_version = getattr(args, "expected_version", None)
    if expected_version is None:
        return {}
    return {"expected_version": expected_version}


def _timeline_actor_from_session(session: Any) -> TimelineActor:
    agent_id = getattr(session, "agent_id", "") or "unknown-agent"
    session_id = getattr(session, "id", "") or "unknown-session"
    return TimelineActor(
        type="agent",
        id=f"{agent_id}:{session_id}",
        display=agent_id,
    )

# ---------------------------------------------------------------------------
# Facade re-exports for command handlers moved to cli_crud / cli_output / cli_edits (M4).
# These are imported here so that legacy monkeypatch seams on
# ``astrid.core.timeline.cli.cmd_*`` continue to work.
from .cli_crud import (  # noqa: E402, F401
    cmd_ls,
    cmd_create,
    cmd_show,
    cmd_rename,
    cmd_finalize,
    cmd_tombstone,
    cmd_purge,
    cmd_set_default,
)
from .cli_output import (  # noqa: E402, F401
    cmd_cost,
    cmd_export,
)
from .cli_edits import (  # noqa: E402, F401
    cmd_arrangement_set,
    cmd_arrangement_show,
    cmd_audio_bind,
    cmd_audio_unbind,
    cmd_clip_add,
    cmd_clip_annotate,
    cmd_clip_move,
    cmd_clip_remove,
    cmd_clip_replace,
    cmd_clip_retime,
    cmd_clip_retrack,
    cmd_clip_set_text,
    cmd_clip_swap,
    cmd_effect_add,
    cmd_effect_remove,
    cmd_effect_tune,
    cmd_pool_add,
    cmd_pool_remove,
    cmd_pool_score,
    cmd_theme_override,
    cmd_theme_set,
    cmd_track_add,
    cmd_track_remove,
    cmd_transition_remove,
    cmd_transition_set,
)
from .cli_events import (  # noqa: E402, F401
    _diff_keys,
    _format_history_row,
    _redact_actor,
    _summarize_event_payload,
    cmd_audit,
    cmd_diff,
    cmd_history,
    cmd_migrate_events,
    cmd_preview,
    cmd_who_edited,
)
from .cli_backends import (  # noqa: E402, F401
    cmd_branch_create,
    cmd_branch_list,
    cmd_erase,
    cmd_mass_undo,
    cmd_pull,
    cmd_push,
    cmd_recover,
    cmd_undo,
)
