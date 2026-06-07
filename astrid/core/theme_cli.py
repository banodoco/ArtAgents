"""Command-line interface for Astrid styledoc themes."""

from __future__ import annotations

import argparse
import json

from astrid.core.theme import list_themes, resolve_themes_root


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid themes",
        description="Inspect Astrid styledoc themes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ls_parser = subparsers.add_parser("ls", help="List themes.")
    ls_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    ls_parser.set_defaults(handler=_cmd_ls)
    return parser


def _cmd_ls(args: argparse.Namespace) -> int:
    themes = list_themes()
    if args.json:
        print(json.dumps({"themes_root": str(resolve_themes_root()), "themes": themes}, indent=2, sort_keys=True))
        return 0
    print(f"themes root: {resolve_themes_root()}")
    if not themes:
        print("themes: none")
        return 0
    print("themes:")
    for theme in themes:
        status = "valid" if theme["valid"] else f"invalid: {theme.get('validation_error', 'unknown error')}"
        print(f"  {theme['id']}  {status}")
    return 0
