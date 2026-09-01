"""Product media family CLI (m4 plan step 27, task T30).

This module is the product parser for the ``media`` family: every verb is
**argument parsing plus exactly one SDK call** on the composed
:class:`~astrid.sdk.client.AstridClient` (stamped onto every subparser by
:func:`astrid.core.cli.registration.register_product_commands`), and every
handler renders through the shared product output layer
(:mod:`astrid.core.cli.domain_output`) so the exact five-key JSON envelope,
concise human output, and stable exit codes stay aligned with the frozen SDK
contract.

Verbs (exactly these six, one SDK call each):

- ``import <path>`` — accepts **only files and folders**: a regular file
  routes to ``client.media.import_file`` and a directory routes to
  ``client.media.import_directory`` (each file commits its own receipt and
  child key); video/audio containers are strictly probed with ``ffprobe``
  before any media/event/receipt write, and an undecodable container is a
  typed validation failure; any other path is a usage error before any SDK call;
- ``list`` — ``client.media.list`` (project-scoped, created_at then id);
- ``show <ref>`` — ``client.media.show`` by exact project-scoped media id
  (aliases resolve through the repository; cross-project ids are
  indistinguishable from missing);
- ``verify <ref>`` — ``client.media.verify`` with a required ``--realm``
  (fingerprint-verified; missing/mutated bytes change zero rows);
- ``relocate <ref>`` — ``client.media.relocate`` with a required
  ``--realm`` and a realm-specific destination. ``external_local`` requires
  ``--locator``; ``managed_local`` may take ``--source`` and rehydrate the
  canonical digest path atomically (identity unchanged);
- ``relate`` — ``client.media.relate`` with ``--from``/``--to``/``--kind``
  restricted to the frozen five media relation kinds (``derived_from``,
  ``variant_of``, ``uses_as_input``, ``mask_for``, ``audio_for``) plus
  optional ``--ordinal``/``--metadata``.

The parser also mounts the canonical ``references`` family beneath ``media``
(``astrid/packs/references/pack.yaml`` owns that declaration): ``astrid media
references <verb>`` embeds the references product parser
(``astrid/packs/references/cli.py``) so reference operations remain pack-owned.

This module contains **no SQL**, **no repository logic**, and **no domain
rules**: it parses argv, makes one SDK call, and renders the returned
envelope.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from astrid.core.cli.domain_output import print_result
from astrid.core.cli.registration import CommandSpec, register_product_commands

__all__ = ["COMMANDS", "build_parser"]

_FAMILY = "media"

REALMS: tuple[str, ...] = ("managed_local", "external_local")
"""The two supported media realms (m4 SDK contract)."""

MEDIA_RELATION_KINDS: tuple[str, ...] = (
    "derived_from",
    "variant_of",
    "uses_as_input",
    "mask_for",
    "audio_for",
)
"""The frozen five media relation kinds (m1 decision artifact section 7)."""


def _parse_json_object(value: str) -> dict[str, Any]:
    """Parse a ``--metadata`` JSON object argument (usage error otherwise)."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON object: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("must be a JSON object")
    return parsed


def _existing_file_or_directory(value: str) -> str:
    """Accept only an existing regular file or directory (usage error else)."""
    path = Path(value)
    if path.is_file() or path.is_dir():
        return value
    raise argparse.ArgumentTypeError(
        f"import accepts only an existing file or directory, got {value!r}"
    )


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


def _add_realm_arg(
    subparser: argparse.ArgumentParser, *, required: bool, default: str | None
) -> None:
    subparser.add_argument(
        "--realm",
        choices=REALMS,
        required=required,
        default=default,
        help="Media realm to operate on "
        f"(choices: {', '.join(REALMS)}).",
    )


# -- handlers (one SDK call each, no domain rules) -------------------------


def _cmd_import(parsed: argparse.Namespace) -> int:
    path = Path(parsed.path)
    if path.is_dir():
        result = parsed.client.media.import_directory(
            project=parsed.project,
            directory=path,
            realm=parsed.realm,
            idempotency_key=parsed.idempotency_key,
        )
    else:
        result = parsed.client.media.import_file(
            project=parsed.project,
            path=path,
            realm=parsed.realm,
            idempotency_key=parsed.idempotency_key,
        )
    return print_result(result, as_json=parsed.json)


def _cmd_list(parsed: argparse.Namespace) -> int:
    result = parsed.client.media.list(parsed.project)
    return print_result(result, as_json=parsed.json)


