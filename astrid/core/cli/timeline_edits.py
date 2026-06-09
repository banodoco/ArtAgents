"""Timeline edit command handlers (clip, transition, effect, theme, track, audio, arrangement).

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
These handlers implement the mutation commands for timeline editing; business
logic is delegated to the existing edit modules.  To preserve legacy
monkeypatch seams, every handler imports its dependencies (session helpers,
edit modules, shared helpers) from ``.cli`` at call time.
"""

from __future__ import annotations

import argparse
import json
from typing import Any
from uuid import uuid4 as _uuid4

from astrid.core.contracts.errors import AstridError

from astrid.core.timeline._edit_helpers import TimelineEditError
from astrid.core.timeline.events.schema import ClipPosition
from astrid.core.timeline._shared import _expected_version_kwargs, _timeline_actor_from_session


# ---------------------------------------------------------------------------
# Shared helpers (used only by edit handlers in this module)
# ---------------------------------------------------------------------------


def _parse_clip_position(args: argparse.Namespace):
    """Normalise CLI position flags into a :class:`ClipPosition`."""
    at_index = getattr(args, "at_index", None)
    after_id = getattr(args, "after_id", None)
    before_id = getattr(args, "before_id", None)

    if at_index is not None:
        return ClipPosition(mode="index", index=at_index)
    if after_id is not None:
        return ClipPosition(mode="after", ref_clip_id=after_id)
    if before_id is not None:
        return ClipPosition(mode="before", ref_clip_id=before_id)
    return None


def _parse_move_position(raw: str):
    """Parse ``--to`` syntax: bare integer → index, ``after:<id>``, ``before:<id>``."""
    from .timeline import clip_edits as _clip_edits  # noqa: PLC0415

    raw = raw.strip()
    if raw.startswith("after:"):
        ref = raw[len("after:"):]
        if not ref:
            raise _clip_edits.ClipEditError("--to after:<id> requires a non-empty clip id")
        return ClipPosition(mode="after", ref_clip_id=ref)
    if raw.startswith("before:"):
        ref = raw[len("before:"):]
        if not ref:
            raise _clip_edits.ClipEditError("--to before:<id> requires a non-empty clip id")
        return ClipPosition(mode="before", ref_clip_id=ref)
    try:
        idx = int(raw)
    except ValueError:
        raise _clip_edits.ClipEditError(
            f"--to must be an index, after:<id>, or before:<id>; got {raw!r}"
        )
    return ClipPosition(mode="index", index=idx)


def _clip_success(event, backend_name: str) -> str:
    """Format a one-line success message for clip commands."""
    return (
        f"clip: event {event.event_id}, kind={event.kind}, "
        f"timeline={event.timeline_id}, backend={backend_name}"
    )


def _parse_between(raw: str) -> tuple[str, str]:
    """Parse ``--between LEFT,RIGHT`` into ``(left_clip_id, right_clip_id)``."""
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        raise TimelineEditError(
            f"--between must be LEFT,RIGHT (comma-separated), got {raw!r}"
        )
    left, right = parts
    if not left or not right:
        raise TimelineEditError("--between clip ids must be non-empty")
    return left, right


def _parse_kv(raw: str) -> tuple[str, str]:
    """Parse ``k=v`` into ``(k, v)``."""
    parts = raw.split("=", 1)
    if len(parts) != 2:
        raise TimelineEditError(f"--params must be k=v, got {raw!r}")
    return parts[0].strip(), parts[1].strip()


def _parse_params(raw_list: list[str] | None) -> dict[str, Any] | None:
    """Convert repeated ``k=v`` args into a dict."""
    if not raw_list:
        return None
    result: dict[str, Any] = {}
    for item in raw_list:
        k, v = _parse_kv(item)
        result[k] = v
    return result


