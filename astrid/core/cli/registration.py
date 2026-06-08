"""Shared CLI command-registration convention for Astrid subcommand parsers.

Every CLI module that uses ``argparse`` subparsers should describe its
commands with :class:`CommandSpec` and register them through
:func:`register_commands` so that command set conformance, help-text
completeness, and phased migration allowlists can be checked centrally.

The helper preserves arbitrary argparse parser configuration: the
``configure`` callback receives the subparser that argparse created and
can call ``.add_argument()``, ``.set_defaults()``, or any other argparse
API without any wrapper restricting the configuration surface.

Usage::

    from argparse import ArgumentParser
    from astrid.core.cli.registration import CommandSpec, register_commands

    def _cmd_ls(parsed, registry):
        ...

    def _configure_ls(subparser):
        subparser.add_argument("--json", action="store_true")
        subparser.set_defaults(handler=_cmd_ls)

    COMMANDS = [
        CommandSpec("ls", help="List items.", aliases=["list"], configure=_configure_ls),
        CommandSpec("show", help="Show one item.", configure=lambda p: p.set_defaults(handler=_cmd_show)),
    ]

    parser = ArgumentParser(prog="astrid example")
    sub = parser.add_subparsers(dest="command", required=True)
    register_commands(sub, COMMANDS)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class CommandSpec:
    """Specification for one argparse subcommand.

    Each CLI module should define a module-level sequence of ``CommandSpec``
    entries (commonly named ``COMMANDS``) that describes every subcommand the
    module's parser accepts.  The ``configure`` callback is the sole mechanism
    for wiring the subparser; it receives a freshly-created argparse subparser
    and must set a default handler (e.g. ``set_defaults(handler=...)``) as
    well as any arguments, sub-subparsers, or custom behaviour the command
    requires.

    Attributes:
        name: The subcommand name as registered on the subparsers container.
        help: Short help text displayed in ``--help`` output.
        aliases: Optional list of alternative subcommand names.
        configure: Callable that configures the subparser.  Must not be
            ``None`` (enforced at registration time).
    """

    name: str
    help: str
    aliases: Sequence[str] = field(default_factory=tuple)
    configure: Callable[[argparse.ArgumentParser], None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("CommandSpec.name must be a non-empty string")
        if not isinstance(self.help, str) or not self.help:
            raise ValueError("CommandSpec.help must be a non-empty string")


def register_commands(
    subparsers: Any,
    commands: Sequence[CommandSpec],
    *,
    _strict_configure: bool = True,
) -> None:
    """Register every :class:`CommandSpec` on an argparse subparsers container.

    Args:
        subparsers: An ``argparse._SubParsersAction`` instance obtained from
            ``parser.add_subparsers(...)``.
        commands: One :class:`CommandSpec` per subcommand.
        _strict_configure: When ``True`` (the default), every ``CommandSpec``
            must have a non-``None`` ``configure`` callback.  Tests and
            phased allowlists may set this to ``False`` to permit entries
            whose configuration is not yet migrated.
    """
    for spec in commands:
        if _strict_configure and spec.configure is None:
            raise ValueError(
                f"CommandSpec {spec.name!r} has no configure callback; "
                f"pass _strict_configure=False to accept unconfigured entries"
            )
        kwargs: dict[str, Any] = {"help": spec.help}
        if spec.aliases:
            kwargs["aliases"] = list(spec.aliases)
        subparser = subparsers.add_parser(spec.name, **kwargs)
        if spec.configure is not None:
            spec.configure(subparser)
