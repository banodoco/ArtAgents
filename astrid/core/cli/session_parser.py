"""Parser construction for the session CLI.

Extracted from ``astrid/core/session/cli.py`` during M4 giant-file split
(T50).  ``build_parser`` remains the public entry point; it uses the shared
:class:`~astrid.core.cli.registration.CommandSpec` convention so the command
set is declarative and can be checked by the phased CLI allowlist.

All handler references are resolved through the ``.cli`` facade at
parser-build time so that legacy monkeypatch seams on
``astrid.core.session.cli.cmd_*`` and ``astrid.core.session.cli.attach_session``
continue to work — the same indirection pattern used by the timeline CLI parser.
"""

from __future__ import annotations

import argparse

from astrid.core.cli.registration import CommandSpec, register_commands


def _configure_attach(sub: argparse.ArgumentParser) -> None:
    from .session import cmd_attach  # late import — preserves monkeypatch seam

    sub.add_argument("project", nargs="?")
    sub.add_argument("--timeline")
    sub.add_argument("--session", help="Resume an existing session id.")
    sub.add_argument(
        "--as", dest="as_agent", help="Per-tab agent override (agent:<slug>)."
    )
    sub.add_argument(
        "--default",
        action="store_true",
        dest="set_default",
        help="Remember this project as the workspace default.",
    )
    sub.add_argument(
        "--user",
        action="store_true",
        dest="user_default",
        help="With --default, write the user-wide default instead of the workspace default.",
    )
    sub.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "Force a new session id even when a reusable session exists for "
            "this (project, agent) pair. By default attach is idempotent and "
            "reuses prior sessions; --fresh opts out."
        ),
    )
    sub.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    sub.set_defaults(handler=cmd_attach)


def _configure_ls(sub: argparse.ArgumentParser) -> None:
    from .session import cmd_sessions_ls  # late import — preserves monkeypatch seam

    sub.set_defaults(handler=cmd_sessions_ls)


def _configure_detach(sub: argparse.ArgumentParser) -> None:
    from .session import cmd_sessions_detach  # late import — preserves monkeypatch seam

    sub.add_argument("session_id", nargs="?")
    sub.set_defaults(handler=cmd_sessions_detach)


def _configure_takeover(sub: argparse.ArgumentParser) -> None:
    from .session import cmd_sessions_takeover  # late import — preserves monkeypatch seam

    sub.add_argument("target", help="Session id or run id.")
    sub.add_argument(
        "--force", action="store_true", help="Allow takeover of a warm target."
    )
    sub.set_defaults(handler=cmd_sessions_takeover)


def _configure_prune(sub: argparse.ArgumentParser) -> None:
    from .session import cmd_sessions_prune  # late import — preserves monkeypatch seam

    sub.add_argument(
        "--older-than-days",
        type=int,
        default=30,
        help="Delete sessions whose last_used_at is older than this many days (default: 30).",
    )
    sub.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete stale sessions. Without this flag, prune runs in dry-run mode.",
    )
    sub.set_defaults(handler=cmd_sessions_prune)


def _configure_status(sub: argparse.ArgumentParser) -> None:
    from .session import cmd_status  # late import — preserves monkeypatch seam

    sub.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    sub.set_defaults(handler=cmd_status)


COMMANDS: list[CommandSpec] = [
    CommandSpec(
        "attach",
        help="Bind the current tab to a project.",
        configure=_configure_attach,
    ),
    CommandSpec(
        "ls",
        help="List sessions in ~/.astrid/sessions/.",
        aliases=["list"],
        configure=_configure_ls,
    ),
    CommandSpec(
        "detach",
        help="Detach a session (defaults to current tab).",
        configure=_configure_detach,
    ),
    CommandSpec(
        "takeover",
        help="Take over a run lease.",
        configure=_configure_takeover,
    ),
    CommandSpec(
        "prune",
        help="Prune stale session records (dry-run by default).",
        configure=_configure_prune,
    ),
    CommandSpec(
        "status",
        help="Print the current session breadcrumb.",
        configure=_configure_status,
    ),
]


def build_parser() -> argparse.ArgumentParser:
    """Build the ``astrid sessions`` subcommand parser.

    Uses :func:`register_commands` so the command set is declarative and
    auditable through the phased CLI allowlist in
    ``tests/test_cli_registration_conformance.py``.
    """
    parser = argparse.ArgumentParser(prog="python3 -m astrid sessions")
    sub = parser.add_subparsers(dest="command", required=True)
    register_commands(sub, COMMANDS)
    return parser
