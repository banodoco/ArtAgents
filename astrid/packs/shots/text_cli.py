"""The same-pack ``timelines text`` parser and one-call handlers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from astrid.core.cli.domain_output import print_result
from astrid.core.cli.registration import CommandSpec, register_product_commands


def _json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true")


def _project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=None)


def _selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--binding", dest="binding_ids", action="append", metavar="ID")
    group.add_argument("--shot", dest="shot_ref", metavar="REF")
    group.add_argument("--all-project", action="store_true")
    parser.add_argument("--kind", default=None)
    parser.add_argument("--slot", default=None)


def _manifest_ids(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--binding", dest="binding_ids", action="append", metavar="ID")


def _mutation_selector(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--binding", dest="binding_id", metavar="ID")
    group.add_argument("--shot", dest="shot_ref", metavar="REF")
    parser.add_argument("--kind", default=None)
    parser.add_argument("--slot", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--expected-head", type=int, required=True)
    parser.add_argument("--idempotency-key", default=None)


def _cmd_list(args: argparse.Namespace) -> int:
    return print_result(
        args.client.shots.list_text_bindings(
            args.project,
            binding_ids=args.binding_ids,
            shot_ref=args.shot_ref,
            kind=args.kind,
            slot=args.slot,
            all_project=args.all_project,
        ),
        as_json=args.json,
    )


def _cmd_checkout(args: argparse.Namespace) -> int:
    return print_result(
        args.client.shots.checkout_text_bindings(
            args.project,
            args.out,
            binding_ids=args.binding_ids,
            shot_ref=args.shot_ref,
            kind=args.kind,
            slot=args.slot,
            all_project=args.all_project,
        ),
        as_json=args.json,
    )


def _cmd_status(args: argparse.Namespace) -> int:
    return print_result(
        args.client.shots.status_text_checkout(
            args.checkout_dir,
            binding_ids=args.binding_ids,
        ),
        as_json=args.json,
    )


def _cmd_diff(args: argparse.Namespace) -> int:
    return print_result(
        args.client.shots.diff_text_checkout(
            args.checkout_dir,
            binding_ids=args.binding_ids,
        ),
        as_json=args.json,
    )


def _cmd_apply(args: argparse.Namespace) -> int:
    return print_result(
        args.client.shots.apply_text_checkout(
            args.checkout_dir,
            binding_ids=args.binding_ids,
            idempotency_key=args.idempotency_key,
        ),
        as_json=args.json,
    )


def _cmd_set(args: argparse.Namespace) -> int:
    value = args.file.read_bytes() if args.file is not None else args.text.encode("utf-8")
    return print_result(
        args.client.shots.set_text_binding(
            args.project,
            text=value,
            expected_head=args.expected_head,
            binding_id=args.binding_id,
            shot_ref=args.shot_ref,
            kind=args.kind,
            slot=args.slot,
            idempotency_key=args.idempotency_key,
        ),
        as_json=args.json,
    )


def _cmd_rebind(args: argparse.Namespace) -> int:
    return print_result(
        args.client.shots.rebind_text_binding(
            args.project,
            media_id=args.media,
            expected_head=args.expected_head,
            binding_id=args.binding_id,
            shot_ref=args.shot_ref,
            kind=args.kind,
            slot=args.slot,
            idempotency_key=args.idempotency_key,
        ),
        as_json=args.json,
    )


def _configure_list(parser: argparse.ArgumentParser) -> None:
    _project(parser)
    _selection(parser)
    _json(parser)
    parser.set_defaults(handler=_cmd_list)


def _configure_checkout(parser: argparse.ArgumentParser) -> None:
    _project(parser)
    _selection(parser)
    parser.add_argument("--out", type=Path, required=True, metavar="DIRECTORY")
    _json(parser)
    parser.set_defaults(handler=_cmd_checkout)


def _configure_status(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("checkout_dir", type=Path)
    _manifest_ids(parser)
    _json(parser)
    parser.set_defaults(handler=_cmd_status)


def _configure_diff(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("checkout_dir", type=Path)
    _manifest_ids(parser)
    _json(parser)
    parser.set_defaults(handler=_cmd_diff)


def _configure_apply(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("checkout_dir", type=Path)
    _manifest_ids(parser)
    parser.add_argument("--idempotency-key", default=None)
    _json(parser)
    parser.set_defaults(handler=_cmd_apply)


def _configure_set(parser: argparse.ArgumentParser) -> None:
    _mutation_selector(parser)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--file", type=Path)
    _json(parser)
    parser.set_defaults(handler=_cmd_set)


def _configure_rebind(parser: argparse.ArgumentParser) -> None:
    _mutation_selector(parser)
    parser.add_argument("--media", required=True)
    _json(parser)
    parser.set_defaults(handler=_cmd_rebind)


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("list", help="List shot-owned text bindings.", configure=_configure_list),
    CommandSpec(
        "checkout", help="Create a text checkout projection.", configure=_configure_checkout
    ),
    CommandSpec("status", help="Inspect a text checkout.", configure=_configure_status),
    CommandSpec(
        "diff", help="Diff a text checkout against its immutable base.", configure=_configure_diff
    ),
    CommandSpec("apply", help="Apply a text checkout atomically.", configure=_configure_apply),
    CommandSpec("set", help="Replace one binding's complete text.", configure=_configure_set),
    CommandSpec(
        "rebind", help="Point one binding at existing text media.", configure=_configure_rebind
    ),
)


def configure_parser(parser: argparse.ArgumentParser, client: Any) -> None:
    """Populate an existing ``timelines text`` mount using normal registration."""
    subparsers = parser.add_subparsers(dest="text_command", required=True)
    register_product_commands(subparsers, COMMANDS, family="text", client=client)


def build_parser(client: Any) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="astrid timelines text")
    configure_parser(parser, client)
    return parser


__all__ = ["COMMANDS", "build_parser", "configure_parser"]
