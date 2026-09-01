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
    """Read the runtime-owned integrity report without local storage."""
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
    from astrid.sdk.workspace_client import WorkspaceClientError

    try:
        with AstridClient.open_from_launcher() as client:
            report = client.doctor()
    except (ServiceUnavailableError, WorkspaceClientError) as exc:
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
        state = report.get("state", "ready") if isinstance(report, dict) else "ready"
        print(f"Astrid doctor\nstate: {state}")
        if isinstance(report, dict) and report.get("recovery_action"):
            print(f"recovery action: {report['recovery_action']}")
    return 0 if not isinstance(report, dict) or report.get("ok", False) else 1


def _dispatch_backup(args: list[str]) -> int:
    """Dispatch online backup, restore, export, and realm lifecycle routes."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(prog="astrid backup", add_help=False)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="operation", required=False)
    create = sub.add_parser("create", add_help=False)
    create.add_argument("destination", nargs="?")
    create.add_argument("--out", dest="out", default=None)
    create.add_argument("--json", action="store_true")
    restore = sub.add_parser("restore", add_help=False)
    restore.add_argument("backup")
    restore.add_argument("destination", nargs="?")
    restore.add_argument("--destination", dest="destination_flag", default=None)
    restore.add_argument("--json", action="store_true")
    export = sub.add_parser("export", add_help=False)
    export.add_argument("--out", dest="out", default=None)
    export.add_argument("--json", action="store_true")
    tombstone = sub.add_parser("tombstone", add_help=False)
    tombstone.add_argument("--reason", default=None)
    tombstone.add_argument("--expected-version", type=int, default=None)
    tombstone.add_argument("--json", action="store_true")
    recover = sub.add_parser("recover", add_help=False)
    recover.add_argument("--expected-realm-id", required=True)
    recover.add_argument("--expected-version", type=int, default=None)
    recover.add_argument("--json", action="store_true")
    purge = sub.add_parser("purge", add_help=False)
    purge.add_argument("confirmation")
    purge.add_argument("--json", action="store_true")

    if any(token in {"-h", "--help"} for token in args):
        parser.print_help()
        return 0
    parsed = parser.parse_args(args)
    json_mode = "--json" in args
    if parsed.operation is None:
        payload = {"ok": False, "state": "unavailable", "next_action": "banodoco-local up --profile astrid", "error": "backup operation is required"}
        if json_mode:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Astrid backup: {payload['error']}", file=sys.stderr)
            print(f"next action: {payload['next_action']}", file=sys.stderr)
        return 1
    try:
        from astrid.sdk.client import AstridClient
        from astrid.sdk.exceptions import ServiceUnavailableError
        from astrid.sdk.workspace_client import WorkspaceClientError

        with AstridClient.open_from_launcher() as client:
            if parsed.operation == "create":
                destination = parsed.destination or parsed.out
                if not destination:
                    parser.error("backup create requires DESTINATION or --out")
                result = client.create_backup(destination)
            elif parsed.operation == "restore":
                destination = parsed.destination_flag or parsed.destination
                if not destination:
                    parser.error("backup restore requires DESTINATION or --destination")
                result = client.restore_backup(parsed.backup, destination)
            elif parsed.operation == "export":
                result = client.export_realm()
            elif parsed.operation == "tombstone":
                result = client.tombstone_realm(reason=parsed.reason, expected_version=parsed.expected_version)
            elif parsed.operation == "recover":
                result = client.recover_realm(expected_realm_id=parsed.expected_realm_id, expected_version=parsed.expected_version)
            else:
                result = client.purge_realm(parsed.confirmation)
    except ServiceUnavailableError as exc:
        payload = {"ok": False, "state": "unavailable", "next_action": "banodoco-local up --profile astrid", "error": str(exc)}
        print(json.dumps(payload, indent=2, sort_keys=True) if json_mode else f"Astrid backup: {payload['error']}\nnext action: {payload['next_action']}", file=None if json_mode else sys.stderr)
        return 1
    except WorkspaceClientError as exc:
        payload = {"ok": False, "error": exc.code, "detail": exc.message, "details": exc.details}
        print(json.dumps(payload, indent=2, sort_keys=True) if json_mode else f"Astrid backup: {exc.message}", file=None if json_mode else sys.stderr)
        return 1

    payload = {"ok": True, **(result if isinstance(result, dict) else dict(result))}
    print(json.dumps(payload, indent=2, sort_keys=True) if json_mode else f"Astrid backup: {parsed.operation} complete")
    return 0


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
        with AstridClient.open_from_launcher() as client:
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
