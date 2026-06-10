"""Command-line interface for Astrid timelines (Sprint 2 / extended Sprint 5b)."""

from __future__ import annotations

import argparse
from typing import Any  # noqa: F401  (re-exported: preserves cli.Any symbol)

from astrid.core.cli_choices import AstridArgumentError
from astrid.core.contracts.errors import AstridError, coerce_astrid_error
from astrid.core.session.binding import (  # noqa: F401  (resolve_current_session re-exported)
    SessionBindingError,
    resolve_current_session,
)
from astrid.core.timeline import (
    audio_edits,  # kept for monkeypatch seams (timeline_cli.audio_edits)
    clip_edits,  # kept for monkeypatch seams (timeline_cli.clip_edits)
    crud,
    effect_edits,  # kept for monkeypatch seams
    theme_edits,  # kept for monkeypatch seams
    track_edits,  # kept for monkeypatch seams
    transition_edits,  # kept for monkeypatch seams
)
from astrid.core.timeline._edit_helpers import TimelineEditError

# Shared session/version helpers were moved to ._shared to break the
# circular-facade dependency (leaves no longer reach back into .cli for them).
# They are re-exported here so the legacy monkeypatch seams
# ``astrid.core.timeline.cli._require_session`` (et al.) keep resolving.
from astrid.core.timeline._shared import (  # noqa: F401
    _SESSION_GATE_HINT,
    _expected_version_kwargs,
    _require_session,
    _resolve_optional_session,
    _resolve_project_slug,
    _timeline_actor_from_session,
)
from astrid.core.timeline.eventlog import EventLogError
from astrid.core.timeline.events.schema import TimelineActor  # noqa: F401  (re-exported)
from astrid.core.timeline.projection import ErasedPayloadProjectionError, ProjectionError


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
from .timeline_parser import build_parser  # noqa: E402, F401


# Legacy stub preserved for the parser-only helpers that were moved.
# These are re-exported so intra-module references (like the cmd_*
# handlers that import from .cli) don't break — but they are no longer
# defined here.
def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    from .timeline_parser import _add_project_arg as _impl
    return _impl(parser)


def _add_expected_version_arg(parser: argparse.ArgumentParser) -> None:
    from .timeline_parser import _add_expected_version_arg as _impl
    return _impl(parser)



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
    from astrid.core._shared.jsonio import read_json  # noqa: PLC0415
    from astrid.core.timeline import clip_edits  # noqa: PLC0415
    from astrid.core.timeline.paths import (  # noqa: PLC0415
        assembly_identity_path,
        find_timeline_by_slug,
    )

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
#
# _resolve_optional_session, _resolve_project_slug, _require_session,
# _expected_version_kwargs, and _timeline_actor_from_session now live in
# ._shared (imported + re-exported at the top of this module).
#
# _add_project_arg and _add_expected_version_arg are now defined in cli_parser.py.
# Stub wrappers at the top of this module delegate to the canonical definitions.

# ---------------------------------------------------------------------------
# Facade re-exports for command handlers moved to cli_crud / cli_output / cli_edits (M4).
# These are imported here so that legacy monkeypatch seams on
# ``astrid.core.timeline.cli.cmd_*`` continue to work.
from .timeline_backends import (  # noqa: E402, F401
    cmd_branch_create,
    cmd_branch_list,
    cmd_erase,
    cmd_mass_undo,
    cmd_pull,
    cmd_push,
    cmd_recover,
    cmd_undo,
)
from .timeline_crud import (  # noqa: E402, F401
    cmd_create,
    cmd_finalize,
    cmd_ls,
    cmd_purge,
    cmd_rename,
    cmd_set_default,
    cmd_show,
    cmd_tombstone,
)
from .timeline_edits import (  # noqa: E402, F401
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
    cmd_theme_override,
    cmd_theme_set,
    cmd_track_add,
    cmd_track_remove,
    cmd_transition_remove,
    cmd_transition_set,
)
from .timeline_events import (  # noqa: E402, F401
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
from .timeline_output import (  # noqa: E402, F401
    cmd_cost,
    cmd_export,
)
