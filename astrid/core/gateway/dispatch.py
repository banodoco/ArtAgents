"""Focused dispatch for the product and operational gateway families."""

from __future__ import annotations

from typing import Any

from astrid.core.contracts.errors import AstridError


def _dispatch(raw: list[str]) -> int:
    from . import _print_entrypoint_help

    if not raw:
        _print_entrypoint_help()
        return 0

    first = raw[0]
    if first not in _top_level_commands():
        raise AstridError(
            f"unknown command '{first}'",
            valid_options=sorted(_top_level_commands()),
            recovery_command="astrid --help",
            state_snapshot={"command": first},
        )

    parser = _build_dispatch_parser()
    parsed, tail = parser.parse_known_args(raw)
    return int(parsed.handler(tail))


def _top_level_commands() -> frozenset[str]:
    return frozenset(_TOP_LEVEL_HANDLERS)


def _build_dispatch_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(prog="astrid", add_help=False)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, handler in _TOP_LEVEL_HANDLERS.items():
        command_parser = sub.add_parser(command, add_help=False)
        command_parser.set_defaults(handler=handler)
    return parser


def _dispatch_projects(args: list[str]) -> int:
    return _dispatch_product(["projects", *args])


def _dispatch_timelines(args: list[str]) -> int:
    return _dispatch_product(["timelines", *args])


def _dispatch_media(args: list[str]) -> int:
    return _dispatch_product(["media", *args])


def _dispatch_doctor(args: list[str]) -> int:
    """Read runtime health without opening local storage."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(prog="astrid doctor", description="Read-only runtime health check.")
    parser.add_argument("--json", action="store_true")
    if any(token in {"-h", "--help"} for token in args):
        parser.print_help()
        return 0
    parsed = parser.parse_args(args)
    from astrid.sdk.client import AstridClient
    from astrid.sdk.exceptions import ServiceUnavailableError

    try:
        with AstridClient.open() as client:
            report = client.health()
    except ServiceUnavailableError as exc:
        payload = {
            "ok": False,
            "state": "unavailable",
            "next_action": "banodoco-local up --profile astrid",
            "error": str(exc),
        }
        if parsed.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Astrid doctor: {payload['error']}", file=sys.stderr)
            print(f"next action: {payload['next_action']}", file=sys.stderr)
        return 1
    if parsed.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        state = report.get("doctor", {}).get("state", "ready") if isinstance(report, dict) else "ready"
        print(f"Astrid doctor\nstate: {state}")
    return 0


def _dispatch_backup(args: list[str]) -> int:
    """Keep backup read-only at the product boundary until a runtime route exists."""
    import argparse
    import json
    import sys

    if any(token in {"-h", "--help"} for token in args):
        print("usage: astrid backup (runtime backup route unavailable)")
        return 0
    parser = argparse.ArgumentParser(prog="astrid backup", add_help=False)
    parser.add_argument("--json", action="store_true")
    parser.parse_known_args(args)
    payload = {
        "ok": False,
        "state": "unavailable",
        "next_action": "banodoco-local up --profile astrid",
        "error": "backup is not available through the workspace runtime yet",
    }
    if "--json" in args:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Astrid backup: {payload['error']}", file=sys.stderr)
        print(f"next action: {payload['next_action']}", file=sys.stderr)
    return 1


def _dispatch_product(args: list[str]) -> int:
    """Run one product-family command through the remote SDK boundary."""
    from astrid.core.cli.domain_product import PRODUCT_FAMILY_SET, run_product_family

    if not args:
        raise AstridError(
            "a product family is required",
            valid_options=sorted(PRODUCT_FAMILY_SET),
            recovery_command="astrid projects --help",
            state_snapshot={"command": "product"},
        )
    family, rest = args[0], args[1:]
    if family not in PRODUCT_FAMILY_SET:
        raise AstridError(
            f"unknown product command '{family}'",
            valid_options=sorted(PRODUCT_FAMILY_SET),
            recovery_command="astrid --help",
            state_snapshot={"command": family},
        )

    if any(token in {"-h", "--help"} for token in rest):
        return run_product_family(family, rest, client=None)

    from astrid.sdk.client import AstridClient

    try:
        with AstridClient.open() as client:
            return run_product_family(family, rest, client=client)
    except Exception as exc:
        from astrid.sdk.exceptions import ServiceUnavailableError

        if not isinstance(exc, ServiceUnavailableError):
            raise
        from astrid.core.cli.domain_output import print_result
        from astrid.sdk.contracts import DomainResult

        return print_result(
            DomainResult.failure(exc.to_error_object()),
            as_json="--json" in rest,
        )


def _product_top_level_commands() -> frozenset[str]:
    from astrid.core.cli.domain_product import product_top_level_commands

    return product_top_level_commands()


_TOP_LEVEL_HANDLERS = {
    "projects": _dispatch_projects,
    "timelines": _dispatch_timelines,
    "media": _dispatch_media,
    "tasks": lambda args: _dispatch_product(["tasks", *args]),
    "runs": lambda args: _dispatch_product(["runs", *args]),
    "doctor": _dispatch_doctor,
    "backup": _dispatch_backup,
}
