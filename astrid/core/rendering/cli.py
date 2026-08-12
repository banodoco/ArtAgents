"""CLI for ``astrid renderers`` — pluggable timeline renderers.

The gateway dispatches the ``renderers`` top-level command here
(``gateway/dispatch.py::_dispatch_renderers``).  ``main`` routes each
sub-verb; the initial verb is ``create``, which writes the exact four-file
renderer scaffold into the requested directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from astrid.core.contracts.errors import AstridError

from .scaffold import create_renderer_scaffold


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return int(handler(args))
    except (FileExistsError, ValueError) as exc:
        raise AstridError(
            str(exc),
            recovery_command="astrid renderers create --help",
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astrid renderers",
        description="Manage pluggable timeline renderers.",
    )
    sub = parser.add_subparsers(dest="command")

    create_parser = sub.add_parser(
        "create",
        help="Scaffold a new four-file renderer pack.",
    )
    create_parser.add_argument(
        "name",
        help="Renderer name; the qualified id becomes rendering.<name>.",
    )
    create_parser.add_argument(
        "dest",
        nargs="?",
        default=".",
        help="Destination directory (default: current directory).",
    )
    create_parser.add_argument(
        "--id",
        dest="renderer_id",
        default=None,
        help="Override the qualified renderer id (default: rendering.<name>).",
    )
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing scaffold (the four scaffold file names).",
    )
    create_parser.set_defaults(handler=_cmd_create)
    return parser


def _cmd_create(args: argparse.Namespace) -> int:
    dest = create_renderer_scaffold(
        args.name,
        Path(args.dest),
        force=bool(args.force),
        renderer_id=args.renderer_id,
    )
    print(f"created renderer scaffold at {dest}")
    print("files: pack.yaml renderer.yaml render.py test_renderer.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
