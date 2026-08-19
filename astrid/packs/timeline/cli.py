"""Product timelines family CLI (m4 plan step 26, task T28).

This module is the product parser for the manifest-owned ``timelines``
family (``astrid/packs/timeline/schema-pack.yaml`` declares the top-level
``timelines`` mount). Every verb is **argument parsing plus exactly one SDK
call** on the composed :class:`~astrid.sdk.client.AstridClient` (stamped
onto every subparser by
:func:`astrid.core.cli.registration.register_product_commands`), and every
handler renders through the shared product output layer
(:mod:`astrid.core.cli.domain_output`) so the exact five-key JSON envelope,
concise human output, and stable exit codes stay aligned with the frozen SDK
contract.

The parser also mounts the manifest-declared nested ``shots`` family beneath
``timelines`` (``astrid/packs/shots/schema-pack.yaml`` declares ``shots:
timelines shots``): ``astrid timelines shots <verb>`` embeds the shots
product parser (``astrid/packs/shots/cli.py``) so shot
``list/create/add/remove/reorder`` are executable only beneath timelines
(plan step 26, task T29). There is **no top-level shots family**.

Verbs (exactly these seven plus the nested ``shots`` mount, one SDK call
each):

- ``create`` — ``client.timelines.create`` (project id/slug, slug, name,
  optional ``--config``/``--registry`` JSON, ``--default``, and
  ``--idempotency-key``; a fresh key is generated and returned when absent);
- ``list`` — ``client.timelines.list`` (active timelines only);
- ``show`` — ``client.timelines.show`` by UUID, ULID, or slug;
- ``save`` — whole-document CAS ``client.timelines.save`` with
  ``--config``/``--registry`` and ``--expected-version``;
- ``archive`` — event-backed terminal ``client.timelines.archive``;
- ``history`` — ordered lifecycle events (read);
- ``diff`` — deterministic adjacent-version diffs (read).

**Negative routes (sense check SC28):** the legacy timeline verbs
``migration``, ``push``, ``pull``, ``sync``, ``audit``, ``erase``, and
``repair`` are **absent** from this product parser, as are all obsolete
aliases (``ls``, ``tl``, ...), and ``copy`` is **absent** — the reserved
save-as-copy route is contractually deferred to m6 (plan step 2 / watch
item) and must never be registered here.

This module contains **no SQL**, **no repository logic**, and **no
domain rules**: it parses argv, makes one SDK call, and renders the
returned envelope.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from astrid.core.cli.domain_output import print_result
from astrid.core.cli.registration import CommandSpec, register_product_commands

__all__ = ["COMMANDS", "build_parser"]

_FAMILY = "timelines"


def _parse_json_object(value: str) -> dict[str, Any]:
    """Parse a ``--config``/``--registry`` JSON object argument."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON object: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("must be a JSON object")
    return parsed


def _add_json_flag(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--json",
        action="store_true",
        help="Print the exact SDK envelope (ok/data/error/receipt/idempotency_key).",
    )


def _add_idempotency_key(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        default=None,
        help="Caller idempotency key (a fresh key is generated when absent).",
    )


def _add_project_arg(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--project",
        required=True,
        help="Owning project id or slug.",
    )


# -- handlers (one SDK call each, no domain rules) -------------------------


def _cmd_create(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.create(
        project=parsed.project,
        slug=parsed.slug,
        name=parsed.name,
        config=parsed.config,
        registry=parsed.registry,
        set_default=parsed.default,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_list(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.list(parsed.project)
    return print_result(result, as_json=parsed.json)


def _cmd_show(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.show(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


def _cmd_save(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.save(
        parsed.project,
        parsed.ref,
        config=parsed.config,
        registry=parsed.registry,
        expected_version=parsed.expected_version,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_archive(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.archive(
        parsed.project,
        parsed.ref,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_history(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.history(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


def _cmd_diff(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.diff(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


# -- parser ----------------------------------------------------------------


def _configure_create(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("slug", help="Timeline slug (immutable).")
    subparser.add_argument("--name", required=True, help="Display name.")
    subparser.add_argument(
        "--config",
        type=_parse_json_object,
        default=None,
        help="Document config as a JSON object.",
    )
    subparser.add_argument(
        "--registry",
        type=_parse_json_object,
        default=None,
        help="Document registry as a JSON object.",
    )
    subparser.add_argument(
        "--default",
        action="store_true",
        help="Set this timeline as the project default.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_create)


def _configure_list(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_list)


def _configure_show(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_show)


def _configure_save(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    subparser.add_argument(
        "--config",
        type=_parse_json_object,
        required=True,
        help="Whole-document config as a JSON object.",
    )
    subparser.add_argument(
        "--registry",
        type=_parse_json_object,
        required=True,
        help="Whole-document registry as a JSON object.",
    )
    subparser.add_argument(
        "--expected-version",
        dest="expected_version",
        type=int,
        required=True,
        help="Expected document version for the CAS save.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_save)


def _configure_archive(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_archive)


def _configure_history(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_history)


def _configure_diff(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_diff)


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "create",
        help="Create a timeline (one SDK call, idempotency key returned).",
        configure=_configure_create,
    ),
    CommandSpec(
        "list",
        help="List active timelines in a project (slug ascending).",
        configure=_configure_list,
    ),
    CommandSpec(
        "show",
        help="Show one timeline by UUID, ULID, or slug.",
        configure=_configure_show,
    ),
    CommandSpec(
        "save",
        help="Whole-document CAS save (one SDK call, stale_version mapped).",
        configure=_configure_save,
    ),
    CommandSpec(
        "archive",
        help="Archive a timeline (event-backed terminal mutation).",
        configure=_configure_archive,
    ),
    CommandSpec(
        "history",
        help="Ordered lifecycle event history for one timeline.",
        configure=_configure_history,
    ),
    CommandSpec(
        "diff",
        help="Deterministic adjacent-version diffs for one timeline.",
        configure=_configure_diff,
    ),
)


def build_parser(client: Any) -> argparse.ArgumentParser:
    """Build the ``timelines`` product-family parser stamped with *client*.

    Exactly the seven verbs above are registered — no aliases, no legacy
    migration/push/pull/sync/audit/erase/repair verbs, and no ``copy``
    (reserved for m6) — plus the manifest-declared nested ``shots`` mount
    (``astrid timelines shots <verb>``) embedded from the shots product
    parser.
    """
    from astrid.packs.shots import cli as shots_cli

    def _configure_shots(subparser: argparse.ArgumentParser) -> None:
        nested = subparser.add_subparsers(dest="shot_command", required=True)
        register_product_commands(
            nested, shots_cli.COMMANDS, family="shots", client=client
        )

    parser = argparse.ArgumentParser(
        prog="astrid timelines",
        description=(
            "Timeline create/list/show/save/archive/history/diff "
            "(product family); nested shots beneath 'timelines shots'."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_product_commands(
        subparsers,
        (
            *COMMANDS,
            CommandSpec(
                "shots",
                help="Nested shot list/create/add/remove/reorder "
                "(manifest-owned mount).",
                configure=_configure_shots,
            ),
        ),
        family=_FAMILY,
        client=client,
    )
    return parser