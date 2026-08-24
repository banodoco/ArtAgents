"""Product runs family CLI (m4 plan step 29, task T32).

This module is the product parser for the plural ``runs`` family: every verb
is **argument parsing plus exactly one SDK call** on the composed
:class:`~astrid.sdk.client.AstridClient` (stamped onto every subparser by
:func:`astrid.core.cli.registration.register_product_commands`), and every
handler renders through the shared product output layer
(:mod:`astrid.core.cli.domain_output`) so the exact five-key JSON envelope,
concise human output, and stable exit codes stay aligned with the frozen SDK
contract.

Verbs (exactly these five, one SDK call each):

- ``list`` — one ``client.runs.list`` call (project-scoped read, no key);
- ``show <run_id>`` — one ``client.runs.show`` call returning the run read
  model plus the **derived child progress** (total/succeeded/failed/
  cancelled counts and the ordered children); ``--evidence`` appends the
  run's ordered evidence items (read, no key);
- ``cancel <run_id>`` — one ``client.runs.cancel`` call driving every
  eligible child to the terminal ``cancelled`` state through the shared
  task-cancel predicate, with the same idempotency-key contract as other
  mutations;
- ``retry-failed <run_id>`` — one ``client.runs.retry_failed`` call;
  repeatable ``--task <id>`` restricts the retry to an explicit ordinal
  subset, and when omitted every eligible failed/expired child is retried;
- ``events <run_id>`` — one ``client.runs.events`` call returning the run's
  ordered ``core.run`` stream events (read, no key).

The singular ``run`` alias is **not** a product family (frozen census,
plan step 24) and is not registered here: the parser exposes exactly the
plural family above, so no product parsing path can reach a singular alias.
This module contains **no SQL**, **no repository logic**, and **no domain
rules**: it parses argv, makes one SDK call, and renders the returned
envelope.
"""

from __future__ import annotations

import argparse
from typing import Any

from astrid.core.cli.domain_output import print_result
from astrid.core.cli.registration import CommandSpec, register_product_commands

__all__ = ["COMMANDS", "build_parser"]

_FAMILY = "runs"


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
        required=False,
        default=None,
        help="Owning project id or slug (defaults to the selected project).",
    )


# -- handlers (one SDK call each, no domain rules) -------------------------


def _cmd_list(parsed: argparse.Namespace) -> int:
    result = parsed.client.runs.list(parsed.project)
    return print_result(result, as_json=parsed.json)


def _cmd_show(parsed: argparse.Namespace) -> int:
    result = parsed.client.runs.show(
        parsed.project,
        parsed.run_id,
        include_evidence=parsed.evidence,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_cancel(parsed: argparse.Namespace) -> int:
    result = parsed.client.runs.cancel(
        parsed.project,
        parsed.run_id,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_retry_failed(parsed: argparse.Namespace) -> int:
    result = parsed.client.runs.retry_failed(
        parsed.project,
        parsed.run_id,
        selected_task_ids=parsed.task,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_events(parsed: argparse.Namespace) -> int:
    result = parsed.client.runs.events(parsed.project, parsed.run_id)
    return print_result(result, as_json=parsed.json)


# -- parser ----------------------------------------------------------------


def _configure_list(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_list)


def _configure_show(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("run_id", help="Exact project-scoped run id.")
    subparser.add_argument(
        "--evidence",
        action="store_true",
        help="Append the run's ordered evidence items to the read model.",
    )
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_show)


def _configure_cancel(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("run_id", help="Exact project-scoped run id.")
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_cancel)


def _configure_retry_failed(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("run_id", help="Exact project-scoped run id.")
    subparser.add_argument(
        "--task",
        dest="task",
        action="append",
        default=None,
        help="Retry only this task id (repeatable; omit to retry every "
        "eligible failed/expired child).",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_retry_failed)


def _configure_events(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("run_id", help="Exact project-scoped run id.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_events)


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "list",
        help="List every run in a project (started_at then id).",
        configure=_configure_list,
    ),
    CommandSpec(
        "show",
        help="Show one run with derived child progress "
        "(optional --evidence).",
        configure=_configure_show,
    ),
    CommandSpec(
        "cancel",
        help="Cancel every eligible child of one run (one SDK call).",
        configure=_configure_cancel,
    ),
    CommandSpec(
        "retry-failed",
        help="Retry a run's eligible failed/expired children "
        "(optional --task subset; one SDK call).",
        configure=_configure_retry_failed,
    ),
    CommandSpec(
        "events",
        help="Show one run's ordered core.run stream events.",
        configure=_configure_events,
    ),
)


def build_parser(client: Any) -> argparse.ArgumentParser:
    """Build the ``runs`` product-family parser stamped with *client*.

    Exactly the five plural verbs above are registered; the singular
    ``run`` alias is not a product family and is never registered here.
    """
    parser = argparse.ArgumentParser(
        prog="astrid runs",
        description=(
            "Run list/show/cancel/retry-failed/events (product family); "
            "the singular 'run' alias is not a product family."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_product_commands(
        subparsers, COMMANDS, family=_FAMILY, client=client
    )
    return parser
