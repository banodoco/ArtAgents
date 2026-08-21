"""Product tasks family CLI (m4 plan step 28, task T31).

This module is the product parser for the ``tasks`` family: every verb is
**argument parsing plus exactly one SDK call** on the composed
:class:`~astrid.sdk.client.AstridClient` (stamped onto every subparser by
:func:`astrid.core.cli.registration.register_product_commands`), and every
handler renders through the shared product output layer
(:mod:`astrid.core.cli.domain_output`) so the exact five-key JSON envelope,
concise human output, and stable exit codes stay aligned with the frozen SDK
contract.

Verbs (exactly these six, one SDK call each):

- ``create`` — one ``client.tasks.create`` call; accepts ``--project`` (the
  owning project id or immutable slug), ``--capability``, ``--spec`` (a JSON
  object), and the
  optional admission controls ``--input-manifest`` (JSON array),
  ``--priority``, ``--available-at``, ``--max-attempts``, and
  ``--dependencies`` (JSON array), plus ``--idempotency-key`` (a fresh key is
  generated and returned by the SDK when absent);
- ``list`` — one ``client.tasks.list`` call (project-scoped read, no key);
- ``show <task_id>`` — one ``client.tasks.show`` call (read, no key);
- ``cancel <task_id>`` — one ``client.tasks.cancel`` call with the same
  idempotency-key contract as create. The executor-owned attempt fence
  (``attempt_id``/``lease_id``/``expected_status_version``) is **not**
  exposed: a running task's cancellation without the fence is the service's
  typed ``validation_error``, unchanged;
- ``retry <task_id>`` — one ``client.tasks.retry`` call with the same
  idempotency-key contract;
- ``events <task_id>`` — one ``client.tasks.events`` call returning the
  task's ordered ``core.task`` stream events (read, no key).

Executor lifecycle verbs (``claim``, ``start``, ``heartbeat``) and
plan/step semantics (``plan``, ``step``, ``next``, ``ack``, ``skip``,
``hook``) are **absent by construction**: the parser registers exactly the
six product verbs above, so there is no product parsing path that can reach
them.

This module contains **no SQL**, **no repository logic**, and **no domain
rules**: it parses argv, makes one SDK call, and renders the returned
envelope.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from astrid.core.cli.domain_output import print_result
from astrid.core.cli.registration import CommandSpec, register_product_commands

__all__ = ["COMMANDS", "build_parser"]

_FAMILY = "tasks"


def _parse_json_object(value: str) -> dict[str, Any]:
    """Parse a JSON object argument (usage error otherwise)."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON object: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("must be a JSON object")
    return parsed


def _parse_json_array(value: str) -> list[Any]:
    """Parse a JSON array argument (usage error otherwise)."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON array: {exc.msg}"
        ) from exc
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError("must be a JSON array")
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
        help="Owning project id or slug (task ids are project-scoped).",
    )


# -- handlers (one SDK call each, no domain rules) -------------------------


def _cmd_create(parsed: argparse.Namespace) -> int:
    result = parsed.client.tasks.create(
        project_id=parsed.project,
        capability=parsed.capability,
        spec=parsed.spec,
        input_manifest=parsed.input_manifest,
        priority=parsed.priority,
        available_at=parsed.available_at,
        max_attempts=parsed.max_attempts,
        dependencies=parsed.dependencies,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_list(parsed: argparse.Namespace) -> int:
    result = parsed.client.tasks.list(parsed.project)
    return print_result(result, as_json=parsed.json)


def _cmd_show(parsed: argparse.Namespace) -> int:
    result = parsed.client.tasks.show(parsed.task_id)
    return print_result(result, as_json=parsed.json)


def _cmd_cancel(parsed: argparse.Namespace) -> int:
    result = parsed.client.tasks.cancel(
        parsed.project,
        parsed.task_id,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_retry(parsed: argparse.Namespace) -> int:
    result = parsed.client.tasks.retry(
        parsed.project,
        parsed.task_id,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_events(parsed: argparse.Namespace) -> int:
    result = parsed.client.tasks.events(parsed.task_id)
    return print_result(result, as_json=parsed.json)


# -- parser ----------------------------------------------------------------


def _configure_create(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument(
        "--capability", required=True, help="Capability id this task invokes."
    )
    subparser.add_argument(
        "--spec",
        type=_parse_json_object,
        required=True,
        help="Immutable task spec as a JSON object (e.g. '{\"size\": 1}').",
    )
    subparser.add_argument(
        "--input-manifest",
        dest="input_manifest",
        type=_parse_json_array,
        default=None,
        help="Optional input manifest as a JSON array.",
    )
    subparser.add_argument(
        "--priority",
        type=int,
        default=0,
        help="Admission priority (default: 0).",
    )
    subparser.add_argument(
        "--available-at",
        dest="available_at",
        default=None,
        help="ISO timestamp before which the task must not run (default: now).",
    )
    subparser.add_argument(
        "--max-attempts",
        dest="max_attempts",
        type=int,
        default=1,
        help="Maximum execution attempts (default: 1).",
    )
    subparser.add_argument(
        "--dependencies",
        type=_parse_json_array,
        default=None,
        help="Optional hard dependencies as a JSON array.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_create)


def _configure_list(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_list)


def _configure_show(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("task_id", help="Exact project-scoped task id.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_show)


def _configure_cancel(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("task_id", help="Exact project-scoped task id.")
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_cancel)


def _configure_retry(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("task_id", help="Exact project-scoped task id.")
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_retry)


def _configure_events(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("task_id", help="Exact project-scoped task id.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_events)


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "create",
        help="Admit one immutable task "
        "(one SDK call; idempotency key and receipt returned).",
        configure=_configure_create,
    ),
    CommandSpec(
        "list",
        help="List every task in a project (created_at then id).",
        configure=_configure_list,
    ),
    CommandSpec(
        "show",
        help="Show one task's full immutable read model by id.",
        configure=_configure_show,
    ),
    CommandSpec(
        "cancel",
        help="Cancel one nonterminal task (one SDK call; no executor fence).",
        configure=_configure_cancel,
    ),
    CommandSpec(
        "retry",
        help="Retry one eligible failed/expired task (one SDK call).",
        configure=_configure_retry,
    ),
    CommandSpec(
        "events",
        help="Show one task's ordered core.task stream events.",
        configure=_configure_events,
    ),
)


def build_parser(client: Any) -> argparse.ArgumentParser:
    """Build the ``tasks`` product-family parser stamped with *client*.

    Exactly the six product verbs above are registered; executor lifecycle
    and plan/step verbs are absent by construction.
    """
    parser = argparse.ArgumentParser(
        prog="astrid tasks",
        description=(
            "Task create/list/show/cancel/retry/events (product family); "
            "executor lifecycle verbs are not exposed."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_product_commands(
        subparsers, COMMANDS, family=_FAMILY, client=client
    )
    return parser