def _parse_json_value(raw: str, *, flag: str) -> Any:
    """Parse a CLI JSON value, surfacing a user-facing error on invalid JSON."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TimelineEditError(f"{flag} must be valid JSON: {exc.msg}") from exc


def _edit_success(domain: str, event, backend_name: str) -> str:
    """Format a one-line success message for non-clip timeline edit commands."""
    return (
        f"{domain}: event {event.event_id}, kind={event.kind}, "
        f"timeline={event.timeline_id}, backend={backend_name}"
    )


# ---------------------------------------------------------------------------
# Handler: clip (9 verbs)
# ---------------------------------------------------------------------------


def cmd_clip_add(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    pos = _parse_clip_position(args)
    extra = _expected_version_kwargs(args)
    event = clip_edits.add_clip(
        session.project,
        args.slug,
        kind=args.kind,
        asset_id=args.asset,
        track_id=getattr(args, "track_id", None),
        position=pos,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_remove(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.remove_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_move(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    pos = _parse_move_position(args.to_position)
    extra = _expected_version_kwargs(args)
    event = clip_edits.move_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        position=pos,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_retrack(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.retrack_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        track_id=args.track_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_retime(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.retime_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        start=args.start,
        duration=args.duration,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_swap(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.swap_clips(
        session.project,
        args.slug,
        clip_a_id=args.clip_a,
        clip_b_id=args.clip_b,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_replace(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.replace_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        with_asset_id=args.with_asset_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_set_text(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.set_clip_text(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        text=args.text,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_annotate(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        clip_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.annotate_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        note=args.note,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: transition (2 verbs)
# ---------------------------------------------------------------------------


def cmd_transition_set(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        transition_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    left, right = _parse_between(args.between)
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = transition_edits.transition_set(
        session.project,
        args.slug,
        left_clip_id=left,
        right_clip_id=right,
        kind=args.kind,
        duration_seconds=args.duration_seconds,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("transition", event, backend_name))
    return 0


def cmd_transition_remove(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        transition_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    left, right = _parse_between(args.between)
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = transition_edits.transition_remove(
        session.project,
        args.slug,
        left_clip_id=left,
        right_clip_id=right,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("transition", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: effect (3 verbs)
# ---------------------------------------------------------------------------


def cmd_effect_add(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        effect_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    params = _parse_params(args.params_raw)
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = effect_edits.effect_add(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        effect_id=args.effect_id,
        params=params,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("effect", event, backend_name))
    return 0


def cmd_effect_remove(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        effect_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = effect_edits.effect_remove(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        effect_id=args.effect_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("effect", event, backend_name))
    return 0


def cmd_effect_tune(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        effect_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    value = _parse_json_value(args.value, flag="--value")
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = effect_edits.effect_tune(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        effect_id=args.effect_id,
        param=args.param,
        value=value,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("effect", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: theme (2 verbs)
# ---------------------------------------------------------------------------


def cmd_theme_set(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        theme_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = theme_edits.theme_set(
        session.project,
        args.slug,
        theme_id=args.theme_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("theme", event, backend_name))
    return 0


def cmd_theme_override(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        theme_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    value = _parse_json_value(args.value, flag="--value")
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = theme_edits.theme_override(
        session.project,
        args.slug,
        override_id=args.override_id,
        value=value,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("theme", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: track (2 verbs)
# ---------------------------------------------------------------------------


def cmd_track_add(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        track_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    track_id = args.track_id or str(_uuid4())
    extra = _expected_version_kwargs(args)
    event = track_edits.track_add(
        session.project,
        args.slug,
        track_id=track_id,
        kind=args.kind,
        label=args.label,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("track", event, backend_name))
    return 0


def cmd_track_remove(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        track_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = track_edits.track_remove(
        session.project,
        args.slug,
        track_id=args.track_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("track", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: audio (2 verbs)
# ---------------------------------------------------------------------------


def cmd_audio_bind(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        audio_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = audio_edits.audio_bind(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        asset_id=args.asset_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("audio", event, backend_name))
    return 0


def cmd_audio_unbind(args: argparse.Namespace) -> int:
    from .timeline import (  # noqa: PLC0415
        _require_session,
        _resolve_clip_backend_name,
        audio_edits,
    )

    session = _require_session(slug=getattr(args, "project", None))
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = audio_edits.audio_unbind(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("audio", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: arrangement (2 verbs)
# ---------------------------------------------------------------------------


def cmd_arrangement_set(args: argparse.Namespace) -> int:
    from .timeline import _require_session  # noqa: PLC0415

    _require_session(slug=getattr(args, "project", None))
    raise TimelineEditError(
        "arrangement set is retired: arrangement.replaced is migration-only "
        "legacy. Use timeline.config_replaced with a raw TimelineConfig for "
        "canonical full-timeline writes."
    )


def cmd_arrangement_show(args: argparse.Namespace) -> int:
    from .timeline import _require_session, crud  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    arrangement = crud.get_arrangement(session.project, args.slug)
    if arrangement is None:
        data = crud.show_timeline(session.project, args.slug)
        if data is None:
            raise AstridError(
                f"timeline '{args.slug}' not found",
                recovery_command="astrid timelines ls",
                state_snapshot={"timeline": args.slug},
            )
    print(json.dumps(arrangement, indent=2, default=str))
    return 0