def _cmd_show(parsed: argparse.Namespace) -> int:
    result = parsed.client.media.show(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


def _cmd_verify(parsed: argparse.Namespace) -> int:
    kwargs = {
        "realm": parsed.realm,
        "idempotency_key": parsed.idempotency_key,
    }
    if parsed.location_id is not None:
        kwargs["location_id"] = parsed.location_id
    if parsed.locator is not None:
        kwargs["locator"] = parsed.locator
    result = parsed.client.media.verify(parsed.project, parsed.ref, **kwargs)
    return print_result(result, as_json=parsed.json)


def _cmd_relocate(parsed: argparse.Namespace) -> int:
    kwargs = {
        "realm": parsed.realm,
        "locator": parsed.locator,
        "idempotency_key": parsed.idempotency_key,
    }
    if parsed.source is not None:
        kwargs["source"] = parsed.source
    result = parsed.client.media.relocate(
        parsed.project, parsed.ref, **kwargs
    )
    return print_result(result, as_json=parsed.json)


def _cmd_relate(parsed: argparse.Namespace) -> int:
    relation: dict[str, Any] = {
        "from_media_id": parsed.from_media,
        "to_media_id": parsed.to_media,
        "kind": parsed.kind,
    }
    if parsed.ordinal is not None:
        relation["ordinal"] = parsed.ordinal
    if parsed.metadata is not None:
        relation["metadata"] = parsed.metadata
    result = parsed.client.media.relate(
        parsed.project,
        relations=[relation],
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


# -- parser ----------------------------------------------------------------


def _configure_import(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument(
        "path",
        type=_existing_file_or_directory,
        help=(
            "Existing file or directory to import (files/folders only); "
            "video/audio containers must be ffprobe-decodable."
        ),
    )
    _add_realm_arg(subparser, required=False, default="managed_local")
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_import)


def _configure_list(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_list)


def _configure_show(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Exact project-scoped media id.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_show)


def _configure_verify(subparser: argparse.ArgumentParser) -> None:
    subparser.description = (
        "Verify every local location in the selected realm. Results are "
        "deterministic and per-location; use one selector for a precise retry."
    )
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Exact project-scoped media id.")
    _add_realm_arg(subparser, required=True, default=None)
    selector = subparser.add_mutually_exclusive_group()
    selector.add_argument(
        "--location-id",
        default=None,
        help="Verify only this exact media-location id.",
    )
    selector.add_argument(
        "--locator",
        default=None,
        help="Verify only this exact realm locator.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_verify)


def _configure_relocate(subparser: argparse.ArgumentParser) -> None:
    subparser.description = (
        "Replace a media location without changing its identity. For "
        "external_local, pass an existing or future reference with --locator. "
        "For managed_local recovery, pass the regular source file with "
        "--source; Astrid verifies its SHA-256 and copies it to the canonical "
        "managed path."
    )
    subparser.epilog = (
        "Examples:\n"
        "  external reference: media relocate M_ID --project demo "
        "--realm external_local --locator /mnt/shots/shot.png\n"
        "  managed recovery: media relocate M_ID --project demo "
        "--realm managed_local --source /backup/shot.png"
    )
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Exact project-scoped media id.")
    _add_realm_arg(subparser, required=True, default=None)
    destination_or_source = subparser.add_mutually_exclusive_group(required=True)
    destination_or_source.add_argument(
        "--locator",
        required=False,
        default=None,
        help=(
            "Destination locator. Required for external_local. For "
            "managed_local, omit it to use the canonical SHA-256 path."
        ),
    )
    destination_or_source.add_argument(
        "--source",
        required=False,
        default=None,
        help=(
            "Regular source file for managed_local rehydration. Its SHA-256 "
            "must match the existing media identity; no database/file state "
            "changes on mismatch."
        ),
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_relocate)


def _configure_relate(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument(
        "--from",
        dest="from_media",
        required=True,
        help="Source media id for the relation edge.",
    )
    subparser.add_argument(
        "--to",
        dest="to_media",
        required=True,
        help="Target media id for the relation edge.",
    )
    subparser.add_argument(
        "--kind",
        choices=MEDIA_RELATION_KINDS,
        required=True,
        help="Frozen relation kind "
        f"(choices: {', '.join(MEDIA_RELATION_KINDS)}).",
    )
    subparser.add_argument(
        "--ordinal",
        type=int,
        default=None,
        help="Optional edge ordinal (default: 0).",
    )
    subparser.add_argument(
        "--metadata",
        type=_parse_json_object,
        default=None,
        help="Optional edge metadata as a JSON object.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_relate)


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "import",
        help="Import one existing file or directory "
        "(files/folders only; one exact-media result per file).",
        configure=_configure_import,
    ),
    CommandSpec(
        "list",
        help="List every media row in a project (created_at then id).",
        configure=_configure_list,
    ),
    CommandSpec(
        "show",
        help="Show one media read model by exact project-scoped media id.",
        configure=_configure_show,
    ),
    CommandSpec(
        "verify",
        help="Fingerprint-verify one realm location "
        "(missing/mutated bytes change zero rows).",
        configure=_configure_verify,
    ),
    CommandSpec(
        "relocate",
        help="Replace one realm location atomically (identity unchanged).",
        configure=_configure_relocate,
    ),
    CommandSpec(
        "relate",
        help="Materialize one media relation edge "
        "(frozen five kinds; constraints delegated to the service).",
        configure=_configure_relate,
    ),
)


def build_parser(client: Any) -> argparse.ArgumentParser:
    """Build the ``media`` product-family parser stamped with *client*.

    Exactly the six verbs above are registered, plus the manifest-declared
    nested ``references`` mount (``astrid media references <verb>``)
    embedded from the references product parser. There is no top-level
    references family.
    """
    from astrid.packs.references import cli as references_cli

    def _configure_references(subparser: argparse.ArgumentParser) -> None:
        nested = subparser.add_subparsers(dest="reference_command", required=True)
        register_product_commands(
            nested, references_cli.COMMANDS, family="references", client=client
        )

    parser = argparse.ArgumentParser(
        prog="astrid media",
        description=(
            "Media import/list/show/verify/relocate/relate (product family); "
            "nested references beneath 'media references'."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_product_commands(
        subparsers,
        (
            *COMMANDS,
            CommandSpec(
                "references",
                help="Nested reference create/update/archive/associate/link/"
                "set-primary/list/show (manifest-owned mount).",
                configure=_configure_references,
            ),
        ),
        family=_FAMILY,
        client=client,
    )
    return parser
